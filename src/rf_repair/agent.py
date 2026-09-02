"""Bounded OpenAI adapter for one-edit RF fault diagnosis proposals."""

from __future__ import annotations

import json
import os
import re
from hashlib import sha256
from pathlib import Path
from typing import Annotated, Literal

from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from rf_repair.netlist import set_component_value


MODEL = "gpt-5.6-luna"
PROMPT_VERSION = "value_one_edit_v1"
CLOSED_LOOP_PROMPT_VERSION = "value_closed_loop_v1"
SCHEMA_VERSION = "agent_proposal_v1"
ALLOWED_COMPONENTS = ("C1", "C2", "C3", "L1", "L2", "L3")
_SPICE_VALUE = re.compile(
    r"^(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+|(?:meg|[tgkmunpf]))?$",
    re.IGNORECASE,
)
EvidenceText = Annotated[str, Field(max_length=200)]


class Diagnosis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component: Literal["C1", "C2", "C3", "L1", "L2", "L3"]
    fault_type: Literal["value_too_low", "value_too_high", "unknown_direction"]
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[EvidenceText] = Field(min_length=1, max_length=2)


class RepairPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["set_value"]
    component: Literal["C1", "C2", "C3", "L1", "L2", "L3"]
    proposed_value: str


class AgentProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    diagnosis: Diagnosis
    repair: RepairPatch


class ProposalResponseError(RuntimeError):
    """Base error retaining safe response metadata and local raw evidence."""

    def __init__(
        self,
        *,
        message: str,
        response_status: str,
        incomplete_reason: str | None,
        usage: dict,
        raw_output: str,
    ) -> None:
        super().__init__(message)
        self.response_status = response_status
        self.incomplete_reason = incomplete_reason
        self.usage = usage
        self.raw_output = raw_output
        self.output_text_sha256 = sha256(raw_output.encode("utf-8")).hexdigest()
        self.output_text_chars = len(raw_output)


class ProposalUnavailable(ProposalResponseError):
    """The API response did not contain a complete output text."""


class ProposalSchemaInvalid(ProposalResponseError):
    """The returned output text failed local schema validation."""

    def __init__(self, *, validation_error_count: int, **kwargs) -> None:
        super().__init__(**kwargs)
        self.validation_error_count = validation_error_count


def load_local_api_key(path: Path) -> None:
    """Load only OPENAI_API_KEY from a local env file without printing it."""

    if os.environ.get("OPENAI_API_KEY"):
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() == "OPENAI_API_KEY":
            value = value.strip().strip("\"'")
            if not value:
                break
            os.environ["OPENAI_API_KEY"] = value
            return
    raise RuntimeError(f"OPENAI_API_KEY is missing from {path}")


def build_agent_input(
    *,
    netlist: str,
    spec: dict,
    metrics: dict | None,
    feedback_history: list[dict] | None = None,
) -> str:
    """Build the agent-visible evidence bundle; no healthy netlist or manifest."""

    payload: dict = {
        "task": "Diagnose one component-value fault and propose exactly one repair edit.",
        "faulty_netlist": netlist,
        "target_specification": spec,
    }
    if metrics is not None:
        payload["measured_simulation"] = metrics
    if feedback_history:
        payload["previous_attempts"] = feedback_history
    return json.dumps(payload, indent=2, sort_keys=True)


def _instructions(prompt_version: str) -> str:
    if prompt_version not in {PROMPT_VERSION, CLOSED_LOOP_PROMPT_VERSION}:
        raise ValueError(f"unsupported prompt_version: {prompt_version}")
    feedback_instruction = (
        " Previous repair attempts may be supplied. Use their deterministic rejection or "
        "simulation feedback to propose a different candidate; do not repeat a failed patch."
        if prompt_version == CLOSED_LOOP_PROMPT_VERSION
        else ""
    )
    return (
        "You are diagnosing an ideal lumped 100 MHz RF band-pass filter. "
        "Use only the supplied faulty netlist, target specification, and available evidence. "
        "The healthy netlist and injected-fault manifest are unavailable. "
        "Choose one R/L/C value edit only. Do not claim success; an external ngspice "
        "validator will decide. proposed_value must be one positive SPICE numeric token. "
        "Keep each evidence string under 200 characters."
        + feedback_instruction
    )


def request_proposal(
    *,
    netlist: str,
    spec: dict,
    metrics: dict | None,
    client: OpenAI | None = None,
    model: str = MODEL,
    max_output_tokens: int = 700,
    reasoning_effort: Literal["none", "low", "medium", "high"] = "low",
    timeout_seconds: float = 90.0,
    max_retries: int = 0,
    prompt_version: str = PROMPT_VERSION,
    feedback_history: list[dict] | None = None,
) -> tuple[AgentProposal, dict]:
    """Request one structured proposal and return safe usage metadata."""

    # Hidden SDK retries would make one logical experiment row consume multiple
    # requests. Keep each attempt explicit and bound transport wait time.
    api = client or OpenAI(timeout=timeout_seconds, max_retries=max_retries)
    response = api.responses.create(
        model=model,
        reasoning={"effort": reasoning_effort},
        max_output_tokens=max_output_tokens,
        store=False,
        text={
            "format": {
                "type": "json_schema",
                "name": SCHEMA_VERSION,
                "schema": AgentProposal.model_json_schema(),
                "strict": True,
            },
            "verbosity": "low",
        },
        instructions=_instructions(prompt_version),
        input=build_agent_input(
            netlist=netlist,
            spec=spec,
            metrics=metrics,
            feedback_history=feedback_history,
        ),
    )
    usage = response.usage.model_dump(mode="json") if response.usage else {}
    raw_output = response.output_text
    incomplete_reason = (
        response.incomplete_details.reason if response.incomplete_details else None
    )
    common_error = {
        "response_status": response.status,
        "incomplete_reason": incomplete_reason,
        "usage": usage,
        "raw_output": raw_output,
    }
    if response.status != "completed" or not raw_output:
        raise ProposalUnavailable(
            message="model returned no complete output text",
            **common_error,
        )
    try:
        proposal = AgentProposal.model_validate_json(raw_output)
    except ValidationError as error:
        raise ProposalSchemaInvalid(
            message="model output failed local schema validation",
            validation_error_count=error.error_count(),
            **common_error,
        ) from None
    metadata = {
        "model": response.model,
        "response_status": response.status,
        "usage": usage,
        "output_text_sha256": sha256(raw_output.encode("utf-8")).hexdigest(),
        "output_text_chars": len(raw_output),
        "prompt_version": prompt_version,
        "schema_version": SCHEMA_VERSION,
    }
    return proposal, metadata


def apply_restricted_patch(source: str, patch: RepairPatch) -> str:
    """Apply one allow-listed, positive numeric R/L/C value edit."""

    if patch.component not in ALLOWED_COMPONENTS:
        raise ValueError(f"component is not allow-listed: {patch.component}")
    if not _SPICE_VALUE.fullmatch(patch.proposed_value):
        raise ValueError("proposed_value is not a permitted SPICE numeric token")

    current_value: str | None = None
    for line in source.splitlines():
        tokens = line.split()
        if tokens and tokens[0].upper() == patch.component:
            if len(tokens) != 4:
                raise ValueError(f"unsupported element syntax for {patch.component}")
            current_value = tokens[3]
            break
    if current_value is None:
        raise ValueError(f"component not found: {patch.component}")
    if current_value.lower() == patch.proposed_value.lower():
        raise ValueError("repair must change the component value")
    return set_component_value(
        source,
        component=patch.component,
        expected_value=current_value,
        new_value=patch.proposed_value,
    )

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

from rf_repair.netlist import (
    normalize_spice_quantity,
    restore_component_from_fault_resistor,
    set_component_value,
    set_port_impedance,
)


MODEL = "gpt-5.6-luna"
PROMPT_VERSION = "value_one_edit_v1"
CLOSED_LOOP_PROMPT_VERSION = "value_closed_loop_v1"
SCHEMA_VERSION = "agent_proposal_v1"
STRUCTURAL_PROMPT_VERSION = "structural_closed_loop_v1"
STRUCTURAL_NORMALIZED_PROMPT_VERSION = "structural_closed_loop_v2"
STRUCTURAL_PORT_ROLE_PROMPT_VERSION = "structural_closed_loop_port_role_v1"
STRUCTURAL_SCHEMA_VERSION = "agent_proposal_structural_v1"
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


class StructuralDiagnosis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component: Literal["C1", "C2", "C3", "L1", "L2", "L3", "VPORT1", "VPORT2"]
    fault_type: Literal[
        "open",
        "short",
        "source_impedance_mismatch",
        "load_impedance_mismatch",
        "unknown",
    ]
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[EvidenceText] = Field(min_length=1, max_length=2)


class StructuralRepairPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["restore_component", "set_port_impedance"]
    component: Literal["C1", "C2", "C3", "L1", "L2", "L3", "VPORT1", "VPORT2"]
    proposed_value: str | None
    proposed_z0: str | None


class StructuralAgentProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    diagnosis: StructuralDiagnosis
    repair: StructuralRepairPatch


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


def _request_common_metadata(response, *, prompt_version: str, schema_version: str) -> dict:
    usage = response.usage.model_dump(mode="json") if response.usage else {}
    return {
        "model": response.model,
        "response_status": response.status,
        "usage": usage,
        "output_text_sha256": sha256(response.output_text.encode("utf-8")).hexdigest(),
        "output_text_chars": len(response.output_text),
        "prompt_version": prompt_version,
        "schema_version": schema_version,
    }


def request_structural_proposal(
    *,
    netlist: str,
    spec: dict,
    metrics: dict,
    feedback_history: list[dict] | None = None,
    client: OpenAI | None = None,
    model: str = MODEL,
    max_output_tokens: int = 2000,
    reasoning_effort: Literal["none", "low", "medium", "high"] = "low",
    timeout_seconds: float = 90.0,
    max_retries: int = 0,
    prompt_version: str = STRUCTURAL_PROMPT_VERSION,
) -> tuple[StructuralAgentProposal, dict]:
    """Request a bounded open/short/port-mismatch repair proposal."""

    api = client or OpenAI(timeout=timeout_seconds, max_retries=max_retries)
    payload = {
        "task": "Diagnose one structural or port-impedance fault and propose one repair.",
        "faulty_netlist": netlist,
        "target_specification": spec,
        "measured_simulation": metrics,
    }
    if feedback_history:
        payload["previous_attempts"] = feedback_history
    if prompt_version not in {
        STRUCTURAL_PROMPT_VERSION,
        STRUCTURAL_NORMALIZED_PROMPT_VERSION,
        STRUCTURAL_PORT_ROLE_PROMPT_VERSION,
    }:
        raise ValueError(f"unsupported structural prompt_version: {prompt_version}")
    port_role_guidance = (
        " VPORT1 is the source/input port and VPORT2 is the load/output port. "
        if prompt_version
        in {STRUCTURAL_NORMALIZED_PROMPT_VERSION, STRUCTURAL_PORT_ROLE_PROMPT_VERSION}
        else ""
    )
    normalized_guidance = (
        "Engineering units such as nH, pF, or ohm are accepted and deterministically "
        "canonicalized to SPICE tokens without changing their numeric meaning."
        if prompt_version == STRUCTURAL_NORMALIZED_PROMPT_VERSION
        else ""
    )
    response = api.responses.create(
        model=model,
        reasoning={"effort": reasoning_effort},
        max_output_tokens=max_output_tokens,
        store=False,
        text={
            "format": {
                "type": "json_schema",
                "name": STRUCTURAL_SCHEMA_VERSION,
                "schema": StructuralAgentProposal.model_json_schema(),
                "strict": True,
            },
            "verbosity": "low",
        },
        instructions=(
            "Diagnose one fault in an ideal lumped 100 MHz RF band-pass filter. "
            "A line named RFAULT<component> represents a synthetic open (1T ohm) or "
            "short (1m ohm) replacement of that original reactive component. RF ports "
            "have explicit z0 values. Choose exactly one repair: restore_component for "
            "an RFAULT line, or set_port_impedance for VPORT1/VPORT2. For restore_component "
            "set proposed_value and set proposed_z0 to null. For set_port_impedance set "
            "proposed_z0 and set proposed_value to null. Do not claim success; an external "
            "ngspice validator decides. Previous failed attempts may be supplied; do not "
            "repeat a failed patch. Keep evidence concise."
            + port_role_guidance
            + normalized_guidance
        ),
        input=json.dumps(payload, indent=2, sort_keys=True),
    )
    metadata = _request_common_metadata(
        response,
        prompt_version=prompt_version,
        schema_version=STRUCTURAL_SCHEMA_VERSION,
    )
    raw_output = response.output_text
    incomplete_reason = (
        response.incomplete_details.reason if response.incomplete_details else None
    )
    common_error = {
        "response_status": response.status,
        "incomplete_reason": incomplete_reason,
        "usage": metadata["usage"],
        "raw_output": raw_output,
    }
    if response.status != "completed" or not raw_output:
        raise ProposalUnavailable(
            message="model returned no complete structural output text",
            **common_error,
        )
    try:
        proposal = StructuralAgentProposal.model_validate_json(raw_output)
    except ValidationError as error:
        raise ProposalSchemaInvalid(
            message="structural output failed local schema validation",
            validation_error_count=error.error_count(),
            **common_error,
        ) from None
    return proposal, metadata


def apply_structural_restricted_patch(
    source: str,
    patch: StructuralRepairPatch,
    *,
    normalize_quantities: bool = False,
) -> str:
    """Apply one operation-specific structural repair with no free-form netlist edit."""

    if patch.operation == "restore_component":
        if not patch.component.startswith(("R", "L", "C")) or patch.component.startswith("V"):
            raise ValueError("restore_component requires an R/L/C component")
        if patch.proposed_value is None or patch.proposed_z0 is not None:
            raise ValueError("restore_component fields are inconsistent")
        proposed_value = (
            normalize_spice_quantity(
                patch.proposed_value,
                expected_unit="H" if patch.component.startswith("L") else "F",
            )
            if normalize_quantities
            else patch.proposed_value
        )
        if not _SPICE_VALUE.fullmatch(proposed_value):
            raise ValueError("proposed_value is not a permitted SPICE numeric token")
        fault_name = f"RFAULT{patch.component}"
        matches = [line.split() for line in source.splitlines() if line.split() and line.split()[0].upper() == fault_name]
        if len(matches) != 1 or len(matches[0]) != 4:
            raise ValueError("matching synthetic fault resistor was not found")
        return restore_component_from_fault_resistor(
            source,
            component=patch.component,
            expected_resistance=matches[0][3],
            healthy_value=proposed_value,
        )

    if patch.operation == "set_port_impedance":
        if not patch.component.startswith("VPORT"):
            raise ValueError("set_port_impedance requires VPORT1 or VPORT2")
        if patch.proposed_z0 is None or patch.proposed_value is not None:
            raise ValueError("set_port_impedance fields are inconsistent")
        proposed_z0 = (
            normalize_spice_quantity(patch.proposed_z0, expected_unit="ohm")
            if normalize_quantities
            else patch.proposed_z0
        )
        if not _SPICE_VALUE.fullmatch(proposed_z0):
            raise ValueError("proposed_z0 is not a permitted SPICE numeric token")
        port_lines = [line.split() for line in source.splitlines() if line.split() and line.split()[0].upper() == patch.component]
        if len(port_lines) != 1:
            raise ValueError("matching RF port was not found")
        tokens = port_lines[0]
        lowered = [token.lower() for token in tokens]
        if "z0" not in lowered:
            raise ValueError("RF port has no z0 value")
        current_z0 = tokens[lowered.index("z0") + 1]
        if current_z0.lower() == proposed_z0.lower():
            raise ValueError("repair must change the port impedance")
        return set_port_impedance(
            source,
            port=patch.component,
            expected_z0=current_z0,
            new_z0=proposed_z0,
        )

    raise ValueError(f"unsupported structural repair operation: {patch.operation}")

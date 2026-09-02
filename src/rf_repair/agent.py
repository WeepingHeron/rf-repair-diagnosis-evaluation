"""Bounded OpenAI adapter for one-edit RF fault diagnosis proposals."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Literal

from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field

from rf_repair.netlist import set_component_value


MODEL = "gpt-5.6-luna"
ALLOWED_COMPONENTS = ("C1", "C2", "C3", "L1", "L2", "L3")
_SPICE_VALUE = re.compile(
    r"^(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+|(?:meg|[tgkmunpf]))?$",
    re.IGNORECASE,
)


class Diagnosis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component: Literal["C1", "C2", "C3", "L1", "L2", "L3"]
    fault_type: Literal["value_too_low", "value_too_high", "unknown_direction"]
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(min_length=1, max_length=3)


class RepairPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["set_value"]
    component: Literal["C1", "C2", "C3", "L1", "L2", "L3"]
    proposed_value: str


class AgentProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    diagnosis: Diagnosis
    repair: RepairPatch


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


def build_agent_input(*, netlist: str, spec: dict, metrics: dict) -> str:
    """Build the agent-visible evidence bundle; no healthy netlist or manifest."""

    payload = {
        "task": "Diagnose one component-value fault and propose exactly one repair edit.",
        "faulty_netlist": netlist,
        "target_specification": spec,
        "measured_simulation": metrics,
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def request_proposal(
    *,
    netlist: str,
    spec: dict,
    metrics: dict,
    client: OpenAI | None = None,
    model: str = MODEL,
) -> tuple[AgentProposal, dict]:
    """Request one structured proposal and return safe usage metadata."""

    api = client or OpenAI()
    response = api.responses.parse(
        model=model,
        reasoning={"effort": "low"},
        max_output_tokens=700,
        store=False,
        text_format=AgentProposal,
        instructions=(
            "You are diagnosing an ideal lumped 100 MHz RF band-pass filter. "
            "Use only the supplied faulty netlist, target specification, and measured "
            "simulation. The healthy netlist and injected-fault manifest are unavailable. "
            "Choose one R/L/C value edit only. Do not claim success; an external ngspice "
            "validator will decide. proposed_value must be one positive SPICE numeric token."
        ),
        input=build_agent_input(netlist=netlist, spec=spec, metrics=metrics),
    )
    proposal = response.output_parsed
    if proposal is None:
        raise RuntimeError("model returned no parseable proposal")
    usage = response.usage.model_dump(mode="json") if response.usage else {}
    metadata = {"model": response.model, "response_status": response.status, "usage": usage}
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

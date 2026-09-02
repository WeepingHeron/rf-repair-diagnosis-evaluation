"""Run the frozen 10-case x 3-repeat value-fault Agent pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rf_repair.agent import (
    PROMPT_VERSION,
    SCHEMA_VERSION,
    apply_restricted_patch,
    load_local_api_key,
    request_proposal,
)
from rf_repair.benchmark import aggregate_runs
from rf_repair.netlist import set_component_value
from rf_repair.simulator import run_sparameter_simulation
from rf_repair.validator import validate_bpf_metrics


DEFAULT_PROTOCOL_PATH = ROOT / "experiments" / "value_fault_repeat_v0_1.json"
HEALTHY_NETLIST = ROOT / "circuits" / "bpf_100mhz" / "butterworth_3rd.cir"
SPEC_PATH = ROOT / "specs" / "bpf_100mhz.json"


def _load_cases(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    manifest_path = ROOT / protocol["fault_manifest"]
    manifest_bytes = manifest_path.read_bytes()
    observed_hash = hashlib.sha256(manifest_bytes).hexdigest()
    if observed_hash != protocol["fault_manifest_sha256"]:
        raise ValueError("fault manifest does not match frozen protocol hash")
    manifest = json.loads(manifest_bytes)
    cases = manifest["cases"]
    if len(cases) != protocol["case_count"]:
        raise ValueError("protocol case_count does not match fault manifest")
    return cases


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _safe_failure_row(*, fault_id: str, repetition: int, stage: str, error: Exception) -> dict:
    response_status = getattr(error, "response_status", None)
    usage = getattr(error, "usage", {})
    row = {
        "fault_id": fault_id,
        "repetition": repetition,
        "api_response_received": response_status is not None,
        "api_completed": response_status == "completed" if stage == "api" else True,
        "structured_response": False,
        "component_correct": False,
        "diagnosis_correct": False,
        "patch_accepted": False,
        "simulation_converged": False,
        "specification_recovered": False,
        "failure_stage": stage,
        "error_type": type(error).__name__,
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
    }
    incomplete_reason = getattr(error, "incomplete_reason", None)
    if response_status is not None:
        row["response_status"] = response_status
    if incomplete_reason is not None:
        row["incomplete_reason"] = incomplete_reason
    output_text_sha256 = getattr(error, "output_text_sha256", None)
    if output_text_sha256 is not None:
        row["output_text_sha256"] = output_text_sha256
        row["output_text_chars"] = getattr(error, "output_text_chars", 0)
    validation_error_count = getattr(error, "validation_error_count", None)
    if validation_error_count is not None:
        row["validation_error_count"] = validation_error_count
    return row


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL_PATH)
    parser.add_argument(
        "--max-new-attempts",
        type=int,
        default=None,
        help="Cost guard: issue at most this many new API requests, then stop cleanly.",
    )
    args = parser.parse_args()
    protocol_path = args.protocol if args.protocol.is_absolute() else ROOT / args.protocol
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    output_root = ROOT / "build" / "experiments" / protocol["experiment_id"]
    evidence_mode = protocol.get("agent_evidence_mode", "netlist_spec_and_spice")
    if evidence_mode not in {"netlist_and_spec", "netlist_spec_and_spice"}:
        raise ValueError(f"unsupported agent_evidence_mode: {evidence_mode}")
    if protocol.get("prompt_version", PROMPT_VERSION) != PROMPT_VERSION:
        raise ValueError("protocol prompt_version does not match implementation")
    if protocol.get("agent_schema_version", SCHEMA_VERSION) != SCHEMA_VERSION:
        raise ValueError("protocol agent_schema_version does not match implementation")
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    healthy_source = HEALTHY_NETLIST.read_text(encoding="utf-8")
    cases = _load_cases(protocol)
    repeats = int(protocol["repetitions_per_case"])
    expected = int(protocol["planned_api_calls"])
    if len(cases) * repeats != expected:
        raise ValueError("planned_api_calls does not match cases x repetitions")

    load_local_api_key(ROOT / ".env.local")
    rows: list[dict[str, Any]] = []
    new_attempts = 0
    for case in cases:
        case_dir = output_root / case["fault_id"]
        faulty_source = set_component_value(
            healthy_source,
            component=case["component"],
            expected_value=case["healthy_value"],
            new_value=case["faulty_value"],
        )
        faulty_path = case_dir / "faulty.cir"
        faulty_path.parent.mkdir(parents=True, exist_ok=True)
        faulty_path.write_text(faulty_source, encoding="utf-8")
        faulty_metrics = run_sparameter_simulation(
            faulty_path, spec, case_dir / "faulty_simulation", cwd=ROOT
        )

        for repetition in range(1, repeats + 1):
            run_path = case_dir / f"run_{repetition}.json"
            if run_path.exists():
                rows.append(json.loads(run_path.read_text(encoding="utf-8")))
                print(f"reuse {case['fault_id']} run {repetition}/{repeats}")
                continue
            if (
                args.max_new_attempts is not None
                and new_attempts >= args.max_new_attempts
            ):
                continue

            new_attempts += 1
            try:
                proposal, api_metadata = request_proposal(
                    netlist=faulty_source,
                    spec=spec,
                    metrics=(
                        faulty_metrics
                        if evidence_mode == "netlist_spec_and_spice"
                        else None
                    ),
                    model=protocol["model"],
                    max_output_tokens=int(protocol["max_output_tokens"]),
                    reasoning_effort=protocol.get("reasoning_effort", "low"),
                    timeout_seconds=float(protocol.get("request_timeout_seconds", 90)),
                    max_retries=int(protocol.get("automatic_api_retries", 0)),
                )
            except Exception as error:
                row = _safe_failure_row(
                    fault_id=case["fault_id"], repetition=repetition, stage="api", error=error
                )
                _write_json(run_path, row)
                raw_output = getattr(error, "raw_output", "")
                if raw_output:
                    (case_dir / f"invalid_output_run_{repetition}.txt").write_text(
                        raw_output, encoding="utf-8"
                    )
                rows.append(row)
                print(f"fail {case['fault_id']} run {repetition}/{repeats}: api")
                continue

            usage = api_metadata.get("usage", {})
            row: dict[str, Any] = {
                "fault_id": case["fault_id"],
                "repetition": repetition,
                "api_completed": api_metadata.get("response_status") == "completed",
                "api_response_received": True,
                "structured_response": True,
                "proposed_component": proposal.diagnosis.component,
                "proposed_fault_type": proposal.diagnosis.fault_type,
                "proposed_value": proposal.repair.proposed_value,
                "component_correct": proposal.diagnosis.component == case["component"],
                "diagnosis_correct": (
                    proposal.diagnosis.component == case["component"]
                    and proposal.diagnosis.fault_type == case["fault_type"]
                ),
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
                "output_text_sha256": api_metadata.get("output_text_sha256"),
                "output_text_chars": api_metadata.get("output_text_chars"),
                "prompt_version": api_metadata.get("prompt_version"),
                "agent_schema_version": api_metadata.get("schema_version"),
            }
            try:
                repaired_source = apply_restricted_patch(faulty_source, proposal.repair)
                row["patch_accepted"] = True
                repaired_path = case_dir / f"repaired_run_{repetition}.cir"
                repaired_path.write_text(repaired_source, encoding="utf-8")
                metrics = run_sparameter_simulation(
                    repaired_path,
                    spec,
                    case_dir / f"repaired_simulation_{repetition}",
                    cwd=ROOT,
                )
                verdict = validate_bpf_metrics(metrics, spec)
                row["simulation_converged"] = metrics.get("simulation_converged") is True
                row["specification_recovered"] = verdict["verdict"] == "PASS"
                row["validation_reason"] = verdict["reason"]
            except Exception as error:
                row["patch_accepted"] = False
                row["simulation_converged"] = False
                row["specification_recovered"] = False
                row["failure_stage"] = "patch_or_simulation"
                row["error_type"] = type(error).__name__

            _write_json(run_path, row)
            rows.append(row)
            outcome = "PASS" if row["specification_recovered"] else "FAIL"
            print(f"done {case['fault_id']} run {repetition}/{repeats}: {outcome}")

    summary = {
        "experiment_id": protocol["experiment_id"],
        "condition": protocol["condition"],
        "claim_boundary": protocol["claim_boundary"],
        **aggregate_runs(rows, expected_attempts=expected),
    }
    _write_json(output_root / "summary.json", summary)
    print(json.dumps(summary, indent=2))
    if args.max_new_attempts is not None:
        return 0
    return 0 if summary["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Run the frozen 10-case x 3-repeat value-fault Agent pilot."""

from __future__ import annotations

import json
import hashlib
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rf_repair.agent import apply_restricted_patch, load_local_api_key, request_proposal
from rf_repair.benchmark import aggregate_runs
from rf_repair.netlist import set_component_value
from rf_repair.simulator import run_sparameter_simulation
from rf_repair.validator import validate_bpf_metrics


PROTOCOL_PATH = ROOT / "experiments" / "value_fault_repeat_v0_1.json"
HEALTHY_NETLIST = ROOT / "circuits" / "bpf_100mhz" / "butterworth_3rd.cir"
SPEC_PATH = ROOT / "specs" / "bpf_100mhz.json"
OUTPUT_ROOT = ROOT / "build" / "experiments" / "value_fault_repeat_v0_1"


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
    row = {
        "fault_id": fault_id,
        "repetition": repetition,
        "api_completed": stage != "api",
        "structured_response": False,
        "component_correct": False,
        "diagnosis_correct": False,
        "patch_accepted": False,
        "simulation_converged": False,
        "specification_recovered": False,
        "failure_stage": stage,
        "error_type": type(error).__name__,
    }
    response_status = getattr(error, "response_status", None)
    incomplete_reason = getattr(error, "incomplete_reason", None)
    if response_status is not None:
        row["response_status"] = response_status
    if incomplete_reason is not None:
        row["incomplete_reason"] = incomplete_reason
    return row


def main() -> int:
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    healthy_source = HEALTHY_NETLIST.read_text(encoding="utf-8")
    cases = _load_cases(protocol)
    repeats = int(protocol["repetitions_per_case"])
    expected = int(protocol["planned_api_calls"])
    if len(cases) * repeats != expected:
        raise ValueError("planned_api_calls does not match cases x repetitions")

    load_local_api_key(ROOT / ".env.local")
    rows: list[dict[str, Any]] = []
    for case in cases:
        case_dir = OUTPUT_ROOT / case["fault_id"]
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

            try:
                proposal, api_metadata = request_proposal(
                    netlist=faulty_source,
                    spec=spec,
                    metrics=faulty_metrics,
                    model=protocol["model"],
                    max_output_tokens=int(protocol["max_output_tokens"]),
                )
            except Exception as error:
                row = _safe_failure_row(
                    fault_id=case["fault_id"], repetition=repetition, stage="api", error=error
                )
                _write_json(run_path, row)
                rows.append(row)
                print(f"fail {case['fault_id']} run {repetition}/{repeats}: api")
                continue

            usage = api_metadata.get("usage", {})
            row: dict[str, Any] = {
                "fault_id": case["fault_id"],
                "repetition": repetition,
                "api_completed": api_metadata.get("response_status") == "completed",
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
    _write_json(OUTPUT_ROOT / "summary.json", summary)
    print(json.dumps(summary, indent=2))
    return 0 if summary["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

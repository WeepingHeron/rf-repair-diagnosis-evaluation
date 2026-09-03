"""Run bounded closed-loop repair on synthetic open/short/port faults."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as importlib_metadata
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rf_repair.agent import (
    STRUCTURAL_BLIND_LABEL_PROMPT_VERSION,
    STRUCTURAL_BLIND_PROMPT_VERSION,
    STRUCTURAL_PROMPT_VERSION,
    STRUCTURAL_NORMALIZED_PROMPT_VERSION,
    STRUCTURAL_PORT_ROLE_PROMPT_VERSION,
    STRUCTURAL_SCHEMA_VERSION,
    apply_structural_restricted_patch,
    load_local_api_key,
    request_structural_proposal,
)
from rf_repair.netlist import replace_component_with_resistor, set_port_impedance
from rf_repair.simulator import run_sparameter_simulation
from rf_repair.validator import validate_bpf_metrics


PROTOCOL_PATH = ROOT / "experiments" / "closed_loop_structural_repeat_v1_0.json"
HEALTHY_NETLIST = ROOT / "circuits" / "bpf_100mhz" / "butterworth_3rd.cir"
SPEC_PATH = ROOT / "specs" / "bpf_100mhz.json"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _command_output(command: list[str]) -> str | None:
    try:
        completed = subprocess.run(
            command, cwd=ROOT, capture_output=True, text=True, check=False
        )
    except OSError:
        return None
    output = (completed.stdout or completed.stderr).strip()
    return output.splitlines()[0] if output else None


def _inject(source: str, case: dict[str, Any]) -> str:
    if case["operation"] == "replace_with_resistor":
        return replace_component_with_resistor(
            source,
            component=case["component"],
            expected_value=case["healthy_value"],
            resistance=case["fault_resistance"],
            fault_name=case.get("fault_name"),
        )
    if case["operation"] == "set_port_impedance":
        return set_port_impedance(
            source,
            port=case["component"],
            expected_z0=case["healthy_z0"],
            new_z0=case["faulty_z0"],
        )
    raise ValueError(f"unsupported fault operation: {case['operation']}")


def _feedback(row: dict, metrics: dict | None, verdict: dict | None) -> dict:
    item = {
        "iteration": row["iteration"],
        "proposal": {
            "operation": row.get("proposed_operation"),
            "component": row.get("proposed_component"),
            "fault_type": row.get("proposed_fault_type"),
            "proposed_value": row.get("proposed_value"),
            "proposed_z0": row.get("proposed_z0"),
        },
        "outcome": row["outcome"],
    }
    if row.get("patch_rejection_code"):
        item["patch_rejection_code"] = row["patch_rejection_code"]
    if metrics is not None:
        item["repaired_simulation"] = metrics
    if verdict is not None:
        item["failed_constraints"] = [
            check for check in verdict["checks"] if not check["passed"]
        ]
    return item


def _rejection_code(error: Exception) -> str:
    message = str(error)
    if "must change" in message:
        return "NO_VALUE_CHANGE"
    if "fields are inconsistent" in message:
        return "OPERATION_FIELDS_INCONSISTENT"
    if "not found" in message:
        return "TARGET_NOT_FOUND"
    return "PATCH_POLICY_REJECTED"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=PROTOCOL_PATH)
    parser.add_argument("--max-new-trajectories", type=int, default=None)
    parser.add_argument("--fault-id", type=str, default=None)
    args = parser.parse_args()
    protocol_path = args.protocol if args.protocol.is_absolute() else ROOT / args.protocol
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol["prompt_version"] not in {
        STRUCTURAL_PROMPT_VERSION,
        STRUCTURAL_NORMALIZED_PROMPT_VERSION,
        STRUCTURAL_PORT_ROLE_PROMPT_VERSION,
        STRUCTURAL_BLIND_PROMPT_VERSION,
        STRUCTURAL_BLIND_LABEL_PROMPT_VERSION,
    }:
        raise ValueError("structural prompt version mismatch")
    if protocol["agent_schema_version"] != STRUCTURAL_SCHEMA_VERSION:
        raise ValueError("structural schema version mismatch")
    raw_manifest = (ROOT / protocol["fault_manifest"]).read_bytes()
    if hashlib.sha256(raw_manifest).hexdigest() != protocol["fault_manifest_sha256"]:
        raise ValueError("fault manifest does not match frozen protocol hash")
    cases = json.loads(raw_manifest)["cases"]
    if len(cases) != int(protocol["case_count"]):
        raise ValueError("fault manifest case count does not match frozen protocol")
    selected_cases = (
        [case for case in cases if case["fault_id"] == args.fault_id]
        if args.fault_id
        else cases
    )
    if args.fault_id and not selected_cases:
        raise ValueError(f"unknown fault_id: {args.fault_id}")
    trajectories_per_case = int(protocol["trajectories_per_case"])
    max_iterations = int(protocol["max_iterations"])
    if len(cases) * trajectories_per_case * max_iterations != int(
        protocol["planned_max_api_calls"]
    ):
        raise ValueError("planned maximum calls do not match protocol dimensions")

    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    healthy_source = HEALTHY_NETLIST.read_text(encoding="utf-8")
    output_root = ROOT / "build" / "experiments" / protocol["experiment_id"]
    environment_path = output_root / "run_environment.json"
    if not environment_path.exists():
        _write_json(
            environment_path,
            {
                "started_at_utc": datetime.now(timezone.utc).isoformat(),
                "git_commit": _command_output(["git", "rev-parse", "HEAD"]),
                "protocol_path": str(protocol_path.relative_to(ROOT)),
                "protocol_sha256": hashlib.sha256(
                    protocol_path.read_bytes()
                ).hexdigest(),
                "fault_manifest_sha256": hashlib.sha256(raw_manifest).hexdigest(),
                "python_version": platform.python_version(),
                "openai_package_version": importlib_metadata.version("openai"),
                "ngspice_version": _command_output(["ngspice", "--version"]),
                "response_storage": protocol.get("response_storage", False),
            },
        )
    load_local_api_key(ROOT / ".env.local")
    new_trajectories = 0

    for case in selected_cases:
        faulty_source = _inject(healthy_source, case)
        case_dir = output_root / case["fault_id"]
        case_dir.mkdir(parents=True, exist_ok=True)
        faulty_path = case_dir / "faulty.cir"
        faulty_path.write_text(faulty_source, encoding="utf-8")
        faulty_metrics = run_sparameter_simulation(
            faulty_path, spec, case_dir / "faulty_simulation", cwd=ROOT
        )

        for trajectory in range(1, trajectories_per_case + 1):
            trajectory_dir = case_dir / f"trajectory_{trajectory}"
            final_path = trajectory_dir / "final.json"
            if final_path.exists():
                print(f"reuse {case['fault_id']} trajectory {trajectory}")
                continue
            if (
                args.max_new_trajectories is not None
                and new_trajectories >= args.max_new_trajectories
            ):
                continue
            new_trajectories += 1
            trajectory_dir.mkdir(parents=True, exist_ok=True)
            history = []
            rows = []

            for iteration in range(1, max_iterations + 1):
                row: dict[str, Any] = {
                    "fault_id": case["fault_id"],
                    "trajectory": trajectory,
                    "iteration": iteration,
                }
                try:
                    proposal, metadata = request_structural_proposal(
                        netlist=faulty_source,
                        spec=spec,
                        metrics=faulty_metrics,
                        feedback_history=history,
                        model=protocol["model"],
                        max_output_tokens=int(protocol["max_output_tokens"]),
                        reasoning_effort=protocol["reasoning_effort"],
                        timeout_seconds=float(protocol["request_timeout_seconds"]),
                        max_retries=int(protocol["automatic_api_retries"]),
                        prompt_version=protocol["prompt_version"],
                    )
                    row.update(
                        {
                            "api_completed": True,
                            "structured_response": True,
                            "proposed_operation": proposal.repair.operation,
                            "proposed_component": proposal.diagnosis.component,
                            "repair_component": proposal.repair.component,
                            "proposed_fault_type": proposal.diagnosis.fault_type,
                            "proposed_value": proposal.repair.proposed_value,
                            "proposed_z0": proposal.repair.proposed_z0,
                            "diagnosis_confidence": proposal.diagnosis.confidence,
                            "diagnosis_evidence": proposal.diagnosis.evidence,
                            "component_correct": proposal.diagnosis.component
                            == case["component"],
                            "diagnosis_correct": (
                                proposal.diagnosis.component == case["component"]
                                and proposal.diagnosis.fault_type == case["fault_type"]
                            ),
                            "usage": metadata["usage"],
                            "response_id": metadata["response_id"],
                            "model": metadata["model"],
                            "response_status": metadata["response_status"],
                            "incomplete_reason": metadata["incomplete_reason"],
                            "response_created_at": metadata["response_created_at"],
                            "output_text": metadata["output_text"],
                            "output_text_sha256": metadata["output_text_sha256"],
                            "output_text_chars": metadata["output_text_chars"],
                            "prompt_version": metadata["prompt_version"],
                            "schema_version": metadata["schema_version"],
                        }
                    )
                except Exception as error:
                    usage = getattr(error, "usage", {})
                    row.update(
                        {
                            "api_completed": False,
                            "structured_response": False,
                            "component_correct": False,
                            "diagnosis_correct": False,
                            "outcome": "API_OR_SCHEMA_FAILURE",
                            "error_type": type(error).__name__,
                            "response_status": getattr(error, "response_status", None),
                            "incomplete_reason": getattr(error, "incomplete_reason", None),
                            "usage": usage,
                            "output_text_sha256": getattr(
                                error, "output_text_sha256", None
                            ),
                            "output_text_chars": getattr(
                                error, "output_text_chars", None
                            ),
                            "prompt_version": protocol["prompt_version"],
                            "schema_version": protocol["agent_schema_version"],
                        }
                    )
                    raw_output = getattr(error, "raw_output", "")
                    if raw_output:
                        (trajectory_dir / f"invalid_output_{iteration}.txt").write_text(
                            raw_output, encoding="utf-8"
                        )
                    _write_json(trajectory_dir / f"iteration_{iteration}.json", row)
                    rows.append(row)
                    break

                metrics = None
                verdict = None
                try:
                    repaired_source = apply_structural_restricted_patch(
                        faulty_source,
                        proposal.repair,
                        normalize_quantities=bool(
                            protocol.get("normalize_engineering_quantities", False)
                        ),
                        neutral_fault_resistor_name=protocol.get(
                            "neutral_fault_resistor_name"
                        ),
                    )
                    row["patch_accepted"] = True
                    repaired_path = trajectory_dir / f"repaired_{iteration}.cir"
                    repaired_path.write_text(repaired_source, encoding="utf-8")
                    metrics = run_sparameter_simulation(
                        repaired_path,
                        spec,
                        trajectory_dir / f"simulation_{iteration}",
                        cwd=ROOT,
                    )
                    verdict = validate_bpf_metrics(metrics, spec)
                    row["simulation_converged"] = metrics.get("simulation_converged") is True
                    row["specification_recovered"] = verdict["verdict"] == "PASS"
                    row["outcome"] = verdict["reason"]
                except ValueError as error:
                    row["patch_accepted"] = False
                    row["simulation_converged"] = False
                    row["specification_recovered"] = False
                    row["outcome"] = "PATCH_REJECTED"
                    row["patch_rejection_code"] = _rejection_code(error)

                _write_json(trajectory_dir / f"iteration_{iteration}.json", row)
                rows.append(row)
                if row["specification_recovered"]:
                    break
                history.append(_feedback(row, metrics, verdict))

            final = {
                "fault_id": case["fault_id"],
                "fault_type": case["fault_type"],
                "trajectory": trajectory,
                "iterations_used": len(rows),
                "first_iteration_recovered": rows[0].get(
                    "specification_recovered", False
                ),
                "final_recovered": any(
                    row.get("specification_recovered") is True for row in rows
                ),
                "first_component_correct": rows[0].get("component_correct", False),
                "final_component_correct": rows[-1].get("component_correct", False),
                "first_diagnosis_correct": rows[0].get("diagnosis_correct", False),
                "final_diagnosis_correct": rows[-1].get("diagnosis_correct", False),
                "accepted_candidate_simulations": sum(
                    row.get("patch_accepted") is True for row in rows
                ),
                "api_or_schema_failures": sum(
                    row.get("outcome") == "API_OR_SCHEMA_FAILURE" for row in rows
                ),
                "total_tokens": sum(
                    int(row.get("usage", {}).get("total_tokens", 0)) for row in rows
                ),
            }
            _write_json(final_path, final)
            print(
                f"done {case['fault_id']} trajectory {trajectory}: "
                f"{'PASS' if final['final_recovered'] else 'FAIL'} "
                f"in {final['iterations_used']}"
            )

    finals = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(output_root.glob("*/trajectory_*/final.json"))
    ]
    initial_fault_simulation_calls = len({row["fault_id"] for row in finals})
    summary = {
        "experiment_id": protocol["experiment_id"],
        "trajectory_count": len(finals),
        "complete": len(finals) == len(cases) * trajectories_per_case,
        "first_component_localization_count": sum(
            row["first_component_correct"] for row in finals
        ),
        "final_component_localization_count": sum(
            row["final_component_correct"] for row in finals
        ),
        "first_full_diagnosis_count": sum(
            row["first_diagnosis_correct"] for row in finals
        ),
        "final_full_diagnosis_count": sum(
            row["final_diagnosis_correct"] for row in finals
        ),
        "first_iteration_recovery_count": sum(
            row["first_iteration_recovered"] for row in finals
        ),
        "final_recovery_count": sum(row["final_recovered"] for row in finals),
        "recovered_after_feedback_count": sum(
            row["final_recovered"] and not row["first_iteration_recovered"] for row in finals
        ),
        "total_agent_calls": sum(row["iterations_used"] for row in finals),
        "accepted_candidate_simulation_calls": sum(
            row["accepted_candidate_simulations"] for row in finals
        ),
        "initial_fault_simulation_calls": initial_fault_simulation_calls,
        "api_or_schema_failure_count": sum(
            row["api_or_schema_failures"] for row in finals
        ),
        "recorded_total_tokens": sum(row["total_tokens"] for row in finals),
    }
    summary["total_simulator_calls"] = (
        summary["accepted_candidate_simulation_calls"]
        + summary["initial_fault_simulation_calls"]
    )
    summary["mean_iterations"] = (
        summary["total_agent_calls"] / len(finals) if finals else 0.0
    )
    _write_json(output_root / "summary.json", summary)
    print(json.dumps(summary, indent=2))
    return 0 if (
        summary["complete"]
        or args.max_new_trajectories is not None
        or args.fault_id is not None
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Run bounded closed-loop repair trajectories on value faults."""

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
    CLOSED_LOOP_PROMPT_VERSION,
    SCHEMA_VERSION,
    apply_restricted_patch,
    load_local_api_key,
    request_proposal,
)
from rf_repair.netlist import set_component_value
from rf_repair.simulator import run_sparameter_simulation
from rf_repair.validator import validate_bpf_metrics


DEFAULT_PROTOCOL = ROOT / "experiments" / "closed_loop_value_pilot_v0_1.json"
HEALTHY_NETLIST = ROOT / "circuits" / "bpf_100mhz" / "butterworth_3rd.cir"
SPEC_PATH = ROOT / "specs" / "bpf_100mhz.json"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _load_cases(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    path = ROOT / protocol["fault_manifest"]
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != protocol["fault_manifest_sha256"]:
        raise ValueError("fault manifest does not match frozen protocol hash")
    cases = json.loads(raw)["cases"]
    if len(cases) != protocol["case_count"]:
        raise ValueError("protocol case_count does not match fault manifest")
    return cases


def _patch_rejection_code(error: Exception) -> str:
    message = str(error)
    if "must change" in message:
        return "NO_VALUE_CHANGE"
    if "numeric token" in message:
        return "VALUE_TOKEN_NOT_ALLOWED"
    if "not found" in message:
        return "COMPONENT_NOT_FOUND"
    return "PATCH_POLICY_REJECTED"


def _feedback(row: dict, metrics: dict | None, verdict: dict | None) -> dict:
    item = {
        "iteration": row["iteration"],
        "proposal": {
            "component": row.get("proposed_component"),
            "fault_type": row.get("proposed_fault_type"),
            "proposed_value": row.get("proposed_value"),
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--max-new-trajectories", type=int, default=None)
    parser.add_argument("--fault-id", type=str, default=None)
    args = parser.parse_args()
    protocol_path = args.protocol if args.protocol.is_absolute() else ROOT / args.protocol
    protocol = _read_json(protocol_path)
    if protocol["prompt_version"] != CLOSED_LOOP_PROMPT_VERSION:
        raise ValueError("closed-loop prompt version mismatch")
    if protocol["agent_schema_version"] != SCHEMA_VERSION:
        raise ValueError("agent schema version mismatch")

    cases = _load_cases(protocol)
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

    spec = _read_json(SPEC_PATH)
    healthy_source = HEALTHY_NETLIST.read_text(encoding="utf-8")
    output_root = ROOT / "build" / "experiments" / protocol["experiment_id"]
    load_local_api_key(ROOT / ".env.local")
    new_trajectories = 0

    for case in selected_cases:
        faulty_source = set_component_value(
            healthy_source,
            component=case["component"],
            expected_value=case["healthy_value"],
            new_value=case["faulty_value"],
        )
        case_dir = output_root / case["fault_id"]
        faulty_path = case_dir / "faulty.cir"
        faulty_path.parent.mkdir(parents=True, exist_ok=True)
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
            history: list[dict] = []
            iteration_rows: list[dict] = []

            for iteration in range(1, max_iterations + 1):
                row: dict[str, Any] = {
                    "fault_id": case["fault_id"],
                    "trajectory": trajectory,
                    "iteration": iteration,
                }
                try:
                    proposal, metadata = request_proposal(
                        netlist=faulty_source,
                        spec=spec,
                        metrics=faulty_metrics,
                        model=protocol["model"],
                        max_output_tokens=int(protocol["max_output_tokens"]),
                        reasoning_effort=protocol["reasoning_effort"],
                        timeout_seconds=float(protocol["request_timeout_seconds"]),
                        max_retries=int(protocol["automatic_api_retries"]),
                        prompt_version=protocol["prompt_version"],
                        feedback_history=history,
                    )
                    row.update(
                        {
                            "api_completed": True,
                            "structured_response": True,
                            "proposed_component": proposal.diagnosis.component,
                            "proposed_fault_type": proposal.diagnosis.fault_type,
                            "proposed_value": proposal.repair.proposed_value,
                            "component_correct": proposal.diagnosis.component
                            == case["component"],
                            "diagnosis_correct": (
                                proposal.diagnosis.component == case["component"]
                                and proposal.diagnosis.fault_type == case["fault_type"]
                            ),
                            "usage": metadata["usage"],
                        }
                    )
                except Exception as error:
                    row.update(
                        {
                            "api_completed": False,
                            "structured_response": False,
                            "component_correct": False,
                            "diagnosis_correct": False,
                            "outcome": "API_OR_SCHEMA_FAILURE",
                            "error_type": type(error).__name__,
                        }
                    )
                    _write_json(trajectory_dir / f"iteration_{iteration}.json", row)
                    iteration_rows.append(row)
                    break

                metrics = None
                verdict = None
                try:
                    repaired_source = apply_restricted_patch(faulty_source, proposal.repair)
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
                    row["patch_rejection_code"] = _patch_rejection_code(error)

                _write_json(trajectory_dir / f"iteration_{iteration}.json", row)
                iteration_rows.append(row)
                if row["specification_recovered"]:
                    break
                history.append(_feedback(row, metrics, verdict))

            final = {
                "fault_id": case["fault_id"],
                "trajectory": trajectory,
                "iterations_used": len(iteration_rows),
                "first_iteration_recovered": iteration_rows[0].get(
                    "specification_recovered", False
                ),
                "final_recovered": any(
                    row.get("specification_recovered") is True for row in iteration_rows
                ),
                "final_component_correct": iteration_rows[-1].get(
                    "component_correct", False
                ),
                "total_tokens": sum(
                    int(row.get("usage", {}).get("total_tokens", 0))
                    for row in iteration_rows
                ),
            }
            _write_json(final_path, final)
            print(
                f"done {case['fault_id']} trajectory {trajectory}: "
                f"{'PASS' if final['final_recovered'] else 'FAIL'} "
                f"in {final['iterations_used']}"
            )

    finals = [_read_json(path) for path in sorted(output_root.glob("*/trajectory_*/final.json"))]
    first_rows = []
    last_rows = []
    all_iteration_rows = []
    for final in finals:
        trajectory_dir = (
            output_root
            / final["fault_id"]
            / f"trajectory_{final['trajectory']}"
        )
        first_rows.append(_read_json(trajectory_dir / "iteration_1.json"))
        last_rows.append(
            _read_json(trajectory_dir / f"iteration_{final['iterations_used']}.json")
        )
        all_iteration_rows.extend(
            _read_json(path) for path in sorted(trajectory_dir.glob("iteration_*.json"))
        )
    initial_fault_simulation_calls = len({row["fault_id"] for row in finals})
    summary = {
        "experiment_id": protocol["experiment_id"],
        "trajectory_count": len(finals),
        "complete": len(finals) == len(cases) * trajectories_per_case,
        "first_iteration_recovery_count": sum(
            row["first_iteration_recovered"] for row in finals
        ),
        "final_recovery_count": sum(row["final_recovered"] for row in finals),
        "recovered_after_feedback_count": sum(
            row["final_recovered"] and not row["first_iteration_recovered"] for row in finals
        ),
        "first_component_localization_count": sum(
            row.get("component_correct") is True for row in first_rows
        ),
        "final_component_localization_count": sum(
            row.get("component_correct") is True for row in last_rows
        ),
        "first_full_diagnosis_count": sum(
            row.get("diagnosis_correct") is True for row in first_rows
        ),
        "final_full_diagnosis_count": sum(
            row.get("diagnosis_correct") is True for row in last_rows
        ),
        "total_agent_calls": sum(row["iterations_used"] for row in finals),
        "accepted_candidate_simulation_calls": sum(
            row.get("patch_accepted") is True for row in all_iteration_rows
        ),
        "initial_fault_simulation_calls": initial_fault_simulation_calls,
        "total_simulator_calls": (
            sum(row.get("patch_accepted") is True for row in all_iteration_rows)
            + initial_fault_simulation_calls
        ),
        "api_or_schema_failure_count": sum(
            row.get("outcome") == "API_OR_SCHEMA_FAILURE" for row in all_iteration_rows
        ),
        "mean_iterations": (
            sum(row["iterations_used"] for row in finals) / len(finals) if finals else 0.0
        ),
        "recorded_total_tokens": sum(row["total_tokens"] for row in finals),
    }
    _write_json(output_root / "summary.json", summary)
    print(json.dumps(summary, indent=2))
    return 0 if (
        summary["complete"]
        or args.max_new_trajectories is not None
        or args.fault_id is not None
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())

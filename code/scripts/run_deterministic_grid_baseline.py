"""Run a transparent component-ratio grid-search repair baseline."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rf_repair.netlist import scale_spice_value, set_component_value
from rf_repair.simulator import run_sparameter_simulation
from rf_repair.validator import validate_bpf_metrics


PROTOCOL_PATH = ROOT / "experiments" / "deterministic_grid_value_v1_0.json"
HEALTHY_NETLIST = ROOT / "circuits" / "bpf_100mhz" / "butterworth_3rd.cir"
SPEC_PATH = ROOT / "specs" / "bpf_100mhz.json"


def _component_values(source: str) -> dict[str, str]:
    values = {}
    for line in source.splitlines():
        tokens = line.split()
        if len(tokens) == 4 and tokens[0].upper().startswith(("R", "L", "C")):
            values[tokens[0].upper()] = tokens[3]
    return values


def main() -> int:
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    manifest_path = ROOT / protocol["fault_manifest"]
    raw_manifest = manifest_path.read_bytes()
    if hashlib.sha256(raw_manifest).hexdigest() != protocol["fault_manifest_sha256"]:
        raise ValueError("fault manifest does not match frozen protocol hash")
    cases = json.loads(raw_manifest)["cases"]
    if len(cases) != protocol["case_count"]:
        raise ValueError("protocol case_count does not match manifest")

    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    healthy_source = HEALTHY_NETLIST.read_text(encoding="utf-8")
    output_root = ROOT / "build" / "experiments" / protocol["experiment_id"]
    rows = []

    for case in cases:
        faulty_source = set_component_value(
            healthy_source,
            component=case["component"],
            expected_value=case["healthy_value"],
            new_value=case["faulty_value"],
        )
        current_values = _component_values(faulty_source)
        case_dir = output_root / case["fault_id"]
        case_dir.mkdir(parents=True, exist_ok=True)
        simulations = 0
        winner = None

        for component in protocol["component_order"]:
            for multiplier in protocol["candidate_multipliers"]:
                simulations += 1
                proposed_value = scale_spice_value(current_values[component], multiplier)
                candidate = set_component_value(
                    faulty_source,
                    component=component,
                    expected_value=current_values[component],
                    new_value=proposed_value,
                )
                candidate_path = case_dir / f"candidate_{simulations:02d}.cir"
                candidate_path.write_text(candidate, encoding="utf-8")
                metrics = run_sparameter_simulation(
                    candidate_path,
                    spec,
                    case_dir / f"simulation_{simulations:02d}",
                    cwd=ROOT,
                )
                verdict = validate_bpf_metrics(metrics, spec)
                if verdict["verdict"] == "PASS":
                    winner = {
                        "component": component,
                        "multiplier": multiplier,
                        "proposed_value": proposed_value,
                    }
                    break
            if winner is not None:
                break

        row = {
            "fault_id": case["fault_id"],
            "simulation_calls": simulations,
            "specification_recovered": winner is not None,
            "selected_component": winner["component"] if winner else None,
            "component_correct": winner is not None
            and winner["component"] == case["component"],
            "winner": winner,
        }
        (case_dir / "result.json").write_text(
            json.dumps(row, indent=2) + "\n", encoding="utf-8"
        )
        rows.append(row)
        print(
            f"{case['fault_id']}: {'PASS' if winner else 'FAIL'} "
            f"after {simulations} simulations"
        )

    summary = {
        "experiment_id": protocol["experiment_id"],
        "case_count": len(rows),
        "specification_recovery_count": sum(
            row["specification_recovered"] for row in rows
        ),
        "component_localization_count": sum(row["component_correct"] for row in rows),
        "total_simulation_calls": sum(row["simulation_calls"] for row in rows),
        "mean_simulation_calls": sum(row["simulation_calls"] for row in rows) / len(rows),
        "claim_boundary": protocol["claim_boundary"],
    }
    (output_root / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    return 0 if summary["specification_recovery_count"] == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())

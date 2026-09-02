"""Verify every pilot fault has a one-edit ground-truth repair that passes."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rf_repair.netlist import (
    replace_component_with_resistor,
    restore_component_from_fault_resistor,
    set_component_value,
    set_port_impedance,
)
from rf_repair.simulator import run_sparameter_simulation
from rf_repair.validator import validate_bpf_metrics


HEALTHY_NETLIST = ROOT / "circuits" / "bpf_100mhz" / "butterworth_3rd.cir"
SPEC_PATH = ROOT / "specs" / "bpf_100mhz.json"
VALUE_MANIFEST = ROOT / "faults" / "pilot" / "bpf_value_fault_candidates.json"
STRUCTURAL_MANIFEST = ROOT / "faults" / "pilot" / "bpf_structural_fault_candidates.json"
OUTPUT_ROOT = ROOT / "build" / "oracle_repair_sweep"


def _inject_value(source: str, case: dict[str, Any]) -> str:
    return set_component_value(
        source,
        component=case["component"],
        expected_value=case["healthy_value"],
        new_value=case["faulty_value"],
    )


def _repair_value(source: str, case: dict[str, Any]) -> str:
    return set_component_value(
        source,
        component=case["component"],
        expected_value=case["faulty_value"],
        new_value=case["healthy_value"],
    )


def _inject_structural(source: str, case: dict[str, Any]) -> str:
    if case["operation"] == "replace_with_resistor":
        return replace_component_with_resistor(
            source,
            component=case["component"],
            expected_value=case["healthy_value"],
            resistance=case["fault_resistance"],
        )
    if case["operation"] == "set_port_impedance":
        return set_port_impedance(
            source,
            port=case["component"],
            expected_z0=case["healthy_z0"],
            new_z0=case["faulty_z0"],
        )
    raise ValueError(f"unsupported fault operation: {case['operation']}")


def _repair_structural(source: str, case: dict[str, Any]) -> str:
    if case["operation"] == "replace_with_resistor":
        return restore_component_from_fault_resistor(
            source,
            component=case["component"],
            expected_resistance=case["fault_resistance"],
            healthy_value=case["healthy_value"],
        )
    if case["operation"] == "set_port_impedance":
        return set_port_impedance(
            source,
            port=case["component"],
            expected_z0=case["faulty_z0"],
            new_z0=case["healthy_z0"],
        )
    raise ValueError(f"unsupported repair operation: {case['operation']}")


def _load_cases(path: Path) -> list[dict[str, Any]]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    return manifest["cases"]


def main() -> int:
    healthy_source = HEALTHY_NETLIST.read_text(encoding="utf-8")
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    groups = [
        ("value", _load_cases(VALUE_MANIFEST), _inject_value, _repair_value),
        (
            "structural",
            _load_cases(STRUCTURAL_MANIFEST),
            _inject_structural,
            _repair_structural,
        ),
    ]
    rows: list[dict[str, Any]] = []

    for group, cases, inject, repair in groups:
        for case in cases:
            case_dir = OUTPUT_ROOT / case["fault_id"]
            case_dir.mkdir(parents=True, exist_ok=True)
            faulty_source = inject(healthy_source, case)
            repaired_source = repair(faulty_source, case)
            repaired_netlist = case_dir / "repaired.cir"
            repaired_netlist.write_text(repaired_source, encoding="utf-8")
            metrics = run_sparameter_simulation(
                repaired_netlist, spec, case_dir / "simulation", cwd=ROOT
            )
            verdict = validate_bpf_metrics(metrics, spec)
            evidence = {
                "fault_id": case["fault_id"],
                "group": group,
                "repair_edit_count": 1,
                "metrics": metrics,
                "validation": verdict,
            }
            (case_dir / "evidence.json").write_text(
                json.dumps(evidence, indent=2) + "\n", encoding="utf-8"
            )
            rows.append(
                {
                    "fault_id": case["fault_id"],
                    "group": group,
                    "simulation_converged": metrics.get("simulation_converged") is True,
                    "repair_verdict": verdict["verdict"],
                    "repair_edit_count": 1,
                }
            )

    summary = {
        "case_count": len(rows),
        "oracle_repair_pass_count": sum(
            row["simulation_converged"] and row["repair_verdict"] == "PASS"
            for row in rows
        ),
        "cases": rows,
    }
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    (OUTPUT_ROOT / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    return 0 if summary["case_count"] == summary["oracle_repair_pass_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())


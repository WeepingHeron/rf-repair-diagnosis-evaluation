"""Screen candidate value faults against the deterministic specification."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rf_repair.netlist import set_component_value
from rf_repair.simulator import run_sparameter_simulation
from rf_repair.validator import validate_bpf_metrics


HEALTHY_NETLIST = ROOT / "circuits" / "bpf_100mhz" / "butterworth_3rd.cir"
SPEC_PATH = ROOT / "specs" / "bpf_100mhz.json"
MANIFEST_PATH = ROOT / "faults" / "pilot" / "bpf_value_fault_candidates.json"
OUTPUT_ROOT = ROOT / "build" / "value_fault_sweep"


def _failed_checks(verdict: dict[str, Any]) -> list[str]:
    return [check["name"] for check in verdict["checks"] if not check["passed"]]


def main() -> int:
    healthy_source = HEALTHY_NETLIST.read_text(encoding="utf-8")
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    summaries: list[dict[str, Any]] = []

    for case in manifest["cases"]:
        case_dir = OUTPUT_ROOT / case["fault_id"]
        case_dir.mkdir(parents=True, exist_ok=True)
        faulty_netlist = case_dir / "faulty.cir"
        faulty_netlist.write_text(
            set_component_value(
                healthy_source,
                component=case["component"],
                expected_value=case["healthy_value"],
                new_value=case["faulty_value"],
            ),
            encoding="utf-8",
        )
        metrics = run_sparameter_simulation(
            faulty_netlist, spec, case_dir / "simulation", cwd=ROOT
        )
        verdict = validate_bpf_metrics(metrics, spec)
        evidence = {"case": case, "metrics": metrics, "validation": verdict}
        (case_dir / "evidence.json").write_text(
            json.dumps(evidence, indent=2) + "\n", encoding="utf-8"
        )
        summaries.append(
            {
                "fault_id": case["fault_id"],
                "component": case["component"],
                "scale": case["scale"],
                "simulation_converged": metrics.get("simulation_converged") is True,
                "verdict": verdict["verdict"],
                "failed_checks": _failed_checks(verdict),
                "peak_frequency_hz": metrics.get("peak_frequency_hz"),
                "peak_s21_db": metrics.get("peak_s21_db"),
            }
        )

    summary = {
        "candidate_count": len(summaries),
        "usable_fault_count": sum(
            row["simulation_converged"] and row["verdict"] == "FAIL" for row in summaries
        ),
        "cases": summaries,
    }
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    (OUTPUT_ROOT / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))

    return 0 if summary["candidate_count"] == summary["usable_fault_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())


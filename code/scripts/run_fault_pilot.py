"""Inject one evaluator-known pilot fault and verify that validation fails."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rf_repair.netlist import set_component_value
from rf_repair.simulator import run_sparameter_simulation
from rf_repair.validator import validate_bpf_metrics


HEALTHY_NETLIST = ROOT / "circuits" / "bpf_100mhz" / "butterworth_3rd.cir"
SPEC_PATH = ROOT / "specs" / "bpf_100mhz.json"
MANIFEST_PATH = ROOT / "faults" / "pilot" / "bpf_c1_x2.json"
OUTPUT_DIR = ROOT / "build" / "fault_pilot" / "bpf_c1_x2"
FAULTY_NETLIST = OUTPUT_DIR / "faulty.cir"


def main() -> int:
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    ground_truth = manifest["ground_truth"]

    faulty_source = set_component_value(
        HEALTHY_NETLIST.read_text(encoding="utf-8"),
        component=ground_truth["component"],
        expected_value=ground_truth["healthy_value"],
        new_value=ground_truth["faulty_value"],
    )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    FAULTY_NETLIST.write_text(faulty_source, encoding="utf-8")

    metrics = run_sparameter_simulation(FAULTY_NETLIST, spec, OUTPUT_DIR / "simulation", cwd=ROOT)
    verdict = validate_bpf_metrics(metrics, spec)
    evidence = {"fault_id": manifest["fault_id"], "metrics": metrics, "validation": verdict}
    (OUTPUT_DIR / "pilot_evidence.json").write_text(
        json.dumps(evidence, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(evidence, indent=2))

    if metrics.get("simulation_converged") is not True:
        raise SystemExit("pilot fault did not produce usable simulator evidence")
    if verdict["verdict"] != "FAIL":
        raise SystemExit("pilot fault unexpectedly passed the specification")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


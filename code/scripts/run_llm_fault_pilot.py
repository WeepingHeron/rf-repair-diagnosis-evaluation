"""Run one cost-bounded LLM diagnosis/repair pilot and verify it with ngspice."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rf_repair.agent import apply_restricted_patch, load_local_api_key, request_proposal
from rf_repair.netlist import set_component_value
from rf_repair.simulator import run_sparameter_simulation
from rf_repair.validator import validate_bpf_metrics


HEALTHY_NETLIST = ROOT / "circuits" / "bpf_100mhz" / "butterworth_3rd.cir"
SPEC_PATH = ROOT / "specs" / "bpf_100mhz.json"
MANIFEST_PATH = ROOT / "faults" / "pilot" / "bpf_c1_x2.json"
OUTPUT_DIR = ROOT / "build" / "llm_fault_pilot" / "bpf_c1_x2"


def main() -> int:
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    truth = manifest["ground_truth"]
    faulty_source = set_component_value(
        HEALTHY_NETLIST.read_text(encoding="utf-8"),
        component=truth["component"],
        expected_value=truth["healthy_value"],
        new_value=truth["faulty_value"],
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    faulty_path = OUTPUT_DIR / "faulty.cir"
    faulty_path.write_text(faulty_source, encoding="utf-8")
    faulty_metrics = run_sparameter_simulation(
        faulty_path, spec, OUTPUT_DIR / "faulty_simulation", cwd=ROOT
    )

    load_local_api_key(ROOT / ".env.local")
    proposal, api_metadata = request_proposal(
        netlist=faulty_source,
        spec=spec,
        metrics=faulty_metrics,
    )
    repaired_source = apply_restricted_patch(faulty_source, proposal.repair)
    repaired_path = OUTPUT_DIR / "repaired.cir"
    repaired_path.write_text(repaired_source, encoding="utf-8")
    repaired_metrics = run_sparameter_simulation(
        repaired_path, spec, OUTPUT_DIR / "repaired_simulation", cwd=ROOT
    )
    verdict = validate_bpf_metrics(repaired_metrics, spec)

    diagnosis_correct = (
        proposal.diagnosis.component == truth["component"]
        and proposal.diagnosis.fault_type == truth["fault_type"]
    )
    evidence = {
        "experiment_status": "SINGLE_LIVE_PILOT_NOT_BENCHMARK",
        "fault_id": manifest["fault_id"],
        "agent_proposal": proposal.model_dump(mode="json"),
        "diagnosis_ground_truth_match": diagnosis_correct,
        "api": api_metadata,
        "repaired_metrics": repaired_metrics,
        "validation": verdict,
    }
    (OUTPUT_DIR / "evidence.json").write_text(
        json.dumps(evidence, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(evidence, indent=2))
    return 0 if repaired_metrics.get("simulation_converged") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())

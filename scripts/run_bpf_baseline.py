"""Run the draft 100 MHz band-pass baseline and retain S-parameter evidence."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rf_repair.simulator import run_sparameter_simulation
from rf_repair.validator import validate_bpf_metrics


SOURCE_NETLIST = ROOT / "circuits" / "bpf_100mhz" / "butterworth_3rd.cir"
SPEC_PATH = ROOT / "specs" / "bpf_100mhz.json"
OUTPUT_DIR = ROOT / "build" / "bpf_100mhz"
METRICS_PATH = OUTPUT_DIR / "baseline_metrics.json"
VERDICT_PATH = OUTPUT_DIR / "baseline_verdict.json"


def main() -> int:
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    metrics = run_sparameter_simulation(SOURCE_NETLIST, spec, OUTPUT_DIR, cwd=ROOT)
    METRICS_PATH.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    verdict = validate_bpf_metrics(metrics, spec)
    VERDICT_PATH.write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({"metrics": metrics, "validation": verdict}, indent=2))
    return 0 if verdict["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

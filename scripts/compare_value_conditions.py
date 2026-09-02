"""Deterministically compare the frozen one-shot value-fault conditions."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILD_ROOT = ROOT / "build" / "experiments"
OUTPUT_PATH = BUILD_ROOT / "comparison_value_v1_0.json"
CONDITIONS = {
    "llm_only": "comparison_llm_only_v1_0",
    "spice_evidence": "comparison_spice_v1_0",
}


def _load_rows(experiment_id: str) -> list[dict]:
    paths = sorted((BUILD_ROOT / experiment_id).glob("*/run_*.json"))
    rows = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    if len(rows) != 30:
        raise ValueError(f"{experiment_id} must contain exactly 30 rows")
    return rows


def _per_fault(rows: list[dict]) -> dict[str, dict[str, int]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row["fault_id"]].append(row)
    return {
        fault_id: {
            "attempts": len(fault_rows),
            "component_correct": sum(
                row.get("component_correct") is True for row in fault_rows
            ),
            "diagnosis_correct": sum(
                row.get("diagnosis_correct") is True for row in fault_rows
            ),
            "specification_recovered": sum(
                row.get("specification_recovered") is True for row in fault_rows
            ),
        }
        for fault_id, fault_rows in sorted(grouped.items())
    }


def main() -> int:
    summaries = {}
    fault_tables = {}
    for name, experiment_id in CONDITIONS.items():
        summary_path = BUILD_ROOT / experiment_id / "summary.json"
        summaries[name] = json.loads(summary_path.read_text(encoding="utf-8"))
        fault_tables[name] = _per_fault(_load_rows(experiment_id))

    rate_names = [
        "component_localization_accuracy",
        "full_diagnosis_accuracy",
        "specification_recovery_rate",
        "component_consistency_rate",
    ]
    rate_comparison = {}
    for metric in rate_names:
        llm_only = summaries["llm_only"]["rates"][metric]
        spice = summaries["spice_evidence"]["rates"][metric]
        rate_comparison[metric] = {
            "llm_only": llm_only,
            "spice_evidence": spice,
            "spice_minus_llm_only": spice - llm_only,
        }

    fault_comparison = {}
    for fault_id in fault_tables["llm_only"]:
        llm_only = fault_tables["llm_only"][fault_id]
        spice = fault_tables["spice_evidence"][fault_id]
        fault_comparison[fault_id] = {
            "llm_only": llm_only,
            "spice_evidence": spice,
            "recovery_delta": (
                spice["specification_recovered"]
                - llm_only["specification_recovered"]
            ),
        }

    output = {
        "comparison_id": "comparison_value_v1_0",
        "status": "PRELIMINARY_NOT_FINAL_BENCHMARK",
        "conditions": CONDITIONS,
        "rate_comparison": rate_comparison,
        "usage": {name: summary["usage"] for name, summary in summaries.items()},
        "per_fault": fault_comparison,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

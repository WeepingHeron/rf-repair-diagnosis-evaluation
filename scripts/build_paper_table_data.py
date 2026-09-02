"""Collect experiment summaries into one machine-checkable table data file."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "build" / "experiments"
OUTPUT = ROOT / "build" / "paper_table_data.json"


def _summary(experiment_id: str) -> dict:
    path = EXPERIMENTS / experiment_id / "summary.json"
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    llm_only = _summary("comparison_llm_only_v1_0")
    initial_spice = _summary("comparison_spice_v1_0")
    value_loop = _summary("closed_loop_value_repeat_v1_0")
    grid = _summary("deterministic_grid_value_v1_0")
    structural_strict = _summary("closed_loop_structural_repeat_v1_0")
    structural_normalized = _summary("closed_loop_structural_normalized_v1_1")

    rows = [
        {
            "condition": "llm_only_one_shot",
            "trajectories": 30,
            "localization": llm_only["counts"]["component_correct"],
            "diagnosis": llm_only["counts"]["diagnosis_correct"],
            "recovery": llm_only["counts"]["specification_recovered"],
            "agent_calls": 30,
            "candidate_simulations": llm_only["counts"]["patch_accepted"],
            "tokens": llm_only["usage"]["total_tokens"],
        },
        {
            "condition": "initial_spice_one_shot",
            "trajectories": 30,
            "localization": initial_spice["counts"]["component_correct"],
            "diagnosis": initial_spice["counts"]["diagnosis_correct"],
            "recovery": initial_spice["counts"]["specification_recovered"],
            "agent_calls": 30,
            "candidate_simulations": initial_spice["counts"]["patch_accepted"],
            "tokens": initial_spice["usage"]["total_tokens"],
        },
        {
            "condition": "value_closed_loop",
            "trajectories": value_loop["trajectory_count"],
            "localization": value_loop["final_component_localization_count"],
            "diagnosis": value_loop["final_full_diagnosis_count"],
            "recovery": value_loop["final_recovery_count"],
            "agent_calls": value_loop["total_agent_calls"],
            "candidate_simulations": value_loop["accepted_candidate_simulation_calls"],
            "tokens": value_loop["recorded_total_tokens"],
        },
        {
            "condition": "deterministic_grid",
            "trajectories": grid["case_count"],
            "localization": grid["component_localization_count"],
            "diagnosis": None,
            "recovery": grid["specification_recovery_count"],
            "agent_calls": 0,
            "candidate_simulations": grid["total_simulation_calls"],
            "tokens": 0,
        },
        {
            "condition": "structural_strict",
            "trajectories": structural_strict["trajectory_count"],
            "localization": structural_strict["final_component_localization_count"],
            "diagnosis": structural_strict["final_full_diagnosis_count"],
            "recovery": structural_strict["final_recovery_count"],
            "agent_calls": structural_strict["total_agent_calls"],
            "candidate_simulations": structural_strict[
                "accepted_candidate_simulation_calls"
            ],
            "tokens": structural_strict["recorded_total_tokens"],
        },
        {
            "condition": "structural_normalized_post_hoc",
            "trajectories": structural_normalized["trajectory_count"],
            "localization": structural_normalized[
                "final_component_localization_count"
            ],
            "diagnosis": structural_normalized["final_full_diagnosis_count"],
            "recovery": structural_normalized["final_recovery_count"],
            "agent_calls": structural_normalized["total_agent_calls"],
            "candidate_simulations": structural_normalized[
                "accepted_candidate_simulation_calls"
            ],
            "tokens": structural_normalized["recorded_total_tokens"],
        },
    ]
    payload = {
        "status": "CURRENT_SIMULATOR_ONLY_RESULTS",
        "rows": rows,
        "normalized_combined": {
            "trajectories": value_loop["trajectory_count"]
            + structural_normalized["trajectory_count"],
            "localization": value_loop["final_component_localization_count"]
            + structural_normalized["final_component_localization_count"],
            "diagnosis": value_loop["final_full_diagnosis_count"]
            + structural_normalized["final_full_diagnosis_count"],
            "recovery": value_loop["final_recovery_count"]
            + structural_normalized["final_recovery_count"],
            "agent_calls": value_loop["total_agent_calls"]
            + structural_normalized["total_agent_calls"],
            "candidate_simulations": value_loop["accepted_candidate_simulation_calls"]
            + structural_normalized["accepted_candidate_simulation_calls"],
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

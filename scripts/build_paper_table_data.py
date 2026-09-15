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
    structural_strict = _summary("closed_loop_structural_blind_v2")
    structural_normalized = _summary("closed_loop_structural_blind_combined_v2_3")
    structural_unit_only = _summary("closed_loop_structural_blind_unit_adapter_v2_1")
    structural_port_only = _summary("closed_loop_structural_blind_label_guidance_v2_2")
    structural_holdout = _summary("closed_loop_structural_blind_holdout_combined_v3_0")

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
            "condition": "blind_structural_strict",
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
            "condition": "blind_combined_development",
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
        "interface_holdout_strict": _summary("closed_loop_structural_blind_holdout_strict_v3_0"),
        "rows": rows,
        "primary_combined": {
            "trajectories": value_loop["trajectory_count"]
            + structural_strict["trajectory_count"],
            "localization": value_loop["final_component_localization_count"]
            + structural_strict["final_component_localization_count"],
            "diagnosis": value_loop["final_full_diagnosis_count"]
            + structural_strict["final_full_diagnosis_count"],
            "recovery": value_loop["final_recovery_count"]
            + structural_strict["final_recovery_count"],
            "agent_calls": value_loop["total_agent_calls"]
            + structural_strict["total_agent_calls"],
            "candidate_simulations": value_loop["accepted_candidate_simulation_calls"]
            + structural_strict["accepted_candidate_simulation_calls"],
        },
        "interface_ablation": [
            {
                "condition": name,
                "trajectories": summary["trajectory_count"],
                "first_recovery": summary["first_iteration_recovery_count"],
                "final_recovery": summary["final_recovery_count"],
                "final_localization": summary["final_component_localization_count"],
                "final_diagnosis": summary["final_full_diagnosis_count"],
                "agent_calls": summary["total_agent_calls"],
                "candidate_simulations": summary[
                    "accepted_candidate_simulation_calls"
                ],
                "tokens": summary["recorded_total_tokens"],
            }
            for name, summary in [
                ("strict", structural_strict),
                ("unit_only", structural_unit_only),
                ("label_guidance", structural_port_only),
                ("unit_and_label_guidance", structural_normalized),
            ]
        ],
        "interface_holdout_combined": {
            "trajectories": structural_holdout["trajectory_count"],
            "first_recovery": structural_holdout["first_iteration_recovery_count"],
            "final_recovery": structural_holdout["final_recovery_count"],
            "final_localization": structural_holdout[
                "final_component_localization_count"
            ],
            "final_diagnosis": structural_holdout["final_full_diagnosis_count"],
            "agent_calls": structural_holdout["total_agent_calls"],
            "candidate_simulations": structural_holdout[
                "accepted_candidate_simulation_calls"
            ],
            "tokens": structural_holdout["recorded_total_tokens"],
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import unittest

from rf_repair.agent import RepairPatch, apply_restricted_patch, build_agent_input


class AgentBoundaryTest(unittest.TestCase):
    def test_input_contains_no_evaluator_ground_truth_fields(self) -> None:
        payload = build_agent_input(
            netlist="C1 in out 2p\n.end\n",
            spec={"target": 1},
            metrics={"simulation_converged": True},
        )
        self.assertIn("faulty_netlist", payload)
        self.assertNotIn("healthy_value", payload)
        self.assertNotIn("ground_truth", payload)

    def test_input_can_exclude_spice_metrics_for_llm_only_condition(self) -> None:
        payload = build_agent_input(
            netlist="C1 in out 2p\n.end\n",
            spec={"target": 1},
            metrics=None,
        )
        self.assertNotIn("measured_simulation", payload)

    def test_input_can_include_closed_loop_feedback(self) -> None:
        payload = build_agent_input(
            netlist="C1 in out 2p\n.end\n",
            spec={"target": 1},
            metrics={"simulation_converged": True},
            feedback_history=[{"iteration": 1, "outcome": "SPECIFICATION_VIOLATION"}],
        )
        self.assertIn("previous_attempts", payload)
        self.assertIn("SPECIFICATION_VIOLATION", payload)

    def test_applies_one_allowlisted_value_patch(self) -> None:
        patch = RepairPatch(operation="set_value", component="C1", proposed_value="1.5p")
        repaired = apply_restricted_patch("C1 in out 2p\n.end\n", patch)
        self.assertIn("C1 in out 1.5p", repaired)

    def test_rejects_non_numeric_spice_expression(self) -> None:
        patch = RepairPatch(
            operation="set_value", component="C1", proposed_value="{secret}"
        )
        with self.assertRaisesRegex(ValueError, "numeric token"):
            apply_restricted_patch("C1 in out 2p\n.end\n", patch)

    def test_rejects_noop_patch(self) -> None:
        patch = RepairPatch(operation="set_value", component="L2", proposed_value="4n")
        with self.assertRaisesRegex(ValueError, "must change"):
            apply_restricted_patch("L2 mid 0 4n\n.end\n", patch)


if __name__ == "__main__":
    unittest.main()

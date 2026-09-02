from __future__ import annotations

import unittest

from rf_repair.agent import (
    RepairPatch,
    StructuralRepairPatch,
    apply_restricted_patch,
    apply_structural_restricted_patch,
    build_agent_input,
)


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

    def test_restores_synthetic_open_component(self) -> None:
        patch = StructuralRepairPatch(
            operation="restore_component",
            component="C1",
            proposed_value="3.183p",
            proposed_z0=None,
        )
        repaired = apply_structural_restricted_patch(
            "RFAULTC1 n1 mid 1T\n.end\n", patch
        )
        self.assertIn("C1 n1 mid 3.183p", repaired)

    def test_restores_component_from_neutral_placeholder(self) -> None:
        patch = StructuralRepairPatch(
            operation="restore_component",
            component="L2",
            proposed_value="3.978873577n",
            proposed_z0=None,
        )
        repaired = apply_structural_restricted_patch(
            "RFAULT1 mid 0 1T\n.end\n",
            patch,
            neutral_fault_resistor_name="RFAULT1",
        )
        self.assertIn("L2 mid 0 3.978873577n", repaired)

    def test_wrong_component_is_not_corrected_by_neutral_placeholder(self) -> None:
        patch = StructuralRepairPatch(
            operation="restore_component",
            component="C1",
            proposed_value="3.183098862p",
            proposed_z0=None,
        )
        repaired = apply_structural_restricted_patch(
            "RFAULT1 mid 0 1T\n.end\n",
            patch,
            neutral_fault_resistor_name="RFAULT1",
        )
        self.assertIn("C1 mid 0 3.183098862p", repaired)
        self.assertNotIn("L2", repaired)

    def test_restores_component_after_unit_canonicalization(self) -> None:
        patch = StructuralRepairPatch(
            operation="restore_component",
            component="L2",
            proposed_value="3.978873577nH",
            proposed_z0=None,
        )
        repaired = apply_structural_restricted_patch(
            "RFAULTL2 mid 0 1T\n.end\n", patch, normalize_quantities=True
        )
        self.assertIn("L2 mid 0 3.978873577n", repaired)

    def test_repairs_port_impedance(self) -> None:
        patch = StructuralRepairPatch(
            operation="set_port_impedance",
            component="VPORT2",
            proposed_value=None,
            proposed_z0="50",
        )
        repaired = apply_structural_restricted_patch(
            "VPORT2 out 0 DC 0 AC 1 portnum 2 z0 100\n.end\n", patch
        )
        self.assertIn("z0 50", repaired)

    def test_rejects_cross_operation_fields(self) -> None:
        patch = StructuralRepairPatch(
            operation="restore_component",
            component="L2",
            proposed_value="3.9n",
            proposed_z0="50",
        )
        with self.assertRaisesRegex(ValueError, "inconsistent"):
            apply_structural_restricted_patch("RFAULTL2 mid 0 1T\n.end\n", patch)


if __name__ == "__main__":
    unittest.main()

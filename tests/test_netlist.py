from __future__ import annotations

import unittest

from rf_repair.netlist import (
    replace_component_with_resistor,
    normalize_spice_quantity,
    restore_component_from_fault_resistor,
    scale_spice_value,
    set_component_value,
    set_port_impedance,
)


class NetlistPatchTest(unittest.TestCase):
    def test_normalizes_bounded_engineering_units(self) -> None:
        self.assertEqual(
            normalize_spice_quantity("3.978873577nH", expected_unit="H"),
            "3.978873577n",
        )
        self.assertEqual(
            normalize_spice_quantity("3.978873577e-9 H", expected_unit="H"),
            "3.978873577e-9",
        )
        self.assertEqual(normalize_spice_quantity("50 ohm", expected_unit="ohm"), "50")

    def test_rejects_wrong_engineering_unit(self) -> None:
        with self.assertRaisesRegex(ValueError, "does not match"):
            normalize_spice_quantity("3.9pF", expected_unit="H")

    def test_scales_spice_value_and_preserves_suffix(self) -> None:
        self.assertEqual(scale_spice_value("3.2p", 2.0), "6.4p")
        self.assertEqual(scale_spice_value("10meg", 0.5), "5meg")

    def test_rejects_nonpositive_spice_scale(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive"):
            scale_spice_value("3.2p", 0.0)

    def test_replaces_exactly_bound_component(self) -> None:
        source = "C1 in out 1p\nC2 out 0 2p\n.end\n"
        patched = set_component_value(
            source, component="C1", expected_value="1p", new_value="2p"
        )
        self.assertIn("C1 in out 2p", patched)
        self.assertIn("C2 out 0 2p", patched)

    def test_rejects_healthy_value_mismatch(self) -> None:
        with self.assertRaisesRegex(ValueError, "healthy value mismatch"):
            set_component_value(
                "C1 in out 1p\n.end\n",
                component="C1",
                expected_value="9p",
                new_value="2p",
            )

    def test_rejects_missing_component(self) -> None:
        with self.assertRaisesRegex(ValueError, "found 0"):
            set_component_value(
                "C1 in out 1p\n.end\n",
                component="C9",
                expected_value="1p",
                new_value="2p",
            )

    def test_rejects_non_rlc_component(self) -> None:
        with self.assertRaisesRegex(ValueError, "only R, L, and C"):
            set_component_value(
                "V1 in 0 1\n.end\n",
                component="V1",
                expected_value="1",
                new_value="2",
            )

    def test_replaces_component_with_explicit_fault_resistor(self) -> None:
        patched = replace_component_with_resistor(
            "C1 in out 1p\n.end\n",
            component="C1",
            expected_value="1p",
            resistance="1T",
        )
        self.assertIn("RFAULTC1 in out 1T", patched)
        self.assertNotIn("C1 in out 1p", patched)

    def test_changes_exactly_bound_port_impedance(self) -> None:
        source = "VPORT2 out 0 DC 0 AC 1 portnum 2 z0 50\n.end\n"
        patched = set_port_impedance(
            source, port="VPORT2", expected_z0="50", new_z0="100"
        )
        self.assertIn("VPORT2 out 0 DC 0 AC 1 portnum 2 z0 100", patched)

    def test_rejects_port_impedance_mismatch(self) -> None:
        with self.assertRaisesRegex(ValueError, "healthy z0 mismatch"):
            set_port_impedance(
                "VPORT1 in 0 DC 0 AC 1 portnum 1 z0 50\n.end\n",
                port="VPORT1",
                expected_z0="75",
                new_z0="25",
            )

    def test_restores_component_from_bound_fault_resistor(self) -> None:
        restored = restore_component_from_fault_resistor(
            "RFAULTC1 in out 1T\n.end\n",
            component="C1",
            expected_resistance="1T",
            healthy_value="1p",
        )
        self.assertIn("C1 in out 1p", restored)
        self.assertNotIn("RFAULTC1", restored)

    def test_rejects_fault_resistance_mismatch(self) -> None:
        with self.assertRaisesRegex(ValueError, "fault resistance mismatch"):
            restore_component_from_fault_resistor(
                "RFAULTL2 mid 0 1m\n.end\n",
                component="L2",
                expected_resistance="1T",
                healthy_value="4n",
            )


if __name__ == "__main__":
    unittest.main()

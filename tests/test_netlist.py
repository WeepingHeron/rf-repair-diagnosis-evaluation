from __future__ import annotations

import unittest

from rf_repair.netlist import set_component_value


class NetlistPatchTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()


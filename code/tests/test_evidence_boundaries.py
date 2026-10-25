import json
import math
import unittest
from pathlib import Path

from rf_repair.netlist import normalize_spice_quantity, validate_component_quantity
from rf_repair.simulator import _measure
from rf_repair.validator import validate_bpf_metrics


class EvidenceBoundaryTests(unittest.TestCase):
    def test_explicit_farads_preserve_magnitude(self):
        self.assertEqual(normalize_spice_quantity("1 F", expected_unit="F"), "1")
        self.assertEqual(normalize_spice_quantity("3.183e-12 F", expected_unit="F"), "3.183e-12")
        self.assertEqual(normalize_spice_quantity("3f", expected_unit="F"), "3f")

    def test_explicit_wrong_dimension_is_rejected(self):
        for value in ["1 F", "1F", "3pF"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_spice_quantity(value, expected_unit="H")

    def test_numeric_domain_before_simulation(self):
        for value in ["0", "1e999", "1e-999", "1e-30", "nan", "{x}"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_component_quantity(value, "C1")
        self.assertAlmostEqual(validate_component_quantity("3.2e0p", "C1"), 3.2e-12)

    def test_missing_frequency_evidence_cannot_pass(self):
        spec = json.loads((Path(__file__).resolve().parents[1] / "specs/bpf_100mhz.json").read_text())
        rows = [{"frequency": f, "db(s_1_1)": -40., "db(s_2_1)": s, "db(s_2_2)": -40.}
                for f, s in [(70e6, -30.), (100e6, 0.), (140e6, -30.)]]
        with self.assertRaisesRegex(ValueError, "missing required"):
            _measure(rows, spec)

    def test_invalid_grid_is_rejected(self):
        spec = {"measurement_frequencies_hz": {"center": 100.}, "target_center_frequency_hz": 100.}
        row = {"frequency": 100., "db(s_1_1)": -40., "db(s_2_1)": 0., "db(s_2_2)": -40.}
        for rows in [[row, row], [{**row, "db(s_2_2)": math.nan}]]:
            with self.assertRaises(ValueError):
                _measure(rows, spec)

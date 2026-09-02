from __future__ import annotations

import copy
import unittest

from rf_repair.validator import validate_bpf_metrics


SPEC = {
    "constraints": {
        "center_frequency_relative_tolerance_max": 0.02,
        "s21_at_center_db_min": -0.25,
        "s11_at_center_db_max": -20.0,
        "s21_at_lower_passband_edge_db_min": -3.5,
        "s21_at_upper_passband_edge_db_min": -3.5,
        "s21_at_lower_stopband_db_max": -15.0,
        "s21_at_upper_stopband_db_max": -15.0,
    }
}

PASSING_METRICS = {
    "simulation_converged": True,
    "peak_frequency_relative_error": 0.0,
    "samples": {
        "center": {"s11_db": -40.0, "s21_db": 0.0},
        "lower_passband_edge": {"s21_db": -3.0},
        "upper_passband_edge": {"s21_db": -3.0},
        "lower_stopband": {"s21_db": -30.0},
        "upper_stopband": {"s21_db": -30.0},
    },
}


class ValidatorTest(unittest.TestCase):
    def test_passing_metrics_pass_all_constraints(self) -> None:
        verdict = validate_bpf_metrics(PASSING_METRICS, SPEC)
        self.assertEqual(verdict["verdict"], "PASS")
        self.assertTrue(all(check["passed"] for check in verdict["checks"]))

    def test_single_constraint_violation_fails(self) -> None:
        metrics = copy.deepcopy(PASSING_METRICS)
        metrics["samples"]["center"]["s21_db"] = -4.0
        verdict = validate_bpf_metrics(metrics, SPEC)
        self.assertEqual(verdict["verdict"], "FAIL")
        self.assertEqual(verdict["reason"], "SPECIFICATION_VIOLATION")

    def test_nonconvergence_fails_without_metrics(self) -> None:
        verdict = validate_bpf_metrics({"simulation_converged": False}, SPEC)
        self.assertEqual(
            verdict,
            {
                "verdict": "FAIL",
                "reason": "SIMULATION_NOT_CONVERGED",
                "checks": [],
            },
        )

    def test_optimistic_caller_verdict_is_ignored(self) -> None:
        metrics = copy.deepcopy(PASSING_METRICS)
        metrics["caller_verdict"] = "PASS"
        metrics["samples"]["upper_stopband"]["s21_db"] = -3.0
        verdict = validate_bpf_metrics(metrics, SPEC)
        self.assertEqual(verdict["verdict"], "FAIL")


if __name__ == "__main__":
    unittest.main()

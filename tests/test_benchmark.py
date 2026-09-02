from __future__ import annotations

import unittest

from rf_repair.benchmark import aggregate_runs


class BenchmarkAggregationTest(unittest.TestCase):
    def test_failures_remain_in_planned_denominator(self) -> None:
        rows = [
            {
                "fault_id": "f1",
                "api_completed": True,
                "structured_response": True,
                "component_correct": True,
                "diagnosis_correct": True,
                "patch_accepted": True,
                "simulation_converged": True,
                "specification_recovered": True,
                "proposed_component": "C1",
                "input_tokens": 10,
                "output_tokens": 5,
                "total_tokens": 15,
            },
            {
                "fault_id": "f1",
                "api_completed": False,
                "structured_response": False,
                "component_correct": False,
                "diagnosis_correct": False,
                "patch_accepted": False,
                "simulation_converged": False,
                "specification_recovered": False,
            },
        ]
        summary = aggregate_runs(rows, expected_attempts=3)
        self.assertEqual(summary["rates"]["specification_recovery_rate"], 1 / 3)
        self.assertEqual(
            summary["rates"]["recovery_rate_given_structured_response"], 1.0
        )
        self.assertFalse(summary["complete"])
        self.assertEqual(summary["usage"]["total_tokens"], 15)

    def test_component_consistency_uses_observed_structured_outputs(self) -> None:
        rows = [
            {"fault_id": "f1", "proposed_component": "C1"},
            {"fault_id": "f1", "proposed_component": "C1"},
            {"fault_id": "f1", "proposed_component": "L1"},
        ]
        summary = aggregate_runs(rows, expected_attempts=3)
        self.assertAlmostEqual(summary["rates"]["component_consistency_rate"], 2 / 3)

    def test_rejects_more_rows_than_planned(self) -> None:
        with self.assertRaisesRegex(ValueError, "exceed"):
            aggregate_runs([{}, {}], expected_attempts=1)


if __name__ == "__main__":
    unittest.main()

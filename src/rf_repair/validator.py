"""Fail-closed validation for the draft band-pass filter specification."""

from __future__ import annotations

import math
from typing import Any


def _finite_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field} must be finite")
    return result


def validate_bpf_metrics(
    metrics: dict[str, Any], spec: dict[str, Any]
) -> dict[str, Any]:
    """Return an auditable verdict without trusting caller-supplied pass fields."""

    if metrics.get("simulation_converged") is not True:
        return {
            "verdict": "FAIL",
            "reason": "SIMULATION_NOT_CONVERGED",
            "checks": [],
        }

    constraints = spec.get("constraints")
    samples = metrics.get("samples")
    if not isinstance(constraints, dict) or not isinstance(samples, dict):
        raise ValueError("spec constraints and metric samples must be objects")

    if "measurement_frequencies_hz" in spec:
        tolerance = _finite_number(spec.get("measurement_frequency_tolerance_hz", 1.0), "frequency tolerance")
        if tolerance < 0:
            raise ValueError("frequency tolerance must be nonnegative")
        for name, frequency in spec["measurement_frequencies_hz"].items():
            measured = _finite_number(samples[name].get("measured_frequency_hz"), name)
            if abs(measured - _finite_number(frequency, name)) > tolerance:
                return {"verdict": "FAIL", "reason": "MEASUREMENT_FREQUENCY_MISMATCH", "checks": []}

    definitions = [
        (
            "center_frequency_relative_tolerance",
            _finite_number(
                metrics.get("peak_frequency_relative_error"),
                "peak_frequency_relative_error",
            ),
            "max",
            "center_frequency_relative_tolerance_max",
        ),
        (
            "s21_at_center_db",
            _finite_number(samples["center"]["s21_db"], "center.s21_db"),
            "min",
            "s21_at_center_db_min",
        ),
        (
            "s11_at_center_db",
            _finite_number(samples["center"]["s11_db"], "center.s11_db"),
            "max",
            "s11_at_center_db_max",
        ),
        (
            "s21_at_lower_passband_edge_db",
            _finite_number(
                samples["lower_passband_edge"]["s21_db"],
                "lower_passband_edge.s21_db",
            ),
            "min",
            "s21_at_lower_passband_edge_db_min",
        ),
        (
            "s21_at_upper_passband_edge_db",
            _finite_number(
                samples["upper_passband_edge"]["s21_db"],
                "upper_passband_edge.s21_db",
            ),
            "min",
            "s21_at_upper_passband_edge_db_min",
        ),
        (
            "s21_at_lower_stopband_db",
            _finite_number(
                samples["lower_stopband"]["s21_db"],
                "lower_stopband.s21_db",
            ),
            "max",
            "s21_at_lower_stopband_db_max",
        ),
        (
            "s21_at_upper_stopband_db",
            _finite_number(
                samples["upper_stopband"]["s21_db"],
                "upper_stopband.s21_db",
            ),
            "max",
            "s21_at_upper_stopband_db_max",
        ),
    ]

    checks: list[dict[str, Any]] = []
    for name, measured, direction, constraint_name in definitions:
        threshold = _finite_number(constraints.get(constraint_name), constraint_name)
        passed = measured >= threshold if direction == "min" else measured <= threshold
        checks.append(
            {
                "name": name,
                "measured": measured,
                "direction": direction,
                "threshold": threshold,
                "passed": passed,
            }
        )

    return {
        "verdict": "PASS" if all(check["passed"] for check in checks) else "FAIL",
        "reason": "ALL_CONSTRAINTS_MET"
        if all(check["passed"] for check in checks)
        else "SPECIFICATION_VIOLATION",
        "checks": checks,
    }

"""Deterministic aggregation for repeated Agent repair experiments."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def aggregate_runs(rows: list[dict[str, Any]], *, expected_attempts: int) -> dict[str, Any]:
    """Aggregate all planned attempts, including failures, into fixed-denominator rates."""

    if len(rows) > expected_attempts:
        raise ValueError("observed rows exceed planned attempts")

    api_completed = sum(row.get("api_completed") is True for row in rows)
    api_response_received = sum(
        row.get("api_response_received", row.get("api_completed")) is True for row in rows
    )
    structured = sum(row.get("structured_response") is True for row in rows)
    component_correct = sum(row.get("component_correct") is True for row in rows)
    diagnosis_correct = sum(row.get("diagnosis_correct") is True for row in rows)
    patch_accepted = sum(row.get("patch_accepted") is True for row in rows)
    converged = sum(row.get("simulation_converged") is True for row in rows)
    recovered = sum(row.get("specification_recovered") is True for row in rows)

    by_fault: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        component = row.get("proposed_component")
        if isinstance(component, str):
            by_fault[row["fault_id"]].append(component)
    consistency_values: list[float] = []
    for components in by_fault.values():
        most_common_count = Counter(components).most_common(1)[0][1]
        consistency_values.append(most_common_count / len(components))

    usage = {
        "input_tokens": sum(int(row.get("input_tokens", 0)) for row in rows),
        "output_tokens": sum(int(row.get("output_tokens", 0)) for row in rows),
        "total_tokens": sum(int(row.get("total_tokens", 0)) for row in rows),
    }
    return {
        "planned_attempts": expected_attempts,
        "observed_attempts": len(rows),
        "complete": len(rows) == expected_attempts,
        "counts": {
            "api_response_received": api_response_received,
            "api_completed": api_completed,
            "structured_response": structured,
            "component_correct": component_correct,
            "diagnosis_correct": diagnosis_correct,
            "patch_accepted": patch_accepted,
            "simulation_converged": converged,
            "specification_recovered": recovered,
        },
        "rates": {
            "api_response_rate": _rate(api_response_received, expected_attempts),
            "api_completion_rate": _rate(api_completed, expected_attempts),
            "structured_response_rate": _rate(structured, expected_attempts),
            "component_localization_accuracy": _rate(component_correct, expected_attempts),
            "full_diagnosis_accuracy": _rate(diagnosis_correct, expected_attempts),
            "patch_acceptance_rate": _rate(patch_accepted, expected_attempts),
            "simulation_convergence_rate": _rate(converged, expected_attempts),
            "specification_recovery_rate": _rate(recovered, expected_attempts),
            "component_accuracy_given_structured_response": _rate(
                component_correct, structured
            ),
            "diagnosis_accuracy_given_structured_response": _rate(
                diagnosis_correct, structured
            ),
            "recovery_rate_given_structured_response": _rate(recovered, structured),
            "component_consistency_rate": (
                sum(consistency_values) / len(consistency_values)
                if consistency_values
                else 0.0
            ),
        },
        "usage": usage,
    }

"""Restricted netlist edits used by fault injection and future Agent patches."""

from __future__ import annotations


def set_component_value(
    source: str,
    *,
    component: str,
    expected_value: str,
    new_value: str,
) -> str:
    """Replace one four-token R/L/C element after exact healthy-value binding."""

    normalized_component = component.upper()
    if not normalized_component.startswith(("R", "L", "C")):
        raise ValueError("only R, L, and C components are supported in the MVP")

    matches = 0
    output: list[str] = []
    for line in source.splitlines():
        tokens = line.split()
        if tokens and tokens[0].upper() == normalized_component:
            matches += 1
            if len(tokens) != 4:
                raise ValueError(f"unsupported element syntax for {component}")
            if tokens[3] != expected_value:
                raise ValueError(
                    f"healthy value mismatch for {component}: "
                    f"expected {expected_value!r}, found {tokens[3]!r}"
                )
            tokens[3] = new_value
            line = " ".join(tokens)
        output.append(line)

    if matches != 1:
        raise ValueError(f"expected exactly one {component}, found {matches}")
    return "\n".join(output) + "\n"


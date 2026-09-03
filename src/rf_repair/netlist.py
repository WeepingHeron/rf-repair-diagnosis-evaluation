"""Restricted netlist edits used by fault injection and future Agent patches."""

from __future__ import annotations

import re


_SPICE_NUMBER = re.compile(
    r"^(?P<number>(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?)"
    r"(?P<suffix>meg|[tgkmunpf]?)$",
    re.IGNORECASE,
)
_ENGINEERING_QUANTITY = re.compile(
    r"^\s*(?P<number>(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?)"
    r"\s*(?P<prefix>meg|[tgkmunpf])?\s*(?P<unit>h|f|ohm|Ω)?\s*$",
    re.IGNORECASE,
)


def normalize_spice_quantity(value: str, *, expected_unit: str) -> str:
    """Canonicalize a bounded engineering quantity to one SPICE value token."""

    match = _ENGINEERING_QUANTITY.fullmatch(value)
    if match is None:
        raise ValueError("quantity is not a permitted engineering value")
    observed_unit = (match.group("unit") or "").lower()
    normalized_expected = expected_unit.lower()
    allowed_units = {
        "h": {"", "h"},
        "f": {"", "f"},
        "ohm": {"", "ohm", "ω"},
    }
    if normalized_expected not in allowed_units:
        raise ValueError(f"unsupported expected unit: {expected_unit}")
    if observed_unit not in allowed_units[normalized_expected]:
        raise ValueError("quantity unit does not match component type")
    prefix = (match.group("prefix") or "").lower()
    return f"{match.group('number')}{prefix}"


def scale_spice_value(value: str, multiplier: float) -> str:
    """Scale a simple positive SPICE value while preserving its SI suffix."""

    match = _SPICE_NUMBER.fullmatch(value)
    if match is None or multiplier <= 0:
        raise ValueError("value and multiplier must be positive simple SPICE numbers")
    scaled = float(match.group("number")) * multiplier
    if not scaled > 0:
        raise ValueError("scaled SPICE value must be positive")
    return f"{scaled:.12g}{match.group('suffix')}"


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


def replace_component_with_resistor(
    source: str,
    *,
    component: str,
    expected_value: str,
    resistance: str,
    fault_name: str | None = None,
) -> str:
    """Replace one bound R/L/C element with an explicit fault resistor."""

    normalized_component = component.upper()
    if not normalized_component.startswith(("R", "L", "C")):
        raise ValueError("only R, L, and C components are supported in the MVP")

    replacement_name = (fault_name or f"RFAULT{normalized_component}").upper()
    if not re.fullmatch(r"RFAULT[A-Z0-9_]+", replacement_name):
        raise ValueError("fault resistor name is not permitted")

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
            line = f"{replacement_name} {tokens[1]} {tokens[2]} {resistance}"
        output.append(line)

    if matches != 1:
        raise ValueError(f"expected exactly one {component}, found {matches}")
    return "\n".join(output) + "\n"


def set_port_impedance(
    source: str,
    *,
    port: str,
    expected_z0: str,
    new_z0: str,
) -> str:
    """Change one explicitly named RF port after exact reference-impedance binding."""

    normalized_port = port.upper()
    if not normalized_port.startswith("VPORT"):
        raise ValueError("only explicitly named VPORT sources are supported")

    matches = 0
    output: list[str] = []
    for line in source.splitlines():
        tokens = line.split()
        if tokens and tokens[0].upper() == normalized_port:
            matches += 1
            lowered = [token.lower() for token in tokens]
            if "portnum" not in lowered or "z0" not in lowered:
                raise ValueError(f"{port} is not an explicit RF port")
            z0_index = lowered.index("z0") + 1
            if z0_index >= len(tokens):
                raise ValueError(f"{port} has no z0 value")
            if tokens[z0_index] != expected_z0:
                raise ValueError(
                    f"healthy z0 mismatch for {port}: "
                    f"expected {expected_z0!r}, found {tokens[z0_index]!r}"
                )
            tokens[z0_index] = new_z0
            line = " ".join(tokens)
        output.append(line)

    if matches != 1:
        raise ValueError(f"expected exactly one {port}, found {matches}")
    return "\n".join(output) + "\n"


def restore_component_from_fault_resistor(
    source: str,
    *,
    component: str,
    expected_resistance: str,
    healthy_value: str,
    fault_name: str | None = None,
) -> str:
    """Restore one R/L/C component from the evaluator's open/short resistor."""

    normalized_component = component.upper()
    if not normalized_component.startswith(("R", "L", "C")):
        raise ValueError("only R, L, and C components are supported in the MVP")
    target_fault_name = (fault_name or f"RFAULT{normalized_component}").upper()
    if not re.fullmatch(r"RFAULT[A-Z0-9_]+", target_fault_name):
        raise ValueError("fault resistor name is not permitted")

    matches = 0
    output: list[str] = []
    for line in source.splitlines():
        tokens = line.split()
        if tokens and tokens[0].upper() == target_fault_name:
            matches += 1
            if len(tokens) != 4:
                raise ValueError(f"unsupported fault resistor syntax for {component}")
            if tokens[3] != expected_resistance:
                raise ValueError(
                    f"fault resistance mismatch for {component}: "
                    f"expected {expected_resistance!r}, found {tokens[3]!r}"
                )
            line = f"{normalized_component} {tokens[1]} {tokens[2]} {healthy_value}"
        output.append(line)

    if matches != 1:
        raise ValueError(f"expected exactly one {target_fault_name}, found {matches}")
    return "\n".join(output) + "\n"

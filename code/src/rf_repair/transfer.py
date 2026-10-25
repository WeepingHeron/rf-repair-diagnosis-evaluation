"""Pure contracts for the parameter-transfer, equal-budget value experiment."""
from __future__ import annotations

import json
import math
import random
from copy import deepcopy

from rf_repair.netlist import set_component_value, validate_component_quantity


INSTRUCTIONS = (
    "Diagnose a single component-value fault in an ideal passive lumped RF network. "
    "Use only the supplied netlist, specification and simulation evidence. "
    "Return one structured value edit on an existing reactive component. "
    "You may diagnose one component and repair another if justified. "
    "The healthy netlist and fault manifest are unavailable. "
    "Use positive finite SPICE numeric tokens. Inductance bounds are 1e-15 to 1e3 H; "
    "capacitance bounds are 1e-18 to 1 F. Do not change topology or RF ports. "
    "When previous attempts are supplied, use their measured outcomes. "
    "An external simulator decides success. Keep evidence concise."
)


def components(source: str) -> dict[str, str]:
    result = {}
    for line in source.splitlines():
        tokens = line.split()
        if tokens and tokens[0].startswith(("L", "C")):
            if len(tokens) != 4 or tokens[0] in result:
                raise ValueError("unsupported or duplicate reactive component")
            result[tokens[0]] = tokens[3]
    if not result:
        raise ValueError("no reactive components")
    return result


def apply_patch(source: str, component: str, value: str) -> str:
    values = components(source)
    if component not in values:
        raise ValueError("component is not in the faulty netlist")
    proposed = validate_component_quantity(value, component)
    if proposed == validate_component_quantity(values[component], component):
        raise ValueError("repair must change the component value")
    return set_component_value(source, component=component,
                               expected_value=values[component], new_value=value)


def response_schema(source: str) -> dict:
    component = {"type": "string", "enum": sorted(components(source))}
    def obj(properties):
        return {"type": "object", "properties": properties,
                "required": list(properties), "additionalProperties": False}
    return obj({
        "diagnosis": obj({"component": component,
                          "fault_type": {"type": "string", "enum": ["value_too_low", "value_too_high", "unknown_direction"]},
                          "evidence": {"type": "string", "maxLength": 400}}),
        "repair": obj({"component": component, "proposed_value": {"type": "string", "maxLength": 64}}),
    })


def agent_payload(source: str, spec: dict, metrics: dict, history: list, condition: str) -> dict:
    if condition not in {"feedback", "no_feedback"}:
        raise ValueError("unknown condition")
    payload = {"faulty_netlist": source, "target_specification": deepcopy(spec),
               "initial_simulation": deepcopy(metrics)}
    if condition == "feedback" and history:
        payload["previous_attempts"] = deepcopy(history)
    return payload


def make_cases() -> list[dict]:
    """All twelve fixed candidates; no result-dependent selection or retry."""
    rng = random.Random(20260906)
    cases = []
    selected = [[0, 3, 5], [1, 2, 4], [0, 2, 3], [1, 4, 5]]
    for design, (f0, bw) in enumerate([(83e6, .10), (117e6, .12), (149e6, .14), (173e6, .16)]):
        omega = 2 * math.pi * f0
        values = [50/(omega*bw), bw/(50*omega), 50*bw/(2*omega),
                  2/(50*omega*bw), 50/(omega*bw), bw/(50*omega)]
        types = ["L", "C", "L", "C", "L", "C"]
        names = [kind+str(n) for kind, n in zip(types, rng.sample(range(11, 98), 6))]
        nodes = ["N"+str(n) for n in rng.sample(range(101, 999), 5)]
        a,b,c,d,e = nodes
        edges = [(a,b), (b,c), (c,"0"), (c,"0"), (c,d), (d,e)]
        lines = [f"{name} {edge[0]} {edge[1]} {value:.12g}" for name,edge,value in zip(names,edges,values)]
        rng.shuffle(lines)
        source = ("* Passive two-port test network\n"
                  f"VPORT1 {a} 0 DC 0 AC 1 portnum 1 z0 50\n"
                  f"VPORT2 {e} 0 DC 0 AC 1 portnum 2 z0 50\n" + "\n".join(lines)
                  + f"\n.sp lin 2001 {f0*.5:.12g} {f0*1.5:.12g}\n.end\n")
        spec = {
            "target_center_frequency_hz": f0, "reference_impedance_ohm": 50.,
            "measurement_frequency_tolerance_hz": 1.,
            "measurement_frequencies_hz": {"center": f0, "lower_passband_edge": f0*(1-bw/2),
                "upper_passband_edge": f0*(1+bw/2), "lower_stopband": f0*.7, "upper_stopband": f0*1.4},
            "constraints": {"center_frequency_relative_tolerance_max": .02,
                "s21_at_center_db_min": -.25, "s11_at_center_db_max": -20.,
                "s21_at_lower_passband_edge_db_min": -4., "s21_at_upper_passband_edge_db_min": -4.,
                "s21_at_lower_stopband_db_max": -15., "s21_at_upper_stopband_db_max": -15.},
        }
        for j, index in enumerate(selected[design]):
            multiplier = [.62, 1.65, 2.3][(design+j)%3]
            component = names[index]; healthy_value = f"{values[index]:.12g}"
            faulty_value = f"{values[index]*multiplier:.12g}"
            faulty = set_component_value(source, component=component, expected_value=healthy_value, new_value=faulty_value)
            cases.append({"case_id": f"transfer_d{design+1}_f{j+1}", "design_id": f"design_{design+1}",
                          "healthy_netlist": source, "faulty_netlist": faulty, "spec": spec,
                          "component": component, "healthy_value": healthy_value, "faulty_value": faulty_value,
                          "multiplier": multiplier, "fault_type": "value_too_low" if multiplier<1 else "value_too_high"})
    return cases

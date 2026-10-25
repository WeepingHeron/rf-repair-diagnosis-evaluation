"""Synthetic finite-Q/parasitic/tolerance condition screen; no API or hidden tuning."""
from __future__ import annotations

import math
import random
from copy import deepcopy

from rf_repair.netlist import set_component_value, spice_value_si
from rf_repair.extensions import deterministic_candidates


SEED = 202609063
DESIGNS = [(103e6, .12), (139e6, .14), (167e6, .16), (211e6, .18)]
Q_LEVELS = [None, 200, 100, 50]
TOLERANCES = [0., .01, .03, .05]


def make_designs():
    rng = random.Random(SEED)
    out = []
    for i, (f0, bw) in enumerate(DESIGNS):
        w = 2 * math.pi * f0
        values = [50/(w*bw), bw/(50*w), 50*bw/(2*w), 2/(50*w*bw),
                  50/(w*bw), bw/(50*w)]
        names = [k+str(n) for k, n in zip('LCLCLC', rng.sample(range(101, 999), 6))]
        a,b,c,d,e = ['N'+str(n) for n in rng.sample(range(1001, 9999), 5)]
        edges = [(a,b),(b,c),(c,'0'),(c,'0'),(c,d),(d,e)]
        parts = [{'name': n, 'nodes': list(edge), 'nominal': v}
                 for n, edge, v in zip(names, edges, values)]
        order = list(range(6)); rng.shuffle(order)
        spec = {'target_center_frequency_hz': f0, 'reference_impedance_ohm': 50.,
                'measurement_frequency_tolerance_hz': 1.,
                'measurement_frequencies_hz': {'center': f0, 'lower_passband_edge': f0*(1-bw/2),
                    'upper_passband_edge': f0*(1+bw/2), 'lower_stopband': f0*.7, 'upper_stopband': f0*1.4},
                'constraints': {'center_frequency_relative_tolerance_max': .02,
                    's21_at_center_db_min': -.25, 's11_at_center_db_max': -20.,
                    's21_at_lower_passband_edge_db_min': -4., 's21_at_upper_passband_edge_db_min': -4.,
                    's21_at_lower_stopband_db_max': -15., 's21_at_upper_stopband_db_max': -15.}}
        out.append({'design_id': f'nonideal_d{i+1}', 'f0': f0, 'bw': bw,
                    'parts': parts, 'order': order, 'ports': [a,e], 'spec': spec,
                    'fault_indices': [[0,3],[1,2],[4,3],[5,2]][i]})
    return out


def make_conditions():
    out = []
    for d, design in enumerate(make_designs()):
        # Common draws across Q/parasitics and scaled tolerance levels allow paired inspection.
        rng = random.Random(SEED + 100 + d)
        draws = [[rng.uniform(-1,1) for _ in range(6)] for _ in range(3)]
        for q in Q_LEVELS:
            for parasitic in [False, True]:
                for tolerance in TOLERANCES:
                    for draw in range(1 if tolerance == 0 else 3):
                        deviations = [tolerance*x for x in draws[draw]]
                        cid = f"{design['design_id']}_q{q or 'inf'}_p{int(parasitic)}_t{int(tolerance*100)}_r{draw+1}"
                        out.append({'condition_id': cid, 'design': deepcopy(design), 'q': q,
                                    'parasitics': parasitic, 'tolerance': tolerance, 'draw': draw+1,
                                    'deviations': deviations})
    return out


def element_parameters(condition):
    """R is fixed at nominal f0/value, never recomputed after a fault or repair."""
    d = condition['design']; w = 2*math.pi*d['f0']; q = condition['q']
    if q is not None and (not math.isfinite(q) or q <= 0):
        raise ValueError('Q must be positive finite or None')
    result = []
    for part, deviation in zip(d['parts'], condition['deviations'], strict=True):
        if not math.isfinite(deviation) or abs(deviation) >= 1:
            raise ValueError('invalid component deviation')
        v = part['nominal']; is_l = part['name'][0] == 'L'
        resistance = (w*v/q if is_l else 1/(w*v*q)) if q is not None else 0.
        # Quantize exactly as the generated SPICE deck.
        result.append({**part, 'value': f'{v*(1+deviation):.12g}',
                       'resistance': float(f'{resistance:.12g}'),
                       'cp': 1e-13 if is_l and condition['parasitics'] else 0.,
                       'esl': 2e-10 if not is_l and condition['parasitics'] else 0.})
    return result


def render(condition, overrides=None, *, core_only=False):
    """Expanded simulation deck, or observed core connectivity for algebraic candidates."""
    overrides = overrides or {}; d = condition['design']; parts = element_parameters(condition)
    allowed = {p['name'] for p in parts}
    if not set(overrides) <= allowed:
        raise ValueError('only primary L/C values are editable; parasitics and ports are protected')
    lines = ['* Synthetic passive RF condition screen',
             f"VPORT1 {d['ports'][0]} 0 DC 0 AC 1 portnum 1 z0 50",
             f"VPORT2 {d['ports'][1]} 0 DC 0 AC 1 portnum 2 z0 50"]
    for index in d['order']:
        p = parts[index]; n = p['name']; a,b = p['nodes']; value = overrides.get(n, p['value'])
        spice_value_si(value)
        if not core_only:
            if p['cp']: lines.append(f'CP_{n} {a} {b} {p["cp"]:.12g}')
            if p['resistance']:
                lines.append(f'RS_{n} {a} XRS_{n} {p["resistance"]:.12g}'); a = f'XRS_{n}'
            if p['esl']:
                lines.append(f'LS_{n} {a} XLS_{n} {p["esl"]:.12g}'); a = f'XLS_{n}'
        lines.append(f'{n} {a} {b} {value}')
    lines += [f'.sp lin 2001 {d["f0"]*.5:.12g} {d["f0"]*1.5:.12g}', '.end']
    return '\n'.join(lines)+'\n'


def protected_patch(source, component, value, allowed):
    if component not in allowed: raise ValueError('protected component')
    tokens = [line.split() for line in source.splitlines()]
    old = [t[3] for t in tokens if len(t) == 4 and t[0] == component]
    if len(old) != 1: raise ValueError('ambiguous component')
    spice_value_si(value)
    if spice_value_si(old[0]) == spice_value_si(value): raise ValueError('no-op patch')
    return set_component_value(source, component=component, expected_value=old[0], new_value=value)


def public_candidates(core_source, frequency):
    """Topology-aware ideal-resonance baseline; no healthy values or fault labels."""
    return deterministic_candidates(core_source, frequency)


def analytic_magnitudes(condition, overrides, frequency):
    """Independent branch impedances + ABCD cascade, used only by the auditor."""
    w = 2*math.pi*frequency; z = []
    for p in element_parameters(condition):
        value = spice_value_si(overrides.get(p['name'], p['value']))
        if p['name'][0] == 'L':
            branch = p['resistance'] + 1j*w*value
            if p['cp']: branch = 1/(1/branch + 1j*w*p['cp'])
        else: branch = p['resistance'] + 1j*w*p['esl'] + 1/(1j*w*value)
        z.append(branch)
    left, shunt, right = z[0]+z[1], 1/z[2]+1/z[3], z[4]+z[5]
    a,b,c,d = 1+left*shunt, left+right+left*shunt*right, shunt, 1+shunt*right
    den = a+b/50+c*50+d
    return abs((a+b/50-c*50-d)/den), abs(2/den), abs((-a+b/50-c*50+d)/den)

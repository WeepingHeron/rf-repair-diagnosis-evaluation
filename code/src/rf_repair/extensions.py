"""New synthetic cases, public-input resonance hints, and matching validation."""
from __future__ import annotations
import math
import random
from collections import Counter
from rf_repair.netlist import set_component_value, validate_component_quantity
from rf_repair.transfer import agent_payload
from rf_repair.validator import validate_bpf_metrics


def resonance_hints(source: str, frequency: float) -> dict:
    """Use only observed connectivity and values; never a manifest or oracle."""
    if not math.isfinite(frequency) or frequency <= 0:
        raise ValueError('frequency must be positive and finite')
    parts, degree = [], Counter()
    for line in source.splitlines():
        t = line.split()
        if t and t[0][0] in 'LCRV':
            if len(t) < 4: raise ValueError('incomplete element')
            degree.update(t[1:3])
            if t[0][0] in 'LC':
                parts.append((t[0], frozenset(t[1:3]), validate_component_quantity(t[3], t[0])))
    pairs = []
    omega = 2 * math.pi * frequency
    for lname, ln, lv in parts:
        if not lname.startswith('L'): continue
        for cname, cn, cv in parts:
            if not cname.startswith('C'): continue
            shared = ln & cn
            topology = 'parallel' if ln == cn else 'series' if len(shared) == 1 and all(n != '0' and degree[n] == 2 for n in shared) else None
            if topology is None: continue
            fr = 1 / (2 * math.pi * math.sqrt(lv * cv))
            pairs.append({'inductor': lname, 'capacitor': cname, 'connection': topology,
                          'current_resonance_hz': fr, 'relative_detuning': abs(fr / frequency - 1),
                          'xl_at_target_ohm': omega * lv, 'xc_magnitude_at_target_ohm': 1 / (omega * cv),
                          'candidate_edits': [
                              {'component': lname, 'proposed_value': f'{1/(omega*omega*cv):.12g}'},
                              {'component': cname, 'proposed_value': f'{1/(omega*omega*lv):.12g}'}]})
    pairs.sort(key=lambda p: (p['inductor'], p['capacitor']))
    return {'assumption': 'Ideal series/parallel LC resonance. Either element may be changed while its partner stays fixed. These are algebraic candidates, not fault labels or guaranteed repairs.',
            'target_frequency_hz': frequency, 'pairs': pairs}


def deterministic_candidates(source: str, frequency: float) -> list[dict]:
    hints = resonance_hints(source, frequency)
    candidates = []
    for pair in sorted(hints['pairs'], key=lambda p: (-p['relative_detuning'], p['inductor'], p['capacitor'])):
        if pair['relative_detuning'] <= 1e-9: continue
        candidates.extend(sorted(pair['candidate_edits'], key=lambda c: c['component']))
    return candidates[:3]


def extension_payload(case: dict, history: list, condition: str) -> dict:
    if condition not in {'feedback', 'calculator_feedback', 'matching_one_shot'}:
        raise ValueError('unsupported condition')
    payload = agent_payload(case['faulty_netlist'], case['spec'], case['initial_metrics'], history, 'feedback')
    if condition == 'calculator_feedback':
        payload['resonance_calculations'] = resonance_hints(case['faulty_netlist'], case['spec']['target_center_frequency_hz'])
    return payload


def make_bpf_extension_cases() -> list[dict]:
    rng = random.Random(202609061)
    cases = []
    selected = [[2, 3], [0, 5], [2, 3], [1, 4]]
    for d, (f0, bw) in enumerate([(97e6, .11), (127e6, .13), (157e6, .15), (193e6, .17)]):
        w = 2 * math.pi * f0
        values = [50/(w*bw), bw/(50*w), 50*bw/(2*w), 2/(50*w*bw), 50/(w*bw), bw/(50*w)]
        names = [k+str(n) for k, n in zip('LCLCLC', rng.sample(range(101, 999), 6))]
        a,b,c,dn,e = ['N'+str(n) for n in rng.sample(range(1001, 9999), 5)]
        edges = [(a,b),(b,c),(c,'0'),(c,'0'),(c,dn),(dn,e)]
        lines = [f'{name} {edge[0]} {edge[1]} {value:.12g}' for name,edge,value in zip(names,edges,values)]
        rng.shuffle(lines)
        healthy = '* Passive two-port test network\n' + f'VPORT1 {a} 0 DC 0 AC 1 portnum 1 z0 50\nVPORT2 {e} 0 DC 0 AC 1 portnum 2 z0 50\n' + '\n'.join(lines) + f'\n.sp lin 2001 {f0*.5:.12g} {f0*1.5:.12g}\n.end\n'
        spec = {'target_center_frequency_hz': f0, 'reference_impedance_ohm': 50., 'measurement_frequency_tolerance_hz': 1.,
                'measurement_frequencies_hz': {'center': f0, 'lower_passband_edge': f0*(1-bw/2), 'upper_passband_edge': f0*(1+bw/2), 'lower_stopband': f0*.7, 'upper_stopband': f0*1.4},
                'constraints': {'center_frequency_relative_tolerance_max': .02, 's21_at_center_db_min': -.25, 's11_at_center_db_max': -20.,
                                's21_at_lower_passband_edge_db_min': -4., 's21_at_upper_passband_edge_db_min': -4., 's21_at_lower_stopband_db_max': -15., 's21_at_upper_stopband_db_max': -15.}}
        for j,index in enumerate(selected[d]):
            mult = [.54, 1.85][(d+j)%2]
            name = names[index]; original = f'{values[index]:.12g}'; faulty = f'{values[index]*mult:.12g}'
            source = set_component_value(healthy, component=name, expected_value=original, new_value=faulty)
            cases.append({'case_id': f'calc_d{d+1}_f{j+1}', 'design_id': f'calc_design_{d+1}', 'family': 'bpf',
                          'healthy_netlist': healthy, 'faulty_netlist': source, 'spec': spec,
                          'component': name, 'healthy_value': original, 'faulty_value': faulty, 'multiplier': mult,
                          'fault_type': 'value_too_low' if mult<1 else 'value_too_high'})
    return cases


def make_matching_cases() -> list[dict]:
    rng = random.Random(202609062); cases = []
    for d, (f0, ratio) in enumerate([(91e6,2), (131e6,3), (181e6,4), (223e6,5)]):
        rs, rl = 50., 50.*ratio
        w = 2*math.pi*f0; loaded_q = math.sqrt(ratio-1)
        lv, cv = loaded_q*rs/w, loaded_q/(w*rl)
        lname, cname = ['L'+str(rng.randrange(101,999)), 'C'+str(rng.randrange(101,999))]
        a,b = ['N'+str(n) for n in rng.sample(range(1001,9999),2)]
        healthy = f'* Passive impedance transformer\nVPORT1 {a} 0 DC 0 AC 1 portnum 1 z0 {rs:g}\nVPORT2 {b} 0 DC 0 AC 1 portnum 2 z0 {rl:g}\n{lname} {a} {b} {lv:.12g}\n{cname} {b} 0 {cv:.12g}\n.sp lin 2001 {f0*.5:.12g} {f0*1.5:.12g}\n.end\n'
        spec = {'target_center_frequency_hz': f0, 'source_impedance_ohm': rs, 'load_impedance_ohm': rl,
                'measurement_frequency_tolerance_hz': 1.,
                'measurement_frequencies_hz': {'center': f0, 'lower_edge': .9*f0, 'upper_edge': 1.1*f0},
                'constraints': {'center': {'s11_db_max': -20., 's21_db_min': -.25},
                                'lower_edge': {'s11_db_max': -12., 's21_db_min': -.5},
                                'upper_edge': {'s11_db_max': -12., 's21_db_min': -.5}}}
        for j,(name,value) in enumerate([(lname,lv),(cname,cv)]):
            mult = [.55,1.8][(d+j)%2]; original=f'{value:.12g}'; faulty=f'{value*mult:.12g}'
            cases.append({'case_id': f'match_d{d+1}_f{j+1}', 'design_id': f'match_design_{d+1}', 'family': 'matching',
                          'healthy_netlist': healthy, 'faulty_netlist': set_component_value(healthy, component=name, expected_value=original, new_value=faulty),
                          'spec': spec, 'component': name, 'healthy_value': original, 'faulty_value': faulty, 'multiplier': mult,
                          'fault_type': 'value_too_low' if mult<1 else 'value_too_high'})
    return cases


def validate_extension(metrics: dict, spec: dict, family: str) -> dict:
    if family == 'bpf': return validate_bpf_metrics(metrics, spec)
    if family != 'matching': raise ValueError('unsupported family')
    if metrics.get('simulation_converged') is not True:
        return {'verdict': 'FAIL', 'reason': 'SIMULATION_NOT_CONVERGED', 'checks': []}
    checks = []
    for name, frequency in spec['measurement_frequencies_hz'].items():
        sample = metrics['samples'][name]
        measured = sample.get('measured_frequency_hz')
        if isinstance(measured, bool) or not isinstance(measured, (float,int)) or not math.isfinite(measured) or abs(measured-frequency)>spec['measurement_frequency_tolerance_hz']:
            return {'verdict': 'FAIL', 'reason': 'MEASUREMENT_FREQUENCY_MISMATCH', 'checks': []}
        for key, bound in spec['constraints'][name].items():
            field, direction = key.rsplit('_',1); value = sample.get(field)
            finite = isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)
            passed = finite and (value<=bound if direction=='max' else value>=bound)
            checks.append({'name': name+'.'+key, 'measured': value, 'threshold': bound, 'passed': passed})
    passed = bool(checks) and all(c['passed'] for c in checks)
    return {'verdict': 'PASS' if passed else 'FAIL', 'reason': 'ALL_CONSTRAINTS_MET' if passed else 'SPECIFICATION_VIOLATION', 'checks': checks}

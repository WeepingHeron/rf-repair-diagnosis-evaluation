"""Frozen-gate sensitivity study; synthetic nuisances, no LLM or threshold tuning."""
from copy import deepcopy
import hashlib
import math
import random
from rf_repair import lossy, reference

CHANNELS = ['s11_db', 's21_db', 's22_db']


def scenarios():
    out = []
    def add(family, level, draw=0, **changes):
        out.append(dict(scenario_id=f'{family}_{level}_{draw}', family=family, level=level,
                        draw=draw, noise_sigma_db=0., offset_db=0., frequency_fraction=0.,
                        lc_drift_fraction=0., rs_fraction=0., parasitic_fraction=0.) | changes)
    add('baseline', '0')
    for sigma in [.005, .01, .02, .05, .1]:
        for draw in range(10):
            add('noise', str(sigma), draw, noise_sigma_db=sigma)
    for value in [-.1, -.05, -.02, -.01, .01, .02, .05, .1]:
        add('offset', str(value), offset_db=value)
    for value in [-.005, -.001, -.0005, -.0001, .0001, .0005, .001, .005]:
        add('frequency', str(value), frequency_fraction=value)
    for value in [-.01, -.005, -.001, .001, .005, .01]:
        add('lc_drift', str(value), lc_drift_fraction=value)
    for family, key in [('rs_model', 'rs_fraction'), ('parasitic_model', 'parasitic_fraction')]:
        for value in [-.5, -.25, -.1, .1, .25, .5]:
            add(family, str(value), **{key: value})
    for sign in [-1, 1]:
        for draw in range(10):
            add('combined', str(sign), draw, noise_sigma_db=.01, lc_drift_fraction=sign*.001,
                rs_fraction=sign*.1, parasitic_fraction=sign*.1)
    assert len(out) == 105 and len({s['scenario_id'] for s in out}) == 105
    return out


def cohort(cases):
    out = []
    seen = set()
    for c in cases:
        out.append(dict(cohort_id=c['case_id'], design_id=c['design_id'], kind='fault',
                        source_case_id=c['case_id'], expected_component=c['component'],
                        expected_direction=c['fault_type'], current_netlist=c['faulty_netlist'],
                        historical_netlist=c['healthy_netlist'], public_model=c['public_model']))
        if c['design_id'] not in seen:
            seen.add(c['design_id'])
            out.append(dict(cohort_id=c['design_id']+'_control', design_id=c['design_id'], kind='control',
                            source_case_id=c['case_id'], expected_component=None, expected_direction=None,
                            current_netlist=c['healthy_netlist'], historical_netlist=c['healthy_netlist'],
                            public_model=c['public_model']))
    return sorted(out, key=lambda c: c['cohort_id'])


def noise_vector(design_id, draw):
    seed = int(hashlib.sha256(f'robustness_v1|{design_id}|{draw}'.encode()).hexdigest()[:16], 16)
    rng = random.Random(seed)
    return seed, [rng.gauss(0., 1.) for _ in range(27)]


def measurement_inputs(item, scenario):
    """Evaluator makes a physical history; estimator only receives assumed model/current values/spectrum."""
    for key in ['noise_sigma_db', 'offset_db', 'frequency_fraction', 'lc_drift_fraction', 'rs_fraction', 'parasitic_fraction']:
        if not math.isfinite(scenario[key]):
            raise ValueError('nonfinite perturbation')
    if scenario['noise_sigma_db'] < 0 or any(scenario[k] <= -1 for k in
            ['frequency_fraction', 'lc_drift_fraction', 'rs_fraction', 'parasitic_fraction']):
        raise ValueError('invalid perturbation')
    assumed = deepcopy(item['public_model'])
    physical = deepcopy(assumed)
    for key in ['inductor_rs_ohm', 'capacitor_rs_ohm']:
        physical['model'][key] *= 1 + scenario['rs_fraction']
    for key in ['inductor_cp_f', 'capacitor_esl_h']:
        physical['model'][key] *= 1 + scenario['parasitic_fraction']
    actual_f0 = assumed['frequency_hz'] * (1 + scenario['frequency_fraction'])
    physical['frequency_hz'] = actual_f0
    values = lossy.observed_values(item['historical_netlist'], assumed)
    historical_source = lossy.render(physical, values)
    nominal_freq = [assumed['frequency_hz'] * r for r in reference.RATIOS]
    actual_freq = [actual_f0 * r for r in reference.RATIOS]
    clean = lossy.curve(physical, values, actual_freq)
    seed, noise = noise_vector(item['design_id'], scenario['draw'])
    samples = [dict(frequency_hz=f, **{k: round(row[j+1] + scenario['offset_db'] +
                    scenario['noise_sigma_db'] * noise[i*3+j], 2) for j, k in enumerate(CHANNELS)})
               for i, (f, row) in enumerate(zip(nominal_freq, clean, strict=True))]
    current = lossy.observed_values(item['current_netlist'], assumed)
    if scenario['lc_drift_fraction']:
        current = {k: f'{float(v)*(1+scenario["lc_drift_fraction"]):.12g}' for k, v in current.items()}
    source = lossy.render(assumed, current)
    spectrum = dict(quantization_db=.01, origin='Synthetic ABCD sensitivity input, independently checked with native SPICE', samples=samples)
    return dict(estimator_input=dict(source=source, public=assumed, reference=spectrum),
                generation=dict(physical_model=physical, historical_source=historical_source,
                    actual_frequencies_hz=actual_freq, clean_curve=clean, noise_seed=seed, standard_normal=noise))


def score(diagnosis, item):
    abstained = diagnosis['component'] == 'unknown'
    if item['kind'] == 'control':
        return dict(correct=False, abstained=abstained, wrong_diagnosis=False, false_alarm=not abstained)
    correct = diagnosis['component'] == item['expected_component'] and diagnosis['fault_type'] == item['expected_direction']
    return dict(correct=correct, abstained=abstained, wrong_diagnosis=not abstained and not correct, false_alarm=False)


def aggregate(rows):
    out = {}
    for r in rows:
        key = r['family'] + '/' + r['level']
        g = out.setdefault(key, dict(family=r['family'], level=r['level'], faults=0, controls=0,
                    correct=0, fault_abstained=0, wrong_diagnosis=0, control_abstained=0, false_alarm=0))
        if r['kind'] == 'fault':
            g['faults'] += 1
            for k in ['correct', 'wrong_diagnosis']: g[k] += r['score'][k]
            g['fault_abstained'] += r['score']['abstained']
        else:
            g['controls'] += 1
            g['control_abstained'] += r['score']['abstained']
            g['false_alarm'] += r['score']['false_alarm']
    return out

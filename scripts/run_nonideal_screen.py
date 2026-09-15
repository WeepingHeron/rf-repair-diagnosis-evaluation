"""Freeze and run an offline condition screen without changing earlier protocols."""
from __future__ import annotations
import argparse
import fcntl
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from rf_repair.nonideal import make_conditions, render, element_parameters, protected_patch, public_candidates
from rf_repair.simulator import run_sparameter_simulation
from rf_repair.validator import validate_bpf_metrics

def sha(data): return hashlib.sha256(data).hexdigest()
def read(path): return json.loads(path.read_text())
def write_once(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as f: json.dump(value, f, indent=2); f.write('\n')

def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    output = ROOT/'build/experiments/nonideal_screen_v1'; output.mkdir(parents=True, exist_ok=True)
    lock = (output/'.run.lock').open('a'); fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
    pp = ROOT/'experiments/nonideal_screen_v1.json'
    if not pp.exists():
        conditions = make_conditions()
        manifest = ROOT/'faults/holdout/nonideal_screen_v1.json'
        write_once(manifest, {'conditions': conditions})
        files = ['src/rf_repair/nonideal.py', 'src/rf_repair/extensions.py', 'src/rf_repair/transfer.py',
                 'src/rf_repair/netlist.py', 'src/rf_repair/simulator.py', 'src/rf_repair/validator.py',
                 'scripts/run_nonideal_screen.py', str(manifest.relative_to(ROOT))]
        write_once(pp, {'experiment_id': 'nonideal_screen_v1', 'frozen_at_utc': datetime.now(timezone.utc).isoformat(),
            'manifest': str(manifest.relative_to(ROOT)), 'condition_count': len(conditions), 'faults_per_condition': 2,
            'max_baseline_candidates': 3, 'max_api_calls': 0, 'selection': 'All predefined conditions retained, including ineligible ones',
            'eligibility': 'healthy PASS and faulty FAIL and exact single-component oracle PASS',
            'specification': 'Unchanged relative BPF limits from v4/v5; no post-result relaxation',
            'model': 'Synthetic fixed-R finite nominal Q; inductor Cp=0/0.1pF, capacitor ESL=0/0.2nH; not vendor or measured data',
            'tolerance': '0/1/3/5 percent; 3 paired uniform draws for nonzero levels, all six main L/C affected',
            'repair': 'One main L/C edit on original faulty deck; all R/ESL/Cp/ports fixed; oracle restores pre-fault toleranced value',
            'baseline': 'Observed primary connectivity and values only; ideal-resonance candidates, largest detuning then name, at most three',
            'file_sha256': {p: sha((ROOT/p).read_bytes()) for p in files}})
    protocol = read(pp)
    for p,h in protocol['file_sha256'].items():
        if sha((ROOT/p).read_bytes()) != h: raise ValueError('frozen input changed: '+p)
    if args.prepare_only:
        print(json.dumps({'frozen_conditions': protocol['condition_count'], 'api_calls': 0})); return
    env = output/'environment.json'
    if not env.exists():
        version = subprocess.run(['ngspice','--version'], capture_output=True, text=True, check=True)
        write_once(env, {'python': platform.python_version(), 'ngspice': version.stdout,
                        'protocol_sha256': sha(pp.read_bytes()), 'started_at_utc': datetime.now(timezone.utc).isoformat()})
    if read(env)['protocol_sha256'] != sha(pp.read_bytes()): raise ValueError('protocol drift')
    conditions = read(ROOT/protocol['manifest'])['conditions']
    def simulate(folder, source, spec, label, overrides):
        path = folder/f'{label}.json'
        if path.exists():
            record = read(path)
            if record['source_sha256'] != sha(source.encode()) or record['overrides'] != overrides:
                raise ValueError('checkpoint mismatch')
            if (folder/f'{label}.cir').read_text() != source: raise ValueError('source checkpoint drift')
            return record
        circuit = folder/f'{label}.cir'; circuit.parent.mkdir(parents=True, exist_ok=True); circuit.write_text(source)
        metrics = run_sparameter_simulation(circuit, spec, folder/label, cwd=ROOT)
        record = {'source_sha256': sha(source.encode()), 'overrides': overrides, 'metrics': metrics,
                  'verdict': validate_bpf_metrics(metrics, spec)}
        write_once(path, record); return record
    for index, condition in enumerate(conditions):
        folder = output/condition['condition_id']; final = folder/'final.json'
        if final.exists(): continue
        d = condition['design']; spec = d['spec']; healthy = render(condition)
        h = simulate(folder, healthy, spec, 'healthy', {})
        parts = element_parameters(condition); allowed = [p['name'] for p in parts]; faults = []
        for j, part_index in enumerate(d['fault_indices']):
            p = parts[part_index]; component = p['name']; multiplier = [.55, 1.8][j]
            overrides = {component: f'{float(p["value"])*multiplier:.12g}'}
            source = render(condition, overrides)
            f = simulate(folder, source, spec, f'fault_{j+1}', overrides)
            oracle = protected_patch(source, component, p['value'], allowed)
            if oracle != healthy: raise ValueError('oracle failed exact recovery')
            o = simulate(folder, oracle, spec, f'oracle_{j+1}', {})
            eligible = h['verdict']['verdict']=='PASS' and f['verdict']['verdict']=='FAIL' and o['verdict']['verdict']=='PASS'
            candidates = []
            if eligible:
                core = render(condition, overrides, core_only=True)
                for k, proposal in enumerate(public_candidates(core, d['f0']), 1):
                    changed = protected_patch(source, proposal['component'], proposal['proposed_value'], allowed)
                    replacement = {**overrides, proposal['component']: proposal['proposed_value']}
                    result = simulate(folder, changed, spec, f'baseline_{j+1}_{k}', replacement)
                    candidates.append({'proposal': proposal, 'evidence': f'baseline_{j+1}_{k}.json',
                                       'recovered': result['verdict']['verdict']=='PASS'})
                    if candidates[-1]['recovered']: break
            faults.append({'fault_id': j+1, 'component': component, 'multiplier': multiplier,
                           'eligible': eligible, 'baseline_attempts': candidates,
                           'baseline_recovered': any(x['recovered'] for x in candidates) if eligible else None})
        write_once(final, {'condition_id': condition['condition_id'], 'healthy_pass': h['verdict']['verdict']=='PASS', 'faults': faults})
        if (index+1)%20 == 0: print(json.dumps({'conditions_complete': index+1, 'total': len(conditions)}), flush=True)
    finals = [read(output/c['condition_id']/'final.json') for c in conditions]
    summary = {'complete': len(finals)==protocol['condition_count'], 'conditions': len(finals),
               'healthy_pass': sum(f['healthy_pass'] for f in finals),
               'fault_instances': sum(len(f['faults']) for f in finals),
               'eligible_faults': sum(r['eligible'] for f in finals for r in f['faults']),
               'baseline_recovered': sum(r['baseline_recovered'] is True for f in finals for r in f['faults']),
               'baseline_simulations': sum(len(r['baseline_attempts']) for f in finals for r in f['faults']), 'api_calls': 0}
    (output/'summary.json').write_text(json.dumps(summary, indent=2)+'\n'); print(json.dumps(summary))

if __name__ == '__main__': main()

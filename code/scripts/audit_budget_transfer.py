"""Offline provenance and fresh-SPICE audit of completed v4 iterations."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from rf_repair.transfer import INSTRUCTIONS, apply_patch
from rf_repair.simulator import run_sparameter_simulation


def read(path):
    return json.loads(path.read_text())


def sha(data):
    return hashlib.sha256(data).hexdigest()


def passes(metrics, spec):
    if not metrics['simulation_converged']:
        return False
    c, s = spec['constraints'], metrics['samples']
    return all([
        metrics['peak_frequency_relative_error'] <= c['center_frequency_relative_tolerance_max'],
        s['center']['s21_db'] >= c['s21_at_center_db_min'],
        s['center']['s11_db'] <= c['s11_at_center_db_max'],
        *[s[n]['s21_db'] >= c[f's21_at_{n}_db_min'] for n in ['lower_passband_edge', 'upper_passband_edge']],
        *[s[n]['s21_db'] <= c[f's21_at_{n}_db_max'] for n in ['lower_stopband', 'upper_stopband']],
    ])


def main():
    protocol_path = ROOT / 'experiments/budget_transfer_v4.json'
    protocol = read(protocol_path)
    for name, expected in protocol['file_sha256'].items():
        assert sha((ROOT / name).read_bytes()) == expected, name
    cases = {c['case_id']: c for c in read(ROOT / protocol['manifest'])['cases']}
    output = ROOT / 'build/experiments/budget_transfer_v4'
    audit = ROOT / 'build/budget_transfer_v4_audit'
    audit.mkdir(parents=True, exist_ok=True)
    ids, count, simulated = set(), 0, 0
    for path in sorted(output.glob('*/*/repeat_*/iteration_*.json')):
        row = read(path)
        case = cases[row['case_id']]
        i = row['iteration']
        request = read(path.parent / f'request_{i}.json')
        payload = request['input']
        assert request['protocol_sha256'] == sha(protocol_path.read_bytes())
        assert request['instructions_sha256'] == sha(INSTRUCTIONS.encode())
        assert request['input_sha256'] == sha(json.dumps(payload, sort_keys=True).encode())
        base = {'faulty_netlist': case['faulty_netlist'], 'target_specification': case['spec'],
                'initial_simulation': case['initial_metrics']}
        if row['condition'] == 'feedback' and i > 1:
            history = []
            for previous in range(1, i):
                old = read(path.parent / f'iteration_{previous}.json')
                history.append({k: old[k] for k in ['proposal', 'outcome', 'rejection', 'metrics', 'verdict'] if k in old})
            base['previous_attempts'] = history
        assert payload == base, str(path)
        if 'response_id' in row:
            assert row['response_id'] not in ids
            ids.add(row['response_id'])
            assert sha(row['output_text'].encode()) == row['output_text_sha256']
            checkpoint = read(path.parent / f'response_{i}.json')
            for key in ['response_id', 'output_text', 'usage', 'response_status']:
                assert checkpoint[key] == row[key]
        if row['simulation_called']:
            proposal = row['proposal']['repair']
            repaired = apply_patch(case['faulty_netlist'], proposal['component'], proposal['proposed_value'])
            source_path = path.parent / f'repaired_{i}.cir'
            assert source_path.read_text() == repaired
            assert sha(repaired.encode()) == row['repaired_sha256']
            fresh = run_sparameter_simulation(source_path, case['spec'], audit / path.parent.relative_to(output) / f'iteration_{i}', cwd=ROOT)
            assert fresh == row['metrics'], str(path)
            assert passes(fresh, case['spec']) == row['recovered']
            simulated += 1
        count += 1
    result = {'audited_iterations': count, 'unique_response_ids': len(ids),
              'fresh_candidate_simulations': simulated, 'issues': []}
    (audit / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()

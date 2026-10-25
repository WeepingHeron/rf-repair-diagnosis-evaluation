"""Screen all predefined cases and freeze the API experiment contract."""
import hashlib
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from rf_repair.transfer import make_cases, apply_patch
from rf_repair.simulator import run_sparameter_simulation
from rf_repair.validator import validate_bpf_metrics

def main():
    protocol_path = ROOT/'experiments/budget_transfer_v4.json'
    if protocol_path.exists():
        raise RuntimeError('Frozen protocol already exists; never overwrite a started experiment')
    cases = make_cases(); evidence = []
    for case in cases:
        folder = ROOT/'build/budget_transfer_prescreen'/case['case_id'];folder.mkdir(parents=True, exist_ok=True)
        row = {'case_id': case['case_id']}
        oracle = apply_patch(case['faulty_netlist'], case['component'], case['healthy_value'])
        assert oracle == case['healthy_netlist']
        for name, source in [('healthy',case['healthy_netlist']),('faulty',case['faulty_netlist']),('oracle',oracle)]:
            path = folder/f'{name}.cir';path.write_text(source)
            metrics = run_sparameter_simulation(path, case['spec'], folder/name, cwd=ROOT)
            verdict = validate_bpf_metrics(metrics, case['spec'])
            row[name] = verdict['verdict']
            if name=='faulty': case['initial_metrics'] = metrics
        evidence.append(row)
    assert all(r['healthy']=='PASS' and r['faulty']=='FAIL' and r['oracle']=='PASS' for r in evidence), evidence
    manifest = ROOT/'faults/holdout/budget_transfer_v4.json'
    manifest.write_text(json.dumps({'selection':'All 12 predefined candidates retained', 'cases':cases},indent=2)+'\n')
    files = ['src/rf_repair/transfer.py','src/rf_repair/netlist.py','src/rf_repair/simulator.py',
             'src/rf_repair/validator.py','scripts/run_budget_transfer.py','scripts/prepare_budget_transfer.py',
             str(manifest.relative_to(ROOT))]
    protocol = {'experiment_id':'budget_transfer_v4','frozen_at_utc':datetime.now(timezone.utc).isoformat(),
        'model':'gpt-5.6-luna','reasoning_effort':'low','max_output_tokens':2000,
        'repetitions':3,'max_iterations':3,'case_count':12,'design_count':4,
        'conditions':['no_feedback','feedback'],'max_api_calls':216,'max_input_chars':40000,
        'manifest':str(manifest.relative_to(ROOT)), 'stop_on_success':True,'automatic_api_retries':0,
        'sampling_order':'case, repetition, alternating condition order',
        'api_prices_usd_per_million_tokens':{'input':.20,'cached_input':.02,'output':1.20},
        'price_source':'https://developers.openai.com/api/docs/models/gpt-5.6-luna',
        'claim_boundary':'Same Butterworth topology with unseen parameters and renamed elements; not unseen-topology or hardware evidence.',
        'file_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in files}}
    protocol_path.write_text(json.dumps(protocol,indent=2)+'\n')
    (ROOT/'build/budget_transfer_prescreen/summary.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps({'screened':len(evidence),'healthy_pass':12,'faulty_fail':12,'oracle_pass':12,'max_calls':216}))

if __name__=='__main__': main()

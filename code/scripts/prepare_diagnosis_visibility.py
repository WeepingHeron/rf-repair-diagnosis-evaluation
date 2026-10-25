"""Prescreen all new cases, freeze visibility protocol before live diagnosis."""
import json
import sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from rf_repair.diagnosis import cases,CONDITIONS
from rf_repair.lossy import patch,numerical_search
from rf_repair.simulator import run_sparameter_simulation
from rf_repair.validator import validate_bpf_metrics
from run_budget_transfer import write_once,digest

def simulate(folder,label,source,spec):
    folder.mkdir(parents=True,exist_ok=True);p=folder/f'{label}.cir';p.write_text(source)
    m=run_sparameter_simulation(p,spec,folder/label,cwd=ROOT);v=validate_bpf_metrics(m,spec)
    write_once(folder/f'{label}.json',{'source_sha256':digest(source.encode()),'metrics':m,'verdict':v})
    return m,v

def main():
    pp=ROOT/'experiments/diagnosis_visibility_v1.json'
    if pp.exists():raise RuntimeError('refuse to overwrite frozen experiment')
    cs=cases();evidence=[]
    for c in cs:
        folder=ROOT/'build/diagnosis_visibility_v1_prescreen'/c['case_id'];row={'case_id':c['case_id']}
        oracle=patch(c['faulty_netlist'],c['public_model'],c['component'],c['healthy_value']);assert oracle==c['healthy_netlist']
        for label,source in [('healthy',c['healthy_netlist']),('faulty',c['faulty_netlist']),('oracle',oracle)]:
            m,v=simulate(folder,label,source,c['spec']);row[label]=v['verdict']
            if label=='faulty':c['initial_metrics']=m
        evidence.append(row)
    write_once(ROOT/'build/diagnosis_visibility_v1_prescreen/summary.json',evidence)
    if not all(r['healthy']=='PASS' and r['faulty']=='FAIL' and r['oracle']=='PASS' for r in evidence):
        write_once(ROOT/'build/diagnosis_visibility_v1_prescreen/ineligible_cases.json',cs)
        raise RuntimeError('predefined case ineligible; stop without retuning')
    for c in cs:
        search=numerical_search(c['faulty_netlist'],c['public_model'],c['spec']);c['numerical_search']=search
        p=search['candidates'][0];source=patch(c['faulty_netlist'],c['public_model'],p['component'],p['proposed_value'])
        m,v=simulate(ROOT/'build/diagnosis_visibility_v1_prescreen'/c['case_id'],'shared_repair',source,c['spec'])
        c['shared_repair_evaluator_only']={'proposal':{k:p[k] for k in ['component','proposed_value']},'metrics':m,'verdict':v}
        print(json.dumps({'case':c['case_id'],'forward_evaluations':search['forward_model_evaluations'],'shared_repair':v['verdict']}),flush=True)
    manifest=ROOT/'faults/holdout/diagnosis_visibility_v1.json';write_once(manifest,{'selection':'All eight predefined cases retained','cases':cs})
    files=['src/rf_repair/diagnosis.py','src/rf_repair/lossy.py','src/rf_repair/nonideal.py','src/rf_repair/extensions.py',
        'src/rf_repair/transfer.py','src/rf_repair/netlist.py','src/rf_repair/simulator.py','src/rf_repair/validator.py','src/rf_repair/agent.py',
        'scripts/prepare_diagnosis_visibility.py','scripts/run_diagnosis_visibility.py','scripts/run_budget_transfer.py',
        'docs/diagnosis_visibility_v1_protocol.md',str(manifest.relative_to(ROOT))]
    write_once(pp,{'experiment_id':'diagnosis_visibility_v1','frozen_at_utc':datetime.now(timezone.utc).isoformat(),
        'model':'gpt-5.6-luna','reasoning_effort':'low','max_output_tokens':2000,'max_input_chars':50000,'case_count':8,
        'conditions':CONDITIONS,'repetitions':2,'calls_per_trajectory':1,'max_api_calls':32,'automatic_retries':0,'store':False,
        'manifest':str(manifest.relative_to(ROOT)),'prices_per_million':{'input':.20,'cached_input':.02,'cache_write':.25,'output':1.20},
        'scope':'Exploratory candidate-visibility diagnosis ablation; fixed downstream repair is not a recovery comparison',
        'file_sha256':{f:digest((ROOT/f).read_bytes()) for f in files}})
    print(json.dumps({'frozen_cases':8,'planned_responses':32,'max_api_calls':32}),flush=True)

if __name__=='__main__':main()

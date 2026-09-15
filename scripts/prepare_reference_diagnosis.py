"""Freeze a new synthetic historical-measurement diagnosis comparison."""
import json
import sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from rf_repair import reference,lossy
from rf_repair.simulator import run_sparameter_simulation
from rf_repair.validator import validate_bpf_metrics
from run_budget_transfer import write_once,digest

def simulate(folder,label,source,spec):
    folder.mkdir(parents=True,exist_ok=True);p=folder/f'{label}.cir';p.write_text(source)
    m=run_sparameter_simulation(p,spec,folder/label,cwd=ROOT);v=validate_bpf_metrics(m,spec)
    write_once(folder/f'{label}.json',{'source_sha256':digest(source.encode()),'metrics':m,'verdict':v})
    return m,v

def main():
    pp=ROOT/'experiments/reference_diagnosis_v1.json'
    if pp.exists():raise RuntimeError('refuse to overwrite frozen protocol')
    cs=reference.cases();evidence=[]
    for c in cs:
        folder=ROOT/'build/reference_diagnosis_v1_prescreen'/c['case_id'];row={'case_id':c['case_id']}
        oracle=lossy.patch(c['faulty_netlist'],c['public_model'],c['component'],c['healthy_value']);assert oracle==c['healthy_netlist']
        for label,source in [('healthy',c['healthy_netlist']),('faulty',c['faulty_netlist']),('oracle',oracle)]:
            m,v=simulate(folder,label,source,c['spec']);row[label]=v['verdict']
            if label=='faulty':c['initial_metrics']=m
        f0=c['spec']['target_center_frequency_hz']
        c['current_spectrum']=reference.spectrum_from_table(folder/'faulty/sparams.tsv',f0)
        c['reference_spectrum']=reference.spectrum_from_table(folder/'healthy/sparams.tsv',f0)
        evidence.append(row)
    write_once(ROOT/'build/reference_diagnosis_v1_prescreen/summary.json',evidence)
    if not all(r['healthy']=='PASS' and r['faulty']=='FAIL' and r['oracle']=='PASS' for r in evidence):
        write_once(ROOT/'build/reference_diagnosis_v1_prescreen/ineligible_cases.json',cs)
        raise RuntimeError('predefined case ineligible; no retuning')
    for c in cs:
        fit=reference.fit_reference(c['faulty_netlist'],c['public_model'],c['reference_spectrum']);c['reference_fit']=fit
        top=fit['hypotheses'][0];source=lossy.patch(c['faulty_netlist'],c['public_model'],top['component'],top['inferred_prefault_value'])
        m,v=simulate(ROOT/'build/reference_diagnosis_v1_prescreen'/c['case_id'],'fit_reconstruction',source,c['spec'])
        diag=reference.deterministic_diagnosis(fit)
        c['fit_evaluator_only']={'diagnosis':diag,'metrics':m,'verdict':v,'diagnosed':diag['component']==c['component'] and diag['fault_type']==c['fault_type']}
        print(json.dumps({'case':c['case_id'],'model_evaluations':fit['forward_model_evaluations'],'resolved':fit['resolved_within_search'],
            'best_rmse_db':top['rmse_db'],'runner_up_rmse_db':fit['hypotheses'][1]['rmse_db']}),flush=True)
    manifest=ROOT/'faults/holdout/reference_diagnosis_v1.json';write_once(manifest,{'selection':'All eight predefined cases retained','cases':cs})
    files=['src/rf_repair/reference.py','src/rf_repair/diagnosis.py','src/rf_repair/lossy.py','src/rf_repair/nonideal.py',
        'src/rf_repair/extensions.py','src/rf_repair/transfer.py','src/rf_repair/netlist.py','src/rf_repair/simulator.py','src/rf_repair/validator.py','src/rf_repair/agent.py',
        'scripts/prepare_reference_diagnosis.py','scripts/run_reference_diagnosis.py','scripts/run_budget_transfer.py',
        'docs/reference_diagnosis_v1_protocol.md',str(manifest.relative_to(ROOT))]
    write_once(pp,{'experiment_id':'reference_diagnosis_v1','frozen_at_utc':datetime.now(timezone.utc).isoformat(),
        'model':'gpt-5.6-luna','reasoning_effort':'low','max_output_tokens':2000,'max_input_chars':50000,'case_count':8,
        'conditions':reference.CONDITIONS,'repetitions':2,'calls_per_trajectory':1,'max_api_calls':48,'automatic_retries':0,'store':False,
        'manifest':str(manifest.relative_to(ROOT)),'prices_per_million':{'input':.20,'cached_input':.02,'cache_write':.25,'output':1.20},
        'scope':'Synthetic stored baseline magnitude reference; exact known model/current values, quantization only; no real hardware claim',
        'file_sha256':{f:digest((ROOT/f).read_bytes()) for f in files}})
    print(json.dumps({'frozen_cases':8,'planned_responses':48,'max_api_calls':48}),flush=True)

if __name__=='__main__':main()

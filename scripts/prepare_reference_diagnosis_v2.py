"""Freeze an explicitly amended eligible-cohort study after v1 precheck abort."""
import json
import sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from rf_repair import reference,lossy
from rf_repair.simulator import run_sparameter_simulation
from rf_repair.validator import validate_bpf_metrics
from run_budget_transfer import read,write_once,digest

def main():
    pp=ROOT/'experiments/reference_diagnosis_v2.json'
    if pp.exists():raise RuntimeError('refuse to overwrite frozen protocol')
    old=read(ROOT/'experiments/reference_diagnosis_v1.json');assert old['status']=='ABORTED_PRECHECK'
    for f,h in old['file_sha256'].items():assert digest((ROOT/f).read_bytes())==h,f
    original=read(ROOT/old['manifest'])['cases'];screen=read(ROOT/'build/reference_diagnosis_v1_prescreen/summary.json')
    eligible={r['case_id'] for r in screen if r['healthy']=='PASS' and r['faulty']=='FAIL' and r['oracle']=='PASS'}
    assert len(eligible)==6
    cs=[c for c in original if c['case_id'] in eligible]
    write_once(ROOT/'build/reference_diagnosis_v2_prescreen/cohort.json',{'selection_made_before_fit_or_llm':True,'included':sorted(eligible),
        'excluded':[c['case_id'] for c in original if c['case_id'] not in eligible],'source_protocol_sha256':digest((ROOT/'experiments/reference_diagnosis_v1.json').read_bytes())})
    for c in cs:
        fit=reference.fit_reference(c['faulty_netlist'],c['public_model'],c['reference_spectrum']);c['reference_fit']=fit
        top=fit['hypotheses'][0];source=lossy.patch(c['faulty_netlist'],c['public_model'],top['component'],top['inferred_prefault_value'])
        folder=ROOT/'build/reference_diagnosis_v2_prescreen'/c['case_id'];folder.mkdir(parents=True,exist_ok=True)
        path=folder/'fit_reconstruction.cir';path.write_text(source)
        m=run_sparameter_simulation(path,c['spec'],folder/'fit_reconstruction',cwd=ROOT);v=validate_bpf_metrics(m,c['spec'])
        write_once(folder/'fit_reconstruction.json',{'source_sha256':digest(source.encode()),'metrics':m,'verdict':v})
        diag=reference.deterministic_diagnosis(fit)
        c['fit_evaluator_only']={'diagnosis':diag,'metrics':m,'verdict':v,'diagnosed':diag['component']==c['component'] and diag['fault_type']==c['fault_type']}
        print(json.dumps({'case':c['case_id'],'forward_evaluations':fit['forward_model_evaluations'],'resolved':fit['resolved_within_search'],
            'best_rmse_db':top['rmse_db'],'runner_up_rmse_db':fit['hypotheses'][1]['rmse_db']}),flush=True)
    manifest=ROOT/'faults/holdout/reference_diagnosis_v2.json';write_once(manifest,{'selection':'v1 prescreen-eligible cohort, chosen before fit/LLM; six retained, two excluded','cases':cs})
    files=['src/rf_repair/reference.py','src/rf_repair/diagnosis.py','src/rf_repair/lossy.py','src/rf_repair/nonideal.py',
        'src/rf_repair/extensions.py','src/rf_repair/transfer.py','src/rf_repair/netlist.py','src/rf_repair/simulator.py','src/rf_repair/validator.py','src/rf_repair/agent.py',
        'scripts/prepare_reference_diagnosis_v2.py','scripts/run_reference_diagnosis_v2.py','scripts/run_budget_transfer.py',
        'docs/reference_diagnosis_v2_protocol.md','docs/reference_diagnosis_v1_protocol.md','experiments/reference_diagnosis_v1.json',str(manifest)]
    write_once(pp,{'experiment_id':'reference_diagnosis_v2','status':'READY','frozen_at_utc':datetime.now(timezone.utc).isoformat(),
        'model':'gpt-5.6-luna','reasoning_effort':'low','max_output_tokens':2000,'max_input_chars':50000,'case_count':6,
        'conditions':reference.CONDITIONS,'repetitions':2,'calls_per_trajectory':1,'max_api_calls':36,'automatic_retries':0,'store':False,
        'manifest':str(manifest.relative_to(ROOT)),'prices_per_million':{'input':.20,'cached_input':.02,'cache_write':.25,'output':1.20},
        'scope':'Post-prescreen amended eligible-cohort exploration, synthetic historical magnitudes; not full v1 or measured hardware performance',
        'file_sha256':{f:digest((ROOT/f).read_bytes()) for f in files}})
    print(json.dumps({'frozen_cases':6,'planned_responses':36,'max_api_calls':36}),flush=True)

if __name__=='__main__':main()

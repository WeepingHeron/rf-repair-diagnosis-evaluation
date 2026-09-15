"""Screen every prespecified candidate and freeze protocols before live calls."""
from pathlib import Path
import sys
import json
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from rf_repair.extensions import make_bpf_extension_cases, make_matching_cases, deterministic_candidates, validate_extension
from rf_repair.simulator import run_sparameter_simulation
from rf_repair.transfer import apply_patch
from run_budget_transfer import write_once, digest


def main():
    for name,generator,repeats,conditions,iterations in [
        ('calculator_v5',make_bpf_extension_cases,2,['feedback','calculator_feedback'],3),
        ('matching_v1',make_matching_cases,1,['matching_one_shot'],1)]:
        pp=ROOT/'experiments'/f'{name}.json'
        if pp.exists(): raise RuntimeError('Existing protocol must not be overwritten: '+str(pp))
        cases=generator();evidence=[];baseline=[]
        for case in cases:
            folder=ROOT/'build'/f'{name}_prescreen'/case['case_id'];folder.mkdir(parents=True,exist_ok=True)
            oracle=apply_patch(case['faulty_netlist'],case['component'],case['healthy_value'])
            assert oracle==case['healthy_netlist']
            row={'case_id':case['case_id']}
            for label,source in [('healthy',case['healthy_netlist']),('faulty',case['faulty_netlist']),('oracle',oracle)]:
                path=folder/f'{label}.cir';path.write_text(source)
                metrics=run_sparameter_simulation(path,case['spec'],folder/label,cwd=ROOT)
                verdict=validate_extension(metrics,case['spec'],case['family']);row[label]=verdict['verdict']
                write_once(folder/f'{label}_evidence.json',{'metrics':metrics,'verdict':verdict})
                if label=='faulty':case['initial_metrics']=metrics
            evidence.append(row)
            if case['family']=='bpf':
                attempts=[]
                for i,proposal in enumerate(deterministic_candidates(case['faulty_netlist'],case['spec']['target_center_frequency_hz']),1):
                    source=apply_patch(case['faulty_netlist'],proposal['component'],proposal['proposed_value'])
                    path=folder/f'deterministic_{i}.cir';path.write_text(source)
                    metrics=run_sparameter_simulation(path,case['spec'],folder/f'deterministic_{i}',cwd=ROOT)
                    verdict=validate_extension(metrics,case['spec'],case['family'])
                    attempts.append({'proposal':proposal,'metrics':metrics,'verdict':verdict})
                    if verdict['verdict']=='PASS':break
                baseline.append({'case_id':case['case_id'],'recovered':any(r['verdict']['verdict']=='PASS' for r in attempts),'attempts':attempts})
        assert all(r['healthy']=='PASS' and r['faulty']=='FAIL' and r['oracle']=='PASS' for r in evidence),evidence
        manifest=ROOT/'faults/holdout'/f'{name}.json';write_once(manifest,{'selection':'All predefined candidates retained; no model-based selection','cases':cases})
        files=['src/rf_repair/extensions.py','src/rf_repair/transfer.py','src/rf_repair/netlist.py','src/rf_repair/simulator.py',
               'src/rf_repair/validator.py','src/rf_repair/agent.py','scripts/run_extension.py','scripts/run_budget_transfer.py',
               'scripts/prepare_extensions.py',str(manifest.relative_to(ROOT))]
        protocol={'experiment_id':name,'frozen_at_utc':datetime.now(timezone.utc).isoformat(),'model':'gpt-5.6-luna','reasoning_effort':'low',
                  'max_output_tokens':2000,'max_input_chars':40000,'case_count':len(cases),'repetitions':repeats,'conditions':conditions,
                  'max_iterations':iterations,'max_api_calls':len(cases)*repeats*len(conditions)*iterations,'manifest':str(manifest.relative_to(ROOT)),
                  'automatic_api_retries':0,'store':False,'stop_on_success':True,'prices_per_million':{'input':.20,'cached_input':.02,'cache_write':.25,'output':1.20},
                  'price_source':'https://developers.openai.com/api/docs/models/gpt-5.6-luna',
                  'scope':'Prospective exploratory extension after v4 inspection; not a universal generalization claim.',
                  'file_sha256':{file:digest((ROOT/file).read_bytes()) for file in files}}
        write_once(ROOT/'build'/f'{name}_prescreen/summary.json',evidence)
        if baseline:write_once(ROOT/'build'/f'{name}_prescreen/deterministic_baseline.json',baseline)
        write_once(pp,protocol)
        print(json.dumps({'experiment':name,'screened':len(cases),'planned':len(cases)*repeats*len(conditions),'max_calls':protocol['max_api_calls'],
                          'deterministic_recovered':sum(r['recovered'] for r in baseline)},ensure_ascii=False))

if __name__=='__main__':main()

"""Development evidence and loss-aware held-out case preparation; never overwrite a frozen run."""
import argparse
import itertools
import json
import sys
from copy import deepcopy
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from rf_repair import lossy
from rf_repair.simulator import run_sparameter_simulation
from rf_repair.validator import validate_bpf_metrics
from run_budget_transfer import write_once,digest


def simulate(path,source,spec):
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(source)
    metrics=run_sparameter_simulation(path,spec,path.with_suffix(''),cwd=ROOT)
    result={'source_sha256':digest(source.encode()),'metrics':metrics,'verdict':validate_bpf_metrics(metrics,spec)}
    write_once(path.with_suffix('.json'),result)
    return result


def development():
    out=ROOT/'build/lossy_repair_v1_development'; results=[]
    original=deepcopy(lossy.MODEL)
    for i,(rl,rc) in enumerate([(.25,.05),(.05,.02),(.05,.01)],1):
        lossy.MODEL.update(inductor_rs_ohm=rl,capacitor_rs_ohm=rc)
        d=lossy.make_design(103e6,.18,202609070,'development',.02)
        source=lossy.render(d['public_model'],d['healthy_values'])
        r=simulate(out/f'development_{i}.cir',source,d['spec'])
        results.append({'r_l':rl,'r_c':rc,'selected':i==2,'evidence':r})
    lossy.MODEL.clear();lossy.MODEL.update(original)
    d=lossy.make_design(103e6,.18,202609070,'development',.02)
    ablations=[]
    keys=list(original)
    for bits in itertools.product([False,True],repeat=4):
        m={k:original[k] if bit else 0. for k,bit in zip(keys,bits)}
        source=lossy.render(d['public_model'],d['healthy_values'],model_override=m)
        label=''.join('1' if b else '0' for b in bits)
        r=simulate(out/f'ablation_{label}.cir',source,d['spec'])
        ablations.append({'enabled':dict(zip(keys,bits)),'evidence':r})
    write_once(out/'summary.json',{'scope':'Development-only, model selection after observed failure; not holdout performance',
        'model_selection':results,'ablation_order':keys,'ablations':ablations,'design':d})
    print(json.dumps({'development_configurations':len(results),'ablations':len(ablations),'selected_model':original}),flush=True)


def prepare():
    pp=ROOT/'experiments/lossy_repair_v1.json'
    if pp.exists():raise RuntimeError('refuse to overwrite frozen protocol')
    cases=[]; rows=[]
    for i,(f0,bw) in enumerate(lossy.HOLDOUT):
        d=lossy.make_design(f0,bw,202609071+i,f'lossy_d{i+1}',.02)
        p=d['public_model']; source=lossy.render(p,d['healthy_values']); folder=ROOT/'build/lossy_repair_v1_prescreen'/d['design_id']
        healthy=simulate(folder/'healthy.cir',source,d['spec'])
        for j,index in enumerate([[0,3],[1,2],[4,3],[5,2]][i]):
            cid=f'lossy_d{i+1}_f{j+1}'; component=p['main_components'][index]['component']; mult=[.55,1.8][j]
            values={**d['healthy_values'],component:f'{float(d["healthy_values"][component])*mult:.12g}'}
            faulty=lossy.render(p,values); fault=simulate(folder/f'fault_{j+1}.cir',faulty,d['spec'])
            oracle=lossy.patch(faulty,p,component,d['healthy_values'][component]); assert oracle==source
            restored=simulate(folder/f'oracle_{j+1}.cir',oracle,d['spec'])
            eligible=healthy['verdict']['verdict']=='PASS' and fault['verdict']['verdict']=='FAIL' and restored['verdict']['verdict']=='PASS'
            rows.append({'case_id':cid,'healthy':healthy['verdict']['verdict'],'faulty':fault['verdict']['verdict'],
                         'oracle':restored['verdict']['verdict'],'eligible':eligible})
            cases.append({'case_id':cid,'design_id':d['design_id'],'public_model':p,'spec':d['spec'],
                'healthy_netlist':source,'faulty_netlist':faulty,'component':component,'healthy_value':d['healthy_values'][component],
                'fault_type':'value_too_low' if mult<1 else 'value_too_high','multiplier':mult,
                'initial_metrics':fault['metrics'],'design_evaluator_only':d,'eligible':eligible})
    write_once(ROOT/'build/lossy_repair_v1_prescreen/summary.json',rows)
    if not all(r['eligible'] for r in rows):
        write_once(ROOT/'build/lossy_repair_v1_prescreen/ineligible_cases.json',cases)
        raise RuntimeError('Predefined holdout contains ineligible cases; stop without retuning')
    for c in cases:
        c['numerical_search']=lossy.numerical_search(c['faulty_netlist'],c['public_model'],c['spec'])
        print(json.dumps({'case':c['case_id'],'forward_evaluations':c['numerical_search']['forward_model_evaluations']}),flush=True)
    manifest=ROOT/'faults/holdout/lossy_repair_v1.json';write_once(manifest,{'selection':'All eight predefined cases retained','cases':cases})
    files=['src/rf_repair/lossy.py','src/rf_repair/nonideal.py','src/rf_repair/extensions.py','src/rf_repair/transfer.py',
        'src/rf_repair/netlist.py','src/rf_repair/simulator.py','src/rf_repair/validator.py','src/rf_repair/agent.py',
        'scripts/prepare_lossy_repair.py','scripts/run_lossy_repair.py','scripts/run_lossy_baselines.py','scripts/run_budget_transfer.py',
        'docs/lossy_repair_v1_protocol.md',str(manifest.relative_to(ROOT))]
    write_once(pp,{'experiment_id':'lossy_repair_v1','frozen_at_utc':datetime.now(timezone.utc).isoformat(),
        'model':'gpt-5.6-luna','reasoning_effort':'low','max_output_tokens':2000,'max_input_chars':50000,
        'case_count':8,'repetitions':2,'conditions':['numerical_feedback'],'max_iterations':3,'max_api_calls':48,
        'manifest':str(manifest.relative_to(ROOT)),'automatic_api_retries':0,'store':False,'stop_on_success':True,
        'prices_per_million':{'input':.20,'cached_input':.02,'cache_write':.25,'output':1.20},
        'price_source':'https://developers.openai.com/api/docs/models/gpt-5.6-luna',
        'scope':'Exploratory loss-aware synthesized models with fixed public ESR; shared numerical candidates, not equal total cost to ideal algebra',
        'file_sha256':{p:digest((ROOT/p).read_bytes()) for p in files}})
    print(json.dumps({'frozen_cases':8,'planned_llm_trajectories':16,'max_api_calls':48}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--development',action='store_true');args=parser.parse_args()
    development() if args.development else prepare()

"""Freeze and execute the no-API, 945-row sensitivity experiment."""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from rf_repair import robustness, reference

PP=ROOT/'experiments/reference_robustness_v1.json'
OUT=ROOT/'build/reference_robustness_v1'

def digest(data): return hashlib.sha256(data).hexdigest()
def read(path): return json.loads(path.read_text())
def write(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')
def check(p):
    for f,h in p['file_sha256'].items():
        if digest((ROOT/f).read_bytes())!=h:raise ValueError('changed frozen file: '+f)

def freeze():
    if PP.exists():check(read(PP));print('Existing frozen protocol retained');return
    prior=read(ROOT/'experiments/reference_diagnosis_v2.json');check(prior)
    cs=read(ROOT/prior['manifest'])['cases'];assert len(cs)==6
    files=set(prior['file_sha256'])|{'experiments/reference_diagnosis_v2.json',
        'src/rf_repair/robustness.py','scripts/run_reference_robustness.py','tests/test_robustness.py',
        'docs/reference_robustness_v1_protocol.md'}
    p=dict(experiment_id='reference_robustness_v1',frozen_at_utc=datetime.now(timezone.utc).isoformat(),
        api_calls=0,scope='Reused eligible synthetic cohort sensitivity; no hardware or new holdout claim',
        cohort=robustness.cohort(cs),scenarios=robustness.scenarios(),planned=945,
        file_sha256={f:digest((ROOT/f).read_bytes()) for f in sorted(files)})
    assert len(p['cohort'])*len(p['scenarios'])==945
    write(PP,p);print('Frozen 105 scenarios x 9 cohort items = 945 fits',flush=True)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--freeze',action='store_true');args=ap.parse_args()
    if args.freeze:freeze();return
    p=read(PP);check(p);ph=digest(PP.read_bytes());rows=[]
    for idx,s in enumerate(p['scenarios']):
        for item in p['cohort']:
            evidence=robustness.measurement_inputs(item,s);ih=digest(json.dumps(evidence,sort_keys=True).encode())
            dest=OUT/'rows'/s['scenario_id']/(item['cohort_id']+'.json')
            if dest.exists():
                r=read(dest);assert r['protocol_sha256']==ph and r['input_sha256']==ih
            else:
                fit=reference.fit_reference(**evidence['estimator_input']);diag=reference.deterministic_diagnosis(fit)
                top=fit['hypotheses'][0]
                r=dict(protocol_sha256=ph,scenario_id=s['scenario_id'],family=s['family'],level=s['level'],draw=s['draw'],
                    cohort_id=item['cohort_id'],kind=item['kind'],input_sha256=ih,**evidence,fit=fit,diagnosis=diag,
                    score=robustness.score(diag,item),top_rank_correct=item['kind']=='fault' and
                    top['component']==item['expected_component'] and top['current_fault_direction']==item['expected_direction'])
                write(dest,r)
            rows.append(r)
        if (idx+1)%10==0 or idx+1==len(p['scenarios']):print(f'Completed {len(rows)}/945 fits',flush=True)
    assert len(rows)==p['planned'];check(p)
    summary=dict(complete=True,protocol_sha256=ph,completed=len(rows),api_calls=0,
        forward_model_evaluations=sum(r['fit']['forward_model_evaluations'] for r in rows),groups=robustness.aggregate(rows))
    write(OUT/'summary.json',summary)
    print(json.dumps({k:v for k,v in summary.items() if k!='groups'},indent=2))

if __name__=='__main__':main()

"""Freeze and run small-change heterogeneous development experiment, without API calls."""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from rf_repair import diagnosis_dev as dev, reference, robustness
from run_reference_robustness import read, write, digest, check
PP=ROOT/'experiments/diagnosis_development_v1.json'
OUT=ROOT/'build/diagnosis_development_v1'


def freeze():
    if PP.exists():check(read(PP));print('Existing protocol retained');return
    prior=read(ROOT/'experiments/reference_robustness_v1.json');check(prior)
    files=set(prior['file_sha256'])|{'experiments/reference_robustness_v1.json','src/rf_repair/diagnosis_dev.py',
        'scripts/run_diagnosis_development.py','tests/test_diagnosis_dev.py','docs/diagnosis_development_v1_protocol.md'}
    p=dict(experiment_id='diagnosis_development_v1',frozen_at_utc=datetime.now(timezone.utc).isoformat(),
        api_calls=0,split='development_only_no_threshold_change',cohort=dev.cohort(),profiles=dev.profiles(),planned=2368,
        file_sha256={f:digest((ROOT/f).read_bytes()) for f in sorted(files)})
    assert len(p['cohort'])*len(p['profiles'])==2368;write(PP,p);print('Frozen 2368 fits, development only',flush=True)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--freeze',action='store_true');args=ap.parse_args()
    if args.freeze:freeze();return
    p=read(PP);check(p);ph=digest(PP.read_bytes());rows=[]
    for profile in p['profiles']:
        for item in p['cohort']:
            evidence=dev.inputs(item,profile);ih=digest(json.dumps(evidence,sort_keys=True).encode())
            path=OUT/'rows'/profile['profile_id']/(item['cohort_id']+'.json')
            if path.exists():
                r=read(path);assert r['protocol_sha256']==ph and r['input_sha256']==ih
            else:
                fit=reference.fit_reference(**evidence['estimator_input']);diag=reference.deterministic_diagnosis(fit)
                top=fit['hypotheses'][0]
                r=dict(protocol_sha256=ph,profile_id=profile['profile_id'],family=profile['family'],draw=profile['draw'],
                    cohort_id=item['cohort_id'],design_id=item['design_id'],kind=item['kind'],change_fraction=item['change_fraction'],
                    input_sha256=ih,**evidence,fit=fit,features=dev.features(evidence['estimator_input'],fit),diagnosis=diag,
                    score=robustness.score(diag,item),top_rank_correct=item['kind']=='fault' and
                    top['component']==item['expected_component'] and top['current_fault_direction']==item['expected_direction'])
                write(path,r)
            rows.append(r)
        print(f'{profile["profile_id"]}: {len(rows)}/2368 fits complete',flush=True)
    check(p);assert len(rows)==p['planned']
    s=dict(complete=True,protocol_sha256=ph,completed=len(rows),api_calls=0,
        fit_forward_evaluations=sum(r['fit']['forward_model_evaluations'] for r in rows),
        no_change_forward_evaluations=len(rows),groups=dev.aggregate(rows))
    write(OUT/'summary.json',s);print(json.dumps({k:v for k,v in s.items() if k!='groups'},indent=2))

if __name__=='__main__':main()

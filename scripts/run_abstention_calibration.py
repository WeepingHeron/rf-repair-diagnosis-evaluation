"""Staged calibration; holdout cannot run until the selected policy is persisted."""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from rf_repair import calibration, abstention, diagnosis_dev as dev, reference, robustness
from run_reference_robustness import read,write,digest,check
PP=ROOT/'experiments/abstention_calibration_v1.json'
POLICY=ROOT/'experiments/diagnosis_abstention_v1.json'
OUT=ROOT/'build/abstention_calibration_v1'


def freeze():
    if PP.exists():check(read(PP));print('Existing protocol retained');return
    prior=read(ROOT/'experiments/diagnosis_development_v1.json');check(prior)
    files=set(prior['file_sha256'])|{'experiments/diagnosis_development_v1.json','src/rf_repair/calibration.py',
        'src/rf_repair/abstention.py','scripts/run_abstention_calibration.py','scripts/diagnose_reference.py',
        'tests/test_abstention.py','docs/abstention_calibration_v1_protocol.md'}
    p=dict(experiment_id='abstention_calibration_v1',frozen_at_utc=datetime.now(timezone.utc).isoformat(),
        splits={name:calibration.cohort(name) for name in calibration.SPLITS},profiles=dev.profiles(),api_calls=0,planned_per_split=2368,
        file_sha256={f:digest((ROOT/f).read_bytes()) for f in sorted(files)})
    assert not ({i['design_id'] for i in p['splits']['calibration']}&{i['design_id'] for i in p['splits']['holdout']})
    write(PP,p);print('Frozen design-disjoint calibration and holdout',flush=True)


def load_rows(split):
    paths=sorted((OUT/split/'rows').glob('*/*.json'))
    return [read(path) for path in paths],{str(path.relative_to(ROOT)):digest(path.read_bytes()) for path in paths}


def calibrate():
    p=read(PP);check(p);rows,hashes=load_rows('calibration');assert len(rows)==2368
    assert read(OUT/'calibration/summary.json')['complete']
    expected=abstention.select(rows,digest(PP.read_bytes()),hashes)
    if POLICY.exists():assert read(POLICY)==expected;print('Frozen policy retained');return
    if (OUT/'holdout').exists():raise ValueError('holdout already exists before policy freeze')
    write(POLICY,expected)
    print(json.dumps({k:v for k,v in expected.items() if k not in ['candidate_results','calibration_rows_sha256']},indent=2))


def collect(split):
    p=read(PP);check(p);ph=digest(PP.read_bytes());policy=None;policy_hash=None
    if split=='holdout':
        policy=read(POLICY);abstention.validate_policy(policy);assert policy['protocol_sha256']==ph
        for f,h in policy['calibration_rows_sha256'].items():assert digest((ROOT/f).read_bytes())==h
        policy_hash=digest(POLICY.read_bytes())
    rows=[]
    for profile in p['profiles']:
        for item in p['splits'][split]:
            ev=dev.inputs(item,profile);ih=digest(json.dumps(ev,sort_keys=True).encode())
            path=OUT/split/'rows'/profile['profile_id']/(item['cohort_id']+'.json')
            if path.exists():
                r=read(path);assert r['protocol_sha256']==ph and r['input_sha256']==ih and r['policy_sha256']==policy_hash
            else:
                bundle=abstention.collect(ev['estimator_input']);legacy=reference.deterministic_diagnosis(bundle['fit'])
                r=dict(protocol_sha256=ph,policy_sha256=policy_hash,split=split,profile_id=profile['profile_id'],family=profile['family'],
                    draw=profile['draw'],cohort_id=item['cohort_id'],design_id=item['design_id'],kind=item['kind'],change_fraction=item['change_fraction'],
                    truth=dict(component=item['expected_component'],fault_type=item['expected_direction']),input_sha256=ih,**ev,bundle=bundle,
                    legacy_diagnosis=legacy,legacy_score=robustness.score(legacy,item))
                if policy is not None:
                    result=abstention.decide(bundle,policy);r['new_result']=result;r['new_score']=robustness.score(result['diagnosis'],item)
                write(path,r)
            rows.append(r)
        print(f'{split} {profile["profile_id"]}: {len(rows)}/2368',flush=True)
    assert len(rows)==2368;check(p)
    if policy is not None:assert digest(POLICY.read_bytes())==policy_hash
    summary=dict(complete=True,split=split,protocol_sha256=ph,policy_sha256=policy_hash,completed=len(rows),api_calls=0,
        original_fits=len(rows),stability_fits=sum(len(r['bundle']['stability']) for r in rows),
        fit_forward_evaluations=sum(r['bundle']['fit']['forward_model_evaluations']+
            sum(s['fit']['forward_model_evaluations'] for s in r['bundle']['stability']) for r in rows),no_change_forward_evaluations=len(rows))
    write(OUT/split/'summary.json',summary);print(json.dumps(summary,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['freeze','calibration','calibrate','holdout']);args=parser.parse_args()
    if args.stage=='freeze':freeze()
    elif args.stage=='calibrate':calibrate()
    else:collect(args.stage)

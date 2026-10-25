"""Frozen conditional stability extension; active policy and prior results remain unchanged."""
import argparse
import json
import sys
import time
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from rf_repair import stability_extension as ext,reference,abstention
from run_reference_robustness import read,write,digest,check
PP=ROOT/'experiments/stability_extension_v1.json'
OUT=ROOT/'build/stability_extension_v1'


def freeze():
    if PP.exists():check(read(PP));print('Frozen protocol retained');return
    prior=read(ROOT/'experiments/abstention_calibration_v1.json');check(prior)
    auditpath=ROOT/'build/abstention_calibration_v1_audit/summary.json';audit=read(auditpath)
    policy=read(ROOT/'experiments/diagnosis_abstention_v1.json');assert audit['complete'] and not audit['issues']
    assert audit['policy_sha256']==digest((ROOT/'experiments/diagnosis_abstention_v1.json').read_bytes())
    targets=[]
    for f,h in sorted(audit['row_sha256'].items()):
        if '/holdout/rows/' not in f:continue
        path=ROOT/f;assert digest(path.read_bytes())==h;r=read(path)
        result=abstention.decide(r['bundle'],policy);assert result==r['new_result']
        if not result['abstained']:
            assert len(r['bundle']['stability'])==4 and r['bundle']['stability_matches']==4
            targets.append(dict(source_path=f,source_sha256=h,profile_id=r['profile_id'],cohort_id=r['cohort_id']))
    assert len(targets)==615
    files=set(prior['file_sha256'])|{'experiments/abstention_calibration_v1.json','experiments/diagnosis_abstention_v1.json',
        'configs/diagnosis_abstention.json',str(auditpath.relative_to(ROOT)),'src/rf_repair/stability_extension.py',
        'scripts/run_stability_extension.py','tests/test_stability_extension.py','docs/stability_extension_v1_protocol.md'}
    p=dict(experiment_id='stability_extension_v1',frozen_at_utc=datetime.now(timezone.utc).isoformat(),target_count=615,
        original_draws=4,total_draws=16,new_fits=7380,api_calls=0,selection='All previously confirmed holdout rows, irrespective of correctness',
        targets=targets,file_sha256={f:digest((ROOT/f).read_bytes()) for f in sorted(files)})
    write(PP,p);print('Frozen 615 inputs, 7380 additional fits',flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--freeze',action='store_true');args=parser.parse_args()
    if args.freeze:freeze();return
    p=read(PP);check(p);ph=digest(PP.read_bytes());total=0;forwards=0;new_unstable=[];start=time.perf_counter()
    for index,t in enumerate(p['targets']):
        path=ROOT/t['source_path'];assert digest(path.read_bytes())==t['source_sha256'];r=read(path);e=r['estimator_input']
        stored=[]
        for v in ext.perturbations(e,16):
            if v['draw']<4:
                old=r['bundle']['stability'][v['draw']]
                assert all(old[k]==v[k] for k in ['draw','seed','offsets_db']);assert old['matches'];continue
            dest=OUT/'rows'/t['profile_id']/t['cohort_id']/f'draw_{v["draw"]+1:02d}.json'
            ih=digest(json.dumps(v['input'],sort_keys=True,allow_nan=False).encode())
            if dest.exists():
                row=read(dest);assert row['protocol_sha256']==ph and row['input_sha256']==ih
            else:
                tick=time.perf_counter();fit=reference.fit_reference(**v['input'])
                row=dict(protocol_sha256=ph,source_sha256=t['source_sha256'],input_sha256=ih,draw=v['draw'],seed=v['seed'],
                    offsets_db=v['offsets_db'],fit=fit,comparison=ext.compare(fit,r['bundle']['fit']),elapsed_seconds=time.perf_counter()-tick)
                write(dest,row)
            total+=1;forwards+=row['fit']['forward_model_evaluations'];stored.append(row)
        unstable=[s['draw']+1 for s in stored if not s['comparison']['matches']]
        if unstable:new_unstable.append(dict(profile_id=t['profile_id'],cohort_id=t['cohort_id'],first_mismatch=unstable[0],mismatching_draws=unstable))
        if (index+1)%50==0 or index+1==615:print(f'Inputs {index+1}/615; additional fits {total}/7380',flush=True)
    assert total==p['new_fits'];check(p)
    summary=dict(complete=True,protocol_sha256=ph,target_count=615,additional_fits=total,additional_forward_evaluations=forwards,
        reused_draws=2460,total_stability_draws=9840,stable_all_16=615-len(new_unstable),unstable_inputs=new_unstable,
        api_calls=0,invocation_wall_seconds=time.perf_counter()-start)
    write(OUT/'summary.json',summary);print(json.dumps(summary,indent=2))

if __name__=='__main__':main()

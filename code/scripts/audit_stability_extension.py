"""Verify selected inputs, RNG continuation, all new fits and independent nodal residuals."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
import math
import random
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from rf_repair import reference,abstention,lossy
from audit_lossy_repair import nodal_magnitudes
from run_reference_robustness import read,write,digest,check
from run_stability_extension import PP,OUT


def main():
    p=read(PP);check(p);ph=digest(PP.read_bytes());s=read(OUT/'summary.json')
    assert s['complete'] and s['protocol_sha256']==ph
    old=read(ROOT/'build/abstention_calibration_v1_audit/summary.json');policy=read(ROOT/'experiments/diagnosis_abstention_v1.json')
    expected=[]
    for f,h in sorted(old['row_sha256'].items()):
        if '/holdout/rows/' not in f:continue
        path=ROOT/f;assert digest(path.read_bytes())==h;r=read(path)
        d=abstention.decide(r['bundle'],policy);assert d==r['new_result']
        if not d['abstained']:expected.append(dict(source_path=f,source_sha256=h,profile_id=r['profile_id'],cohort_id=r['cohort_id']))
    assert p['targets']==expected and len(expected)==615
    assert p['total_draws']==16 and p['original_draws']==4 and p['new_fits']==7380
    hashes={};seen=set();forward=0;prefix=0;points=0;maximum=0.;mismatches=[];byinput=[];families={};draws=Counter();compute_seconds=0.
    for i,t in enumerate(expected):
        source=ROOT/t['source_path'];r=read(source);e=r['estimator_input'];top=r['bundle']['fit']['hypotheses'][0]
        seed=int(hashlib.sha256(b'abstention_v1|'+json.dumps(e,sort_keys=True,allow_nan=False).encode()).hexdigest()[:16],16)
        rng=random.Random(seed);input_mismatches=[];locations=0;directions=0;offset_set=set()
        for draw in range(16):
            copied=deepcopy(e);offsets=[]
            for sample in copied['reference']['samples']:
                for channel in ['s11_db','s21_db','s22_db']:
                    delta=.01*(1 if rng.getrandbits(1) else -1);offsets.append(delta);sample[channel]=round(sample[channel]+delta,2)
            assert tuple(offsets) not in offset_set;offset_set.add(tuple(offsets))
            if draw<4:
                st=r['bundle']['stability'][draw]
                assert st['draw']==draw and st['seed']==seed and st['offsets_db']==offsets and st['matches'];prefix+=1
                continue
            path=OUT/'rows'/t['profile_id']/t['cohort_id']/f'draw_{draw+1:02d}.json';row=read(path)
            key=(t['profile_id'],t['cohort_id'],draw);assert key not in seen;seen.add(key)
            hashes[str(path.relative_to(ROOT))]=digest(path.read_bytes())
            assert row['protocol_sha256']==ph and row['source_sha256']==t['source_sha256']
            assert row['input_sha256']==digest(json.dumps(copied,sort_keys=True,allow_nan=False).encode())
            assert row['draw']==draw and row['seed']==seed and row['offsets_db']==offsets
            fit=reference.fit_reference(**copied);assert row['fit']==fit and fit['forward_model_evaluations']<=402
            forward+=fit['forward_model_evaluations'];assert math.isfinite(row['elapsed_seconds']) and row['elapsed_seconds']>=0;compute_seconds+=row['elapsed_seconds']
            for h in fit['hypotheses'][:2]:
                patched=lossy.patch(e['source'],e['public'],h['component'],h['inferred_prefault_value']);squared=0.
                for sample in copied['reference']['samples']:
                    mags=nodal_magnitudes(patched,sample['frequency_hz']);points+=1
                    squared+=sum((20*math.log10(max(v,1e-150))-sample[k])**2 for v,k in zip(mags,['s11_db','s21_db','s22_db']))
                error=abs(math.sqrt(squared/27)-h['rmse_db']);maximum=max(maximum,error);assert error<1e-7
            candidate=fit['hypotheses'][0];loc=candidate['component']==top['component'];direction=candidate['current_fault_direction']==top['current_fault_direction']
            comparison=dict(component_matches=loc,direction_matches=direction,matches=loc and direction)
            assert row['comparison']==comparison;locations+=not loc;directions+=not direction;draws[draw+1]+=1
            if not comparison['matches']:
                input_mismatches.append(draw+1);mismatches.append(dict(source_path=t['source_path'],draw=draw+1,original=top,candidate=candidate))
        item=dict(profile_id=t['profile_id'],cohort_id=t['cohort_id'],stable_all_16=not input_mismatches,
            component_flip_draws=locations,direction_flip_draws=directions,first_mismatch=input_mismatches[0] if input_mismatches else None,
            mismatching_draws=input_mismatches)
        byinput.append(item);g=families.setdefault(r['family'],dict(inputs=0,stable_all_16=0,component_flip_draws=0,direction_flip_draws=0))
        g['inputs']+=1;g['stable_all_16']+=not input_mismatches;g['component_flip_draws']+=locations;g['direction_flip_draws']+=directions
        if (i+1)%50==0 or i+1==615:print(f'Audited inputs {i+1}/615; new fits {len(seen)}/7380',flush=True)
    assert len(seen)==7380 and prefix==2460 and len(list((OUT/'rows').glob('*/*/draw_*.json')))==7380
    assert all(draws[draw]==615 for draw in range(5,17)) and points==132840
    unstable=[dict(profile_id=x['profile_id'],cohort_id=x['cohort_id'],first_mismatch=x['first_mismatch'],mismatching_draws=x['mismatching_draws']) for x in byinput if not x['stable_all_16']]
    assert s['unstable_inputs']==unstable and s['stable_all_16']==615-len(unstable)
    assert s['additional_forward_evaluations']==forward and s['additional_fits']==7380 and s['reused_draws']==2460 and s['total_stability_draws']==9840
    check(p)
    result=dict(complete=True,issues=[],protocol_sha256=ph,confirmed_inputs=615,reused_draws_verified=prefix,
        additional_fits_replayed=len(seen),total_stability_draws=9840,stable_all_16=615-len(unstable),
        newly_withheld_if_16_required=len(unstable),mismatching_draw_count=len(mismatches),families=families,
        by_input=byinput,mismatches=mismatches,nodal_residual_points=points,max_nodal_rmse_difference_db=maximum,
        additional_forward_evaluations=forward,recorded_additional_fit_seconds=compute_seconds,
        policy_unchanged=True,new_native_sweeps=0,api_calls=0,row_sha256=hashes,summary_sha256=digest((OUT/'summary.json').read_bytes()))
    write(ROOT/'build/stability_extension_v1_audit/summary.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ['row_sha256','by_input','mismatches']},indent=2))

if __name__=='__main__':main()

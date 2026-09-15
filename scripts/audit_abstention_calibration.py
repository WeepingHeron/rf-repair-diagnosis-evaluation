"""Audit disjoint calibration, selected thresholds, paired holdout and physical evidence."""
from collections import Counter
import hashlib
import json
import math
import random
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from rf_repair import calibration, abstention, diagnosis_dev as dev, lossy, reference
from rf_repair.simulator import run_sparameter_simulation
from rf_repair.validator import validate_bpf_metrics
from audit_lossy_repair import nodal_magnitudes
from run_reference_robustness import read,write,digest,check
from run_abstention_calibration import PP,POLICY,OUT


def manual_decision(bundle,params):
    f=bundle['features'];reasons=[]
    if f['best_rmse_db']>params['fit_max_db']:reasons.append('MODEL_MISMATCH')
    if f['gap_db']<params['gap_min_db'] or f['separation_ratio']<params['ratio_min']:reasons.append('AMBIGUOUS_COMPONENT')
    if f['null_score']<params['null_score_min']:reasons.append('CHANGE_NOT_DISTINGUISHED_FROM_NULL')
    if len(bundle['stability'])!=4 or sum(s['matches'] for s in bundle['stability'])!=4:reasons.append('STABILITY_NOT_CONFIRMED')
    h=bundle['fit']['hypotheses'][0]
    d=dict(component='unknown',fault_type='unknown_direction') if reasons else dict(component=h['component'],fault_type=h['current_fault_direction'])
    return dict(diagnosis=d,abstained=bool(reasons),reasons=reasons)


def manual_score(d,item):
    hold=d['component']=='unknown';correct=item['kind']=='fault' and d['component']==item['expected_component'] and d['fault_type']==item['expected_direction']
    return dict(correct=correct,abstained=hold,wrong_diagnosis=item['kind']=='fault' and not hold and not correct,false_alarm=item['kind']=='control' and not hold)


def main():
    p=read(PP);check(p);ph=digest(PP.read_bytes());policy=read(POLICY);policy_hash=digest(POLICY.read_bytes())
    assert policy['protocol_sha256']==ph;abstention.validate_policy(policy)
    for split in ['calibration','holdout']:assert p['splits'][split]==calibration.cohort(split)
    assert p['profiles']==dev.profiles()
    assert not ({i['design_id'] for i in p['splits']['calibration']}&{i['design_id'] for i in p['splits']['holdout']})
    assert not ({i['public_model']['frequency_hz'] for i in dev.cohort()}&{i['public_model']['frequency_hz'] for cs in p['splits'].values() for i in cs})
    audit=ROOT/'build/abstention_calibration_v1_audit';physics={};native_error=nodal_error=feature_error=0.;baseline=[]
    def native(source,public,spec):
        nonlocal native_error,nodal_error
        key=digest(source.encode())
        if key in physics:return physics[key]
        folder=audit/'physics'/key[:20];folder.mkdir(parents=True,exist_ok=True);path=folder/'network.cir';path.write_text(source)
        m=run_sparameter_simulation(path,spec,folder/'native',cwd=ROOT);assert m['simulation_converged'] and m['point_count']==2001
        verdict=validate_bpf_metrics(m,spec);write(folder/'metrics.json',dict(metrics=m,verdict=verdict))
        with (folder/'native/sparams.tsv').open() as f:
            assert f.readline().split()==['frequency','db(s_1_1)','db(s_2_1)','db(s_2_2)']
            raw=[list(map(float,line.split())) for line in f]
        f0=public['frequency_hz'];assert len(raw)==2001 and all(len(r)==4 and all(map(math.isfinite,r)) for r in raw)
        assert all(abs(r[0]-(f0*.5+i*f0/2000))<1 for i,r in enumerate(raw))
        predicted=dev.heterogeneous_curve(source,public,[r[0] for r in raw])
        for a,b in zip(raw,predicted,strict=True):
            err=max(abs(10**(x/20)-10**(y/20)) for x,y in zip(a[1:],b[1:]));native_error=max(native_error,err);assert err<2e-7
        clean=[]
        for ratio in reference.RATIOS:
            freq=f0*ratio;mags=nodal_magnitudes(source,freq);row=min(raw,key=lambda r:abs(r[0]-freq));assert abs(row[0]-freq)<1
            err=max(abs(x-10**(y/20)) for x,y in zip(mags,row[1:]));nodal_error=max(nodal_error,err);assert err<2e-7
            clean.append([freq,*[20*math.log10(max(x,1e-150)) for x in mags]])
        physics[key]=dict(clean=clean,verdict=verdict['verdict'],folder=str(folder.relative_to(ROOT)))
        return physics[key]
    allrows={};hashes={};fit_count=forward=feature_points=measurements=0;summary_hashes={};results={};profiles={x['profile_id']:x for x in p['profiles']}
    for split in ['calibration','holdout']:
        items={i['cohort_id']:i for i in p['splits'][split]};rows=[];seen=set();split_stability=0;split_forward=0
        for item in items.values():
            phys=native(item['current_netlist'],item['public_model'],item['spec'])
            baseline.append(dict(split=split,cohort_id=item['cohort_id'],kind=item['kind'],change_fraction=item['change_fraction'],verdict=phys['verdict']))
        paths=sorted((OUT/split/'rows').glob('*/*.json'));assert len(paths)==2368
        for index,path in enumerate(paths):
            r=read(path);key=(r['profile_id'],r['cohort_id']);assert key not in seen;seen.add(key)
            item=items[key[1]];profile=profiles[key[0]];hashes[str(path.relative_to(ROOT))]=digest(path.read_bytes())
            assert r['protocol_sha256']==ph and r['policy_sha256']==(None if split=='calibration' else policy_hash)
            assert r['split']==split and r['truth']==dict(component=item['expected_component'],fault_type=item['expected_direction'])
            assert (r['family'],r['draw'],r['kind'],r['change_fraction'])==(profile['family'],profile['draw'],item['kind'],item['change_fraction'])
            ev=dev.inputs(item,profile);assert r['estimator_input']==ev['estimator_input'] and r['generation']==ev['generation']
            assert r['input_sha256']==digest(json.dumps(ev,sort_keys=True).encode())
            e=r['estimator_input'];g=r['generation'];public=item['public_model'];assert e['public']==public and set(e)=={'source','public','reference'}
            # Independent seed/perturbation reconstruction; no truth is available to the estimator.
            vectors={}
            for tag,n in [('noise',27),('drift',6),('model',12)]:
                seed=int(hashlib.sha256(f'diagnosis_dev_v1|{item["design_id"]}|{profile["draw"]}|{tag}'.encode()).hexdigest()[:16],16)
                rng=random.Random(seed);vectors[tag]=dict(seed=seed,values=[rng.gauss(0.,1.) if tag=='noise' else rng.uniform(-1.,1.) for _ in range(n)])
            assert vectors==g['vectors'];names=[x['component'] for x in public['main_components']]
            coeff={}
            for j,n in enumerate(names):coeff['RS_'+n]=vectors['model']['values'][2*j];coeff[('CP_' if n[0]=='L' else 'LS_')+n]=vectors['model']['values'][2*j+1]
            lines=[]
            for line in item['historical_netlist'].splitlines():
                t=line.split()
                if t and t[0] in coeff and profile['model_amplitude']:
                    t[3]=f'{float(t[3])*(1+profile["model_amplitude"]*coeff[t[0]]):.12g}';line=' '.join(t)
                lines.append(line)
            assert g['historical_source']=='\n'.join(lines)+'\n'
            current=lossy.observed_values(item['current_netlist'],public)
            if profile['drift_amplitude']:current={n:f'{float(current[n])*(1+profile["drift_amplitude"]*vectors["drift"]["values"][j]):.12g}' for j,n in enumerate(names)}
            assert e['source']==lossy.render(public,current)
            phys=native(g['historical_source'],public,item['spec'])
            for j,(row,sample) in enumerate(zip(phys['clean'],e['reference']['samples'],strict=True)):
                assert row[0]==sample['frequency_hz']
                for k,channel in enumerate(['s11_db','s21_db','s22_db']):
                    assert abs(row[k+1]-g['clean_curve'][j][k+1])<1e-7
                    assert sample[channel]==round(row[k+1]+profile['noise_sigma_db']*vectors['noise']['values'][3*j+k],2);measurements+=1
            b=abstention.collect(e);assert b==r['bundle']
            base=b['fit'];top=base['hypotheses'][0];features=b['features']
            f0=[]
            for source in [e['source']]+[lossy.patch(e['source'],public,h['component'],h['inferred_prefault_value']) for h in base['hypotheses'][:2]]:
                sq=0.
                for sample in e['reference']['samples']:
                    mags=nodal_magnitudes(source,sample['frequency_hz']);feature_points+=1
                    sq+=sum((20*math.log10(max(v,1e-150))-sample[k])**2 for v,k in zip(mags,['s11_db','s21_db','s22_db']))
                f0.append(math.sqrt(sq/27))
            e0,e1,e2=f0
            expected=dict(no_change_rmse_db=e0,best_rmse_db=e1,second_rmse_db=e2,gap_db=e2-e1,improvement_db=e0-e1,
                inferred_change_fraction=float(current[top['component']])/float(top['inferred_prefault_value'])-1,
                separation_ratio=e2/max(e1,.01),null_score=(e0-e1)/max(e1,.01))
            for k,v in expected.items():
                err=abs(v-features[k]);feature_error=max(feature_error,err);assert err<(1e-5 if k in ['separation_ratio','null_score'] else 1e-7)
            qualifies=features['best_rmse_db']<=.02 and features['gap_db']>=.015 and features['separation_ratio']>=3
            assert len(b['stability'])==(4 if qualifies else 0)
            seed=int(hashlib.sha256(b'abstention_v1|'+json.dumps(e,sort_keys=True,allow_nan=False).encode()).hexdigest()[:16],16);rng=random.Random(seed)
            matches=0
            for draw,st in enumerate(b['stability']):
                offsets=[.01*(1 if rng.getrandbits(1) else -1) for _ in range(27)]
                assert st['draw']==draw and st['seed']==seed and st['offsets_db']==offsets
                candidate=st['fit']['hypotheses'][0]
                ok=candidate['component']==top['component'] and candidate['current_fault_direction']==top['current_fault_direction']
                assert st['matches']==ok;matches+=ok
            assert matches==b['stability_matches']
            legacy=dict(component=top['component'],fault_type=top['current_fault_direction']) if features['best_rmse_db']<=.02 and features['second_rmse_db']>=.1 else dict(component='unknown',fault_type='unknown_direction')
            assert legacy==r['legacy_diagnosis'] and manual_score(legacy,item)==r['legacy_score']
            new=manual_decision(b,policy['parameters']);newscore=manual_score(new['diagnosis'],item)
            if split=='holdout':assert new==r['new_result'] and newscore==r['new_score']
            r['new_result']=new;r['new_score']=newscore;rows.append(r)
            calls=base['forward_model_evaluations']+sum(st['fit']['forward_model_evaluations'] for st in b['stability'])
            split_forward+=calls;split_stability+=len(b['stability']);fit_count+=1+len(b['stability'])
            if (index+1)%300==0:print(f'Audited {split} {index+1}/2368; stability fits {split_stability}',flush=True)
        assert seen=={(a,c) for a in profiles for c in items}
        summ=read(OUT/split/'summary.json');assert summ['complete'] and summ['fit_forward_evaluations']==split_forward and summ['stability_fits']==split_stability
        assert summ['no_change_forward_evaluations']==len(rows)==summ['original_fits']==summ['completed']==2368
        summary_hashes[split]=digest((OUT/split/'summary.json').read_bytes());forward+=split_forward;allrows[split]=rows
        groups={};bydesign={};paired=Counter();reason_counts=Counter();errors=[]
        for r in rows:
            keys=[r['family']+'/'+f'{abs(r["change_fraction"])*100:g}'];design=r['design_id']
            for collection,key in [(groups,keys[0]),(bydesign,design)]:
                group=collection.setdefault(key,dict(faults=0,controls=0,legacy_correct=0,legacy_wrong=0,legacy_false_alarm=0,new_correct=0,new_wrong=0,new_false_alarm=0,new_abstained_faults=0))
                group['faults']+=r['kind']=='fault';group['controls']+=r['kind']=='control'
                for label in ['legacy','new']:
                    score=r[label+'_score'];group[label+'_correct']+=score['correct'];group[label+'_wrong']+=score['wrong_diagnosis'];group[label+'_false_alarm']+=score['false_alarm']
                group['new_abstained_faults']+=r['kind']=='fault' and r['new_score']['abstained']
            for reason in r['new_result']['reasons']:reason_counts[reason]+=1
            if r['kind']=='fault':
                old=r['legacy_score']['correct'];new=r['new_score']['correct'];paired['both_correct' if old and new else 'legacy_only' if old else 'new_only' if new else 'neither_correct']+=1
            if r['new_score']['wrong_diagnosis'] or r['new_score']['false_alarm']:errors.append(dict(profile_id=r['profile_id'],cohort_id=r['cohort_id'],truth=r['truth'],result=r['new_result'],features=r['bundle']['features']))
        totals={k:sum(g[k] for g in groups.values()) for k in next(iter(groups.values()))}
        assert totals['faults']==2304 and totals['controls']==64
        assert totals['new_correct']+totals['new_wrong']+totals['new_abstained_faults']==2304
        results[split]=dict(totals=totals,groups=groups,by_design=bydesign,paired=dict(paired),reason_counts=dict(reason_counts),errors=errors)
    # Independently reproduce all 36 candidates and the deterministic selection rule.
    cal=allrows['calibration'];cal_hashes={k:v for k,v in hashes.items() if '/calibration/rows/' in k}
    assert policy['calibration_rows_sha256']==cal_hashes
    controls=[r for r in cal if r['kind']=='control'];null_max=max(0.,max(r['bundle']['features']['null_score'] for r in controls))
    assert policy['null_score_max']==null_max and policy['parameters']['null_score_min']==max(1.,1.1*null_max)
    candidates=[]
    for fit in [.01,.015,.02]:
        for gap in [.015,.03,.05,.08]:
            for ratio in [3.,5.,10.]:
                params=dict(fit_max_db=fit,gap_min_db=gap,ratio_min=ratio,null_score_min=max(1.,1.1*null_max),stability_required=4,score_floor_db=.01)
                stats=dict(correct=0,wrong=0,false_alarm=0,confirmed=0)
                for r in cal:
                    d=manual_decision(r['bundle'],params)['diagnosis'];iswrong=d['component']!='unknown' and (d['component']!=r['truth']['component'] or d['fault_type']!=r['truth']['fault_type'])
                    confirmed=d['component']!='unknown';correct=r['kind']=='fault' and confirmed and not iswrong
                    stats['correct']+=correct;stats['wrong']+=r['kind']=='fault' and iswrong;stats['false_alarm']+=r['kind']=='control' and confirmed;stats['confirmed']+=confirmed
                candidates.append(dict(parameters=params,stats=stats))
    assert candidates==policy['candidate_results'];eligible=[c for c in candidates if c['stats']['wrong']==0 and c['stats']['false_alarm']==0]
    selected=min(eligible,key=lambda c:(-c['stats']['correct'],c['parameters']['fit_max_db'],-c['parameters']['gap_min_db'],-c['parameters']['ratio_min']))
    assert selected['parameters']==policy['parameters'] and selected['stats']==policy['calibration_stats']
    assert abstention.select(cal,ph,cal_hashes)==policy
    check(p);assert digest(POLICY.read_bytes())==policy_hash
    t=results['holdout']['totals'];eligible_to_activate=t['new_wrong']==0 and t['new_false_alarm']==0 and t['new_correct']>=t['legacy_correct']
    report=dict(complete=True,issues=[],protocol_sha256=ph,policy_sha256=policy_hash,rows=4736,fit_count=fit_count,
        native_sweeps=len(physics),native_frequency_points=len(physics)*2001,nodal_generation_points=len(physics)*9,nodal_feature_points=feature_points,
        measurements_recomputed=measurements,fit_forward_evaluations=forward,max_native_magnitude_error=native_error,
        max_nodal_magnitude_error=nodal_error,max_feature_difference=feature_error,baseline=baseline,results=results,
        calibration_candidates_checked=36,eligible_to_activate=eligible_to_activate,row_sha256=hashes,summary_sha256=summary_hashes)
    write(audit/'summary.json',report)
    print(json.dumps({k:v for k,v in report.items() if k not in ['baseline','results','row_sha256']},indent=2))
    print(json.dumps({split:results[split]['totals'] for split in results},indent=2))

if __name__=='__main__':main()

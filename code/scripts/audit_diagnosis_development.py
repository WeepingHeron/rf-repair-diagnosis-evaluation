"""Independent development-data audit, native sweeps and nodal diagnostic features."""
import hashlib
import json
import math
import random
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from rf_repair import diagnosis_dev as dev, reference, lossy, robustness
from rf_repair.simulator import run_sparameter_simulation
from rf_repair.validator import validate_bpf_metrics
from audit_lossy_repair import nodal_magnitudes
from run_diagnosis_development import PP, OUT
from run_reference_robustness import read,write,digest,check


def main():
    p=read(PP);check(p);ph=digest(PP.read_bytes());s=read(OUT/'summary.json');assert s['complete'] and s['protocol_sha256']==ph
    assert p['cohort']==dev.cohort() and p['profiles']==dev.profiles()
    items={i['cohort_id']:i for i in p['cohort']};profiles={r['profile_id']:r for r in p['profiles']}
    audit=ROOT/'build/diagnosis_development_v1_audit';physics={};native_max=nodal_max=0.;baseline=[]
    def physics_check(source,public,spec):
        nonlocal native_max,nodal_max
        key=digest(source.encode())
        if key in physics:return physics[key]
        folder=audit/'physics'/key[:20];folder.mkdir(parents=True,exist_ok=True);path=folder/'network.cir';path.write_text(source)
        metrics=run_sparameter_simulation(path,spec,folder/'native',cwd=ROOT);assert metrics['simulation_converged'] and metrics['point_count']==2001
        verdict=validate_bpf_metrics(metrics,spec);write(folder/'metrics.json',dict(metrics=metrics,verdict=verdict))
        with (folder/'native/sparams.tsv').open() as f:
            assert f.readline().split()==['frequency','db(s_1_1)','db(s_2_1)','db(s_2_2)']
            raw=[list(map(float,line.split())) for line in f]
        assert len(raw)==2001 and all(len(row)==4 and all(map(math.isfinite,row)) for row in raw)
        f0=public['frequency_hz'];assert all(abs(row[0]-(f0*.5+i*f0/2000))<1 for i,row in enumerate(raw))
        calculated=dev.heterogeneous_curve(source,public,[row[0] for row in raw])
        for a,b in zip(raw,calculated,strict=True):
            error=max(abs(10**(x/20)-10**(y/20)) for x,y in zip(a[1:],b[1:]));native_max=max(native_max,error);assert error<2e-7
        clean=[]
        for ratio in reference.RATIOS:
            freq=f0*ratio;mags=nodal_magnitudes(source,freq);row=min(raw,key=lambda row:abs(row[0]-freq));assert abs(row[0]-freq)<1
            error=max(abs(x-10**(y/20)) for x,y in zip(mags,row[1:]));nodal_max=max(nodal_max,error);assert error<2e-7
            clean.append([freq,*[20*math.log10(max(x,1e-150)) for x in mags]])
        physics[key]=dict(clean=clean,verdict=verdict['verdict'],folder=str(folder.relative_to(ROOT)))
        return physics[key]
    # Record every new baseline state; performance is descriptive, never an exclusion gate.
    for item in items.values():
        r=physics_check(item['current_netlist'],item['public_model'],item['spec'])
        baseline.append(dict(cohort_id=item['cohort_id'],kind=item['kind'],change_fraction=item['change_fraction'],verdict=r['verdict']))
    paths=sorted((OUT/'rows').glob('*/*.json'));assert len(paths)==2368
    groups={};seen=set();hashes={};forward=0;measurement_count=0;fit_nodal_points=0;errors=[];rank_errors=[];allrows=[]
    feature_max_error=0.
    for index,path in enumerate(paths):
        r=read(path);key=(r['profile_id'],r['cohort_id']);assert key not in seen;seen.add(key)
        hashes[str(path.relative_to(ROOT))]=digest(path.read_bytes());item=items[key[1]];profile=profiles[key[0]]
        assert r['protocol_sha256']==ph
        assert (r['family'],r['draw'],r['kind'],r['change_fraction'])==(profile['family'],profile['draw'],item['kind'],item['change_fraction'])
        evidence=dev.inputs(item,profile);assert r['estimator_input']==evidence['estimator_input'] and r['generation']==evidence['generation']
        assert r['input_sha256']==digest(json.dumps(evidence,sort_keys=True).encode())
        e=r['estimator_input'];g=r['generation'];public=item['public_model']
        assert set(e)=={'source','public','reference'} and e['public']==public
        vectors={}
        for tag,n in [('noise',27),('drift',6),('model',12)]:
            seed=int(hashlib.sha256(f'diagnosis_dev_v1|{item["design_id"]}|{profile["draw"]}|{tag}'.encode()).hexdigest()[:16],16)
            rng=random.Random(seed);values=[rng.gauss(0.,1.) if tag=='noise' else rng.uniform(-1.,1.) for _ in range(n)]
            vectors[tag]=dict(seed=seed,values=values)
        assert vectors==g['vectors']
        names=[part['component'] for part in public['main_components']];changes={}
        for i,name in enumerate(names):
            changes['RS_'+name]=vectors['model']['values'][i*2]
            changes[('CP_' if name[0]=='L' else 'LS_')+name]=vectors['model']['values'][i*2+1]
        reconstructed=[]
        for line in item['historical_netlist'].splitlines():
            t=line.split()
            if t and t[0] in changes and profile['model_amplitude']:
                t[3]=f'{float(t[3])*(1+profile["model_amplitude"]*changes[t[0]]):.12g}';line=' '.join(t)
            reconstructed.append(line)
        assert g['historical_source']=='\n'.join(reconstructed)+'\n'
        current=lossy.observed_values(item['current_netlist'],public)
        if profile['drift_amplitude']:
            current={name:f'{float(current[name])*(1+profile["drift_amplitude"]*vectors["drift"]["values"][i]):.12g}' for i,name in enumerate(names)}
        assert e['source']==lossy.render(public,current)
        phys=physics_check(g['historical_source'],public,item['spec'])
        for i,(row,sample) in enumerate(zip(phys['clean'],e['reference']['samples'],strict=True)):
            assert sample['frequency_hz']==row[0]
            for j,k in enumerate(robustness.CHANNELS):
                assert abs(row[j+1]-g['clean_curve'][i][j+1])<1e-7
                assert sample[k]==round(row[j+1]+profile['noise_sigma_db']*vectors['noise']['values'][i*3+j],2)
                measurement_count+=1
        fit=reference.fit_reference(**e);assert fit==r['fit'];forward+=fit['forward_model_evaluations'];assert fit['forward_model_evaluations']<=402
        rmses=[]
        sources=[e['source']]+[lossy.patch(e['source'],public,h['component'],h['inferred_prefault_value']) for h in fit['hypotheses'][:2]]
        for source in sources:
            sq=0.
            for sample in e['reference']['samples']:
                mags=nodal_magnitudes(source,sample['frequency_hz']);fit_nodal_points+=1
                sq+=sum((20*math.log10(max(v,1e-150))-sample[k])**2 for v,k in zip(mags,robustness.CHANNELS))
            rmses.append(math.sqrt(sq/27))
        best,second=fit['hypotheses'][:2];e0,e1,e2=rmses
        independently=dict(no_change_rmse_db=e0,best_rmse_db=e1,second_rmse_db=e2,gap_db=e2-e1,
            improvement_db=e0-e1,inferred_change_fraction=float(current[best['component']])/float(best['inferred_prefault_value'])-1)
        for k,v in independently.items():
            error=abs(v-r['features'][k]);feature_max_error=max(feature_max_error,error);assert error<1e-7
        accepted=best['rmse_db']<=.02 and second['rmse_db']>=.10
        diag=dict(component=best['component'],fault_type=best['current_fault_direction']) if accepted else dict(component='unknown',fault_type='unknown_direction')
        assert fit['resolved_within_search']==accepted and r['diagnosis']==diag
        abstain=diag['component']=='unknown';correct=item['kind']=='fault' and diag['component']==item['expected_component'] and diag['fault_type']==item['expected_direction']
        wrong=item['kind']=='fault' and not abstain and not correct;alarm=item['kind']=='control' and not abstain
        assert r['score']==dict(correct=correct,abstained=abstain,wrong_diagnosis=wrong,false_alarm=alarm)
        rank=item['kind']=='fault' and best['component']==item['expected_component'] and best['current_fault_direction']==item['expected_direction']
        assert rank==r['top_rank_correct']
        name=profile['family']+'/'+f'{abs(item["change_fraction"])*100:g}'
        group=groups.setdefault(name,dict(family=profile['family'],magnitude_pct=abs(item['change_fraction'])*100,
            faults=0,controls=0,correct=0,abstained=0,wrong=0,false_alarm=0,top_rank_correct=0))
        if item['kind']=='fault':
            group['faults']+=1;group['correct']+=correct;group['abstained']+=abstain;group['wrong']+=wrong;group['top_rank_correct']+=rank
        else:group['controls']+=1;group['false_alarm']+=alarm
        ex=dict(profile_id=key[0],cohort_id=key[1],kind=item['kind'],expected_component=item['expected_component'],
            expected_direction=item['expected_direction'],diagnosis=diag,top=best,features=r['features'])
        if wrong or alarm:errors.append(ex)
        if item['kind']=='fault' and not rank:rank_errors.append(ex)
        allrows.append(r)
        if (index+1)%300==0:print(f'Audited {index+1}/2368; native sweeps {len(physics)}',flush=True)
    assert seen=={(a,b) for a in profiles for b in items} and groups==s['groups']
    assert sum(g['faults'] for g in groups.values())==2304 and sum(g['controls'] for g in groups.values())==64
    assert forward==s['fit_forward_evaluations'] and s['no_change_forward_evaluations']==2368
    for g in groups.values():assert g['correct']+g['wrong']+g['abstained']==g['faults']
    check(p)
    report=dict(complete=True,issues=[],protocol_sha256=ph,rows=2368,fault_rows=2304,controls=64,
        baseline=baseline,groups=groups,accepted_errors=errors,rank_errors=rank_errors,
        native_sweeps=len(physics),native_frequency_points=len(physics)*2001,nodal_generation_points=len(physics)*9,
        nodal_feature_points=fit_nodal_points,independent_measurements=measurement_count,
        max_native_magnitude_error=native_max,max_nodal_magnitude_error=nodal_max,max_feature_difference=feature_max_error,
        fit_forward_evaluations=forward,row_sha256=hashes,summary_sha256=digest((OUT/'summary.json').read_bytes()))
    write(audit/'summary.json',report)
    print(json.dumps({k:v for k,v in report.items() if k not in ['baseline','groups','accepted_errors','rank_errors','row_sha256']},indent=2))
    print('accepted_errors',len(errors),'rank_errors',len(rank_errors),flush=True)

if __name__=='__main__':main()

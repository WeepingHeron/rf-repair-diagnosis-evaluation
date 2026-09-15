"""Audit every sensitivity input/fit, with native SPICE and independent nodal physics."""
import hashlib
import json
import math
import random
import sys
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from rf_repair import robustness, reference, lossy
from rf_repair.simulator import run_sparameter_simulation
from audit_lossy_repair import nodal_magnitudes
from run_reference_robustness import PP, OUT, check, read, write, digest


def main():
    protocol=read(PP);check(protocol);ph=digest(PP.read_bytes());summary=read(OUT/'summary.json')
    assert summary['complete'] and summary['protocol_sha256']==ph
    audit=ROOT/'build/reference_robustness_v1_audit';prior=read(ROOT/'faults/holdout/reference_diagnosis_v2.json')['cases']
    bycase={c['case_id']:c for c in prior};items={c['cohort_id']:c for c in protocol['cohort']}
    scenarios={s['scenario_id']:s for s in protocol['scenarios']}
    assert protocol['cohort']==robustness.cohort(prior) and protocol['scenarios']==robustness.scenarios()
    assert len(items)==9 and sum(c['kind']=='fault' for c in items.values())==6 and len(scenarios)==105
    for item in items.values():
        orig=bycase[item['source_case_id']]
        assert item['historical_netlist']==orig['healthy_netlist']
        assert item['current_netlist']==orig['faulty_netlist' if item['kind']=='fault' else 'healthy_netlist']
    paths=sorted((OUT/'rows').glob('*/*.json'));assert len(paths)==945
    seen=set();physics={};groups={};row_hashes={};forward=0;residual_values=0;max_nodal=max_native=0.;nodal_fit_points=0
    baseline_count=0;baseline_frequency_error=0.;baseline_rmse_error=0.;allrows=[];errors=[]
    for idx,path in enumerate(paths):
        r=read(path);key=(r['scenario_id'],r['cohort_id']);assert key not in seen;seen.add(key)
        row_hashes[str(path.relative_to(ROOT))]=digest(path.read_bytes());item=items[key[1]];s=scenarios[key[0]]
        assert r['protocol_sha256']==ph and (r['family'],r['level'],r['draw'],r['kind'])==(s['family'],s['level'],s['draw'],item['kind'])
        regenerated=robustness.measurement_inputs(item,s)
        assert r['estimator_input']==regenerated['estimator_input'] and r['generation']==regenerated['generation']
        assert r['input_sha256']==digest(json.dumps(regenerated,sort_keys=True).encode())
        e=r['estimator_input'];g=r['generation'];assumed=e['public'];original=item['public_model']
        assert set(e)=={'source','public','reference'} and assumed==original
        physical=deepcopy(original);physical['frequency_hz']*=1+s['frequency_fraction']
        for k in ['inductor_rs_ohm','capacitor_rs_ohm']:physical['model'][k]*=1+s['rs_fraction']
        for k in ['inductor_cp_f','capacitor_esl_h']:physical['model'][k]*=1+s['parasitic_fraction']
        assert physical==g['physical_model']
        values=lossy.observed_values(item['historical_netlist'],original)
        assert g['historical_source']==lossy.render(physical,values)
        current=lossy.observed_values(item['current_netlist'],original)
        if s['lc_drift_fraction']:current={k:f'{float(v)*(1+s["lc_drift_fraction"]):.12g}' for k,v in current.items()}
        assert e['source']==lossy.render(original,current)
        expected_freq=[physical['frequency_hz']*ratio for ratio in reference.RATIOS]
        assert g['actual_frequencies_hz']==expected_freq
        pk=digest((g['historical_source']+json.dumps(expected_freq)).encode())
        if pk not in physics:
            folder=audit/'physics'/pk[:20];folder.mkdir(parents=True,exist_ok=True);sourcepath=folder/'historical.cir'
            sourcepath.write_text(g['historical_source'])
            spec=deepcopy(bycase[item['source_case_id']]['spec']);factor=1+s['frequency_fraction']
            spec['target_center_frequency_hz']*=factor
            spec['measurement_frequencies_hz']={k:v*factor for k,v in spec['measurement_frequencies_hz'].items()}
            native=run_sparameter_simulation(sourcepath,spec,folder/'native',cwd=ROOT)
            assert native['simulation_converged'] and native['point_count']==2001
            write(folder/'metrics.json',native)
            with (folder/'native/sparams.tsv').open() as handle:
                assert handle.readline().split()==['frequency','db(s_1_1)','db(s_2_1)','db(s_2_2)']
                raw=[list(map(float,line.split())) for line in handle]
            assert len(raw)==2001 and all(len(row)==4 and all(map(math.isfinite,row)) for row in raw)
            assert all(abs(row[0]-(physical['frequency_hz']*.5+i*physical['frequency_hz']/2000))<=1 for i,row in enumerate(raw))
            predicted=lossy.curve(physical,values,[row[0] for row in raw])
            for a,b in zip(raw,predicted,strict=True):
                error=max(abs(10**(x/20)-10**(y/20)) for x,y in zip(a[1:],b[1:]));max_native=max(max_native,error);assert error<2e-7
            clean=[]
            for row,freq in zip(g['clean_curve'],expected_freq,strict=True):
                calculated=nodal_magnitudes(g['historical_source'],freq)
                error=max(abs(x-10**(y/20)) for x,y in zip(calculated,row[1:]));max_nodal=max(max_nodal,error);assert error<2e-7
                clean.append([freq,*[20*math.log10(max(x,1e-150)) for x in calculated]])
                nearest=min(raw,key=lambda row:abs(row[0]-freq));assert abs(nearest[0]-freq)<=1
                assert max(abs(10**(x/20)-y) for x,y in zip(nearest[1:],calculated))<2e-7
            physics[pk]=dict(clean=clean,source_sha256=digest(sourcepath.read_bytes()),folder=str(folder.relative_to(ROOT)))
        seed=int(hashlib.sha256(f'robustness_v1|{item["design_id"]}|{s["draw"]}'.encode()).hexdigest()[:16],16)
        rng=random.Random(seed);normal=[rng.gauss(0,1) for _ in range(27)]
        assert seed==g['noise_seed'] and normal==g['standard_normal']
        for i,(independent,sample) in enumerate(zip(physics[pk]['clean'],e['reference']['samples'],strict=True)):
            assert sample['frequency_hz']==original['frequency_hz']*reference.RATIOS[i]
            for j,k in enumerate(robustness.CHANNELS):
                value=independent[j+1]+s['offset_db']+s['noise_sigma_db']*normal[i*3+j]
                assert round(value,2)==sample[k],(key,k,value,sample[k])
                residual_values+=1
        fit=reference.fit_reference(**e);assert fit==r['fit'];forward+=fit['forward_model_evaluations'];assert fit['forward_model_evaluations']<=402
        for h in fit['hypotheses']:
            vals=lossy.observed_values(e['source'],assumed);vals[h['component']]=h['inferred_prefault_value']
            predicted=lossy.curve(assumed,vals,[s['frequency_hz'] for s in e['reference']['samples']])
            rmse=math.sqrt(sum((v-sample[k])**2 for row,sample in zip(predicted,e['reference']['samples']) for v,k in zip(row[1:],robustness.CHANNELS))/27)
            assert abs(rmse-h['rmse_db'])<1e-12
        for h in fit['hypotheses'][:2]:
            source=lossy.patch(e['source'],assumed,h['component'],h['inferred_prefault_value']);sq=0.
            for sample in e['reference']['samples']:
                mags=nodal_magnitudes(source,sample['frequency_hz']);nodal_fit_points+=1
                sq+=sum((20*math.log10(max(v,1e-150))-sample[k])**2 for v,k in zip(mags,robustness.CHANNELS))
            assert abs(math.sqrt(sq/27)-h['rmse_db'])<1e-7
        best,second=fit['hypotheses'][:2];resolved=best['rmse_db']<=.02 and second['rmse_db']>=.10
        expected={'component':best['component'],'fault_type':best['current_fault_direction']} if resolved else {'component':'unknown','fault_type':'unknown_direction'}
        assert fit['resolved_within_search']==resolved and r['diagnosis']==expected
        correct=item['kind']=='fault' and expected['component']==item['expected_component'] and expected['fault_type']==item['expected_direction']
        abstain=expected['component']=='unknown';wrong=item['kind']=='fault' and not abstain and not correct;alarm=item['kind']=='control' and not abstain
        assert r['score']==dict(correct=correct,abstained=abstain,wrong_diagnosis=wrong,false_alarm=alarm)
        rank=item['kind']=='fault' and best['component']==item['expected_component'] and best['current_fault_direction']==item['expected_direction']
        assert r['top_rank_correct']==rank
        name=s['family']+'/'+s['level'];group=groups.setdefault(name,dict(family=s['family'],level=s['level'],faults=0,controls=0,
            correct=0,fault_abstained=0,wrong_diagnosis=0,control_abstained=0,false_alarm=0))
        if item['kind']=='fault':group['faults']+=1;group['correct']+=correct;group['fault_abstained']+=abstain;group['wrong_diagnosis']+=wrong
        else:group['controls']+=1;group['control_abstained']+=abstain;group['false_alarm']+=alarm
        if wrong or alarm:errors.append(dict(scenario_id=key[0],cohort_id=key[1],diagnosis=expected,best_rmse_db=best['rmse_db'],runner_up_rmse_db=second['rmse_db']))
        if s['family']=='baseline' and item['kind']=='fault':
            previous=bycase[item['source_case_id']]
            # Native TSV stores decimal frequency; ratio multiplication can differ by a float ULP.
            for a,b in zip(e['reference']['samples'],previous['reference_spectrum']['samples'],strict=True):
                freq_error=abs(a['frequency_hz']-b['frequency_hz']);baseline_frequency_error=max(baseline_frequency_error,freq_error)
                assert freq_error<1e-6 and all(a[k]==b[k] for k in robustness.CHANNELS)
            oldfit=previous['reference_fit']
            assert {k:v for k,v in fit.items() if k!='hypotheses'}=={k:v for k,v in oldfit.items() if k!='hypotheses'}
            for a,b in zip(fit['hypotheses'],oldfit['hypotheses'],strict=True):
                error=abs(a['rmse_db']-b['rmse_db']);baseline_rmse_error=max(baseline_rmse_error,error)
                assert error<1e-12 and {k:v for k,v in a.items() if k!='rmse_db'}=={k:v for k,v in b.items() if k!='rmse_db'}
            baseline_count+=1
        allrows.append(r)
        if (idx+1)%150==0:print(f'Audited {idx+1}/945 fits; native physics {len(physics)}',flush=True)
    assert seen=={(s,i) for s in scenarios for i in items} and baseline_count==6
    assert sum(g['faults'] for g in groups.values())==630 and sum(g['controls'] for g in groups.values())==315
    for g in groups.values():
        assert g['correct']+g['wrong_diagnosis']+g['fault_abstained']==g['faults']
        assert g['false_alarm']+g['control_abstained']==g['controls']
    assert groups==summary['groups'] and forward==summary['forward_model_evaluations']
    check(protocol)
    report=dict(complete=True,issues=[],protocol_sha256=ph,rows=945,fault_rows=630,control_rows=315,
        native_physics_sweeps=len(physics),native_frequency_points=len(physics)*2001,
        nodal_generation_points=len(physics)*9,nodal_fit_points=nodal_fit_points,
        measurements_independently_recomputed=residual_values,fit_forward_evaluations=forward,
        baseline_fits_matched=baseline_count,max_native_magnitude_error=max_native,max_nodal_magnitude_error=max_nodal,
        baseline_max_frequency_error_hz=baseline_frequency_error,baseline_max_rmse_difference_db=baseline_rmse_error,
        groups=groups,wrong_diagnoses_and_false_alarms=errors,row_sha256=row_hashes,
        top_rank_correct_faults=sum(r['top_rank_correct'] for r in allrows),
        summary_sha256=digest((OUT/'summary.json').read_bytes()))
    write(audit/'summary.json',report)
    print(json.dumps({k:v for k,v in report.items() if k not in ['groups','row_sha256','wrong_diagnoses_and_false_alarms']},indent=2))

if __name__=='__main__':main()

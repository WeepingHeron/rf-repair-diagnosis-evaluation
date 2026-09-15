"""Audit baseline-measurement provenance, cohort amendment, inverse fit and every API response."""
import json
import math
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from rf_repair import reference,lossy
from rf_repair.simulator import run_sparameter_simulation
from rf_repair.validator import validate_bpf_metrics
from run_budget_transfer import read,digest,validate_proposal
from run_reference_diagnosis_v2 import check,FIELDS
from audit_lossy_repair import nodal_magnitudes
from audit_budget_transfer import passes

def main():
    pp=ROOT/'experiments/reference_diagnosis_v2.json';protocol=read(pp);check(protocol);phash=digest(pp.read_bytes())
    old=read(ROOT/'experiments/reference_diagnosis_v1.json');assert old['status']=='ABORTED_PRECHECK' and old['api_calls']==0
    for f,h in old['file_sha256'].items():assert digest((ROOT/f).read_bytes())==h
    original=read(ROOT/old['manifest'])['cases'];cs=read(ROOT/protocol['manifest'])['cases'];byid={c['case_id']:c for c in cs}
    screen=read(ROOT/'build/reference_diagnosis_v1_prescreen/summary.json')
    eligible={r['case_id'] for r in screen if r['healthy']=='PASS' and r['faulty']=='FAIL' and r['oracle']=='PASS'}
    assert set(byid)==eligible and len(eligible)==6
    cohort=read(ROOT/'build/reference_diagnosis_v2_prescreen/cohort.json');assert cohort['included']==sorted(eligible)
    assert set(cohort['excluded'])==set(old['excluded_case_ids']) and cohort['selection_made_before_fit_or_llm']
    output=ROOT/'build/experiments/reference_diagnosis_v2';summary=read(output/'summary.json');assert summary['complete']
    audit=ROOT/'build/reference_diagnosis_v2_audit';audit.mkdir(parents=True,exist_ok=True)
    count=0;nodes=0;max_nodal=max_abcd=0.;spectral_values=0
    def verify(path,folder,m,spec,public):
        nonlocal count,nodes,max_nodal,max_abcd
        source=path.read_text();rows=[]
        with (folder/'sparams.tsv').open() as f:
            assert f.readline().split()==['frequency','db(s_1_1)','db(s_2_1)','db(s_2_2)']
            for line in f:
                r=list(map(float,line.split()));assert len(r)==4 and all(map(math.isfinite,r));rows.append(r)
        assert m['simulation_converged'] and len(rows)==m['point_count']==2001;f0=spec['target_center_frequency_hz']
        assert all(abs(r[0]-(f0*.5+i*f0/2000))<=1 for i,r in enumerate(rows))
        peak=max(rows,key=lambda r:r[2]);assert m['peak_s21_db']==peak[2] and m['peak_frequency_hz']==peak[0]
        assert m['peak_frequency_relative_error']==abs(peak[0]-f0)/f0
        for n,f in spec['measurement_frequencies_hz'].items():
            r=min(rows,key=lambda r:abs(r[0]-f));assert m['samples'][n]==dict(requested_frequency_hz=float(f),measured_frequency_hz=r[0],s11_db=r[1],s21_db=r[2],s22_db=r[3])
        analytic=lossy.curve(public,lossy.observed_values(source,public),[r[0] for r in rows])
        for native,predicted in zip(rows,analytic,strict=True):
            err=max(abs(10**(a/20)-10**(b/20)) for a,b in zip(native[1:],predicted[1:]));max_abcd=max(max_abcd,err);assert err<2e-7
        for ratio in reference.RATIOS:
            r=min(rows,key=lambda r:abs(r[0]-f0*ratio));calc=nodal_magnitudes(source,r[0])
            err=max(abs(a-10**(b/20)) for a,b in zip(calc,r[1:]));max_nodal=max(max_nodal,err);assert err<2e-7;nodes+=1
        fresh=run_sparameter_simulation(path,spec,audit/'native_replay'/path.relative_to(ROOT).with_suffix(''),cwd=ROOT);assert fresh==m
        count+=1;return rows
    regenerated={c['case_id']:c for c in reference.cases()}
    for c in original:
        assert all(c[k]==v for k,v in regenerated[c['case_id']].items())
        folder=ROOT/'build/reference_diagnosis_v1_prescreen'/c['case_id'];verdicts={}
        for label,source in [('healthy',c['healthy_netlist']),('faulty',c['faulty_netlist']),('oracle',c['healthy_netlist'])]:
            path=folder/f'{label}.cir';r=read(folder/f'{label}.json');assert path.read_text()==source and digest(source.encode())==r['source_sha256']
            raw=verify(path,folder/label,r['metrics'],c['spec'],c['public_model'])
            assert r['verdict']==validate_bpf_metrics(r['metrics'],c['spec']) and passes(r['metrics'],c['spec'])==(r['verdict']['verdict']=='PASS')
            verdicts[label]=r['verdict']['verdict']
            if label=='faulty':assert r['metrics']==c['initial_metrics']
            if label in ['healthy','faulty']:
                spectrum=c['reference_spectrum'] if label=='healthy' else c['current_spectrum']
                assert spectrum['quantization_db']==.01 and spectrum['origin']=='Synthetic ngspice emulation, not hardware measurement'
                extracted=[]
                for ratio in reference.RATIOS:
                    row=min(raw,key=lambda r:abs(r[0]-c['public_model']['frequency_hz']*ratio))
                    extracted.append(dict(frequency_hz=row[0],**{k:round(v,2) for k,v in zip(['s11_db','s21_db','s22_db'],row[1:])}))
                assert spectrum['samples']==extracted;spectral_values+=27
        assert next(r for r in screen if r['case_id']==c['case_id'])=={'case_id':c['case_id'],**verdicts}
    assert len(original)==8
    forward=0;det_correct=0;fit_recovered=0;fits=[]
    for c in cs:
        orig=next(r for r in original if r['case_id']==c['case_id']);assert all(c[k]==v for k,v in orig.items())
        fit=reference.fit_reference(c['faulty_netlist'],c['public_model'],c['reference_spectrum']);assert fit==c['reference_fit'];forward+=fit['forward_model_evaluations']
        assert fit['forward_model_evaluations']<=402
        for h in fit['hypotheses']:
            values=lossy.observed_values(c['faulty_netlist'],c['public_model']);values[h['component']]=h['inferred_prefault_value']
            predicted=lossy.curve(c['public_model'],values,[s['frequency_hz'] for s in c['reference_spectrum']['samples']])
            mse=sum((a-s[k])**2 for row,s in zip(predicted,c['reference_spectrum']['samples']) for a,k in zip(row[1:],['s11_db','s21_db','s22_db']))/27
            assert abs(math.sqrt(mse)-h['rmse_db'])<1e-12
        top=fit['hypotheses'][0];resolved=top['rmse_db']<=.02 and fit['hypotheses'][1]['rmse_db']>=.10;assert resolved==fit['resolved_within_search']
        diag={'component':top['component'],'fault_type':top['current_fault_direction']} if resolved else {'component':'unknown','fault_type':'unknown_direction'}
        evaluator=c['fit_evaluator_only'];assert evaluator['diagnosis']==diag
        correct=diag['component']==c['component'] and diag['fault_type']==c['fault_type'];assert correct==evaluator['diagnosed'];det_correct+=correct
        folder=ROOT/'build/reference_diagnosis_v2_prescreen'/c['case_id'];path=folder/'fit_reconstruction.cir';r=read(folder/'fit_reconstruction.json')
        source=lossy.patch(c['faulty_netlist'],c['public_model'],top['component'],top['inferred_prefault_value'])
        assert path.read_text()==source and digest(source.encode())==r['source_sha256']
        verify(path,folder/'fit_reconstruction',r['metrics'],c['spec'],c['public_model'])
        assert evaluator['metrics']==r['metrics'] and evaluator['verdict']==r['verdict']==validate_bpf_metrics(r['metrics'],c['spec'])
        fit_recovered+=passes(r['metrics'],c['spec'])
        fits.append({'case_id':c['case_id'],'diagnosed':correct,'best_rmse_db':top['rmse_db'],'runner_up_rmse_db':fit['hypotheses'][1]['rmse_db']})
    expected={(cond,c['case_id'],rep) for c in cs for cond in reference.CONDITIONS for rep in [1,2]};seen=set();ids=set();bykey={};rows=[]
    for path in sorted(output.glob('*/*/repeat_*/result.json')):
        r=read(path);key=(r['condition'],r['case_id'],r['repetition']);assert key in expected and key not in seen;seen.add(key);bykey[key]=r
        c=byid[r['case_id']];request=read(path.parent/'request.json');response=read(path.parent/'response.json')
        base={'faulty_netlist':c['faulty_netlist'],'public_main_component_model':c['public_model'],'target_specification':c['spec'],
            'initial_simulation':c['initial_metrics'],'current_spectrum':c['current_spectrum']}
        if r['condition'] in reference.CONDITIONS[1:]:base['prefault_reference_spectrum']=c['reference_spectrum']
        if r['condition']==reference.CONDITIONS[2]:base['reference_inverse_fit']=c['reference_fit']
        assert request['input']==base and request['input_sha256']==digest(json.dumps(base,sort_keys=True).encode())
        assert request['protocol_sha256']==phash and request['instructions_sha256']==digest(reference.PROMPT.encode())
        assert (request['condition'],request['case_id'],request['repetition'])==key
        assert response['id']==r['response_id'] and r['response_id'] not in ids;ids.add(r['response_id'])
        assert response['model']==r['model']==protocol['model'] and response['usage']==r['usage']
        assert response['status']==r['response_status'] and response.get('incomplete_details')==r['incomplete_details']
        text=''.join(c['text'] for item in response['output'] if item['type']=='message' for c in item['content'] if c['type']=='output_text')
        assert text==r['output_text'] and digest(text.encode())==r['output_text_sha256']
        valid=True
        try:
            assert response['status']=='completed';proposal=json.loads(text);validate_proposal(proposal,reference.schema(c['public_model']))
            if proposal['component']=='unknown' and proposal['fault_type']!='unknown_direction':raise ValueError('inconsistent abstention')
        except (AssertionError,ValueError,TypeError):valid=False
        assert r['valid_response']==valid
        if valid:
            assert r['proposal']==proposal;loc=proposal['component']==c['component']
            scores={'localized':loc,'diagnosed':loc and proposal['fault_type']==c['fault_type'],'abstained':proposal['component']=='unknown',
                'direction_unknown':proposal['fault_type']=='unknown_direction','false_location':proposal['component'] not in {'unknown',c['component']},
                'matches_fit_component':proposal['component']==c['reference_fit']['hypotheses'][0]['component']}
            assert all(r[k]==v for k,v in scores.items())
        else:assert all(r[k] is False for k in FIELDS)
        rows.append(r)
    assert seen==expected and len(rows)==len(ids)==summary['api_attempts']==36
    assert len(list(output.glob('*/*/repeat_*/request.json')))==36
    result={'complete':True,'protocol_sha256':phash,'v1_status':'ABORTED_PRECHECK','screened_cases':8,'included_cases':6,'excluded_cases':cohort['excluded'],
        'audited_responses':len(ids),'fresh_native_replays':count,'nodal_measurement_points':nodes,'max_nodal_magnitude_error':max_nodal,
        'max_abcd_magnitude_error':max_abcd,'rounded_measurements_verified':spectral_values,'forward_fit_evaluations':forward,
        'deterministic_diagnosed':det_correct,'fit_reconstruction_recovered':fit_recovered,'fits':fits,'conditions':{},'paired_joint':{},'by_case':[],'issues':[]}
    for cond in reference.CONDITIONS:
        rs=[r for r in rows if r['condition']==cond];stats={k:sum(r[k] for r in rs) for k in FIELDS}
        stats.update(completed=len(rs),valid_responses=sum(r['valid_response'] for r in rs),api_schema_failures=sum(not r['valid_response'] for r in rs))
        assert stats['localized']+stats['false_location']+stats['abstained']+stats['api_schema_failures']==12
        for k,v in stats.items():assert v==summary['conditions'][cond][k]
        cost=0.;prices=protocol['prices_per_million']
        for r in rs:
            u=r['usage'];d=u.get('input_tokens_details',{});i=u['input_tokens'];ca=d.get('cached_tokens',0);wr=d.get('cache_write_tokens',0);assert 0<=ca+wr<=i
            cost+=((i-ca-wr)*prices['input']+ca*prices['cached_input']+wr*prices['cache_write']+u['output_tokens']*prices['output'])/1e6
        assert abs(cost-summary['conditions'][cond]['estimated_api_cost_usd'])<1e-10
        stats['estimated_api_cost_usd']=cost;stats['incomplete_responses']=sum(r['response_status']=='incomplete' for r in rs)
        result['conditions'][cond]=stats
    for a,b in zip(reference.CONDITIONS,reference.CONDITIONS[1:]):
        paired={'both_correct':0,'first_only_correct':0,'second_only_correct':0,'neither_correct':0}
        for c in cs:
            for rep in [1,2]:
                x=bykey[(a,c['case_id'],rep)]['diagnosed'];y=bykey[(b,c['case_id'],rep)]['diagnosed']
                k='both_correct' if x and y else 'first_only_correct' if x else 'second_only_correct' if y else 'neither_correct';paired[k]+=1
        assert sum(paired.values())==12;result['paired_joint'][a+'_vs_'+b]=paired
    for c in cs:
        row={'case_id':c['case_id'],'fault_component':c['component'],'fault_type':c['fault_type']}
        for cond in reference.CONDITIONS:
            rs=[bykey[(cond,c['case_id'],rep)] for rep in [1,2]]
            row[cond]={'diagnosed':sum(r['diagnosed'] for r in rs),'abstained':sum(r['abstained'] for r in rs),
                'false_location':sum(r['false_location'] for r in rs),'responses':[r.get('proposal') for r in rs]}
        result['by_case'].append(row)
    (audit/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='by_case'},indent=2))

if __name__=='__main__':main()

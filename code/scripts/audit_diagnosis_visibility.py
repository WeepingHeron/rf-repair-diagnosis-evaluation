"""Audit the complete paired diagnosis experiment and its shared physical repair stage."""
import json
import math
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from rf_repair import diagnosis,lossy
from rf_repair.simulator import run_sparameter_simulation
from rf_repair.validator import validate_bpf_metrics
from run_budget_transfer import read,digest,validate_proposal
from run_diagnosis_visibility import check,FIELDS
from audit_lossy_repair import nodal_magnitudes
from audit_budget_transfer import passes


def main():
    pp=ROOT/'experiments/diagnosis_visibility_v1.json';protocol=read(pp);check(protocol);phash=digest(pp.read_bytes())
    cs=read(ROOT/protocol['manifest'])['cases'];byid={c['case_id']:c for c in cs};assert len(byid)==8
    output=ROOT/'build/experiments/diagnosis_visibility_v1';summary=read(output/'summary.json');assert summary['complete']
    audit=ROOT/'build/diagnosis_visibility_v1_audit';audit.mkdir(parents=True,exist_ok=True)
    physics=0;nodal_points=0;max_nodal=max_abcd=0.;forward=0
    for c,regenerated in zip(cs,diagnosis.cases(),strict=True):
        assert all(c[k]==v for k,v in regenerated.items())
        searched=lossy.numerical_search(c['faulty_netlist'],c['public_model'],c['spec'])
        assert searched==c['numerical_search'];forward+=searched['forward_model_evaluations']
        folder=ROOT/'build/diagnosis_visibility_v1_prescreen'/c['case_id'];top=searched['candidates'][0]
        expected={'healthy':c['healthy_netlist'],'faulty':c['faulty_netlist'],
            'oracle':lossy.patch(c['faulty_netlist'],c['public_model'],c['component'],c['healthy_value']),
            'shared_repair':lossy.patch(c['faulty_netlist'],c['public_model'],top['component'],top['proposed_value'])}
        assert expected['oracle']==expected['healthy']
        for label,source in expected.items():
            path=folder/f'{label}.cir';r=read(folder/f'{label}.json');assert path.read_text()==source and r['source_sha256']==digest(source.encode())
            m=r['metrics'];assert m['simulation_converged'];rows=[]
            with (folder/label/'sparams.tsv').open() as f:
                assert f.readline().split()==['frequency','db(s_1_1)','db(s_2_1)','db(s_2_2)']
                for line in f:
                    row=list(map(float,line.split()));assert len(row)==4 and all(map(math.isfinite,row));rows.append(row)
            assert len(rows)==m['point_count']==2001;f0=c['spec']['target_center_frequency_hz']
            assert all(abs(row[0]-(f0*.5+i*f0/2000))<=1 for i,row in enumerate(rows))
            peak=max(rows,key=lambda r:r[2]);assert m['peak_frequency_hz']==peak[0] and m['peak_s21_db']==peak[2]
            assert m['peak_frequency_relative_error']==abs(peak[0]-f0)/f0
            prediction=lossy.curve(c['public_model'],lossy.observed_values(source,c['public_model']),[r[0] for r in rows])
            for native,calc in zip(rows,prediction,strict=True):
                err=max(abs(10**(a/20)-10**(b/20)) for a,b in zip(native[1:],calc[1:]));max_abcd=max(max_abcd,err);assert err<2e-7
            for name,f in c['spec']['measurement_frequencies_hz'].items():
                row=min(rows,key=lambda r:abs(r[0]-f))
                assert m['samples'][name]==dict(requested_frequency_hz=float(f),measured_frequency_hz=row[0],s11_db=row[1],s21_db=row[2],s22_db=row[3])
                independent=nodal_magnitudes(source,row[0]);err=max(abs(a-10**(b/20)) for a,b in zip(independent,row[1:]))
                max_nodal=max(max_nodal,err);assert err<2e-7;nodal_points+=1
            assert r['verdict']==validate_bpf_metrics(m,c['spec']) and passes(m,c['spec'])==(r['verdict']['verdict']=='PASS')
            if label in {'healthy','oracle'}:assert passes(m,c['spec'])
            if label=='faulty':assert not passes(m,c['spec']) and m==c['initial_metrics']
            if label=='shared_repair':
                assert c['shared_repair_evaluator_only']=={'proposal':{k:top[k] for k in ['component','proposed_value']},'metrics':m,'verdict':r['verdict']}
            fresh=run_sparameter_simulation(path,c['spec'],audit/'native_replay'/c['case_id']/label,cwd=ROOT)
            assert fresh==m;physics+=1
        print(json.dumps({'audited_physical_case':c['case_id']}),flush=True)
    expected={(condition,c['case_id'],rep) for c in cs for condition in diagnosis.CONDITIONS for rep in [1,2]}
    seen=set();ids=set();rows=[];bykey={}
    for path in sorted(output.glob('*/*/repeat_*/result.json')):
        r=read(path);key=(r['condition'],r['case_id'],r['repetition']);assert key in expected and key not in seen;seen.add(key);bykey[key]=r
        c=byid[r['case_id']];request=read(path.parent/'request.json');response=read(path.parent/'response.json')
        assert (request['condition'],request['case_id'],request['repetition'])==key
        base={'faulty_netlist':c['faulty_netlist'],'public_main_component_model':c['public_model'],
            'target_specification':c['spec'],'initial_simulation':c['initial_metrics']}
        if r['condition']=='diagnose_with_candidates':base['numerical_search']=c['numerical_search']
        assert request['input']==base and request['input_sha256']==digest(json.dumps(base,sort_keys=True).encode())
        assert request['instructions_sha256']==digest(diagnosis.PROMPT.encode()) and request['protocol_sha256']==phash
        assert response['id']==r['response_id'] and r['response_id'] not in ids;ids.add(r['response_id'])
        assert response['model']==r['model']==protocol['model'] and response['usage']==r['usage']
        assert response['status']==r['response_status'] and response.get('incomplete_details')==r['incomplete_details']
        text=''.join(t['text'] for item in response['output'] if item['type']=='message' for t in item['content'] if t['type']=='output_text')
        assert text==r['output_text'] and digest(text.encode())==r['output_text_sha256']
        valid=True
        try:
            assert response['status']=='completed'
            proposal=json.loads(text);validate_proposal(proposal,diagnosis.schema(c['public_model']))
            if proposal['component']=='unknown' and proposal['fault_type']!='unknown_direction':raise ValueError('inconsistent abstention')
        except (AssertionError,ValueError,TypeError):valid=False
        assert r['valid_response']==valid
        if valid:
            assert r['proposal']==proposal
            localized=proposal['component']==c['component'];top=c['numerical_search']['candidates'][0]['component']
            expected_scores={'localized':localized,'diagnosed':localized and proposal['fault_type']==c['fault_type'],
                'abstained':proposal['component']=='unknown','direction_unknown':proposal['fault_type']=='unknown_direction',
                'false_location':proposal['component'] not in {c['component'],'unknown'},'matches_top_repair_component':proposal['component']==top}
            assert all(r[k]==v for k,v in expected_scores.items())
        else:assert all(r[k] is False for k in FIELDS)
        rows.append(r)
    assert seen==expected and len(rows)==len(ids)==summary['api_attempts']==32
    assert len(list(output.glob('*/*/repeat_*/request.json')))==32
    result={'complete':True,'protocol_sha256':phash,'audited_responses':len(ids),'fresh_native_replays':physics,
        'nodal_measurement_points':nodal_points,'max_nodal_magnitude_error':max_nodal,'max_abcd_magnitude_error':max_abcd,
        'reproduced_forward_evaluations':forward,'shared_repair_recovered':sum(c['shared_repair_evaluator_only']['verdict']['verdict']=='PASS' for c in cs),
        'conditions':{},'paired_joint':{'both_correct':0,'before_only_correct':0,'with_only_correct':0,'neither_correct':0},'by_case':[],'issues':[]}
    for condition in diagnosis.CONDITIONS:
        rs=[r for r in rows if r['condition']==condition]
        stats={k:sum(r[k] for r in rs) for k in FIELDS};stats['api_schema_failures']=sum(not r['valid_response'] for r in rs)
        assert stats['localized']+stats['false_location']+stats['abstained']+stats['api_schema_failures']==16
        stats['completed']=len(rs);stats['valid_responses']=sum(r['valid_response'] for r in rs)
        for k,v in stats.items():assert summary['conditions'][condition][k]==v
        stats['incomplete_responses']=sum(r['response_status']=='incomplete' for r in rs)
        cost=0.;prices=protocol['prices_per_million']
        for r in rs:
            u=r['usage'];d=u.get('input_tokens_details',{});i=u['input_tokens'];cached=d.get('cached_tokens',0);written=d.get('cache_write_tokens',0)
            assert 0<=cached+written<=i
            cost+=((i-cached-written)*prices['input']+cached*prices['cached_input']+written*prices['cache_write']+u['output_tokens']*prices['output'])/1e6
        assert abs(cost-summary['conditions'][condition]['estimated_api_cost_usd'])<1e-10
        stats['estimated_api_cost_usd']=cost
        stats['false_matches_top']=sum(r['false_location'] and r['matches_top_repair_component'] for r in rs)
        result['conditions'][condition]=stats
    for c in cs:
        row={'case_id':c['case_id'],'fault_component':c['component'],'top_repair_component':c['numerical_search']['candidates'][0]['component']}
        for condition in diagnosis.CONDITIONS:
            rs=[bykey[(condition,c['case_id'],rep)] for rep in [1,2]]
            row[condition]={'diagnosed':sum(r['diagnosed'] for r in rs),'localized':sum(r['localized'] for r in rs),
                'abstained':sum(r['abstained'] for r in rs),'false_location':sum(r['false_location'] for r in rs),
                'responses':[r.get('proposal') for r in rs]}
        for rep in [1,2]:
            a=bykey[(diagnosis.CONDITIONS[0],c['case_id'],rep)]['diagnosed'];b=bykey[(diagnosis.CONDITIONS[1],c['case_id'],rep)]['diagnosed']
            name='both_correct' if a and b else 'before_only_correct' if a else 'with_only_correct' if b else 'neither_correct'
            result['paired_joint'][name]+=1
        result['by_case'].append(row)
    assert sum(result['paired_joint'].values())==16
    result['audit_code_sha256']=digest(Path(__file__).read_bytes())
    (audit/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='by_case'},indent=2))

if __name__=='__main__':main()

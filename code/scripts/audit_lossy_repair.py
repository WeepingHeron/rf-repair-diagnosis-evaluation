"""Independent nodal physics, frozen-input, native replay and API provenance audit."""
from __future__ import annotations
import json
import math
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from rf_repair import lossy
from rf_repair.netlist import spice_value_si
from rf_repair.simulator import run_sparameter_simulation
from rf_repair.validator import validate_bpf_metrics
from run_budget_transfer import read,digest,validate_proposal
from audit_budget_transfer import passes


def nodal_magnitudes(source,frequency):
    """Actual flat netlist stamping; no ladder order, ABCD, synthesis or manifest values."""
    elements=[];ports={};nodes=set()
    for line in source.splitlines():
        t=line.split()
        if not t:continue
        if t[0][0] in 'RLC':
            assert len(t)==4
            elements.append(t);nodes.update(t[1:3])
        elif t[0].startswith('VPORT'):
            assert t[2]=='0'
            ports[int(t[t.index('portnum')+1])]=(t[1],float(t[t.index('z0')+1]));nodes.add(t[1])
    nodes.discard('0'); names=sorted(nodes);positions={n:i for i,n in enumerate(names)}; n=len(names)
    assert set(ports)=={1,2}
    matrix=[[0j]*(n+2) for _ in range(n)];w=2*math.pi*frequency
    for t in elements:
        v=spice_value_si(t[3]); y=1/v if t[0][0]=='R' else 1/complex(0,w*v) if t[0][0]=='L' else complex(0,w*v)
        a=positions.get(t[1]);b=positions.get(t[2])
        if a is not None:matrix[a][a]+=y
        if b is not None:matrix[b][b]+=y
        if a is not None and b is not None:matrix[a][b]-=y;matrix[b][a]-=y
    for port,(node,z0) in ports.items():
        i=positions[node];matrix[i][i]+=1/z0;matrix[i][n+port-1]=2/math.sqrt(z0)
    for k in range(n):
        pivot=max(range(k,n),key=lambda r:abs(matrix[r][k]));assert abs(matrix[pivot][k])>1e-20
        matrix[k],matrix[pivot]=matrix[pivot],matrix[k]
        scale=matrix[k][k]
        for j in range(k,n+2):matrix[k][j]/=scale
        for i in range(k+1,n):
            factor=matrix[i][k]
            for j in range(k,n+2):matrix[i][j]-=factor*matrix[k][j]
    values=[[0j,0j] for _ in range(n)]
    for i in reversed(range(n)):
        for port in range(2):values[i][port]=matrix[i][n+port]-sum(matrix[i][j]*values[j][port] for j in range(i+1,n))
    p1,z1=ports[1];p2,z2=ports[2]
    return (abs(values[positions[p1]][0]/math.sqrt(z1)-1),
            abs(values[positions[p2]][0]/math.sqrt(z2)),abs(values[positions[p2]][1]/math.sqrt(z2)-1))


def main():
    pp=ROOT/'experiments/lossy_repair_v1.json';protocol=read(pp);phash=digest(pp.read_bytes())
    for p,h in protocol['file_sha256'].items():assert digest((ROOT/p).read_bytes())==h,p
    cases=read(ROOT/protocol['manifest'])['cases']; byid={c['case_id']:c for c in cases};assert len(byid)==8
    output=ROOT/'build/experiments/lossy_repair_v1';summary=read(output/'summary.json');assert summary['complete']
    audit=ROOT/'build/lossy_repair_v1_audit';audit.mkdir(parents=True,exist_ok=True)
    physics_records=0;nodal_points=0;raw_points=0;replays=0;max_nodal=0.;max_abcd=0.
    def verify(sourcepath,tsv,metrics,spec,public=None,replay=False):
        nonlocal physics_records,nodal_points,raw_points,replays,max_nodal,max_abcd
        source=sourcepath.read_text();rows=[]
        with tsv.open() as f:
            assert f.readline().split()==['frequency','db(s_1_1)','db(s_2_1)','db(s_2_2)']
            for line in f:
                r=list(map(float,line.split()));assert len(r)==4 and all(map(math.isfinite,r));rows.append(r)
        assert len(rows)==2001; f0=spec['target_center_frequency_hz']
        assert all(abs(r[0]-(f0*.5+i*f0/2000))<=1 for i,r in enumerate(rows))
        assert metrics['simulation_converged'] and metrics['point_count']==2001
        peak=max(rows,key=lambda r:r[2]);assert metrics['peak_frequency_hz']==peak[0] and metrics['peak_s21_db']==peak[2]
        assert metrics['peak_frequency_relative_error']==abs(peak[0]-f0)/f0
        for name,freq in spec['measurement_frequencies_hz'].items():
            r=min(rows,key=lambda r:abs(r[0]-freq));s=metrics['samples'][name]
            assert s==dict(requested_frequency_hz=float(freq),measured_frequency_hz=r[0],s11_db=r[1],s21_db=r[2],s22_db=r[3])
            expected=nodal_magnitudes(source,r[0]);measured=[10**(v/20) for v in r[1:]]
            err=max(abs(a-b) for a,b in zip(expected,measured));max_nodal=max(max_nodal,err);assert err<2e-7,(sourcepath,err)
            nodal_points+=1
        if public is not None:
            values=lossy.observed_values(source,public);curve=lossy.curve(public,values,[r[0] for r in rows])
            for observed,expected in zip(rows,curve,strict=True):
                error=max(abs(10**(a/20)-10**(b/20)) for a,b in zip(observed[1:],expected[1:]));max_abcd=max(max_abcd,error)
                assert error<2e-7,(sourcepath,error)
        if replay:
            fresh=run_sparameter_simulation(sourcepath,spec,audit/'native_replay'/sourcepath.relative_to(ROOT).with_suffix(''),cwd=ROOT)
            assert fresh==metrics,sourcepath;replays+=1
        physics_records+=1;raw_points+=len(rows)
    # Every development configuration and ablation has raw-data and independent nodal checks.
    dev=read(ROOT/'build/lossy_repair_v1_development/summary.json');dspec=dev['design']['spec']
    for path in sorted((ROOT/'build/lossy_repair_v1_development').glob('*.cir')):
        r=read(path.with_suffix('.json'));assert r['source_sha256']==digest(path.read_bytes())
        verify(path,path.with_suffix('')/'sparams.tsv',r['metrics'],dspec,replay=True)
        assert r['verdict']==validate_bpf_metrics(r['metrics'],dspec)
    assert len(dev['ablations'])==16
    # All predefined holdout designs, initial faults and oracles, with exact regeneration.
    seen_designs=set();search_evaluations=0
    for case in cases:
        d=case['design_evaluator_only'];i=int(case['design_id'][-1])-1
        assert d==lossy.make_design(*lossy.HOLDOUT[i],202609071+i,case['design_id'],.02)
        assert case['public_model']==d['public_model'] and case['spec']==d['spec']
        assert case['healthy_netlist']==lossy.render(d['public_model'],d['healthy_values'])
        component=case['component']; assert case['healthy_value']==d['healthy_values'][component]
        expected_fault=lossy.patch(case['healthy_netlist'],case['public_model'],component,f'{float(case["healthy_value"])*case["multiplier"]:.12g}')
        assert expected_fault==case['faulty_netlist'] and case['eligible']
        assert lossy.patch(expected_fault,case['public_model'],component,case['healthy_value'])==case['healthy_netlist']
        folder=ROOT/'build/lossy_repair_v1_prescreen'/case['design_id'];j=int(case['case_id'][-1])
        labels=[(f'fault_{j}',case['faulty_netlist'],'FAIL'),(f'oracle_{j}',case['healthy_netlist'],'PASS')]
        if case['design_id'] not in seen_designs:labels.append(('healthy',case['healthy_netlist'],'PASS'));seen_designs.add(case['design_id'])
        for label,source,verdict in labels:
            path=folder/f'{label}.cir';r=read(folder/f'{label}.json')
            assert path.read_text()==source and r['source_sha256']==digest(source.encode())
            verify(path,folder/label/'sparams.tsv',r['metrics'],case['spec'],case['public_model'],replay=True)
            assert r['verdict']==validate_bpf_metrics(r['metrics'],case['spec']) and r['verdict']['verdict']==verdict
            if label.startswith('fault'):assert r['metrics']==case['initial_metrics']
        regenerated=lossy.numerical_search(case['faulty_netlist'],case['public_model'],case['spec'])
        assert regenerated==case['numerical_search'];search_evaluations+=regenerated['forward_model_evaluations']
        assert regenerated['forward_model_evaluations']<=354
        print(json.dumps({'audited_search_case':case['case_id']}),flush=True)
    baseline_finals=[];baseline_rows=[]
    for case in cases:
        for method in ['ideal_resonance','numerical_search']:
            folder=ROOT/'build/lossy_repair_v1_baselines'/method/case['case_id'];final=read(folder/'final.json')
            candidates=lossy.ideal_candidates(case['faulty_netlist'],case['public_model']) if method=='ideal_resonance' else case['numerical_search']['candidates']
            rows=[]
            for i in range(1,final['simulations']+1):
                r=read(folder/f'iteration_{i}.json');assert r['protocol_sha256']==phash
                proposal={k:candidates[i-1][k] for k in ['component','proposed_value']};assert r['proposal']==proposal
                source=lossy.patch(case['faulty_netlist'],case['public_model'],proposal['component'],proposal['proposed_value'])
                path=folder/f'repaired_{i}.cir';assert path.read_text()==source and r['source_sha256']==digest(source.encode())
                verify(path,folder/f'simulation_{i}/sparams.tsv',r['metrics'],case['spec'],case['public_model'],replay=True)
                assert r['verdict']==validate_bpf_metrics(r['metrics'],case['spec']) and r['recovered']==passes(r['metrics'],case['spec'])
                rows.append(r);baseline_rows.append(r)
            assert 1<=len(rows)<=3 and all(not r['recovered'] for r in rows[:-1])
            assert rows[-1]['recovered'] or len(rows)==len(candidates)
            assert final['recovered']==any(r['recovered'] for r in rows) and final['first_recovered']==rows[0]['recovered']
            assert len(list(folder.glob('iteration_*.json')))==len(rows);baseline_finals.append(final)
    expected={('numerical_feedback',c['case_id'],rep) for c in cases for rep in [1,2]};seen=set();ids=set();rows=[];finals=[]
    for path in sorted(output.glob('*/*/repeat_*/final.json')):
        final=read(path);key=(final['condition'],final['case_id'],final['repetition']);assert key in expected and key not in seen;seen.add(key)
        case=byid[final['case_id']];history=[];trajectory=[]
        for i in range(1,final['iterations']+1):
            r=read(path.parent/f'iteration_{i}.json');request=read(path.parent/f'request_{i}.json')
            assert request['protocol_sha256']==phash and request['instructions_sha256']==digest(lossy.PROMPT.encode())
            base={'faulty_netlist':case['faulty_netlist'],'public_main_component_model':case['public_model'],
                'target_specification':case['spec'],'initial_simulation':case['initial_metrics'],'numerical_search':case['numerical_search']}
            if history:base['previous_attempts']=history
            assert request['input']==base and request['input_sha256']==digest(json.dumps(base,sort_keys=True).encode())
            assert (r['condition'],r['case_id'],r['repetition'],r['iteration'])==(*key,i)
            response=read(path.parent/f'response_{i}.json');assert r['response_id']==response['id'] and r['response_id'] not in ids;ids.add(r['response_id'])
            assert response['usage']==r['usage'] and response['model']==r['model']==protocol['model']
            assert response['status']==r['response_status'] and response.get('incomplete_details')==r['incomplete_details']
            text=''.join(c['text'] for item in response['output'] if item['type']=='message' for c in item['content'] if c['type']=='output_text')
            assert text==r['output_text'] and digest(text.encode())==r['output_text_sha256']
            if 'proposal' in r:
                assert json.loads(text)==r['proposal'];validate_proposal(r['proposal'],lossy.schema(case['public_model']))
                diag=r['proposal']['diagnosis'];assert r['localized']==(diag['component']==case['component'])
                assert r['diagnosed']==(r['localized'] and diag['fault_type']==case['fault_type'])
            if r['simulation_called']:
                p=r['proposal']['repair'];source=lossy.patch(case['faulty_netlist'],case['public_model'],p['component'],p['proposed_value'])
                cp=path.parent/f'repaired_{i}.cir';assert cp.read_text()==source and r['repaired_sha256']==digest(source.encode())
                verify(cp,path.parent/f'simulation_{i}/sparams.tsv',r['metrics'],case['spec'],case['public_model'],replay=True)
                assert r['verdict']==validate_bpf_metrics(r['metrics'],case['spec']) and r['recovered']==passes(r['metrics'],case['spec'])
            history.append({k:r[k] for k in ['proposal','outcome','rejection','metrics','verdict'] if k in r});trajectory.append(r);rows.append(r)
        assert 1<=len(trajectory)<=3 and all(not r['recovered'] and r['outcome']!='API_OR_SCHEMA_FAILURE' for r in trajectory[:-1])
        assert final['recovered']==any(r['recovered'] for r in trajectory) and final['first_recovered']==trajectory[0]['recovered']
        assert final['localized']==trajectory[-1]['localized'] and final['diagnosed']==trajectory[-1]['diagnosed']
        assert len(list(path.parent.glob('iteration_*.json')))==len(trajectory)
        finals.append(final)
    assert seen==expected and len(rows)==len(ids)==summary['api_attempts']<=48
    assert len(rows)==len(list(output.glob('*/*/repeat_*/request_*.json')))
    llm={'completed':len(finals),'first_recovered':sum(f['first_recovered'] for f in finals),'final_recovered':sum(f['recovered'] for f in finals),
         'localized':sum(f['localized'] for f in finals),'diagnosed':sum(f['diagnosed'] for f in finals),
         'api_calls_recorded':len(rows),'candidate_simulations':sum(r['simulation_called'] for r in rows),
         'api_schema_failures':sum(r['outcome']=='API_OR_SCHEMA_FAILURE' for r in rows)}
    for k,v in llm.items():assert summary['conditions']['numerical_feedback'][k]==v
    cost=0.;prices=protocol['prices_per_million']
    for r in rows:
        u=r['usage'];d=u.get('input_tokens_details',{});i=u['input_tokens'];c=d.get('cached_tokens',0);w=d.get('cache_write_tokens',0)
        assert 0<=c+w<=i
        cost+=((i-c-w)*prices['input']+c*prices['cached_input']+w*prices['cache_write']+u['output_tokens']*prices['output'])/1e6
    assert abs(cost-summary['conditions']['numerical_feedback']['estimated_api_cost_usd'])<1e-10
    llm['estimated_api_cost_usd']=cost
    llm['top_numerical_candidate_used']=sum(r.get('proposal',{}).get('repair')=={k:byid[r['case_id']]['numerical_search']['candidates'][0][k] for k in ['component','proposed_value']} for r in rows)
    baseline_summary={}
    for method in ['ideal_resonance','numerical_search']:
        fs=[f for f in baseline_finals if f['method']==method]
        baseline_summary[method]={'cases':len(fs),'recovered':sum(f['recovered'] for f in fs),
            'first_recovered':sum(f['first_recovered'] for f in fs),'native_simulations':sum(f['simulations'] for f in fs)}
    assert baseline_summary==read(ROOT/'build/lossy_repair_v1_baselines/summary.json')
    result={'complete':True,'protocol_sha256':phash,'physics_records':physics_records,'raw_frequency_points':raw_points,
        'independent_nodal_points':nodal_points,'max_nodal_magnitude_error':max_nodal,'max_abcd_magnitude_error':max_abcd,
        'fresh_native_replays':replays,'forward_search_evaluations_reproduced':search_evaluations,
        'unique_api_responses':len(ids),'llm':llm,'baselines':baseline_summary,'by_case':[], 'issues':[]}
    for c in cases:
        fs=[f for f in finals if f['case_id']==c['case_id']]
        result['by_case'].append({'case_id':c['case_id'],'fault_component':c['component'],
            'llm_recovered':sum(f['recovered'] for f in fs),'llm_repetitions':len(fs),
            **{method:next(f['recovered'] for f in baseline_finals if f['case_id']==c['case_id'] and f['method']==method) for method in baseline_summary}})
    (audit/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':main()

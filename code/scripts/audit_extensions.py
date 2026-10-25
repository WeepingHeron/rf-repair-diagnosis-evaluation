"""Complete-run provenance audit, fresh simulation, and independent aggregation."""
from pathlib import Path
import argparse
import json
import math
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from rf_repair.transfer import apply_patch
from rf_repair.extensions import resonance_hints, deterministic_candidates
from rf_repair.simulator import run_sparameter_simulation
from run_extension import check, PROMPT
from run_budget_transfer import read, digest
from audit_budget_transfer import passes


def independent_pass(metrics,spec,family):
    if family=='bpf':return passes(metrics,spec)
    if not metrics['simulation_converged']:return False
    for name,frequency in spec['measurement_frequencies_hz'].items():
        s=metrics['samples'][name]
        if abs(s['measured_frequency_hz']-frequency)>1:return False
        c=spec['constraints'][name]
        if not (math.isfinite(s['s11_db']) and math.isfinite(s['s21_db']) and s['s11_db']<=c['s11_db_max'] and s['s21_db']>=c['s21_db_min']):return False
    return True


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--protocol',required=True,choices=['calculator_v5','matching_v1']);args=parser.parse_args()
    pp=ROOT/'experiments'/f'{args.protocol}.json';protocol=read(pp);check(protocol);phash=digest(pp.read_bytes())
    cases=read(ROOT/protocol['manifest'])['cases'];byid={c['case_id']:c for c in cases}
    output=ROOT/'build/experiments'/args.protocol;summary=read(output/'summary.json')
    assert summary['complete'], 'Wait for the complete run'
    expected={(condition,c['case_id'],repeat) for c in cases for condition in protocol['conditions'] for repeat in range(1,protocol['repetitions']+1)}
    seen=set();ids=set();rows=[];finals=[];replays=0
    audit=ROOT/'build'/f'{args.protocol}_audit'
    for p in sorted(output.glob('*/*/repeat_*/final.json')):
        final=read(p);key=(final['condition'],final['case_id'],final['repetition'])
        assert key in expected and key not in seen;seen.add(key);case=byid[final['case_id']]
        history=[];trajectory=[]
        for i in range(1,final['iterations']+1):
            row=read(p.parent/f'iteration_{i}.json');request=read(p.parent/f'request_{i}.json');payload=request['input']
            assert (row['condition'],row['case_id'],row['repetition'],row['iteration'])==(*key,i)
            assert request['protocol_sha256']==phash and request['instructions_sha256']==digest(PROMPT.encode())
            assert request['input_sha256']==digest(json.dumps(payload,sort_keys=True).encode())
            base={'faulty_netlist':case['faulty_netlist'],'target_specification':case['spec'],'initial_simulation':case['initial_metrics']}
            if history:base['previous_attempts']=history
            if final['condition']=='calculator_feedback':base['resonance_calculations']=resonance_hints(case['faulty_netlist'],case['spec']['target_center_frequency_hz'])
            assert payload==base
            if 'response_id' in row:
                assert row['response_id'] not in ids;ids.add(row['response_id'])
                response=read(p.parent/f'response_{i}.json')
                assert response['id']==row['response_id'] and response['usage']==row['usage']
                assert response['model']==row['model']==protocol['model']
                text=''.join(c['text'] for item in response['output'] if item['type']=='message' for c in item['content'] if c['type']=='output_text')
                assert text==row['output_text'] and digest(text.encode())==row['output_text_sha256']
            if 'proposal' in row:
                diag=row['proposal']['diagnosis']
                assert row['localized']==(diag['component']==case['component'])
                assert row['diagnosed']==(row['localized'] and diag['fault_type']==case['fault_type'])
            if row['simulation_called']:
                repair=row['proposal']['repair'];source=apply_patch(case['faulty_netlist'],repair['component'],repair['proposed_value'])
                candidate=p.parent/f'repaired_{i}.cir'
                assert candidate.read_text()==source and digest(source.encode())==row['repaired_sha256']
                metrics=run_sparameter_simulation(candidate,case['spec'],audit/p.parent.relative_to(output)/f'iteration_{i}',cwd=ROOT)
                assert metrics==row['metrics'] and independent_pass(metrics,case['spec'],case['family'])==row['recovered'];replays+=1
            trajectory.append(row);rows.append(row)
            history.append({k:row[k] for k in ['proposal','outcome','rejection','metrics','verdict'] if k in row})
        assert 1<=len(trajectory)<=protocol['max_iterations']
        assert len(list(p.parent.glob('iteration_*.json')))==len(trajectory)
        assert all(not r['recovered'] and r['outcome']!='API_OR_SCHEMA_FAILURE' for r in trajectory[:-1])
        assert final['first_recovered']==trajectory[0]['recovered']
        assert final['recovered']==any(r['recovered'] for r in trajectory)
        assert final['localized']==trajectory[-1]['localized'] and final['diagnosed']==trajectory[-1]['diagnosed']
        final['compensated']=bool(final['recovered'] and trajectory[-1]['proposal']['repair']['component']!=case['component'])
        finals.append(final)
    assert seen==expected and len(rows)==summary['api_attempts']<=protocol['max_api_calls']
    assert len(rows)==len(list(output.glob('*/*/repeat_*/request_*.json')))
    result={'protocol':args.protocol,'complete':True,'audited_trajectories':len(finals),'audited_responses':len(ids),
            'fresh_candidate_simulations':replays,'conditions':{},'by_case':[],'issues':[]}
    for condition in protocol['conditions']:
        fs=[f for f in finals if f['condition']==condition];rs=[r for r in rows if r['condition']==condition]
        r={'completed':len(fs),'first_recovered':sum(f['first_recovered'] for f in fs),'final_recovered':sum(f['recovered'] for f in fs),
           'localized':sum(f['localized'] for f in fs),'diagnosed':sum(f['diagnosed'] for f in fs),'compensated':sum(f['compensated'] for f in fs),
           'api_calls_recorded':len(rs),'candidate_simulations':sum(x['simulation_called'] for x in rs),
           'incomplete_responses':sum(x.get('response_status')=='incomplete' for x in rs),
           'api_schema_failures':sum(x['outcome']=='API_OR_SCHEMA_FAILURE' for x in rs)}
        for k in ['completed','first_recovered','final_recovered','localized','diagnosed','api_calls_recorded','candidate_simulations','api_schema_failures']:
            assert r[k]==summary['conditions'][condition][k]
        cost=0.;price=protocol['prices_per_million']
        for row in rs:
            usage=row.get('usage',{});detail=usage.get('input_tokens_details',{})
            inp=usage.get('input_tokens',0);cached=detail.get('cached_tokens',0);written=detail.get('cache_write_tokens',0)
            assert 0<=cached+written<=inp
            cost+=((inp-cached-written)*price['input']+cached*price['cached_input']+written*price['cache_write']+usage.get('output_tokens',0)*price['output'])/1e6
        assert abs(cost-summary['conditions'][condition]['estimated_api_cost_usd'])<1e-9
        r['estimated_api_cost_usd']=cost
        r['elapsed_seconds']=sum(x['elapsed_seconds'] for x in rs)
        result['conditions'][condition]=r
    for case in cases:
        r={'case_id':case['case_id'],'design_id':case['design_id'],'fault_component':case['component'],'multiplier':case['multiplier']}
        for cond in protocol['conditions']:
            fs=[f for f in finals if f['condition']==cond and f['case_id']==case['case_id']]
            r[cond]={'first':sum(f['first_recovered'] for f in fs),'final':sum(f['recovered'] for f in fs),'total':len(fs)}
        result['by_case'].append(r)
    if args.protocol=='calculator_v5':
        baseline=read(ROOT/'build/calculator_v5_prescreen/deterministic_baseline.json');bcalls=0
        assert len(baseline)==len(cases) and {e['case_id'] for e in baseline}==set(byid)
        for entry in baseline:
            case=byid[entry['case_id']]
            proposed=deterministic_candidates(case['faulty_netlist'],case['spec']['target_center_frequency_hz'])
            assert 1<=len(entry['attempts'])<=len(proposed)<=3
            assert all(a['verdict']['verdict']!='PASS' for a in entry['attempts'][:-1])
            for i,attempt in enumerate(entry['attempts'],1):
                assert attempt['proposal']==proposed[i-1]
                candidate=ROOT/'build/calculator_v5_prescreen'/case['case_id']/f'deterministic_{i}.cir'
                p=attempt['proposal'];assert candidate.read_text()==apply_patch(case['faulty_netlist'],p['component'],p['proposed_value'])
                metrics=run_sparameter_simulation(candidate,case['spec'],audit/'deterministic'/case['case_id']/str(i),cwd=ROOT)
                assert metrics==attempt['metrics'];assert independent_pass(metrics,case['spec'],'bpf')==(attempt['verdict']['verdict']=='PASS');bcalls+=1
            assert entry['recovered']==any(r['verdict']['verdict']=='PASS' for r in entry['attempts'])
        result['deterministic_baseline']={'cases':len(baseline),'recovered':sum(r['recovered'] for r in baseline),'candidate_simulations':bcalls,'api_calls':0}
    audit.mkdir(parents=True,exist_ok=True);(audit/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()

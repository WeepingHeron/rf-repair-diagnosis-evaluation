"""Run the frozen loss-aware numerical-candidate LLM comparison."""
import argparse
import fcntl
import hashlib
import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from importlib.metadata import version

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from openai import OpenAI
from rf_repair.agent import load_local_api_key
from rf_repair.lossy import payload, schema, patch, PROMPT
from rf_repair.validator import validate_bpf_metrics
from rf_repair.simulator import run_sparameter_simulation
from run_budget_transfer import read, write_once, digest, validate_proposal




def check(protocol):
    for file, sha in protocol['file_sha256'].items():
        if digest((ROOT/file).read_bytes()) != sha: raise ValueError('Frozen file changed: '+file)


def summarize(output, protocol):
    finals = [read(p) for p in output.glob('*/*/repeat_*/final.json')]
    rows = [read(p) for p in output.glob('*/*/repeat_*/iteration_*.json')]
    planned = protocol['case_count']*protocol['repetitions']*len(protocol['conditions'])
    result = {'experiment_id': protocol['experiment_id'], 'complete': len(finals)==planned,
              'planned': planned, 'completed': len(finals), 'api_attempts': len(list(output.glob('*/*/repeat_*/request_*.json'))), 'conditions': {}}
    for c in protocol['conditions']:
        fs=[f for f in finals if f['condition']==c]; rs=[r for r in rows if r['condition']==c]
        inp=cache=write=out=0
        for r in rs:
            u=r.get('usage',{}); d=u.get('input_tokens_details',{})
            inp+=u.get('input_tokens',0); cache+=d.get('cached_tokens',0); write+=d.get('cache_write_tokens',0); out+=u.get('output_tokens',0)
        price=protocol['prices_per_million']
        cost=((inp-cache-write)*price['input']+cache*price['cached_input']+write*price['cache_write']+out*price['output'])/1e6
        result['conditions'][c]={'planned':protocol['case_count']*protocol['repetitions'], 'completed':len(fs),
            'first_recovered':sum(f['first_recovered'] for f in fs), 'final_recovered':sum(f['recovered'] for f in fs),
            'localized':sum(f['localized'] for f in fs),'diagnosed':sum(f['diagnosed'] for f in fs),
            'api_calls_recorded':len(rs),'candidate_simulations':sum(r['simulation_called'] for r in rs),
            'api_schema_failures':sum(r['outcome']=='API_OR_SCHEMA_FAILURE' for r in rs),
            'input_tokens':inp,'cached_input_tokens':cache,'cache_write_tokens':write,'output_tokens':out,
            'estimated_api_cost_usd':cost}
    tmp=output/'summary.tmp';tmp.write_text(json.dumps(result,indent=2)+'\n');tmp.replace(output/'summary.json')
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--protocol',required=True,choices=['lossy_repair_v1'])
    parser.add_argument('--max-new-calls',type=int,default=48);parser.add_argument('--summary-only',action='store_true')
    args=parser.parse_args();pp=ROOT/'experiments'/f'{args.protocol}.json';protocol=read(pp);check(protocol)
    output=ROOT/'build/experiments'/protocol['experiment_id'];output.mkdir(parents=True,exist_ok=True)
    lock=(output/'.run.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if args.summary_only: print(json.dumps(summarize(output,protocol),indent=2));return
    phash=digest(pp.read_bytes());env=output/'run_environment.json'
    if not env.exists():
        raw=subprocess.run(['ngspice','--version'],capture_output=True,text=True,timeout=5)
        write_once(env,{'protocol_sha256':phash,'started_at_utc':datetime.now(timezone.utc).isoformat(),
                       'python':platform.python_version(),'openai':version('openai'),
                       'ngspice':next(s.strip() for s in (raw.stdout+raw.stderr).splitlines() if 'ngspice-' in s.lower())})
    elif read(env)['protocol_sha256']!=phash: raise ValueError('Protocol changed after start')
    load_local_api_key(ROOT/'.env.local');client=OpenAI(timeout=90.,max_retries=0);calls=0
    cases=read(ROOT/protocol['manifest'])['cases']
    for index,case in enumerate(cases):
        response_contract=schema(case['public_model'])
        for repetition in range(1,protocol['repetitions']+1):
            order=protocol['conditions'] if (index+repetition)%2 else list(reversed(protocol['conditions']))
            for condition in order:
                folder=output/condition/case['case_id']/f'repeat_{repetition}'; final=folder/'final.json'
                if final.exists():continue
                folder.mkdir(parents=True,exist_ok=True);history=[];rows=[];transport_failed=False
                for iteration in range(1,protocol['max_iterations']+1):
                    path=folder/f'iteration_{iteration}.json';request=folder/f'request_{iteration}.json'
                    if path.exists(): row=read(path)
                    else:
                        if request.exists():raise RuntimeError('Unresolved prior request; no automatic reissue: '+str(request))
                        if calls>=args.max_new_calls:print(json.dumps(summarize(output,protocol),indent=2));return
                        if len(list(output.glob('*/*/repeat_*/request_*.json')))>=protocol['max_api_calls']:raise RuntimeError('Global attempt cap reached')
                        request_payload=payload(case,history);encoded=json.dumps(request_payload,sort_keys=True)
                        if len(encoded)>protocol['max_input_chars']:raise ValueError('Input limit exceeded')
                        write_once(request,{'started_at_utc':datetime.now(timezone.utc).isoformat(),'input':request_payload,
                            'input_sha256':digest(encoded.encode()),'instructions_sha256':digest(PROMPT.encode()),'protocol_sha256':phash})
                        calls+=1;start=time.monotonic()
                        row={'case_id':case['case_id'],'condition':condition,'repetition':repetition,'iteration':iteration,
                             'recovered':False,'localized':False,'diagnosed':False,'simulation_called':False}
                        try:
                            response=client.responses.create(model=protocol['model'],reasoning={'effort':protocol['reasoning_effort']},
                                max_output_tokens=protocol['max_output_tokens'],store=False,instructions=PROMPT,input=encoded,
                                text={'verbosity':'low','format':{'type':'json_schema','name':'extension_value','strict':True,'schema':response_contract}})
                            raw=response.output_text
                            write_once(folder/f'response_{iteration}.json',response.model_dump(mode='json'))
                            row.update({'response_id':response.id,'model':response.model,'response_status':response.status,
                                        'incomplete_details':response.incomplete_details.model_dump(mode='json') if response.incomplete_details else None,
                                        'usage':response.usage.model_dump(mode='json') if response.usage else {},
                                        'output_text':raw,'output_text_sha256':digest(raw.encode())})
                            if response.status!='completed':raise ValueError('Response incomplete')
                            proposal=json.loads(raw);validate_proposal(proposal,response_contract);row['proposal']=proposal
                            row['localized']=proposal['diagnosis']['component']==case['component']
                            row['diagnosed']=row['localized'] and proposal['diagnosis']['fault_type']==case['fault_type']
                        except Exception as e:
                            row.update({'outcome':'API_OR_SCHEMA_FAILURE','error_type':type(e).__name__})
                            transport_failed='response_id' not in row
                        else:
                            try: repaired=patch(case['faulty_netlist'],case['public_model'],proposal['repair']['component'],proposal['repair']['proposed_value'])
                            except ValueError as e:row.update({'outcome':'PATCH_REJECTED','rejection':str(e)})
                            else:
                                candidate=folder/f'repaired_{iteration}.cir';candidate.write_text(repaired)
                                row.update({'simulation_called':True,'repaired_sha256':digest(repaired.encode())})
                                metrics=run_sparameter_simulation(candidate,case['spec'],folder/f'simulation_{iteration}',cwd=ROOT)
                                verdict=validate_bpf_metrics(metrics,case['spec'])
                                row.update({'metrics':metrics,'verdict':verdict,'recovered':verdict['verdict']=='PASS','outcome':verdict['reason']})
                        row['elapsed_seconds']=time.monotonic()-start;write_once(path,row)
                    rows.append(row)
                    print(f"{condition} {case['case_id']} r{repetition} i{iteration}: {row['outcome']}",flush=True)
                    if row['recovered'] or row['outcome']=='API_OR_SCHEMA_FAILURE':break
                    history.append({k:row[k] for k in ['proposal','outcome','rejection','metrics','verdict'] if k in row})
                write_once(final,{'case_id':case['case_id'],'condition':condition,'repetition':repetition,'iterations':len(rows),
                                  'first_recovered':rows[0]['recovered'],'recovered':any(r['recovered'] for r in rows),
                                  'localized':rows[-1]['localized'],'diagnosed':rows[-1]['diagnosed']})
                summarize(output,protocol)
                if transport_failed:raise RuntimeError('Transport failure recorded; stopping remaining calls')
    print(json.dumps(summarize(output,protocol),indent=2))

if __name__=='__main__':main()

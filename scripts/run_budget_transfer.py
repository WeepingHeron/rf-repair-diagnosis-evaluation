"""Resume a frozen equal-budget comparison without hidden retries or rewriting evidence."""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
import sys
import time
import platform
import subprocess
import fcntl
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from openai import OpenAI
from rf_repair.agent import load_local_api_key
from rf_repair.transfer import INSTRUCTIONS, agent_payload, apply_patch, response_schema
from rf_repair.simulator import run_sparameter_simulation
from rf_repair.validator import validate_bpf_metrics


def read(path): return json.loads(path.read_text())
def digest(data): return hashlib.sha256(data).hexdigest()
def write_once(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as f:
        f.write(json.dumps(value, indent=2)+'\n')


def check_contract(protocol):
    for name, expected in protocol['file_sha256'].items():
        if digest((ROOT/name).read_bytes()) != expected:
            raise ValueError('Frozen input or evaluator changed: '+name)


def validate_proposal(proposal, schema):
    def validate(value, definition):
        kind = definition['type']
        if kind == 'object':
            if not isinstance(value, dict) or set(value) != set(definition['required']):
                raise ValueError('response object keys do not match schema')
            for key, child in definition['properties'].items(): validate(value[key], child)
        elif kind == 'string':
            if not isinstance(value, str): raise ValueError('response field must be string')
            if 'enum' in definition and value not in definition['enum']: raise ValueError('unknown label or component')
            if len(value) > definition.get('maxLength', 10000): raise ValueError('response field too long')
        else: raise ValueError('unsupported schema type')
    validate(proposal, schema)


def summarize(output, protocol):
    finals = [read(p) for p in output.glob('*/*/repeat_*/final.json')]
    rows = [read(p) for p in output.glob('*/*/repeat_*/iteration_*.json')]
    starts = list(output.glob('*/*/repeat_*/request_*.json'))
    result = {'experiment_id':protocol['experiment_id'], 'planned_trajectories':72,
              'completed_trajectories':len(finals), 'complete':len(finals)==72,
              'actual_api_attempts':len(starts), 'conditions':{}}
    for condition in protocol['conditions']:
        fs = [f for f in finals if f['condition']==condition]
        rs = [r for r in rows if r['condition']==condition]
        usage = {'input_tokens':0, 'cached_input_tokens':0, 'output_tokens':0}
        for row in rs:
            u = row.get('usage',{});usage['input_tokens']+=u.get('input_tokens',0)
            usage['cached_input_tokens']+=u.get('input_tokens_details',{}).get('cached_tokens',0)
            usage['output_tokens']+=u.get('output_tokens',0)
        cost = ((usage['input_tokens']-usage['cached_input_tokens'])*.20
                + usage['cached_input_tokens']*.02 + usage['output_tokens']*1.20)/1e6
        result['conditions'][condition] = {'planned':36, 'completed':len(fs),
            'first_recovered':sum(f['first_recovered'] for f in fs),
            'final_recovered':sum(f['recovered'] for f in fs),
            'localized':sum(f['localized'] for f in fs), 'diagnosed':sum(f['diagnosed'] for f in fs),
            'iterations_recorded':len(rs), 'candidate_simulations':sum(r.get('simulation_called',False) for r in rs),
            'api_schema_failures':sum(r['outcome']=='API_OR_SCHEMA_FAILURE' for r in rs),
            'estimated_api_cost_usd':cost, **usage,
            'by_case':{case_id:{'completed':sum(f['case_id']==case_id for f in fs),
                'recovered':sum(f['case_id']==case_id and f['recovered'] for f in fs)}
                for case_id in sorted({f['case_id'] for f in fs})}}
    tmp = output/'summary.tmp';tmp.write_text(json.dumps(result,indent=2)+'\n');tmp.replace(output/'summary.json')
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--max-new-calls',type=int,default=216)
    parser.add_argument('--summary-only',action='store_true');args=parser.parse_args()
    pp=ROOT/'experiments/budget_transfer_v4.json';protocol=read(pp);check_contract(protocol)
    output=ROOT/'build/experiments'/protocol['experiment_id'];output.mkdir(parents=True,exist_ok=True)
    lock=(output/'.run.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if args.summary_only:
        print(json.dumps(summarize(output,protocol),indent=2));return 0
    envpath=output/'run_environment.json'
    contract_hash=digest(pp.read_bytes())
    if envpath.exists():
        if read(envpath)['protocol_sha256']!=contract_hash:raise ValueError('existing run has a different protocol')
    else:
        version=subprocess.run(['ngspice','--version'],capture_output=True,text=True,timeout=5)
        write_once(envpath,{'protocol_sha256':contract_hash,'started_at_utc':datetime.now(timezone.utc).isoformat(),
            'python':platform.python_version(),'openai':importlib.metadata.version('openai'),
            'ngspice_version':next((l.strip() for l in (version.stdout+version.stderr).splitlines() if 'ngspice-' in l.lower()),'UNKNOWN')})
    load_local_api_key(ROOT/'.env.local');client=OpenAI(timeout=90.,max_retries=0)
    cases=read(ROOT/protocol['manifest'])['cases'];new_calls=0
    for index,case in enumerate(cases):
        source=case['faulty_netlist'];schema=response_schema(source)
        for repetition in range(1,protocol['repetitions']+1):
            order=protocol['conditions'] if (index+repetition)%2 else list(reversed(protocol['conditions']))
            for condition in order:
                folder=output/condition/case['case_id']/f'repeat_{repetition}';final_path=folder/'final.json'
                if final_path.exists():continue
                folder.mkdir(parents=True,exist_ok=True);history=[];rows=[];transport_failed=False
                for iteration in range(1,protocol['max_iterations']+1):
                    row_path=folder/f'iteration_{iteration}.json';request_path=folder/f'request_{iteration}.json'
                    if row_path.exists():row=read(row_path)
                    else:
                        if request_path.exists():
                            raise RuntimeError('Unresolved prior request; refuse automatic reissue: '+str(request_path))
                        if new_calls>=args.max_new_calls:
                            print(json.dumps(summarize(output,protocol),indent=2));return 0
                        if len(list(output.glob('*/*/repeat_*/request_*.json')))>=protocol['max_api_calls']:
                            raise RuntimeError('Total API attempt cap reached')
                        payload=agent_payload(source,case['spec'],case['initial_metrics'],history,condition)
                        encoded=json.dumps(payload,sort_keys=True)
                        if len(encoded)>protocol['max_input_chars']:raise ValueError('Input exceeds frozen budget')
                        write_once(request_path,{'started_at_utc':datetime.now(timezone.utc).isoformat(),
                            'condition':condition,'input':payload,'input_sha256':digest(encoded.encode()),
                            'instructions_sha256':digest(INSTRUCTIONS.encode()),'protocol_sha256':contract_hash})
                        new_calls+=1;start=time.monotonic()
                        row={'case_id':case['case_id'],'condition':condition,'repetition':repetition,'iteration':iteration,
                             'recovered':False,'localized':False,'diagnosed':False,'simulation_called':False}
                        try:
                            response=client.responses.create(model=protocol['model'],
                                reasoning={'effort':protocol['reasoning_effort']},max_output_tokens=protocol['max_output_tokens'],
                                store=False,instructions=INSTRUCTIONS,input=encoded,
                                text={'verbosity':'low','format':{'type':'json_schema','name':'transfer_value_v4','strict':True,'schema':schema}})
                            raw=response.output_text
                            row.update({'response_id':response.id,'model':response.model,'response_status':response.status,
                                'response_created_at':response.created_at,'usage':response.usage.model_dump(mode='json') if response.usage else {},
                                'output_text':raw,'output_text_sha256':digest(raw.encode())})
                            write_once(folder/f'response_{iteration}.json',row)
                            if response.status!='completed':raise ValueError('incomplete response')
                            proposal=json.loads(raw);validate_proposal(proposal,schema);row['proposal']=proposal
                            row['localized']=proposal['diagnosis']['component']==case['component']
                            row['diagnosed']=row['localized'] and proposal['diagnosis']['fault_type']==case['fault_type']
                        except Exception as error:
                            row.update({'outcome':'API_OR_SCHEMA_FAILURE','error_type':type(error).__name__})
                            transport_failed='response_id' not in row
                        else:
                            try:
                                repaired=apply_patch(source,proposal['repair']['component'],proposal['repair']['proposed_value'])
                            except ValueError as error:
                                row.update({'outcome':'PATCH_REJECTED','rejection':str(error)})
                            else:
                                path=folder/f'repaired_{iteration}.cir';path.write_text(repaired)
                                row['repaired_sha256']=digest(repaired.encode());row['simulation_called']=True
                                before_sim=time.monotonic()
                                metrics=run_sparameter_simulation(path,case['spec'],folder/f'simulation_{iteration}',cwd=ROOT)
                                verdict=validate_bpf_metrics(metrics,case['spec'])
                                row.update({'metrics':metrics,'verdict':verdict,'recovered':verdict['verdict']=='PASS',
                                            'outcome':verdict['reason'],'simulation_seconds':time.monotonic()-before_sim})
                        row['elapsed_seconds']=time.monotonic()-start;write_once(row_path,row)
                    rows.append(row)
                    print(f"{condition} {case['case_id']} r{repetition} i{iteration}: {row['outcome']}",flush=True)
                    if row['recovered'] or row['outcome']=='API_OR_SCHEMA_FAILURE':break
                    history.append({k:row[k] for k in ['proposal','outcome','rejection','metrics','verdict'] if k in row})
                final={'case_id':case['case_id'],'condition':condition,'repetition':repetition,
                    'iterations':len(rows),'first_recovered':rows[0]['recovered'],'recovered':any(r['recovered'] for r in rows),
                    'localized':rows[-1]['localized'],'diagnosed':rows[-1]['diagnosed']}
                write_once(final_path,final);summarize(output,protocol)
                if transport_failed:raise RuntimeError('Transport failure recorded; stopping to avoid repeated failed calls')
    print(json.dumps(summarize(output,protocol),indent=2));return 0

if __name__=='__main__':raise SystemExit(main())

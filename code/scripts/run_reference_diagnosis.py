"""One independent diagnosis call per frozen condition/case/repetition; no retries."""
import argparse
import fcntl
import json
import platform
import sys
import time
from datetime import datetime,timezone
from importlib.metadata import version
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from openai import OpenAI
from rf_repair.agent import load_local_api_key
from rf_repair.reference import payload,schema,score,PROMPT,FIELDS
from run_budget_transfer import read,write_once,digest,validate_proposal


def check(protocol):
    for path,h in protocol['file_sha256'].items():
        if digest((ROOT/path).read_bytes())!=h:raise ValueError('frozen input changed: '+path)

def summarize(output,protocol):
    rows=[read(p) for p in output.glob('*/*/repeat_*/result.json')];planned=protocol['case_count']*protocol['repetitions']*len(protocol['conditions'])
    summary={'complete':len(rows)==planned,'planned':planned,'completed':len(rows),
             'api_attempts':len(list(output.glob('*/*/repeat_*/request.json'))),'conditions':{}}
    for condition in protocol['conditions']:
        rs=[r for r in rows if r['condition']==condition];cost=0.;inp=cache=write=out=0;price=protocol['prices_per_million']
        for r in rs:
            u=r.get('usage',{});d=u.get('input_tokens_details',{})
            inp+=u.get('input_tokens',0);cache+=d.get('cached_tokens',0);write+=d.get('cache_write_tokens',0);out+=u.get('output_tokens',0)
        cost=((inp-cache-write)*price['input']+cache*price['cached_input']+write*price['cache_write']+out*price['output'])/1e6
        summary['conditions'][condition]={'planned':16,'completed':len(rs),'valid_responses':sum(r['valid_response'] for r in rs),
            'api_schema_failures':sum(not r['valid_response'] for r in rs),**{k:sum(r[k] for r in rs) for k in FIELDS},
            'input_tokens':inp,'cached_input_tokens':cache,'cache_write_tokens':write,'output_tokens':out,'estimated_api_cost_usd':cost}
    tmp=output/'summary.tmp';tmp.write_text(json.dumps(summary,indent=2)+'\n');tmp.replace(output/'summary.json')
    return summary

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--max-new-calls',type=int,default=48);parser.add_argument('--summary-only',action='store_true');args=parser.parse_args()
    pp=ROOT/'experiments/reference_diagnosis_v1.json';protocol=read(pp);check(protocol);phash=digest(pp.read_bytes())
    if protocol.get('status')!='READY':raise RuntimeError('experiment is not ready: '+protocol.get('status','UNKNOWN'))
    output=ROOT/'build/experiments/reference_diagnosis_v1';output.mkdir(parents=True,exist_ok=True)
    lock=(output/'.run.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if args.summary_only:print(json.dumps(summarize(output,protocol),indent=2));return
    env=output/'environment.json'
    if not env.exists():write_once(env,{'protocol_sha256':phash,'started_at_utc':datetime.now(timezone.utc).isoformat(),'python':platform.python_version(),'openai':version('openai')})
    assert read(env)['protocol_sha256']==phash
    load_local_api_key(ROOT/'.env.local');client=OpenAI(timeout=90,max_retries=0);new_calls=0
    cases=read(ROOT/protocol['manifest'])['cases']
    for index,case in enumerate(cases):
        for repeat in range(1,protocol['repetitions']+1):
            shift=(index+repeat-1)%len(protocol['conditions'])
            order=protocol['conditions'][shift:]+protocol['conditions'][:shift]
            for condition in order:
                folder=output/condition/case['case_id']/f'repeat_{repeat}';path=folder/'result.json';request=folder/'request.json'
                if path.exists():continue
                if request.exists():raise RuntimeError('unresolved request; refuse automatic reissue: '+str(request))
                if new_calls>=args.max_new_calls:print(json.dumps(summarize(output,protocol),indent=2));return
                if len(list(output.glob('*/*/repeat_*/request.json')))>=protocol['max_api_calls']:raise RuntimeError('global API cap reached')
                data=payload(case,condition);encoded=json.dumps(data,sort_keys=True)
                if len(encoded)>protocol['max_input_chars']:raise ValueError('input budget exceeded')
                write_once(request,{'started_at_utc':datetime.now(timezone.utc).isoformat(),'input':data,'input_sha256':digest(encoded.encode()),
                    'instructions_sha256':digest(PROMPT.encode()),'protocol_sha256':phash,'condition':condition,'case_id':case['case_id'],'repetition':repeat})
                row={'condition':condition,'case_id':case['case_id'],'repetition':repeat,'valid_response':False,**{k:False for k in FIELDS}}
                new_calls+=1;start=time.monotonic()
                try:
                    response=client.responses.create(model=protocol['model'],reasoning={'effort':protocol['reasoning_effort']},max_output_tokens=protocol['max_output_tokens'],
                        store=False,instructions=PROMPT,input=encoded,text={'verbosity':'low','format':{'type':'json_schema','name':'reference_diagnosis','strict':True,'schema':schema(case['public_model'])}})
                    write_once(folder/'response.json',response.model_dump(mode='json'));raw=response.output_text
                    row.update({'response_id':response.id,'model':response.model,'response_status':response.status,
                        'incomplete_details':response.incomplete_details.model_dump(mode='json') if response.incomplete_details else None,
                        'usage':response.usage.model_dump(mode='json') if response.usage else {},'output_text':raw,'output_text_sha256':digest(raw.encode())})
                    if response.status!='completed':raise ValueError('incomplete response')
                    proposal=json.loads(raw);validate_proposal(proposal,schema(case['public_model']));scores=score(proposal,case)
                    row.update({'proposal':proposal,'valid_response':True,'outcome':'DIAGNOSIS_RECORDED',**scores})
                except Exception as e:row.update({'outcome':'API_OR_SCHEMA_FAILURE','error_type':type(e).__name__})
                row['elapsed_seconds']=time.monotonic()-start;write_once(path,row)
                print(f"{condition} {case['case_id']} r{repeat}: {row['outcome']}",flush=True);summarize(output,protocol)
                if 'response_id' not in row:raise RuntimeError('transport failure recorded; stopping remaining calls')
    print(json.dumps(summarize(output,protocol),indent=2))

if __name__=='__main__':main()

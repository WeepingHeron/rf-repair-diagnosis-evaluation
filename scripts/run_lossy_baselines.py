"""Two deterministic policies, at most three native candidates, with frozen inputs."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from rf_repair.lossy import ideal_candidates,patch
from rf_repair.simulator import run_sparameter_simulation
from rf_repair.validator import validate_bpf_metrics
from run_budget_transfer import read,write_once,digest

def main():
    pp=ROOT/'experiments/lossy_repair_v1.json'; p=read(pp)
    for file,h in p['file_sha256'].items():assert digest((ROOT/file).read_bytes())==h,file
    cases=read(ROOT/p['manifest'])['cases']; rows=[]
    for case in cases:
        for method in ['ideal_resonance','numerical_search']:
            folder=ROOT/'build/lossy_repair_v1_baselines'/method/case['case_id']; final=folder/'final.json'
            if final.exists():rows.append(read(final));continue
            candidates=ideal_candidates(case['faulty_netlist'],case['public_model']) if method=='ideal_resonance' else case['numerical_search']['candidates']
            attempts=[]
            for i,c in enumerate(candidates[:3],1):
                path=folder/f'iteration_{i}.json'
                if path.exists():r=read(path)
                else:
                    proposal={k:c[k] for k in ['component','proposed_value']}
                    source=patch(case['faulty_netlist'],case['public_model'],**{'component':proposal['component'],'value':proposal['proposed_value']})
                    folder.mkdir(parents=True,exist_ok=True); cp=folder/f'repaired_{i}.cir';cp.write_text(source)
                    m=run_sparameter_simulation(cp,case['spec'],folder/f'simulation_{i}',cwd=ROOT);v=validate_bpf_metrics(m,case['spec'])
                    r={'case_id':case['case_id'],'method':method,'iteration':i,'proposal':proposal,
                        'metrics':m,'verdict':v,'recovered':v['verdict']=='PASS','source_sha256':digest(source.encode()),
                        'protocol_sha256':digest(pp.read_bytes())}
                    write_once(path,r)
                attempts.append(r)
                if r['recovered']:break
            result={'case_id':case['case_id'],'method':method,'recovered':any(r['recovered'] for r in attempts),
                'first_recovered':attempts[0]['recovered'] if attempts else False,'simulations':len(attempts)}
            write_once(final,result);rows.append(result)
            print(json.dumps(result),flush=True)
    summary={method:{'cases':sum(r['method']==method for r in rows),'recovered':sum(r['method']==method and r['recovered'] for r in rows),
        'first_recovered':sum(r['method']==method and r['first_recovered'] for r in rows),
        'native_simulations':sum(r['simulations'] for r in rows if r['method']==method)} for method in ['ideal_resonance','numerical_search']}
    (ROOT/'build/lossy_repair_v1_baselines/summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))

if __name__=='__main__':main()

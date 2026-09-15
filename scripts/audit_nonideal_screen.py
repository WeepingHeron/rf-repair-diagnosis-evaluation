"""Reconcile every record, raw grid and decision, plus independent ABCD physics."""
from __future__ import annotations
import json
import math
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from rf_repair.nonideal import make_conditions, render, element_parameters, protected_patch, public_candidates
from rf_repair.simulator import run_sparameter_simulation
from rf_repair.validator import validate_bpf_metrics
from run_nonideal_screen import read, sha
from audit_budget_transfer import passes


def abcd_from_deck(condition, source):
    # Parse actual SPICE tokens, not the generator's loss/value calculations.
    elements = {t[0]:t for t in map(str.split, source.splitlines()) if len(t)==4 and t[0][0] in 'RLC'}
    branches = []
    for p in condition['design']['parts']:
        n = p['name']
        branches.append((n[0], float(elements[n][3]), float(elements.get('RS_'+n,[0,0,0,0])[3]),
                         float(elements.get('CP_'+n,[0,0,0,0])[3]), float(elements.get('LS_'+n,[0,0,0,0])[3])))
    def evaluate(f):
        w=2*math.pi*f; impedances=[]
        for kind,value,resistance,cp,esl in branches:
            if kind=='L':
                z=complex(resistance,w*value)
                if cp: z=z/(1+z*complex(0,w*cp))
            else: z=complex(resistance,w*esl-1/(w*value))
            impedances.append(z)
        z1=impedances[0]+impedances[1]; y=1/impedances[2]+1/impedances[3]; z2=impedances[4]+impedances[5]
        # Multiply series(z1), shunt(y), series(z2) explicitly.
        a=1+z1*y; b=a*z2+z1; c=y; d=y*z2+1
        den=a+b/50+c*50+d
        return abs((a+b/50-c*50-d)/den),abs(2/den),abs((-a+b/50-c*50+d)/den)
    return evaluate


def main():
    pp=ROOT/'experiments/nonideal_screen_v1.json'; protocol=read(pp)
    for p,h in protocol['file_sha256'].items(): assert sha((ROOT/p).read_bytes())==h,p
    conditions=read(ROOT/protocol['manifest'])['conditions']
    assert conditions==make_conditions()
    assert len(conditions)==320 and len({c['condition_id'] for c in conditions})==320
    output=ROOT/'build/experiments/nonideal_screen_v1'; audit=ROOT/'build/nonideal_screen_v1_audit'
    audit.mkdir(parents=True, exist_ok=True)
    physics_cache={}; records=0; max_error=0.; fresh_count=0; groups={}; failures=Counter(); detailed=[]
    expected_files=set()
    def check(condition, label, overrides, expected_source):
        nonlocal records,max_error
        folder=output/condition['condition_id']; path=folder/f'{label}.json'; expected_files.add(path)
        r=read(path); source=(folder/f'{label}.cir').read_text(); spec=condition['design']['spec']
        assert source==expected_source and sha(source.encode())==r['source_sha256'],path
        assert r['overrides']==overrides,path
        assert r['metrics']['simulation_converged'] is True,path
        rows=[]
        with (folder/label/'sparams.tsv').open() as f:
            assert f.readline().split()==['frequency','db(s_1_1)','db(s_2_1)','db(s_2_2)']
            for line in f:
                row=list(map(float,line.split())); assert len(row)==4 and all(map(math.isfinite,row)); rows.append(row)
        f0=condition['design']['f0']
        assert len(rows)==2001
        assert all(abs(row[0]-(f0*.5+i*f0/2000))<=1 for i,row in enumerate(rows))
        # All raw points checked physically. Repeated exact sources use a cached reference curve.
        if r['source_sha256'] not in physics_cache:
            analytic=abcd_from_deck(condition,source)
            physics_cache[r['source_sha256']]=[analytic(row[0]) for row in rows]
        reference=physics_cache[r['source_sha256']]
        for row, expected in zip(rows,reference,strict=True):
            measured=[10**(v/20) for v in row[1:]]
            error=max(abs(x-y) for x,y in zip(measured,expected,strict=True)); max_error=max(max_error,error)
            assert error<=2e-7,(path,row[0],error)
            assert measured[0]**2+measured[1]**2 <= 1+1e-6,(path,'nonpassive')
        m=r['metrics']; peak=max(rows,key=lambda row:row[2])
        assert m['point_count']==len(rows) and m['peak_frequency_hz']==peak[0] and m['peak_s21_db']==peak[2]
        assert m['peak_frequency_relative_error']==abs(peak[0]-f0)/f0
        for name,freq in spec['measurement_frequencies_hz'].items():
            row=min(rows,key=lambda row:abs(row[0]-freq)); s=m['samples'][name]
            assert s==dict(requested_frequency_hz=float(freq),measured_frequency_hz=row[0],s11_db=row[1],s21_db=row[2],s22_db=row[3])
        assert r['verdict']==validate_bpf_metrics(m,spec)
        assert (r['verdict']['verdict']=='PASS')==passes(m,spec)
        records+=1
        return r
    for index,condition in enumerate(conditions):
        cid=condition['condition_id']; folder=output/cid; d=condition['design']; healthy=render(condition)
        h=check(condition,'healthy',{},healthy); final=read(folder/'final.json')
        assert final['condition_id']==cid and len(final['faults'])==2
        hp=h['verdict']['verdict']=='PASS'; assert final['healthy_pass']==hp
        # Fresh SPICE on each nominal-tolerance cell (4 designs x 4 Q x 2 parasitics).
        if condition['tolerance']==0:
            fresh=run_sparameter_simulation(folder/'healthy.cir',d['spec'],audit/cid,cwd=ROOT)
            assert fresh==h['metrics']; fresh_count+=1
        fail_names=[c['name'] for c in h['verdict']['checks'] if not c['passed']]; failures.update(fail_names)
        row={'condition_id':cid,'design_id':d['design_id'],'q':condition['q'],'parasitics':condition['parasitics'],
             'tolerance':condition['tolerance'],'draw':condition['draw'],'healthy_pass':hp,
             'center_s21_db':h['metrics']['samples']['center']['s21_db'],'failed_checks':fail_names,
             'eligible':0,'recovered':0,'attempts':0}
        parts=element_parameters(condition); allowed=[p['name'] for p in parts]
        for j,(part_index,fr) in enumerate(zip(d['fault_indices'],final['faults'],strict=True),1):
            part=parts[part_index]; component=part['name']; multiplier=[.55,1.8][j-1]
            overrides={component:f'{float(part["value"])*multiplier:.12g}'}; source=render(condition,overrides)
            f=check(condition,f'fault_{j}',overrides,source)
            oracle=protected_patch(source,component,part['value'],allowed); assert oracle==healthy
            o=check(condition,f'oracle_{j}',{},oracle)
            eligible=hp and f['verdict']['verdict']=='FAIL' and o['verdict']['verdict']=='PASS'
            assert fr['eligible']==eligible and fr['component']==component and fr['fault_id']==j and fr['multiplier']==multiplier
            candidates=public_candidates(render(condition,overrides,core_only=True),d['f0']) if eligible else []
            attempts=fr['baseline_attempts']; assert len(attempts)<=3
            recovered=False
            for k,attempt in enumerate(attempts,1):
                assert not recovered
                proposal=candidates[k-1]; assert proposal==attempt['proposal']
                replacement={**overrides,proposal['component']:proposal['proposed_value']}
                changed=protected_patch(source,proposal['component'],proposal['proposed_value'],allowed)
                r=check(condition,f'baseline_{j}_{k}',replacement,changed)
                assert changed==render(condition,replacement)
                recovered=r['verdict']['verdict']=='PASS'; assert attempt['recovered']==recovered
                assert attempt['evidence']==f'baseline_{j}_{k}.json'
            assert recovered or len(attempts)==len(candidates)
            assert fr['baseline_recovered']==(recovered if eligible else None)
            row['eligible']+=eligible; row['recovered']+=recovered; row['attempts']+=len(attempts)
        detailed.append(row)
        if (index+1)%40==0: print(json.dumps({'audited_conditions':index+1,'records':records}),flush=True)
    actual_files={p for p in output.glob('*/*.json') if p.name!='final.json'}
    assert actual_files==expected_files,(actual_files-expected_files,expected_files-actual_files)
    s=read(output/'summary.json')
    assert s=={'complete':True,'conditions':320,'healthy_pass':sum(r['healthy_pass'] for r in detailed),
               'fault_instances':640,'eligible_faults':sum(r['eligible'] for r in detailed),
               'baseline_recovered':sum(r['recovered'] for r in detailed),
               'baseline_simulations':sum(r['attempts'] for r in detailed),'api_calls':0}
    result={'complete':True,'records':records,'unique_circuits':len(physics_cache),'raw_frequency_points':records*2001,
            'fresh_ngspice_replays':fresh_count,'max_absolute_sparameter_magnitude_error':max_error,
            'healthy_failure_checks':dict(failures),'summary':s,'conditions':detailed,'issues':[],
            'protocol_sha256':sha(pp.read_bytes())}
    (audit/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='conditions'}))

if __name__=='__main__': main()

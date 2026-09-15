"""Loss-aware synthetic BPF synthesis and public-input numerical repair search."""
from __future__ import annotations
import math
import random
from copy import deepcopy

from rf_repair.nonideal import protected_patch
from rf_repair.netlist import spice_value_si, validate_component_quantity
from rf_repair.extensions import deterministic_candidates
from rf_repair.transfer import response_schema

MODEL = {'inductor_rs_ohm': .05, 'capacitor_rs_ohm': .02,
         'inductor_cp_f': 1e-13, 'capacitor_esl_h': 2e-10}
HOLDOUT = [(109e6,.16),(143e6,.18),(191e6,.20),(229e6,.22)]
PROMPT = ('Diagnose one main L/C component-value fault in a synthetic lossy passive lumped RF filter. '
          'Use only the observed netlist, public main-component connectivity, specification and measured evidence. '
          'Return one value edit on an allowed main component; all parasitics, loss resistors and RF ports are protected. '
          'Every proposal is independently applied to the initial faulty netlist, not cumulatively. '
          'The healthy netlist, nominal values, fault labels and oracle are unavailable. '
          'Numerical search candidates use the disclosed equivalent circuit model and observed values; '
          'their predicted metrics are not native SPICE verification or guaranteed fault labels. '
          'You may choose a listed candidate or another allowed value. Use previous measured failures if supplied. '
          'Use positive finite SPICE numeric tokens, L in 1e-15..1e3 H and C in 1e-18..1 F. '
          'Keep evidence concise. An external native ngspice validator decides recovery.')


def specification(f0,bw):
    return {'target_center_frequency_hz':f0,'reference_impedance_ohm':50.,'measurement_frequency_tolerance_hz':1.,
        'measurement_frequencies_hz':{'center':f0,'lower_passband_edge':f0*(1-bw/2),
            'upper_passband_edge':f0*(1+bw/2),'lower_stopband':f0*.7,'upper_stopband':f0*1.4},
        'constraints':{'center_frequency_relative_tolerance_max':.03,'s21_at_center_db_min':-2.,
            's11_at_center_db_max':-15.,'s21_at_lower_passband_edge_db_min':-6.,
            's21_at_upper_passband_edge_db_min':-6.,'s21_at_lower_stopband_db_max':-12.,
            's21_at_upper_stopband_db_max':-12.}}


def compensated_value(kind, target, f0):
    """Match the ideal branch reactance at f0; finite real loss is retained."""
    w=2*math.pi*f0
    if kind=='C': return 1/(1/target+w*w*MODEL['capacitor_esl_h'])
    desired=w*target; r=MODEL['inductor_rs_ohm']; cp=MODEL['inductor_cp_f']
    lo=target*.1; hi=min(target*2,.8/(w*w*cp))
    def imag(v):
        z=complex(r,w*v)
        return (z/(1+z*complex(0,w*cp))).imag
    if not imag(lo)<desired<imag(hi): raise ValueError('cannot bracket compensated inductor')
    for _ in range(60):
        mid=(lo+hi)/2
        if imag(mid)<desired: lo=mid
        else: hi=mid
    return (lo+hi)/2


def make_design(f0,bw,seed,design_id,tolerance=.02):
    rng=random.Random(seed); w=2*math.pi*f0
    ideal=[50/(w*bw),bw/(50*w),50*bw/(2*w),2/(50*w*bw),50/(w*bw),bw/(50*w)]
    names=[k+str(n) for k,n in zip('LCLCLC',rng.sample(range(101,999),6))]
    a,b,c,d,e=['N'+str(n) for n in rng.sample(range(1001,9999),5)]
    edges=[(a,b),(b,c),(c,'0'),(c,'0'),(c,d),(d,e)]
    values={}; nominal={}; deviations={}
    for name,v in zip(names,ideal):
        nominal[name]=compensated_value(name[0],v,f0)
        deviations[name]=rng.uniform(-tolerance,tolerance)
        values[name]=f'{nominal[name]*(1+deviations[name]):.12g}'
    order=list(range(6)); rng.shuffle(order)
    # Connectivity and fixed equivalent-circuit coefficients are public; values above are private evaluator data.
    public={'main_components':[{'component':n,'nodes':list(edge)} for n,edge in zip(names,edges)],
            'ports':[a,e],'line_order':order,'frequency_hz':f0,'model':deepcopy(MODEL)}
    return {'design_id':design_id,'public_model':public,'nominal_values':nominal,'healthy_values':values,
            'tolerance':tolerance,'deviations':deviations,'spec':specification(f0,bw)}


def render(public, values, *, core_only=False, model_override=None):
    m=model_override or public['model']; f0=public['frequency_hz']
    names=[p['component'] for p in public['main_components']]
    if set(values)!=set(names): raise ValueError('need exactly the allowed main values')
    lines=['* Synthetic loss-aware two-port network',
        f"VPORT1 {public['ports'][0]} 0 DC 0 AC 1 portnum 1 z0 50",
        f"VPORT2 {public['ports'][1]} 0 DC 0 AC 1 portnum 2 z0 50"]
    for i in public['line_order']:
        p=public['main_components'][i]; n=p['component']; a,b=p['nodes']; validate_component_quantity(values[n],n)
        if not core_only:
            if n[0]=='L' and m['inductor_cp_f']: lines.append(f'CP_{n} {a} {b} {m["inductor_cp_f"]:.12g}')
            r=m['inductor_rs_ohm'] if n[0]=='L' else m['capacitor_rs_ohm']
            if r: lines.append(f'RS_{n} {a} XRS_{n} {r:.12g}'); a=f'XRS_{n}'
            if n[0]=='C' and m['capacitor_esl_h']:
                lines.append(f'LS_{n} {a} XLS_{n} {m["capacitor_esl_h"]:.12g}'); a=f'XLS_{n}'
        lines.append(f'{n} {a} {b} {values[n]}')
    return '\n'.join(lines+[f'.sp lin 2001 {f0*.5:.12g} {f0*1.5:.12g}', '.end'])+'\n'


def observed_values(source,public):
    tokens={t[0]:t for t in map(str.split,source.splitlines()) if len(t)==4}
    return {p['component']:tokens[p['component']][3] for p in public['main_components']}


def patch(source, public, component, value):
    validate_component_quantity(value,component)
    return protected_patch(source,component,value,[p['component'] for p in public['main_components']])


def schema(public):
    dummy=render(public,{p['component']:'1' for p in public['main_components']},core_only=True)
    return response_schema(dummy)


def native_values(source):
    return {t[0]:float(t[3]) for t in map(str.split,source.splitlines()) if len(t)==4 and t[0][0] in 'RLC'}


def curve(public,values,frequencies):
    m=public['model']; ordered=[(p['component'][0],spice_value_si(values[p['component']])) for p in public['main_components']]
    out=[]
    for f in frequencies:
        w=2*math.pi*f; z=[]
        for kind,v in ordered:
            if kind=='L':
                branch=complex(m['inductor_rs_ohm'],w*v)
                branch=branch/(1+branch*complex(0,w*m['inductor_cp_f']))
            else: branch=complex(m['capacitor_rs_ohm'],w*m['capacitor_esl_h']-1/(w*v))
            z.append(branch)
        zl=z[0]+z[1]; yr=1/z[2]+1/z[3]; zr=z[4]+z[5]
        a=1+zl*yr; b=zl+zr+zl*yr*zr; c=yr; d=1+yr*zr; den=a+b/50+c*50+d
        mags=[abs((a+b/50-c*50-d)/den),abs(2/den),abs((-a+b/50-c*50+d)/den)]
        out.append([f,*[20*math.log10(max(v,1e-150)) for v in mags]])
    return out


def predict(public,values,spec):
    f0=public['frequency_hz']; frequencies=[f0*.5+i*f0/2000 for i in range(2001)]
    rows=curve(public,values,frequencies); peak=max(rows,key=lambda r:r[2]); samples={}
    for n,f in spec['measurement_frequencies_hz'].items():
        index=round((f-f0*.5)/(f0/2000)); r=rows[index]
        if abs(r[0]-f)>1: raise ValueError('off-grid prediction')
        samples[n]={'requested_frequency_hz':f,'measured_frequency_hz':r[0],'s11_db':r[1],'s21_db':r[2],'s22_db':r[3]}
    return {'simulation_converged':True,'point_count':2001,'peak_s21_db':peak[2],
            'peak_frequency_hz':peak[0],'peak_frequency_relative_error':abs(peak[0]-f0)/f0,'samples':samples}


def objective(metrics,spec,factor):
    c=spec['constraints']; s=metrics['samples']
    violations=[max(0,metrics['peak_frequency_relative_error']/c['center_frequency_relative_tolerance_max']-1),
        max(0,c['s21_at_center_db_min']-s['center']['s21_db']),max(0,s['center']['s11_db']-c['s11_at_center_db_max'])]
    violations += [max(0,c[f's21_at_{n}_db_min']-s[n]['s21_db']) for n in ['lower_passband_edge','upper_passband_edge']]
    violations += [max(0,s[n]['s21_db']-c[f's21_at_{n}_db_max']) for n in ['lower_stopband','upper_stopband']]
    # Small tie-breaker favors center matching and small edits within feasible solutions.
    return sum(v*v for v in violations)+.001*(10**(s['center']['s11_db']/10)+.01*abs(math.log(factor)))


def numerical_search(source,public,spec):
    """Fixed full-grid forward-model budget, same cached output for deterministic and LLM policies."""
    values=observed_values(source,public); candidates=[]; evaluations=0
    for name in sorted(values):
        base=spice_value_si(values[name]); logmin=math.log(.4); step=math.log(2.5/.4)/40
        cache={}
        def evaluate(x):
            nonlocal evaluations
            key=f'{base*math.exp(x):.12g}'
            if key not in cache:
                candidate={**values,name:key}; metrics=predict(public,candidate,spec)
                cache[key]=(objective(metrics,spec,float(key)/base),metrics,x); evaluations+=1
            return cache[key][0]
        xs=[logmin+i*step for i in range(41)]; scores=[evaluate(x) for x in xs]
        best=min(range(41),key=lambda i:scores[i]); left=xs[max(0,best-1)]; right=xs[min(40,best+1)]
        ratio=(math.sqrt(5)-1)/2
        x1=right-ratio*(right-left); x2=left+ratio*(right-left)
        y1=evaluate(x1); y2=evaluate(x2)
        for _ in range(16):
            if y1<y2: right,x2,y2=x2,x1,y1; x1=right-ratio*(right-left); y1=evaluate(x1)
            else: left,x1,y1=x1,x2,y2; x2=left+ratio*(right-left); y2=evaluate(x2)
        value,(score,metrics,_)=min(cache.items(),key=lambda item:(item[1][0],item[0]))
        if spice_value_si(value)!=base:
            candidates.append({'component':name,'proposed_value':value,'model_score':score,'predicted_metrics':metrics})
    candidates.sort(key=lambda c:(c['model_score'],c['component']))
    return {'method':'Public lossy ABCD full-grid one-coordinate search: 41 log-spaced values x6, then 18 golden-section evaluations per coordinate',
            'forward_model_evaluations':evaluations,'frequency_points_per_evaluation':2001,'candidates':candidates[:3]}


def ideal_candidates(source,public):
    core=render(public,observed_values(source,public),core_only=True)
    return deterministic_candidates(core,public['frequency_hz'])


def payload(case,history):
    out={'faulty_netlist':case['faulty_netlist'],'public_main_component_model':case['public_model'],
         'target_specification':case['spec'],'initial_simulation':case['initial_metrics'],
         'numerical_search':case['numerical_search']}
    if history: out['previous_attempts']=deepcopy(history)
    return out

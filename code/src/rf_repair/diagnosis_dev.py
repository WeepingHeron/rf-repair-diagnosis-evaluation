"""Small injected changes and heterogeneous nuisance development data; gates unchanged."""
import hashlib
import math
import random
from copy import deepcopy
from rf_repair import lossy, reference, robustness

DESIGNS=[(127e6,.18),(173e6,.20),(217e6,.22),(269e6,.24)]
CHANGES=[-.10,-.03,-.01,.01,.03,.10]


def cohort():
    out=[]
    for index,(freq,bw) in enumerate(DESIGNS):
        d=lossy.make_design(freq,bw,202609100+index,f'diagdev_d{index+1}',.02)
        p=d['public_model'];historical=lossy.render(p,d['healthy_values'])
        common=dict(design_id=d['design_id'],public_model=p,spec=d['spec'],historical_netlist=historical,design_evaluator_only=d)
        out.append(common|dict(cohort_id=d['design_id']+'_control',kind='control',current_netlist=historical,
            expected_component=None,expected_direction=None,change_fraction=0.))
        for part in p['main_components']:
            name=part['component']
            for change in CHANGES:
                source=lossy.patch(historical,p,name,f'{float(d["healthy_values"][name])*(1+change):.12g}')
                suffix=('m' if change<0 else 'p')+f'{abs(change)*100:g}'
                out.append(common|dict(cohort_id=f'{d["design_id"]}_{name}_{suffix}',kind='fault',current_netlist=source,
                    expected_component=name,expected_direction='value_too_low' if change<0 else 'value_too_high',change_fraction=change))
    assert len(out)==148
    return out


def profiles():
    out=[dict(profile_id='clean',family='clean',draw=0,noise_sigma_db=0.,drift_amplitude=0.,model_amplitude=0.)]
    for family,noise,drift,model in [('noise',.01,0.,0.),('drift_0.1pct',0.,.001,0.),
            ('drift_0.5pct',0.,.005,0.),('model_10pct',0.,0.,.1),('combined',.01,.001,.1)]:
        for draw in range(3):
            out.append(dict(profile_id=f'{family}_{draw}',family=family,draw=draw,
                noise_sigma_db=noise,drift_amplitude=drift,model_amplitude=model))
    return out


def vectors(design_id,draw):
    out={}
    for tag,n in [('noise',27),('drift',6),('model',12)]:
        seed=int(hashlib.sha256(f'diagnosis_dev_v1|{design_id}|{draw}|{tag}'.encode()).hexdigest()[:16],16)
        rng=random.Random(seed)
        out[tag]=dict(seed=seed,values=[rng.gauss(0.,1.) if tag=='noise' else rng.uniform(-1.,1.) for _ in range(n)])
    return out


def historical_model_source(item,profile,v):
    """Twelve independent fixed equivalent-element deviations, hidden from the estimator."""
    names=[p['component'] for p in item['public_model']['main_components']]
    elements={}
    for i,n in enumerate(names):
        elements['RS_'+n]=v['model']['values'][2*i]
        elements[('CP_' if n[0]=='L' else 'LS_')+n]=v['model']['values'][2*i+1]
    rows=[]
    for line in item['historical_netlist'].splitlines():
        t=line.split()
        if t and t[0] in elements and profile['model_amplitude']:
            t[3]=f'{float(t[3])*(1+profile["model_amplitude"]*elements[t[0]]):.12g}';line=' '.join(t)
        rows.append(line)
    return '\n'.join(rows)+'\n'


def heterogeneous_curve(source,public,frequencies):
    """ABCD for the known six-branch topology, reading each actual R/C/L coefficient."""
    tokens={t[0]:float(t[3]) for t in map(str.split,source.splitlines()) if len(t)==4 and t[0][0] in 'RLC'}
    names=[p['component'] for p in public['main_components']];out=[]
    for f in frequencies:
        w=2*math.pi*f;zs=[]
        for n in names:
            value=tokens[n];rs=tokens.get('RS_'+n,0.)
            if n[0]=='L':
                z=complex(rs,w*value);z=z/(1+z*complex(0,w*tokens.get('CP_'+n,0.)))
            else:z=complex(rs,w*tokens.get('LS_'+n,0.)-1/(w*value))
            zs.append(z)
        left=zs[0]+zs[1];shunt=1/zs[2]+1/zs[3];right=zs[4]+zs[5]
        a=1+left*shunt;b=left+right+left*shunt*right;c=shunt;d=1+shunt*right
        denominator=a+b/50+c*50+d
        mags=[abs((a+b/50-c*50-d)/denominator),abs(2/denominator),abs((-a+b/50-c*50+d)/denominator)]
        out.append([f,*[20*math.log10(max(m,1e-150)) for m in mags]])
    return out


def inputs(item,profile):
    for k in ['noise_sigma_db','drift_amplitude','model_amplitude']:
        if not math.isfinite(profile[k]) or not 0<=profile[k]<1:raise ValueError('invalid nuisance')
    v=vectors(item['design_id'],profile['draw']);public=deepcopy(item['public_model'])
    physical=historical_model_source(item,profile,v)
    freq=[public['frequency_hz']*r for r in reference.RATIOS]
    clean=heterogeneous_curve(physical,public,freq)
    samples=[dict(frequency_hz=f,**{k:round(row[j+1]+profile['noise_sigma_db']*v['noise']['values'][3*i+j],2)
                    for j,k in enumerate(robustness.CHANNELS)}) for i,(f,row) in enumerate(zip(freq,clean,strict=True))]
    current=lossy.observed_values(item['current_netlist'],public)
    if profile['drift_amplitude']:
        for i,part in enumerate(public['main_components']):
            name=part['component'];current[name]=f'{float(current[name])*(1+profile["drift_amplitude"]*v["drift"]["values"][i]):.12g}'
    return dict(estimator_input=dict(source=lossy.render(public,current),public=public,
                    reference=dict(quantization_db=.01,samples=samples,origin='Synthetic heterogeneous development spectrum')),
        generation=dict(historical_source=physical,clean_curve=clean,vectors=v))


def features(estimator_input,fit):
    e=estimator_input;samples=e['reference']['samples'];vals=lossy.observed_values(e['source'],e['public'])
    pred=lossy.curve(e['public'],vals,[s['frequency_hz'] for s in samples])
    e0=math.sqrt(sum((v-s[k])**2 for row,s in zip(pred,samples,strict=True) for v,k in zip(row[1:],robustness.CHANNELS))/27)
    best,second=fit['hypotheses'][:2]
    return dict(no_change_rmse_db=e0,best_rmse_db=best['rmse_db'],second_rmse_db=second['rmse_db'],
        gap_db=second['rmse_db']-best['rmse_db'],improvement_db=e0-best['rmse_db'],
        inferred_change_fraction=float(vals[best['component']])/float(best['inferred_prefault_value'])-1)


def aggregate(rows):
    out={}
    for r in rows:
        key=r['family']+'/'+f'{abs(r["change_fraction"])*100:g}'
        g=out.setdefault(key,dict(family=r['family'],magnitude_pct=abs(r['change_fraction'])*100,
            faults=0,controls=0,correct=0,abstained=0,wrong=0,false_alarm=0,top_rank_correct=0))
        if r['kind']=='fault':
            g['faults']+=1;g['correct']+=r['score']['correct'];g['abstained']+=r['score']['abstained']
            g['wrong']+=r['score']['wrong_diagnosis'];g['top_rank_correct']+=r['top_rank_correct']
        else:g['controls']+=1;g['false_alarm']+=r['score']['false_alarm']
    return out

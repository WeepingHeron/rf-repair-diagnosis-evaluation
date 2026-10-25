"""Historical S-parameter evidence and bounded single-component inverse fitting."""
import math
from copy import deepcopy
from rf_repair.lossy import make_design,render,patch,observed_values,curve
from rf_repair.netlist import spice_value_si
from rf_repair.diagnosis import schema

DESIGNS=[(115e6,.16),(153e6,.18),(203e6,.20),(257e6,.22)]
RATIOS=[.70,.85,.92,.96,1.,1.04,1.08,1.15,1.4]
CONDITIONS=['current_only','historical_reference','reference_with_fit']
FIELDS=['localized','diagnosed','abstained','direction_unknown','false_location','matches_fit_component']
PROMPT=('Diagnose the originally faulty main L/C component and value-error direction in a synthetic lossy passive RF filter. '
        'Exactly one main L/C value changed; fixed loss resistors, parasitics and RF ports are not faulty. '
        'Use only the supplied current netlist, public model, target specification and measurements. '
        'Optional pre-fault reference measurements are magnitudes at the same frequencies, rounded to 0.01 dB; '
        'they emulate a stored baseline sweep, not a list of healthy component values. '
        'If inverse-fit hypotheses are supplied, they are calculated from the current network and that reference, '
        'not oracle fault labels; judge their residuals and separation under the stated model assumptions. '
        'The healthy netlist, nominal component values and fault manifest are unavailable. '
        'Report diagnosis only, not a repair. Fault direction compares the current value to its pre-fault value. '
        'Use component unknown and fault_type unknown_direction when the faulty component is not determined by the evidence. '
        'An identified component may have unknown_direction if direction is uncertain. Keep evidence concise.')

def cases():
    out=[]
    for i,(f0,bw) in enumerate(DESIGNS):
        d=make_design(f0,bw,202609090+i,f'reference_d{i+1}',.02);p=d['public_model'];healthy=render(p,d['healthy_values'])
        for j,index in enumerate([[0,3],[1,2],[4,3],[5,2]][i]):
            component=p['main_components'][index]['component'];value=d['healthy_values'][component];mult=[.55,1.8][j]
            faulty=patch(healthy,p,component,f'{float(value)*mult:.12g}')
            out.append({'case_id':f'reference_d{i+1}_f{j+1}','design_id':d['design_id'],'public_model':p,'spec':d['spec'],
                'healthy_netlist':healthy,'faulty_netlist':faulty,'component':component,'healthy_value':value,'multiplier':mult,
                'fault_type':'value_too_low' if mult<1 else 'value_too_high','design_evaluator_only':d})
    return out

def spectrum_from_table(path,f0):
    with path.open() as f:
        if f.readline().split()!=['frequency','db(s_1_1)','db(s_2_1)','db(s_2_2)']:raise ValueError('unexpected spectrum header')
        rows=[list(map(float,line.split())) for line in f]
    if not rows or any(len(r)!=4 or not all(map(math.isfinite,r)) for r in rows):raise ValueError('invalid spectrum')
    samples=[]
    for ratio in RATIOS:
        requested=f0*ratio;r=min(rows,key=lambda r:abs(r[0]-requested))
        if abs(r[0]-requested)>1:raise ValueError('missing requested frequency')
        samples.append(dict(frequency_hz=r[0],**{k:round(v,2) for k,v in zip(['s11_db','s21_db','s22_db'],r[1:])}))
    return {'origin':'Synthetic ngspice emulation, not hardware measurement','quantization_db':.01,
            'representation':'20 log10 magnitude; no phase; no added noise or calibration drift','samples':samples}

def fit_reference(source,public,reference):
    """Fit only measured pre-fault spectral magnitudes; never healthy values or fault labels."""
    samples=reference['samples']
    if len(samples)!=9 or reference.get('quantization_db')!=.01:raise ValueError('wrong measurement contract')
    frequencies=[s['frequency_hz'] for s in samples]
    expected=[public['frequency_hz']*r for r in RATIOS]
    if any(not math.isfinite(f) or abs(f-e)>1 for f,e in zip(frequencies,expected)):raise ValueError('invalid reference frequencies')
    targets=[[s[k] for k in ['s11_db','s21_db','s22_db']] for s in samples]
    if not all(math.isfinite(x) for row in targets for x in row):raise ValueError('invalid reference measurements')
    values=observed_values(source,public);candidates=[];calls=0
    for component in sorted(values):
        base=spice_value_si(values[component]);cache={};left0=math.log(.4);step=math.log(2.5/.4)/40
        def evaluate(x):
            nonlocal calls
            value=f'{base*math.exp(x):.12g}'
            if value not in cache:
                predicted=curve(public,{**values,component:value},frequencies)
                mse=sum((a-b)**2 for row,target in zip(predicted,targets) for a,b in zip(row[1:],target))/27
                cache[value]=mse;calls+=1
            return cache[value]
        grid=[left0+i*step for i in range(41)];scores=[evaluate(x) for x in grid];i=min(range(41),key=lambda i:scores[i])
        left=grid[max(0,i-1)];right=grid[min(40,i+1)];ratio=(math.sqrt(5)-1)/2
        x1=right-ratio*(right-left);x2=left+ratio*(right-left);y1=evaluate(x1);y2=evaluate(x2)
        for _ in range(24):
            if y1<y2:right,x2,y2=x2,x1,y1;x1=right-ratio*(right-left);y1=evaluate(x1)
            else:left,x1,y1=x1,x2,y2;x2=left+ratio*(right-left);y2=evaluate(x2)
        value,mse=min(cache.items(),key=lambda x:(x[1],x[0]));prior=float(value)
        direction='value_too_high' if base>prior else 'value_too_low' if base<prior else 'unknown_direction'
        candidates.append({'component':component,'inferred_prefault_value':value,'current_fault_direction':direction,'rmse_db':math.sqrt(mse)})
    candidates.sort(key=lambda p:(p['rmse_db'],p['component']))
    resolved=candidates[0]['rmse_db']<=.02 and candidates[1]['rmse_db']>=.10
    return {'method':'Single-main-component inverse fit to 9 pre-fault S11/S21/S22 magnitude samples; 41 log grid + 26 golden-section evaluations per component',
        'forward_model_evaluations':calls,'frequency_points_per_evaluation':9,'search_factor_range':[.4,2.5],
        'acceptance':{'best_rmse_db_max':.02,'runner_up_rmse_db_min':.10},'resolved_within_search':resolved,
        'assumptions':'Exactly one main value changed; current values and fixed equivalent model known; no drift or noise beyond 0.01 dB rounding. This bounded fit is not a global identifiability proof.',
        'hypotheses':candidates}

def deterministic_diagnosis(fit):
    if not fit['resolved_within_search']:return {'component':'unknown','fault_type':'unknown_direction'}
    first=fit['hypotheses'][0]
    return {'component':first['component'],'fault_type':first['current_fault_direction']}

def payload(case,condition):
    if condition not in CONDITIONS:raise ValueError('unknown condition')
    out={'faulty_netlist':case['faulty_netlist'],'public_main_component_model':deepcopy(case['public_model']),
         'target_specification':deepcopy(case['spec']),'initial_simulation':deepcopy(case['initial_metrics']),
         'current_spectrum':deepcopy(case['current_spectrum'])}
    if condition in CONDITIONS[1:]:out['prefault_reference_spectrum']=deepcopy(case['reference_spectrum'])
    if condition==CONDITIONS[2]:out['reference_inverse_fit']=deepcopy(case['reference_fit'])
    return out

def score(proposal,case):
    if proposal['component']=='unknown' and proposal['fault_type']!='unknown_direction':raise ValueError('inconsistent abstention')
    localized=proposal['component']==case['component']
    return {'localized':localized,'diagnosed':localized and proposal['fault_type']==case['fault_type'],
        'abstained':proposal['component']=='unknown','direction_unknown':proposal['fault_type']=='unknown_direction',
        'false_location':proposal['component'] not in {'unknown',case['component']},
        'matches_fit_component':proposal['component']==case['reference_fit']['hypotheses'][0]['component']}

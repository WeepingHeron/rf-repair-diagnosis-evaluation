"""Candidate-visibility ablation with identical diagnostic instructions and one-call budgets."""
from copy import deepcopy
from rf_repair.lossy import make_design,render,patch

DESIGNS=[(101e6,.16),(163e6,.18),(199e6,.20),(241e6,.22)]
CONDITIONS=['diagnose_before_candidates','diagnose_with_candidates']
PROMPT=('Diagnose the originally faulty main L/C component and value-error direction in a synthetic lossy passive RF filter. '
        'Exactly one main L/C value was changed; fixed loss resistors, parasitics and RF ports are not faulty. '
        'Use only the observed netlist, public component model, target specification and measured evidence. '
        'The healthy netlist, nominal component values and fault labels are unavailable. '
        'If numerical repair candidates are present, they are optional model predictions for restoring performance, '
        'not verified fault labels: changing another component can compensate for the real fault. '
        'Report diagnosis only; do not propose or select a repair. '
        'Use component unknown and fault_type unknown_direction when the original faulty component cannot be determined from the evidence. '
        'An identified component may have unknown_direction if its direction is uncertain. '
        'Do not infer that a successful repair candidate must identify the fault. Keep the evidence concise.')


def cases():
    out=[]
    for i,(f0,bw) in enumerate(DESIGNS):
        d=make_design(f0,bw,202609080+i,f'diagnosis_d{i+1}',.02);public=d['public_model']
        healthy=render(public,d['healthy_values'])
        for j,index in enumerate([[0,3],[1,2],[4,3],[5,2]][i]):
            component=public['main_components'][index]['component'];multiplier=[.55,1.8][j]
            value=d['healthy_values'][component]
            faulty=patch(healthy,public,component,f'{float(value)*multiplier:.12g}')
            out.append({'case_id':f'diagnosis_d{i+1}_f{j+1}','design_id':d['design_id'],
                'public_model':public,'spec':d['spec'],'healthy_netlist':healthy,'faulty_netlist':faulty,
                'component':component,'fault_type':'value_too_low' if multiplier<1 else 'value_too_high',
                'healthy_value':value,'multiplier':multiplier,'design_evaluator_only':d})
    return out


def payload(case,condition):
    if condition not in CONDITIONS:raise ValueError('unknown condition')
    out={'faulty_netlist':case['faulty_netlist'],'public_main_component_model':deepcopy(case['public_model']),
        'target_specification':deepcopy(case['spec']),'initial_simulation':deepcopy(case['initial_metrics'])}
    if condition=='diagnose_with_candidates':out['numerical_search']=deepcopy(case['numerical_search'])
    return out


def schema(public):
    return {'type':'object','properties':{
        'component':{'type':'string','enum':sorted(p['component'] for p in public['main_components'])+['unknown']},
        'fault_type':{'type':'string','enum':['value_too_low','value_too_high','unknown_direction']},
        'evidence':{'type':'string','maxLength':600}},'required':['component','fault_type','evidence'],'additionalProperties':False}


def score(proposal,case):
    if proposal['component']=='unknown' and proposal['fault_type']!='unknown_direction':
        raise ValueError('unknown component must have unknown direction')
    localized=proposal['component']==case['component']
    return {'localized':localized,'diagnosed':localized and proposal['fault_type']==case['fault_type'],
            'abstained':proposal['component']=='unknown','direction_unknown':proposal['fault_type']=='unknown_direction',
            'false_location':proposal['component'] not in {'unknown',case['component']},
            'matches_top_repair_component':proposal['component']==case['numerical_search']['candidates'][0]['component']}

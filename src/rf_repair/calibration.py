"""Predeclared design-disjoint cohorts for abstention calibration and final evaluation."""
from rf_repair import lossy, diagnosis_dev as dev
SPLITS={'calibration':[(133e6,.18),(179e6,.20),(227e6,.22),(283e6,.24)],
        'holdout':[(147e6,.18),(193e6,.20),(251e6,.22),(307e6,.24)]}


def cohort(split):
    out=[];seed0=202609110 if split=='calibration' else 202609120
    for i,(freq,bw) in enumerate(SPLITS[split]):
        d=lossy.make_design(freq,bw,seed0+i,f'abstention_{split}_d{i+1}',.02);p=d['public_model']
        healthy=lossy.render(p,d['healthy_values']);common=dict(design_id=d['design_id'],public_model=p,spec=d['spec'],historical_netlist=healthy,design_evaluator_only=d)
        out.append(common|dict(cohort_id=d['design_id']+'_control',kind='control',current_netlist=healthy,expected_component=None,expected_direction=None,change_fraction=0.))
        for part in p['main_components']:
            n=part['component']
            for change in dev.CHANGES:
                source=lossy.patch(healthy,p,n,f'{float(d["healthy_values"][n])*(1+change):.12g}')
                suffix=('m' if change<0 else 'p')+f'{abs(change)*100:g}'
                out.append(common|dict(cohort_id=f'{d["design_id"]}_{n}_{suffix}',kind='fault',current_netlist=source,
                    expected_component=n,expected_direction='value_too_low' if change<0 else 'value_too_high',change_fraction=change))
    assert len(out)==148
    return out

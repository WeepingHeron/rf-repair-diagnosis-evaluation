"""Input-derived multi-gate diagnosis with calibrated empirical-null and stability checks."""
import hashlib
import itertools
import json
import math
import random
from copy import deepcopy
from rf_repair import reference, diagnosis_dev as dev

UNKNOWN={'component':'unknown','fault_type':'unknown_direction'}
FIT_MAX=[.01,.015,.02]
GAP_MIN=[.015,.03,.05,.08]
RATIO_MIN=[3.,5.,10.]
FLOOR_DB=.01
STABILITY_DRAWS=4


def candidates():
    return [dict(fit_max_db=a,gap_min_db=b,ratio_min=c) for a,b,c in itertools.product(FIT_MAX,GAP_MIN,RATIO_MIN)]


def measure_features(e,fit):
    f=dev.features(e,fit)
    f['separation_ratio']=f['second_rmse_db']/max(f['best_rmse_db'],FLOOR_DB)
    f['null_score']=f['improvement_db']/max(f['best_rmse_db'],FLOOR_DB)
    return f


def may_qualify(f):
    return f['best_rmse_db']<=max(FIT_MAX) and f['gap_db']>=min(GAP_MIN) and f['separation_ratio']>=min(RATIO_MIN)


def perturbations(e):
    encoded=json.dumps(e,sort_keys=True,allow_nan=False).encode()
    seed=int(hashlib.sha256(b'abstention_v1|'+encoded).hexdigest()[:16],16)
    rng=random.Random(seed);out=[]
    for index in range(STABILITY_DRAWS):
        copied=deepcopy(e);offsets=[]
        for sample in copied['reference']['samples']:
            for key in ['s11_db','s21_db','s22_db']:
                delta=FLOOR_DB*(1 if rng.getrandbits(1) else -1)
                sample[key]=round(sample[key]+delta,2);offsets.append(delta)
        out.append(dict(draw=index,seed=seed,offsets_db=offsets,input=copied))
    return out


def collect(e):
    """No case labels, nominal values, nuisance truth or optimistic caller scores accepted."""
    fit=reference.fit_reference(**e);f=measure_features(e,fit);top=fit['hypotheses'][0]
    stability=[]
    if may_qualify(f):
        for p in perturbations(e):
            changed=reference.fit_reference(**p['input']);candidate=changed['hypotheses'][0]
            stability.append(dict(draw=p['draw'],seed=p['seed'],offsets_db=p['offsets_db'],fit=changed,
                matches=candidate['component']==top['component'] and candidate['current_fault_direction']==top['current_fault_direction']))
    return dict(fit=fit,features=f,stability=stability,stability_matches=sum(s['matches'] for s in stability))


def validate_policy(policy):
    params=policy['parameters']
    if {k:params[k] for k in ['fit_max_db','gap_min_db','ratio_min']} not in candidates():raise ValueError('unregistered parameter combination')
    if not math.isfinite(params['null_score_min']) or params['null_score_min']<1:raise ValueError('invalid null threshold')
    if params.get('stability_required')!=4 or params.get('score_floor_db')!=FLOOR_DB:raise ValueError('changed fixed policy')
    if policy.get('status')!='CALIBRATED_SYNTHETIC':raise ValueError('uncalibrated policy')
    return params


def decide(bundle,policy):
    """Pure internal decision; public callers use diagnose(), which recomputes all evidence."""
    p=validate_policy(policy);f=bundle['features'];reasons=[]
    if not all(math.isfinite(v) for v in f.values()):raise ValueError('nonfinite features')
    if f['best_rmse_db']>p['fit_max_db']:reasons.append('MODEL_MISMATCH')
    if f['gap_db']<p['gap_min_db'] or f['separation_ratio']<p['ratio_min']:reasons.append('AMBIGUOUS_COMPONENT')
    if f['null_score']<p['null_score_min']:reasons.append('CHANGE_NOT_DISTINGUISHED_FROM_NULL')
    if len(bundle['stability'])!=4 or bundle['stability_matches']!=4:reasons.append('STABILITY_NOT_CONFIRMED')
    top=bundle['fit']['hypotheses'][0]
    diagnosis=UNKNOWN.copy() if reasons else dict(component=top['component'],fault_type=top['current_fault_direction'])
    return dict(diagnosis=diagnosis,abstained=bool(reasons),reasons=reasons)


def diagnose(e,policy):
    try:
        validate_policy(policy)
        bundle=collect(e)
        return dict(**decide(bundle,policy),evidence=bundle)
    except (ValueError,TypeError,KeyError,IndexError,OverflowError,ZeroDivisionError) as exc:
        return dict(diagnosis=UNKNOWN.copy(),abstained=True,reasons=['INVALID_INPUT_OR_POLICY'],error_type=type(exc).__name__)


def select(calibration_rows,protocol_sha256,rows_sha256):
    """Empirical calibration only; no probabilistic risk guarantee or holdout access."""
    controls=[r for r in calibration_rows if r['kind']=='control']
    if not controls:raise ValueError('null controls required')
    maximum=max(0.,max(r['bundle']['features']['null_score'] for r in controls))
    null_min=max(1.,1.1*maximum)
    evaluated=[]
    for pars in candidates():
        policy=dict(status='CALIBRATED_SYNTHETIC',parameters=pars|dict(null_score_min=null_min,stability_required=4,score_floor_db=FLOOR_DB))
        stats=dict(correct=0,wrong=0,false_alarm=0,confirmed=0)
        for r in calibration_rows:
            d=decide(r['bundle'],policy)['diagnosis'];accepted=d['component']!='unknown'
            correct=r['kind']=='fault' and d['component']==r['truth']['component'] and d['fault_type']==r['truth']['fault_type']
            stats['correct']+=correct;stats['wrong']+=r['kind']=='fault' and accepted and not correct
            stats['false_alarm']+=r['kind']=='control' and accepted;stats['confirmed']+=accepted
        evaluated.append(dict(parameters=policy['parameters'],stats=stats))
    eligible=[r for r in evaluated if r['stats']['wrong']==0 and r['stats']['false_alarm']==0]
    if not eligible:raise ValueError('no zero-observed-error calibration rule')
    # Deterministic conservative tie break: smaller fit error, larger gap, larger ratio.
    chosen=min(eligible,key=lambda r:(-r['stats']['correct'],r['parameters']['fit_max_db'],-r['parameters']['gap_min_db'],-r['parameters']['ratio_min']))
    return dict(policy_id='diagnosis_abstention_v1',status='CALIBRATED_SYNTHETIC',parameters=chosen['parameters'],
        calibration_stats=chosen['stats'],null_control_count=len(controls),null_score_max=maximum,null_safety_multiplier=1.1,
        protocol_sha256=protocol_sha256,calibration_rows_sha256=rows_sha256,
        selection_scope='Zero observed calibration errors, not a bound on population risk; four calibration design clusters',
        candidate_results=evaluated)

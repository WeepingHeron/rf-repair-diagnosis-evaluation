"""Extend the frozen four-draw perturbation stream without changing the active policy."""
from copy import deepcopy
import hashlib
import json
import random


def perturbations(e,total=16):
    if type(total) is not int or total<4 or total>64:raise ValueError('unsupported draw count')
    encoded=json.dumps(e,sort_keys=True,allow_nan=False).encode()
    seed=int(hashlib.sha256(b'abstention_v1|'+encoded).hexdigest()[:16],16)
    rng=random.Random(seed)
    for draw in range(total):
        item=deepcopy(e);offsets=[]
        for sample in item['reference']['samples']:
            for channel in ['s11_db','s21_db','s22_db']:
                delta=.01*(1 if rng.getrandbits(1) else -1)
                sample[channel]=round(sample[channel]+delta,2);offsets.append(delta)
        yield dict(draw=draw,seed=seed,offsets_db=offsets,input=item)


def compare(fit,original):
    candidate=fit['hypotheses'][0];target=original['hypotheses'][0]
    return dict(component_matches=candidate['component']==target['component'],
        direction_matches=candidate['current_fault_direction']==target['current_fault_direction'],
        matches=candidate['component']==target['component'] and candidate['current_fault_direction']==target['current_fault_direction'])

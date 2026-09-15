"""Connect a qualified audited policy to the new diagnosis CLI, preserving frozen experiments."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from rf_repair import abstention
from run_abstention_calibration import PP,POLICY,OUT
from run_reference_robustness import read,write,digest,check


def main():
    protocol=read(PP);check(protocol);policy=read(POLICY);abstention.validate_policy(policy)
    auditpath=ROOT/'build/abstention_calibration_v1_audit/summary.json';audit=read(auditpath)
    assert audit['complete'] and not audit['issues'] and audit['protocol_sha256']==digest(PP.read_bytes())
    assert audit['policy_sha256']==digest(POLICY.read_bytes())
    for f,h in audit['row_sha256'].items():assert digest((ROOT/f).read_bytes())==h
    counts=dict(new_correct=0,legacy_correct=0,new_wrong=0,new_false_alarm=0)
    for path in (OUT/'holdout/rows').glob('*/*.json'):
        r=read(path);d=abstention.decide(r['bundle'],policy)['diagnosis'];accepted=d['component']!='unknown'
        correct=r['kind']=='fault' and accepted and d['component']==r['truth']['component'] and d['fault_type']==r['truth']['fault_type']
        counts['new_correct']+=correct;counts['legacy_correct']+=r['legacy_score']['correct']
        counts['new_wrong']+=r['kind']=='fault' and accepted and not correct;counts['new_false_alarm']+=r['kind']=='control' and accepted
    eligible=counts['new_wrong']==0 and counts['new_false_alarm']==0 and counts['new_correct']>=counts['legacy_correct']
    assert eligible==audit['eligible_to_activate']
    if not eligible:
        print('Not activated: predeclared holdout qualification failed');print(counts);return
    config=dict(status='ACTIVE_SYNTHETIC_VALIDATED',policy_id=policy['policy_id'],policy_path=str(POLICY.relative_to(ROOT)),
        policy_sha256=digest(POLICY.read_bytes()),audit_path=str(auditpath.relative_to(ROOT)),audit_sha256=digest(auditpath.read_bytes()),
        qualification=counts,scope='Synthetic single-value BPF diagnosis; design-disjoint four-design evaluation, not hardware or population-risk guarantee')
    path=ROOT/'configs/diagnosis_abstention.json';write(path,config);print(path);print(counts)

if __name__=='__main__':main()

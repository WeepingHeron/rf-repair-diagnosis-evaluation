"""Run the active calibrated synthetic diagnosis policy from raw observed inputs."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from rf_repair.abstention import diagnose,UNKNOWN


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--input',type=Path,required=True);parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    try:
        config=json.loads((ROOT/'configs/diagnosis_abstention.json').read_text())
        if config['status']!='ACTIVE_SYNTHETIC_VALIDATED':raise ValueError('policy not active')
        policy_path=ROOT/config['policy_path'];data=policy_path.read_bytes()
        if hashlib.sha256(data).hexdigest()!=config['policy_sha256']:raise ValueError('policy integrity failure')
        request=json.loads(args.input.read_text());e=request.get('estimator_input',request)
        result=diagnose(e,json.loads(data))
        result['policy_id']=config['policy_id'];result['scope']='Synthetic calibration domain; no hardware assurance'
    except (OSError,ValueError,KeyError,TypeError) as exc:
        result=dict(diagnosis=UNKNOWN.copy(),abstained=True,reasons=['POLICY_OR_INPUT_UNAVAILABLE'],error_type=type(exc).__name__)
    text=json.dumps(result,indent=2,allow_nan=False)+'\n'
    if args.output:args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(text)
    else:print(text,end='')

if __name__=='__main__':main()

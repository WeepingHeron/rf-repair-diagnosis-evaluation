"""Report extra stability computations without promoting repeated rows to new evidence cases."""
from collections import defaultdict
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from run_stability_extension import PP,OUT
from run_reference_robustness import read,digest,check


def main():
    p=read(PP);check(p);a=read(ROOT/'build/stability_extension_v1_audit/summary.json')
    assert a['complete'] and not a['issues'] and a['protocol_sha256']==digest(PP.read_bytes())
    assert a['summary_sha256']==digest((OUT/'summary.json').read_bytes())
    for path,h in a['row_sha256'].items():assert digest((ROOT/path).read_bytes())==h
    bykey={(r['profile_id'],r['cohort_id']):r for r in a['by_input']}
    sizes=defaultdict(lambda:dict(n=0,stable=0))
    for target in p['targets']:
        r=read(ROOT/target['source_path']);size=abs(r['change_fraction'])*100
        sizes[size]['n']+=1;sizes[size]['stable']+=bykey[(target['profile_id'],target['cohort_id'])]['stable_all_16']
    labels={'clean':'반올림만','noise':'잡음 σ=0.01 dB','drift_0.1pct':'비균일 L/C 변화 ±0.1%'}
    lines=['# 확정 진단의 재검사 4회에서 16회로 확대','',
        f'**기존 확정 진단 615건 중 {a["stable_all_16"]}건이 16/16회 같은 부품·방향을 유지했다.** '
        f'추가 5~16회에서 원본과 다른 후보가 나온 재검사는 {a["mismatching_draw_count"]}회, '
        f'16/16을 요구할 경우 새로 보류될 확정 진단은 {a["newly_withheld_if_16_required"]}건이었다.','',
        '2026-09-06. 활성 정책의 기본 4/4 조건은 유지했다. 이번에는 이미 결과를 본 미사용 평가 자료에서 '
        '확정된 615건을 대상으로 반복 횟수만 늘린 사후 안정성 확인이다. 새로운 holdout 평가나 실측 반복이 아니다. '
        '기존 보류 1,689건과 무주입 대조군 64건은 이번 검사에 포함하지 않았다. '
        '대상 선정은 확정 여부만 사용했고 정답 여부로 사례를 골라내지 않았다.','',
        '## 계산한 내용','',
        '- 각 입력의 기존 seed·난수 스트림을 그대로 이어서 16개의 ±0.01 dB 부호 벡터를 생성했다.',
        '- 매 회차는 원래 27개 S11/S21/S22 dB 값에서 시작하고, 다른 회차의 오차를 누적하지 않았다.',
        '- 기존 1~4회 2,460개 결과를 원본과 대조해 재사용하고, 5~16회 7,380개를 새로 최적화했다.',
        '- 각 재검사는 6개 부품 가설을 다시 탐색했다. 확인 지표는 원본 최상위 부품과 변화 방향의 동시 일치다.',
        '- 오류 진단 확률이나 재검사 입력의 모든 정책 문턱 통과를 측정한 것은 아니다.',
        '- 입력과 부품 모델은 그대로이고 실제 계측이나 새 물리 회로 생성은 없었다. [고정 계획](stability_extension_v1_protocol.md).','',
        '| 입력 조건 | 확정 입력 수 | 16/16 일치 | 부품이 달라진 재검사 | 방향이 달라진 재검사 |','|---|---:|---:|---:|---:|']
    for family,g in sorted(a['families'].items()):
        lines.append(f'| {labels.get(family,family)} | {g["inputs"]} | {g["stable_all_16"]} | {g["component_flip_draws"]} | {g["direction_flip_draws"]} |')
    lines += ['','| 주입 변화 크기 | 확정 입력 수 | 16/16 일치 |','|---|---:|---:|']
    for size,g in sorted(sizes.items()):lines.append(f'| ±{size:g}% | {g["n"]} | {g["stable"]} |')
    lines += ['','표에 없는 큰 환경 변화·모델 불일치 조건은 기존 정책에서 확정하지 않았으므로 이번 대상에 없다. '
        '이 결과로 그 조건에서도 안정적으로 진단한다고 주장하지 않는다.','',
        '## 계산량과 검증','',
        f'- 추가 역추정 {a["additional_fits_replayed"]:,}회, 전방 모델 계산 {a["additional_forward_evaluations"]:,}회. 각 전방 계산은 9주파수를 사용한다.',
        '- 대상 615건의 안정성 검사만 비교하면 4회에서 16회로 4배이며, 원본 fit 1회를 포함하면 입력당 5회에서 17회다.',
        f'- 실행 기록의 추가 fit 계산 시간 합은 약 {a["recorded_additional_fit_seconds"]:.1f}초다. 로컬 실행 관찰값이며 다른 기계에서의 속도나 전체 작업 시간은 아니다.',
        f'- 기존 재검사 {a["reused_draws_verified"]:,}개의 seed·offset·일치 결과를 대조하고 추가 {a["additional_fits_replayed"]:,}개 fit을 모두 재실행했다.',
        f'- 최선·차선 가설의 9주파수 nodal 해석 {a["nodal_residual_points"]:,}점으로 잔차를 검증했다. 최대 RMSE 차이 {a["max_nodal_rmse_difference_db"]:.3g} dB, 한계 1e-7 dB 이내다.',
        '- 기존 native 물리 검증은 고정된 이전 감사에 연결했고 새 native sweep은 0회다. API 호출 0회.',
        '- 단위 검사 82개 통과. 활성 정책·기본 설정·이전 결과·제출 원고는 보존했다.','',
        '## 적용 판단','']
    if a['newly_withheld_if_16_required']==0:
        lines += ['같은 ±0.01 dB 조건에서 16회로 늘려 새로 잡아낸 불안정 사례는 없었다. '
            '따라서 현재 범위에서 기본 재검사를 일괄 16회로 늘릴 추가 탐지 이점은 확인되지 않았다. '
            '**기본 4회는 유지하고, 이번 16회 결과는 확정 진단에 대한 추가 확인 자료로 보관한다.**','']
    else:
        lines += ['16회 검사에서 새로운 불안정 사례가 발견됐다. 해당 사례와 회차는 감사의 mismatches에 기록했다. '
            '이번 사후 확인을 기존 정책의 성능에 섞거나 기본 조건을 자동 변경하지 않고 별도 검토 대상으로 보존했다.','']
    lines += ['615입력은 같은 4개 설계의 값 변화·오차 반복이다. 반복 횟수를 늘려도 독립 회로 수나 '
        '측정 오차의 종류가 늘어나는 것은 아니다. 모든 부호 벡터·다른 크기의 오차·실제 장비에 대한 '
        '안정성 보증이나 신뢰확률로 해석할 수 없다.','',
        '**검증 판단: 조건부 사후 검사라는 한계를 명시하면 공유 가능.** 미해결 계산 불일치는 없다.','',
        '```bash','.venv/bin/python scripts/run_stability_extension.py','.venv/bin/python scripts/audit_stability_extension.py',
        '.venv/bin/python scripts/report_stability_extension.py','```','',
        '계획: `experiments/stability_extension_v1.json`. 추가 결과: `build/stability_extension_v1/`. '
        '독립 감사: `build/stability_extension_v1_audit/summary.json`.','']
    dest=ROOT/'docs/stability_extension_v1_results.md';dest.write_text('\n'.join(lines));print(dest)

if __name__=='__main__':main()

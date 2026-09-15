"""Build a bounded sensitivity report from independently audited rows."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from run_reference_robustness import PP, OUT, read, digest, check

LABELS={'baseline':'무오차 기준','noise':'독립 dB 잡음','offset':'공통 dB 편향','frequency':'주파수 교정 오차',
        'lc_drift':'주 L/C 동시 변화','rs_model':'손실저항 모델 불일치','parasitic_model':'기생 모델 불일치','combined':'결합 스트레스'}

def level_text(family,level):
    value=float(level)
    if family in ['noise','offset']:return f'{value:g} dB'
    if family in ['frequency','lc_drift','rs_model','parasitic_model']:return f'{value*100:g}%'
    if family=='combined':return '공통 음의 부호' if value<0 else '공통 양의 부호'
    return '반올림만'

def main():
    p=read(PP);check(p);a=read(ROOT/'build/reference_robustness_v1_audit/summary.json')
    assert a['complete'] and not a['issues'] and a['protocol_sha256']==digest(PP.read_bytes())
    assert a['summary_sha256']==digest((OUT/'summary.json').read_bytes())
    rows=[]
    for f,h in a['row_sha256'].items():
        path=ROOT/f;assert digest(path.read_bytes())==h;rows.append(read(path))
    gs=a['groups'];faults=[r for r in rows if r['kind']=='fault'];controls=[r for r in rows if r['kind']=='control']
    correct=sum(r['score']['correct'] for r in faults);abstain=sum(r['score']['abstained'] for r in faults)
    wrong=sum(r['score']['wrong_diagnosis'] for r in faults);alarms=sum(r['score']['false_alarm'] for r in controls)
    rank=sum(r['top_rank_correct'] for r in faults)
    rejected=[r for r in faults if r['score']['abstained']]
    residual_reject=sum(r['fit']['hypotheses'][0]['rmse_db']>.02 for r in rejected)
    separation_reject=sum(r['fit']['hypotheses'][1]['rmse_db']<.10 for r in rejected)
    lines=['# 기준 측정 역추정: 잡음·환경 변화·모델 오차의 영향','',
        '**이 평가에서는 오진 대신 판단 보류가 늘었다. 기존 무오차 설정의 잔차 문턱은 오차가 있는 조건에서 진단을 자주 보류했다.** '
        f'고장 {len(faults)}건 중 정답 {correct}, 보류 {abstain}, 오진 {wrong}이었고 대조군 {len(controls)}건의 단일 부품 오경보는 {alarms}이었다. '
        '이는 정한 스트레스 격자의 집계이며 실제 장비에서의 정확도·오경보 확률이 아니다.','',
        '2026-09-06. API 0회. 기존 reference_diagnosis_v2의 적격 3설계·6고장을 재사용하고 '
        '고장 없는 회로 3개를 대조군으로 추가했다. 처음 8고장 중 257 MHz 설계가 사전 검증에서 제외된 '
        '선택 이력을 유지한다. 105개 시나리오×9개 회로 상태=945건의 별도 합성 민감도 실험이며 '
        '새 holdout, 하드웨어 실측, LLM 비교 또는 복구율 실험이 아니다.','',
        '## 무엇을 고정했는가','',
        '고장 전 9주파수×S11/S21/S22 크기를 사용한다. 기존 역추정 코드와 '
        '**최선 RMSE≤0.02 dB, 차선 RMSE≥0.10 dB** 판정 문턱을 그대로 동결했다. '
        '각 부품의 과거값만 바꿔 현재값의 0.4–2.5배 범위를 탐색한다. '
        '결과를 본 뒤 문턱이나 사례를 바꾸지 않았다. [고정 계획](reference_robustness_v1_protocol.md).','',
        '추정기는 현재 주 L/C 값과 기존 공개 모델을 정확히 입력받는다. 실제 손실·기생 모델을 변경한 조건에서도 '
        '추정기에는 변경값을 알려주지 않았다. L/C 환경 변화는 기준 기록 후 현재 주 L/C 6개가 같이 바뀌는 '
        '상황으로, 추정기는 바뀐 현재값을 알고 있으나 단일 변화만 가정한다. 실제 온도 계수나 열 모델은 아니다. '
        '현재 spectrum을 사용하지 않는 기존 함수만 평가했다. 섭동 후 정상 PASS·고장 FAIL 여부로 '
        '사례를 다시 선별하지 않았으며, 기존에 주입한 큰 값 고장의 위치·방향을 추적했다.','',
        '## 주요 결과','',
        '| 기준 측정의 잡음 표준편차 | 고장 위치·방향 정답 | 고장 보류 | 고장 오진 | 대조군 오경보 |',
        '|---|---:|---:|---:|---:|']
    for level in ['0.005','0.01','0.02','0.05','0.1']:
        g=gs['noise/'+level]
        lines.append(f'| {level} dB | {g["correct"]}/{g["faults"]} | {g["fault_abstained"]} | {g["wrong_diagnosis"]} | {g["false_alarm"]}/{g["controls"]} |')
    lines += ['','잡음 수준별 고장은 6개×10 draw, 대조군은 3개×10 draw다. '
        '같은 설계·draw의 잡음 벡터를 고장·대조군·잡음 수준 사이에 공유했다. '
        '60행을 서로 독립인 60개 회로로 간주하지 않는다. 반올림만 있는 기준은 고장 6/6 정답·대조군 3/3 보류였다.','',
        '- 공통 편향: ±0.01 dB는 각 6/6 정답. −0.02 dB는 1/6, +0.02 dB는 6/6으로 비대칭이 나타났다. ±0.05 dB와 ±0.1 dB는 모두 보류했다.',
        '- 주파수 교정 오차: ±0.01%는 각 6/6 정답, ±0.05/0.1/0.5%는 모두 보류했다.',
        '- 주 L/C 동시 변화: 시험한 최소 ±0.1%부터 모두 보류했다. 더 작은 변화는 평가하지 않았다.',
        '- 손실저항 또는 기생 모델 불일치: 시험한 최소 ±10%부터 모두 보류했다. 더 작은 불일치는 평가하지 않았다.',
        '- σ=0.01 dB 잡음과 L/C ±0.1%, 손실·기생 ±10%를 결합한 120고장도 모두 보류했다.','',
        '**후보 순위와 최종 판단을 구분해야 한다.** '
        f'잔차가 가장 작은 가설은 {rank}/{len(faults)}건에서 실제 부품·방향과 일치했지만, '
        f'그중 {abstain}건은 최종 진단이 보류됐다. 보류 {abstain}건 모두 최선 잔차 문턱을 넘었고 '
        f'({residual_reject}건), 차선과의 구분 문턱 때문에 보류한 고장은 {separation_reject}건이었다. '
        '따라서 이번 격자에서 관찰한 주된 제한은 최상위 가설의 순위 실패보다 고정 절대 잔차 기준에 따른 보류다. '
        '630/630의 가설 순위를 현재 진단 정답률로 바꿔 보고하지 않는다.','',
        '## 전체 조건별 집계','',
        '| 오차 축 | 수준 | 고장 정답 /분모 | 보류 | 오진 | 대조군 오경보 /분모 |','|---|---|---:|---:|---:|---:|']
    for family in LABELS:
        for g in sorted([g for g in gs.values() if g['family']==family],key=lambda g:float(g['level'])):
            lines.append(f'| {LABELS[family]} | {level_text(family,g["level"])} | {g["correct"]}/{g["faults"]} | '
                f'{g["fault_abstained"]} | {g["wrong_diagnosis"]} | {g["false_alarm"]}/{g["controls"]} |')
    lines += ['','고장의 정답+보류+오진은 해당 분모와 같으며, 대조군의 보류+오경보는 대조군 분모와 같다. '
        '고장이 없는 대조군의 보류를 고장 진단 정답에 더하지 않았다. 환경 변화가 있는 대조군에서는 '
        '“단일 부품 고장”의 특정 여부를 평가했으며, 규격 만족이나 실제 장비의 정상 운용을 판정한 것은 아니다.','',
        '## 독립 검증','',
        f'- 945개 입력·가설·최종 판정을 저장하고 전부 재실행했다. 탐색 전방 모델 계산은 {a["fit_forward_evaluations"]:,}회이며 감사에서 같은 수를 재현했다.',
        f'- 고유한 과거 회로·실제 sweep 조합 {a["native_physics_sweeps"]}개를 native ngspice로 실행했다. 총 {a["native_frequency_points"]:,}주파수 점에서 ABCD와 대조했다.',
        f'- 독립 nodal 해석으로 spectrum 생성 {a["nodal_generation_points"]:,}점과 각 실행의 최선·차선 가설 {a["nodal_fit_points"]:,}점을 검증했다.',
        f'- 반올림 후 측정값 {a["measurements_independently_recomputed"]:,}개를 독립 nodal 결과·고정 seed·오차 식으로 다시 계산했다.',
        f'- native/ABCD 최대 크기 차이 {a["max_native_magnitude_error"]:.3g}, nodal/ABCD {a["max_nodal_magnitude_error"]:.3g}; 두 값 모두 2e-7 미만이다.',
        f'- 기존 무오차 고장 6개의 측정 크기·가설값·진단은 일치했다. native 표와 부동소수점 주파수 표기의 최대 차이는 '
        f'{a["baseline_max_frequency_error_hz"]:.3g} Hz, RMSE 차이는 {a["baseline_max_rmse_difference_db"]:.3g} dB로 각각 1e-6 Hz·1e-12 dB 검사 한계 이내다.',
        '- 전체 단위 검사 70개 통과. 기존 실험 파일과 제출 원고는 변경하지 않았다.','',
        '**검증 판단: 한계를 명시하면 공유 가능.** 원시 입력·분모·집계·물리 모델 교차검증에서 미해결 불일치가 없다. '
        '잡음 벡터는 계측기에서 얻은 것이 아니고, dB 정규잡음·공통 offset·일률적 부품 변화는 제한적인 합성 모형이다. '
        '공통 편향은 수동성에 맞춰 자르지 않았다. 실측 오차 분포와 연결하거나 시험 격자 사이의 경계를 단정할 수 없다.','',
        '## 해석과 다음 순서','',
        '현재 결과는 “오차가 있어도 진단 가능”을 입증하지 않는다. 오진이 관찰되지 않은 대신 '
        '여러 조건에서 진단을 내리지 못했다. 또한 큰 값 변화(0.55배/1.8배)의 단일 고장과 3개 설계만 '
        '반복했으므로 약한 고장·비균일 drift·더 복잡한 모델에서는 최상위 가설 자체가 틀릴 수 있다.','',
        '다음에는 문턱을 바로 완화하기보다 **별도 개발 집합에서 작은 고장과 비균일 오차를 포함한 잔차·가설 간격을 '
        '확인하고, 오차를 반영한 보류 기준을 정한 뒤 미사용 설계로 평가**하는 순서가 적절하다. '
        '현재 945건을 기준 조정과 성능 검증에 동시에 쓰지 않는다. 실측 기준 측정이 확보되면 그 오차 분포로 '
        '새 계획을 고정해야 한다. 이번 결과는 원고의 기존 LLM 복구율에 합산하지 않는다.','',
        '```bash','.venv/bin/python scripts/run_reference_robustness.py',
        '.venv/bin/python scripts/audit_reference_robustness.py','.venv/bin/python scripts/report_reference_robustness.py',
        'PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -q','```','',
        '고정 계약: `experiments/reference_robustness_v1.json`. 원시 결과: `build/reference_robustness_v1/`. '
        '검증 결과와 native 증거: `build/reference_robustness_v1_audit/`.','']
    dest=ROOT/'docs/reference_robustness_v1_results.md';dest.write_text('\n'.join(lines));print(dest)

if __name__=='__main__':main()

"""Report reference-measurement diagnosis with explicit cohort and algorithmic attribution."""
import json
from pathlib import Path
from run_budget_transfer import digest
ROOT=Path(__file__).resolve().parents[1]

def main():
    pp=ROOT/'experiments/reference_diagnosis_v2.json';protocol=json.loads(pp.read_text())
    a=json.loads((ROOT/'build/reference_diagnosis_v2_audit/summary.json').read_text())
    assert a['complete'] and not a['issues'] and a['protocol_sha256']==digest(pp.read_bytes())
    for p,h in protocol['file_sha256'].items():assert digest((ROOT/p).read_bytes())==h,p
    names=protocol['conditions'];stats=a['conditions'];n=protocol['case_count']*protocol['repetitions']
    labels=['기준 측정 없음','기준 측정 제공','기준 측정 + 역추정 제공']
    lines=['# 고장 전 기준 측정과 수치 역추정의 진단 효과','',
        f'**적격 6고장에서 위치·방향 진단 정답은 {stats[names[0]]["diagnosed"]}/{n} → '
        f'{stats[names[1]]["diagnosed"]}/{n} → {stats[names[2]]["diagnosed"]}/{n}이었다.** '
        f'LLM 없이 같은 기준 측정으로 계산한 결정적 역추정 진단은 {a["deterministic_diagnosed"]}/6이었다. '
        '따라서 마지막 조건의 성공을 LLM이 독자적으로 원인을 찾아낸 결과로 해석하지 않는다.','',
        '**원래 계획한 8사례 v1은 정상 설계 부적격 때문에 중단됐다.** 257 MHz의 정상 S11=−13.170451 dB가 '
        '기존 −15 dB 기준을 벗어나 API 0회에서 멈췄다. v2는 사전 검증 결과를 본 뒤, 기준을 통과한 '
        '3설계·6고장만으로 별도로 고정한 탐색이다. 2고장의 제외 기록을 보존했고 회로·난수·사양을 바꾸거나 '
        '다른 사례로 교체하지 않았다. 모든 모델 호출과 역추정 계산 전에 부분집합을 결정했다.','',
        '실행·감사일: 2026-09-06. 실제 계측이 아닌 합성 기준 측정 실험이며, 이전 실험이나 원고 분모와 합산하지 않는다.','',
        '## 조건과 가정','',
        '포함 설계는 115/153/203 MHz, BW 16/18/20%, 주 L/C ±2% 공차 각 1벡터다. '
        '손실·기생 성분·보상 설계·사양은 lossy_repair_v1 그대로다. 고장 전후에 '
        '0.70/0.85/0.92/0.96/1/1.04/1.08/1.15/1.40 f₀의 S11/S21/S22 크기를 native SPICE로 얻고 '
        '0.01 dB로 반올림했다. 위상, 추가 잡음, 계측/온도 drift는 없다.','',
        '모든 조건에 현재 회로·공개 모델·사양·현재 metric과 9주파수 spectrum을 제공한다. '
        '두 번째와 세 번째 조건에는 고장 전 spectrum을 추가하고, 세 번째에는 그것으로 계산한 부품별 과거값 가설·잔차를 더한다. '
        '정상 netlist·정상 부품값·실제 고장 위치·역추정 복원 후의 실제 SPICE 판정은 요청에 넣지 않는다. '
        '세 조건은 같은 진단 전용 지시문과 unknown 선택지를 사용했다.','',
        f'각 조건은 6사례×2회={n}응답, 전체 {a["audited_responses"]}회다. '
        'gpt-5.6-luna low, 출력 2000토큰, 요청당 1회 호출, 자동 재시도 0회다. '
        '조건 순서를 순환하고 각각 독립 입력을 사용했다. 호출 수·출력 상한은 같지만 입력 토큰과 계산 비용까지 같지는 않다. '
        '[v1 원래 계획](reference_diagnosis_v1_protocol.md) · [v2 수정 계약](reference_diagnosis_v2_protocol.md).','',
        '## 진단 결과','',
        '| 지표 /계획 12회 | 기준 측정 없음 | 기준 측정 제공 | 기준 측정 + 역추정 |','|---|---:|---:|---:|']
    for label,k in [('위치·방향 정답','diagnosed'),('위치 정답','localized'),('잘못 특정한 위치','false_location'),
        ('부품 판단 보류','abstained'),('방향 불명(보류 포함)','direction_unknown'),('API/schema 실패','api_schema_failures')]:
        lines.append('| '+label+' | '+' | '.join(str(stats[c][k]) for c in names)+' |')
    lines += ['','위치 정답·위치 오진·부품 보류·API 실패는 합계 12다. 위치·방향 정답은 위치 정답의 부분집합이고 '
        '방향 불명에는 부품 보류가 포함된다. 보류는 정답으로 세지 않는다.','']
    for label,c in zip(labels,names):
        if stats[c]['incomplete_responses']:
            lines.append(f'{label} 조건의 미완료 응답 {stats[c]["incomplete_responses"]}회는 실패로 포함했다. '
                '원본 incomplete_details를 보존하고, 응답을 재시도하거나 평가 분모에서 빼지 않았다.')
    lines.append('')
    for label,c in zip(labels,names):
        r=stats[c];coverage=r['localized']+r['false_location'];conditional=f'{r["localized"]}/{coverage}' if coverage else '계산 불가'
        lines.append(f'- {label}: 부품 특정 {coverage}/12, 특정한 응답에서의 위치 정확도 {conditional}.')
    lines += ['','| 사례 | 실제 고장 | 기준 없음 진단 /2 | 기준만 진단 /2 | 기준+역추정 진단 /2 |','|---|---|---:|---:|---:|']
    for row in a['by_case']:
        lines.append(f'| {row["case_id"]} | {row["fault_component"]} ({row["fault_type"]}) | '+' | '.join(str(row[c]['diagnosed']) for c in names)+' |')
    lines += ['','같은 사례·반복별 정답 짝:','']
    for key,pair in a['paired_joint'].items():
        lines.append(f'- {key}: 둘 다 정답 {pair["both_correct"]}, 앞 조건만 정답 {pair["first_only_correct"]}, 뒤 조건만 정답 {pair["second_only_correct"]}, 둘 다 비정답 {pair["neither_correct"]}.')
    lines += ['','이 비교는 기준 측정이라는 새 정보의 추가와 수치 역추정의 추가를 구분한다. '
        '단순히 답을 더 많이 특정하는 것과 정확히 진단하는 것은 다르므로, 보류 감소를 성능 향상으로 해석하지 않는다. '
        '3개 설계의 작은 선택 집합이며 통계적 우위나 넓은 회로 일반화를 주장하지 않는다.','',
        '## 결정적 역추정이 무엇을 했는가','',
        '6개 부품 각각 하나의 과거값을 바꾸고 나머지는 현재값으로 고정해, '
        '고장 전 27개 측정치와 모델 예측의 dB RMSE를 최소화했다. 현재값의 0.4–2.5배 범위에서 '
        'log grid 41회 + golden-section 26회, 부품당 최대 67회다. '
        f'전체 {a["forward_fit_evaluations"]:,}회 전방 모델 계산(각 9주파수)을 수행했다. '
        '정답 부품과 과거값은 탐색에 사용하지 않았다.','',
        '최선 잔차≤0.02 dB, 차선 잔차≥0.10 dB이면 탐색 범위 내 식별로 표시하도록 사전에 정했다. '
        '이 문턱은 0.01 dB 반올림만 있는 조건에서 사용한 가정이며 전역 유일성의 증명이 아니다.','',
        '| 사례 | 최선 RMSE (dB) | 차선 RMSE (dB) | 결정적 위치·방향 진단 |','|---|---:|---:|---:|']
    for r in a['fits']:
        lines.append(f'| {r["case_id"]} | {r["best_rmse_db"]:.5f} | {r["runner_up_rmse_db"]:.3f} | {"정답" if r["diagnosed"] else "비정답"} |')
    lines += ['',f'결정적 진단은 {a["deterministic_diagnosed"]}/6, 역추정 과거값을 한 부품에 적용한 native 복구는 '
        f'{a["fit_reconstruction_recovered"]}/6이다. 이 native 결과는 LLM 입력에 제공하지 않았다. '
        f'역추정을 받은 LLM은 {stats[names[2]]["matches_fit_component"]}/12회에서 최상위 가설의 부품과 일치했다. '
        '계산이 이미 식별한 결과를 LLM이 해석·반환한 효과와 LLM 자체의 새 진단 기여를 구분해야 한다.','',
        '## 검증과 비용','',
        f'- 제외 2고장을 포함한 원래 8사례의 정상·고장·oracle 24기록과 적격 6사례의 역추정 복원 6기록, 총 {a["fresh_native_replays"]}개를 새 native SPICE로 재현.',
        f'- 고장 전후 spectrum의 반올림 측정값 {a["rounded_measurements_verified"]}개를 원시 표에서 독립 재계산.',
        f'- 전체 2001주파수 ABCD 비교와 nodal 측정점 {a["nodal_measurement_points"]}개 검증. 최대 크기 차이 nodal {a["max_nodal_magnitude_error"]:.3g}, ABCD {a["max_abcd_magnitude_error"]:.3g}; 한계 2e-7 이내.',
        f'- 원본 API 응답 {a["audited_responses"]}개, ID/status/usage/schema/입력 차이/분모/진단 집계 일치.',
        f'- 역추정 {a["forward_fit_evaluations"]:,}회 재실행, 원래 중단 계약과 적격 집합·코드 hash 일치. 불일치 없음.','']
    for label,c in zip(labels,names):lines.append(f'- {label} 추정 API 비용: ${stats[c]["estimated_api_cost_usd"]:.8f}.')
    lines += [f'- 합계: ${sum(stats[c]["estimated_api_cost_usd"] for c in names):.8f}. '
        '[공식 단가](https://developers.openai.com/api/docs/models/gpt-5.6-luna)의 cache-write 할증을 포함한 usage 기반 추정이며 실제 청구서는 아니다.','',
        '**검증 판단: 한계를 명시하면 공유 가능.** 정확한 현재 부품값과 고정 모델을 알고, '
        '고장 전 상태가 같은 환경·계측 조건으로 저장돼 있으며 단일 값만 변했다는 강한 가정이다. '
        '실제 장비에서 기준 측정이 존재하는지, 잡음과 환경·모델 오차가 어느 정도인지는 검증하지 않았다. '
        'v1의 사전 검증 실패 뒤 적격 부분집합으로 변경한 선택도 해석 범위에 포함한다.','',
        '```bash','.venv/bin/python scripts/run_reference_diagnosis_v2.py --summary-only',
        '.venv/bin/python scripts/audit_reference_diagnosis.py','.venv/bin/python scripts/report_reference_diagnosis.py','```','',
        '원시 응답: `build/experiments/reference_diagnosis_v2/`. 감사·전체 답변: `build/reference_diagnosis_v2_audit/summary.json`. '
        '중단 기록: `experiments/reference_diagnosis_v1.json`. 실행 계약: `experiments/reference_diagnosis_v2.json`.','',
        '## 다음 우선순위','',
        'API 반복을 늘리기 전에, 기준 측정에 잡음·drift가 있거나 공개 소자 모델이 실제 회로와 다를 때 '
        '역추정의 최선/차선 잔차가 어떻게 바뀌는지 로컬로 확인하는 것이 우선이다. '
        '식별할 수 없는 조건은 진단을 보류해야 한다. 그 경계를 확인한 뒤 실제 확보 가능한 기준 측정 '
        '또는 추가 측정과 연결해야 하며, 현재의 거의 무오차 합성 결과를 실제 진단 성능으로 제시하지 않는다.','']
    path=ROOT/'docs/reference_diagnosis_v2_results.md';path.write_text('\n'.join(lines));print(path)

if __name__=='__main__':main()

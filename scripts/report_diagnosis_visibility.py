"""Render audited diagnosis visibility results without converting abstention into accuracy."""
import json
from pathlib import Path
from run_budget_transfer import digest
ROOT=Path(__file__).resolve().parents[1]

def main():
    pp=ROOT/'experiments/diagnosis_visibility_v1.json';p=json.loads(pp.read_text())
    audit=json.loads((ROOT/'build/diagnosis_visibility_v1_audit/summary.json').read_text())
    assert audit['complete'] and not audit['issues'] and audit['protocol_sha256']==digest(pp.read_bytes())
    for f,h in p['file_sha256'].items():assert digest((ROOT/f).read_bytes())==h,f
    before='diagnose_before_candidates';shown='diagnose_with_candidates';a=audit['conditions'][before];b=audit['conditions'][shown]
    delta=b['diagnosed']-a['diagnosed']
    conclusion=('위치·방향 정답 수는 두 조건이 같았다.' if delta==0 else
                f'위치·방향 정답 수는 후보 공개 조건이 {abs(delta)}회 {"많았다" if delta>0 else "적었다"}.')
    lines=['# 수정 후보 공개 전후의 진단 비교 결과','',
        f'**후보를 보기 전 진단은 {a["diagnosed"]}/16, 후보를 함께 본 진단은 {b["diagnosed"]}/16이었다.** '
        +conclusion+' 판단 보류를 성공으로 바꾸지 않고 정답·오진·보류를 별도로 집계했다.','',
        '2026-09-06 실행 및 감사 완료. 새 고장 8개×2반복×2조건, 총 32회 독립 호출이다. '
        '두 조건의 동일한 진단 전용 지시문·schema에서 수치 후보 필드 유무만 바꿨다. '
        '이전 lossy_repair_v1의 진단+수정 출력과는 다르므로 이전 진단 8/16에 대한 직접 인과 비교가 아니다.','',
        '## 비교 조건','',
        '새 정상 설계는 101/163/199/241 MHz, BW 16/18/20/22%, 각 주 L/C ±2% 공차 1벡터다. '
        '손실·기생 보상 모델과 사양은 lossy_repair_v1 그대로다. 사전 지정한 두 부품의 0.55배/1.8배 '
        '고장 8개가 모두 정상 PASS·고장 FAIL·한 값 oracle PASS를 통과했다. 결과에 따른 사례 교체는 없다.','',
        '후보 미공개 조건에는 관측 회로·공개 소자 모델·사양·최초 SPICE metric을 넣고, '
        '후보 공개 조건에만 상위 3개 수치 후보와 예측 metric을 추가했다. 두 조건 모두 '
        'gpt-5.6-luna low, 2000 출력 토큰, 1회 호출이며 다른 응답이나 조건의 진단을 공유하지 않았다. '
        '호출 상한은 같지만 후보 공개로 입력 길이가 늘어나므로 입력 토큰까지 동일한 예산은 아니다.','',
        '동일한 지시문에서 보상 수정이 실제 고장 위치와 다를 수 있음을 알렸고, '
        'component=unknown과 unknown_direction을 허용했다. 정상 netlist·명목값·정답 부품·공통 수정의 실제 결과는 '
        '어느 요청에도 넣지 않았다. 진단은 후속 수정 결과로 교정하지 않았다. '
        '[사전 계약](diagnosis_visibility_v1_protocol.md).','',
        '## 진단 결과','',
        '| 지표 /계획 16회 | 후보 미공개 후 진단 | 후보 공개 후 진단 |','|---|---:|---:|']
    for label,k in [('위치·방향 모두 정답','diagnosed'),('위치 정답','localized'),('잘못 특정한 위치','false_location'),
                    ('부품 판단 보류','abstained'),('방향 불명(부품 보류 포함)','direction_unknown'),('API/schema 실패','api_schema_failures')]:
        lines.append(f'| {label} | {a[k]} | {b[k]} |')
    lines += ['','위치 정답 + 잘못 특정한 위치 + 부품 보류 + API/schema 실패 = 16이다. '
        '위치·방향 정답은 위치 정답의 부분집합이고 방향 불명은 부품 보류와 겹치므로 표 전체를 더하지 않는다.','']
    for label,r in [('미공개',a),('공개',b)]:
        coverage=r['localized']+r['false_location']
        accuracy=f'{r["localized"]}/{coverage}' if coverage else '계산 불가(부품을 특정한 응답 없음)'
        lines.append(f'- 후보 {label}: 부품 특정 coverage {coverage}/16, 특정한 응답에서의 위치 정확도 {accuracy}.')
    lines += ['','판단 보류는 정답 위치를 맞힌 결과가 아니므로 진단 정답률 개선으로 세지 않는다. '
        '반대로 판단 보류를 잘못된 위치를 확신한 응답과도 합치지 않는다. '
        '이 실험의 정답은 주입 기록의 고장 위치이며, 관측 정보만으로 그 위치가 유일하게 식별되는지는 '
        '별도의 문제다. 많은 보류가 정확한 불확실성 판단인지 지나치게 보수적인 반응인지 이 비교만으로 판정하지 않는다.','',
        '| 사례 | 실제 고장 | 최상위 수정 대상 | 미공개 진단 정답 /2 | 미공개 보류 /2 | 공개 진단 정답 /2 | 공개 보류 /2 |',
        '|---|---|---|---:|---:|---:|---:|']
    for r in audit['by_case']:
        x=r[before];y=r[shown]
        lines.append(f'| {r["case_id"]} | {r["fault_component"]} | {r["top_repair_component"]} | {x["diagnosed"]} | {x["abstained"]} | {y["diagnosed"]} | {y["abstained"]} |')
    pair=audit['paired_joint']
    lines += ['',f'같은 사례·반복의 정답 짝 16개: 둘 다 정답 {pair["both_correct"]}, 미공개만 정답 {pair["before_only_correct"]}, '
        f'공개만 정답 {pair["with_only_correct"]}, 둘 다 비정답 {pair["neither_correct"]}. '
        '비정답에는 보류와 실패가 포함된다. 4설계에 묶인 작은 탐색 표본이며 통계적 우위를 주장하지 않는다.','',
        '## 공통 수정과 진단의 관계','',
        f'고정된 결정적 최상위 수치 후보는 {audit["shared_repair_recovered"]}/8을 복구했다. '
        '이 수정은 LLM 진단을 입력으로 받지 않고 동일 후보를 적용했다. 실제 시뮬레이션도 사례별 '
        '한 번 실행해 양쪽의 공통 후속 결과로 사용했다. 따라서 8/8은 LLM의 복구율이나 '
        '진단 분리의 복구 개선이 아니라 **공통 결정적 수정 절차의 결과**다.','',
        f'실제 고장과 다른 최상위 수정 대상을 고장으로 지목한 횟수는 미공개 {a["false_matches_top"]}/16, '
        f'공개 {b["false_matches_top"]}/16이었다. '
        '전체 위치 오진과 함께 해석하며, 이전의 8/16 진단과 비교해 특정한 한 요인만의 효과라고 말하지 않는다.','',
        '## 검증과 비용','',
        f'- 원본 API 응답 {audit["audited_responses"]}개: ID 중복, 원문/usage/status, schema, 조건별 입력 차이, 전체 진단 집계 검증.',
        f'- 정상·고장·oracle·공통 수정 {audit["fresh_native_replays"]}기록을 모두 새 ngspice 실행으로 재현.',
        f'- 각 기록의 전체 2001주파수 원시 표/ABCD 확인 및 독립 nodal 측정점 {audit["nodal_measurement_points"]}개 검증.',
        f'- 최대 S-parameter 크기 차이: nodal {audit["max_nodal_magnitude_error"]:.3g}, ABCD {audit["max_abcd_magnitude_error"]:.3g}; 허용 한계 2e-7 이내.',
        f'- 수치 후보 생성 {audit["reproduced_forward_evaluations"]:,}회 전방 계산을 재실행해 같은 후보/예측값을 확인. 고정 파일·분모 불일치 없음.',
        f'- 추정 API 비용: 미공개 ${a["estimated_api_cost_usd"]:.8f}, 공개 ${b["estimated_api_cost_usd"]:.8f}, '
        f'합계 ${a["estimated_api_cost_usd"]+b["estimated_api_cost_usd"]:.8f}. 실제 청구서는 아니며 '
        '[공식 단가](https://developers.openai.com/api/docs/models/gpt-5.6-luna)의 cache-write 할증을 포함했다.','',
        '**검증 판단: 한계를 명시하면 공유 가능.** 고정한 합성 모델과 작은 사례 집합의 비교다. '
        '판단 불가 허용과 진단 전용 지시문을 두 조건에 공통 적용했으므로, 그 두 변경의 개별 효과를 분리한 실험은 아니다.','',
        '```bash','.venv/bin/python scripts/run_diagnosis_visibility.py --summary-only',
        '.venv/bin/python scripts/audit_diagnosis_visibility.py','.venv/bin/python scripts/report_diagnosis_visibility.py','```','',
        '원시 기록: `build/experiments/diagnosis_visibility_v1/`. 독립 감사와 전체 답변: '
        '`build/diagnosis_visibility_v1_audit/summary.json`. 고정 계약: `experiments/diagnosis_visibility_v1.json`.','',
        '## 다음 판단','',
        '수정 후보가 존재한다는 사실만으로 원인 진단이 성립하지 않는다. 다음 확장은 단순 프롬프트 반복보다 '
        '고장 전 기준 측정, 허용 부품 범위, 추가 자극/측정처럼 원인을 구분할 수 있는 증거를 정의하는 데 초점을 두는 것이 타당하다. '
        '그 증거가 실제 운용에서 얻을 수 있는지 먼저 정하고, 정상값이나 정답 위치를 직접 넘기는 지름길과 구분해야 한다. '
        '진단이 보류돼도 사양 복구가 검증된 수정은 별도로 보고하되 실제 고장 부품이라고 표현하지 않는다.','']
    path=ROOT/'docs/diagnosis_visibility_v1_results.md';path.write_text('\n'.join(lines));print(path)

if __name__=='__main__':main()

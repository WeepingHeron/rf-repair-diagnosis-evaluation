"""Audited loss-aware experiment readout, keeping diagnosis separate from recovery."""
import json
from pathlib import Path
from run_budget_transfer import digest
ROOT=Path(__file__).resolve().parents[1]

def main():
    pp=ROOT/'experiments/lossy_repair_v1.json';p=json.loads(pp.read_text())
    audit=json.loads((ROOT/'build/lossy_repair_v1_audit/summary.json').read_text())
    assert audit['complete'] and not audit['issues'] and audit['protocol_sha256']==digest(pp.read_bytes())
    for path,h in p['file_sha256'].items():assert digest((ROOT/path).read_bytes())==h,path
    cases=json.loads((ROOT/p['manifest']).read_text())['cases'];llm=audit['llm'];baselines=audit['baselines']
    lines=['# 손실 보상 설계의 수치 탐색과 LLM 비교 결과','',
        '**손실·기생 성분·공차를 반영한 새 정상 설계 4개가 모두 기준을 통과했다.** '
        '고장 8개에서 이상적 공진 계산은 5/8, 손실 모델 수치 탐색은 8/8을 복구했다. '
        '같은 수치 후보를 받은 LLM은 각 2회 모두 성공해 16/16이었지만, 모든 응답이 '
        '이미 계산된 최상위 후보를 그대로 골랐다. 이번 조건에서 LLM의 추가 복구 이점은 확인되지 않았다.','',
        '**위치·방향 진단은 8/16이었다.** L 고장 4개에서는 다른 C를 수정해 성능을 복구했고, '
        'LLM은 그 C를 고장 부품으로 지목했다. 성능 복구와 원인 진단을 구분해야 한다.','',
        '실행·감사일: 2026-09-06. 기존 승인된 키를 사용한 API 16회와 로컬 시뮬레이션이다. '
        '기존 v4/v5·정합·320조건 점검의 고정 입력과 제출 원고는 변경하지 않았다.','',
        '## 1. 정상 설계의 성립 확인','',
        '이전 320조건 실험을 소급해서 통과 처리하지 않고, 별도의 손실 모델과 연구 기준을 정했다. '
        '개발 회로 103 MHz에서 ESR 조합을 확인한 뒤 고정했으며, 선택 과정과 탈락한 첫 조합도 기록했다. '
        '평가 설계는 109/143/191/229 MHz, BW 16/18/20/22%, 각 주 L/C ±2% 고정 난수 1회다. '
        '모든 8고장을 보존했고 정상 PASS·고장 FAIL·한 값 oracle PASS의 사전 검증을 통과했다.','',
        '모델은 L 직렬 R=0.05 Ω·병렬 Cp=0.1 pF, C 직렬 R=0.02 Ω·ESL=0.2 nH다. '
        '이 값들은 특정 제품 보증치가 아닌 합성 가정이다. 손실 저항을 정상 L/C 값에서 계산하지 않아 '
        '공개 저항만으로 정답을 역산할 수 있는 인위적인 정보를 제거했다. 각 소자의 Q는 값과 주파수에 따라 달라진다.','',
        '정상 L/C는 목표 중심 주파수에서 기생 성분을 포함한 리액턴스를 보상한다. '
        '손실·기생 성분과 포트는 수정 중 고정하고 주 L/C 값 하나만 변경한다. '
        '기준은 중심 손실≤2 dB, 반사손실≥15 dB, peak 오차≤3%, 양 통과대역 가장자리 S21≥−6 dB, '
        '양 저지대역 S21≤−12 dB다. 제품 표준이 아닌 **탐색적 연구 예산**이며 실제 용도에 따른 사양 검증은 별도다.','',
        '| 설계 | 중심 주파수 | 정상 중심 손실 | 정상 반사손실 | peak 오차 |','|---|---:|---:|---:|---:|']
    for design in sorted({c['design_id'] for c in cases}):
        c=next(c for c in cases if c['design_id']==design)
        m=json.loads((ROOT/'build/lossy_repair_v1_prescreen'/design/'healthy.json').read_text())['metrics']
        lines.append(f'| {design} | {c["spec"]["target_center_frequency_hz"]/1e6:g} MHz | {-m["samples"]["center"]["s21_db"]:.3f} dB | {-m["samples"]["center"]["s11_db"]:.2f} dB | {m["peak_frequency_relative_error"]*100:.2f}% |')
    lines += ['','[고정한 실험 계약](lossy_repair_v1_protocol.md). 개발용 손실 L/손실 C/Cp/ESL의 '
        '16개 조합 제거 결과는 `build/lossy_repair_v1_development/summary.json`에 별도 보존했다. '
        '그 실험은 보상 설계에서 항을 제거하는 분석이며 조합별 재최적화를 하지 않았다.','',
        '## 2. 복구 비교와 실제 예산','',
        '| 방법 | 최초 = 최종 복구 | native 후보 시뮬레이션 | API 호출 |','|---|---:|---:|---:|',
        f'| 이상적 LC 공진 | {baselines["ideal_resonance"]["recovered"]}/8 | {baselines["ideal_resonance"]["native_simulations"]} | 0 |',
        f'| 손실 모델 수치 탐색 | {baselines["numerical_search"]["recovered"]}/8 | {baselines["numerical_search"]["native_simulations"]} | 0 |',
        f'| 같은 수치 후보 + LLM | {llm["final_recovered"]}/16 | {llm["candidate_simulations"]} | {llm["api_calls_recorded"]} |','',
        '모든 방법은 사례당 native 후보 평가 최대 3회다. LLM은 8사례를 2회씩 반복했으며 '
        'gpt-5.6-luna low, 출력 2000토큰, 최대 3회 호출로 고정했다. 실제로는 모두 첫 후보에 성공해 '
        '후속 피드백 효과를 측정할 기회가 없었다. 이번 결과로 피드백 우위를 주장할 수 없다.','',
        f'수치 탐색은 사례당 354회, 전체 {audit["forward_search_evaluations_reproduced"]:,}회의 ABCD 전방 모델 계산을 '
        '실행했고 각 계산에서 2001주파수를 평가했다. 이 계산 결과를 수치 기준선과 LLM에 똑같이 제공하고 '
        'LLM의 두 반복에서도 재사용했다. 이상적 LC 방법에는 이 추가 탐색이 없으므로 '
        '**전체 계산 비용까지 같은 비교는 아니다.** native 호출과 전방 모델 계산, API 비용을 분리해서 해석해야 한다.','',
        f'LLM은 {llm["top_numerical_candidate_used"]}/{llm["api_calls_recorded"]}회에서 최상위 수치 후보의 부품과 값을 '
        '그대로 반환했다. 수치 기준선도 그 후보로 이미 8/8을 복구하므로, 이 조건에서 LLM이 추가 복구를 '
        '만들었다는 근거는 없다. 좁은 합성 모델에 대한 결과이며 LLM이 모든 RF 문제에서 불필요하다는 뜻은 아니다.','',
        f'실제 usage 기반 추정 API 비용은 ${llm["estimated_api_cost_usd"]:.8f}다. '
        '[공식 단가](https://developers.openai.com/api/docs/models/gpt-5.6-luna)의 cache-write 1.25배를 포함했고 '
        '실제 청구서 금액은 아니다.','',
        '## 3. 진단과 보상 복구','',
        '| 사례 | 실제 고장 | 최상위 수정 대상 | 이상적 LC 복구 | 수치 탐색 복구 | LLM 복구 | LLM 위치·방향 진단 |',
        '|---|---|---|---:|---:|---:|---:|']
    for r in audit['by_case']:
        c=next(c for c in cases if c['case_id']==r['case_id']); records=[]
        for rep in [1,2]:
            records.append(json.loads((ROOT/'build/experiments/lossy_repair_v1/numerical_feedback'/c['case_id']/f'repeat_{rep}/iteration_1.json').read_text()))
        lines.append(f'| {c["case_id"]} | {c["component"]} | {c["numerical_search"]["candidates"][0]["component"]} | {int(r["ideal_resonance"])}/1 | {int(r["numerical_search"])}/1 | {r["llm_recovered"]}/2 | {sum(x["diagnosed"] for x in records)}/2 |')
    lines += ['','예를 들어 lossy_d1_f1의 고장은 L743이지만 C442를 조정해 사양을 만족했다. '
        '그런데 두 LLM 응답은 C442를 고장 부품이라고 진단했다. 단일 수정으로 기능을 회복하는 행위와 '
        '주입한 고장의 위치를 알아내는 행위는 별개다. 후보 정보를 제공하지 않은 대조군이 없으므로 '
        '후보가 오진을 유발했다는 인과적 결론까지 내리지 않는다.','',
        '## 4. 검증 결과','',
        f'- 원본 API 응답 {audit["unique_api_responses"]}개: ID 중복, request/prompt/source hash, 입력 누출, schema, 수정 대상, 진단 집계 검증.',
        f'- 개발 19개 + 사전 검증 20개 + 결정적 후보 22개 + LLM 후보 16개 = {audit["physics_records"]}개 기록을 모두 새 ngspice 실행으로 재현.',
        f'- 원시 표 {audit["raw_frequency_points"]:,}행의 격자·metric 계산을 검증. 평가 단계 58기록의 전체 2001주파수를 ABCD 계산과 비교.',
        f'- 별도 nodal 행렬 해법으로 모든 77기록의 5개 측정점, 총 {audit["independent_nodal_points"]}점을 확인. 최대 S-parameter 크기 차이 {audit["max_nodal_magnitude_error"]:.3g}.',
        f'- ABCD 최대 크기 차이 {audit["max_abcd_magnitude_error"]:.3g}, 두 비교 모두 허용 한계 2e-7 이내.',
        f'- 전방 수치 탐색 {audit["forward_search_evaluations_reproduced"]:,}회도 다시 실행해 후보·순서·예측치를 재현. 불일치 없음.','',
        '검증 판단: **한계를 명시하면 공유 가능**. 설계 4개·고장 8개·공차 벡터 4개에 대한 탐색이며 '
        '16개 독립 설계나 제조 수율 평가가 아니다. 실제 PCB·온도·바이어스·주파수 의존 ESR·부품 공급사 모델로 일반화하지 않는다.','',
        '재현 및 확인:','',
        '```bash','.venv/bin/python scripts/run_lossy_repair.py --protocol lossy_repair_v1 --summary-only',
        '.venv/bin/python scripts/audit_lossy_repair.py','.venv/bin/python scripts/report_lossy_repair.py','```','',
        '고정 계약은 `experiments/lossy_repair_v1.json`, 모든 새 사례는 `faults/holdout/lossy_repair_v1.json`, '
        '원시 응답은 `build/experiments/lossy_repair_v1/`, 감사는 `build/lossy_repair_v1_audit/summary.json`에 있다.','',
        '## 다음 우선순위','',
        '새 회로 수를 늘리기 전에 진단과 수정의 역할을 분리하는 것이 우선이다. '
        '정답 위치를 주장하는 단계에는 보상 후보를 고장 증거로 사용하지 않도록 하고, '
        '수정 단계는 검증된 수치 후보와 실제 시뮬레이션에 맡긴다. 다음 진단 실험은 이번 사례로 '
        '프롬프트를 맞춘 뒤 재평가하지 말고, 별도의 미사용 사례에서 후보 공개 전후를 '
        '동일 호출 예산으로 비교해야 한다. 실제 부품 모델 도입은 출처·용도 사양을 확보한 뒤 별도 검증한다.','']
    path=ROOT/'docs/lossy_repair_v1_results.md';path.write_text('\n'.join(lines));print(path)

if __name__=='__main__':main()

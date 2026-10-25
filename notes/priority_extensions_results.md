# 계산 보조와 정합회로 확장 결과

새 필터 고장 8개를 2회씩 평가한 최종 복구는 일반 피드백 12/16, 계산 보조 피드백 15/16이다. 같은 공진 계산의 결정적 기준선은 LLM 없이 8/8을 복구했다. 별도의 L형 정합회로 one-shot 파일럿은 5/8 복구다.

실행일은 2026-09-06이다. v4 결과를 본 뒤 정한 탐색적 확장으로, v4 원시 기록이나 이미 고정한 실행 계약을 바꾸지 않았다. 기존 승인된 키와 같은 모델을 사용했고 전체 결과를 보존했다.

## 1. 공진 후보 정보의 효과

97/127/157/193 MHz와 대역폭 비율 11/13/15/17%의 새 4개 설계에서 고장 8개를 생성했다. 각 2회 ×2조건으로 32개 경로이며 모두 정상 PASS·고장 FAIL·정답 수정 PASS를 먼저 확인했다. 두 조건은 gpt-5.6-luna low, 2000 출력 토큰, 최대 3회 호출, 같은 prompt와 SPICE feedback 정책을 사용한다. 계산 보조 조건에만 고장 netlist 연결 관계와 목표 주파수에서 유도한 LC 공진 후보를 추가했다.

| 지표 | 일반 피드백 | 계산 보조 피드백 |
|---|---:|---:|
| 첫 복구 /16 | 11 | 8 |
| 최종 복구 /16 | 12 | 15 |
| 최종 위치·방향 진단 /16 | 16 | 14 |
| 다른 부품으로 보상 복구 | 0 | 1 |
| 실제 API 호출 | 25 | 25 |
| 후보 simulation | 25 | 25 |
| 응답 미완료 | 0 | 0 |
| API/schema 실패 | 0 | 0 |
| 추정 API 비용 (USD) | 0.03421 | 0.02586 |

| 사례 | 일반 피드백 최초→최종 /2 | 계산 보조 최초→최종 /2 |
|---|---:|---:|
| calc_d1_f1 | 0→0 | 0→2 |
| calc_d1_f2 | 1→2 | 0→1 |
| calc_d2_f1 | 2→2 | 0→2 |
| calc_d2_f2 | 2→2 | 2→2 |
| calc_d3_f1 | 1→1 | 0→2 |
| calc_d3_f2 | 1→1 | 2→2 |
| calc_d4_f1 | 2→2 | 2→2 |
| calc_d4_f2 | 2→2 | 2→2 |

결정적 기준선은 8개 사례에서 11회 후보 simulation, API 0회로 8/8을 복구했다. 관측 회로의 공진 오차가 큰 LC 쌍부터, 부품명 순서로 최대 3개 후보를 평가한 결과다. 정답 manifest를 이용한 후보 선택은 없으며 결과를 보고 순서를 바꾸지 않았다.
계산 보조의 차이는 수치 후보와 연결 관계 정보를 입력에 추가한 효과다. 동적 tool calling, 순수한 산술 능력 향상 또는 LLM의 필수성을 입증한 것이 아니다. 결정적 기준선의 성공은 이상적 공진 회로와 단일 값 고장 가정에서 유도한 좁은 해결 가능성을 보여준다. 8개 사례는 4개 설계에 묶이며 각 2회 반복이므로 32개 독립 회로로 해석하지 않는다.

## 2. L형 정합회로 전이 파일럿

91/131/181/223 MHz의 4개 설계에서 L/C 고장 8개를 각 한 번 평가했다. 50 Ω source와 100/150/200/250 Ω load의 포트 임피던스는 고정했고 L/C 값 하나만 수정할 수 있다. 정합 설계의 입력 임피던스가 중심주파수에서 50 Ω이 되는지는 SPICE 외의 복소수 계산으로도 확인했다.
중심 S11≤−20 dB·S21≥−0.25 dB, 0.9f/1.1f S11≤−12 dB·S21≥−0.5 dB의 전용 판정기를 사용했다. BPF의 peak·저지대역 제약을 재사용하지 않았다.

최종 복구 5/8, 위치·방향 진단 6/8, API 8회, 후보 simulation 7회다. 응답 미완료 1건도 분모에 포함했다. 추정 API 비용은 $0.01082다.

| 사례 | 고장 부품 | 복구 /1 |
|---|---|---:|
| match_d1_f1 | L346 | 1 |
| match_d1_f2 | C843 | 1 |
| match_d2_f1 | L707 | 0 |
| match_d2_f2 | C952 | 1 |
| match_d3_f1 | L549 | 0 |
| match_d3_f2 | C235 | 1 |
| match_d4_f1 | L699 | 1 |
| match_d4_f2 | C640 | 0 |

match_d2_f1은 고장 L707을 맞게 지목했으나 수정값이 성능 조건을 만족하지 못했다. match_d3_f1은 max_output_tokens로 응답이 끝났고, match_d4_f2는 고장 C640 대신 L699를 수정해 실패했다. 사례별 반복과 대조군이 없는 one-shot 파일럿이므로 피드백 효과나 넓은 topology 일반화를 주장하지 않는다.

## 검증과 해석

계산 보조 비교: 응답 50개·후보 재시뮬레이션 50개 및 결정적 기준선 11개를 감사했다. 정합 파일럿: 응답 8개·후보 재시뮬레이션 7개를 감사했다. 원문 hash, ID 중복, 입력·수정 회로·metric·판정·최종 집계의 불일치는 없었다.
가격은 cache write 1.25배를 포함한 usage 기반 추정이며 실제 청구서가 아니다. [공식 단가](https://developers.openai.com/api/docs/models/gpt-5.6-luna). 정합식과 물리 가정의 참고 자료는 [Analog Devices](https://www.analog.com/en/resources/technical-articles/radio-frequency-impedance-matching-calculations-and-simulations.html)이다.
원시 결과는 `build/experiments/calculator_v5/`, `build/experiments/matching_v1/`에, 독립 감사는 `build/calculator_v5_audit/summary.json`, `build/matching_v1_audit/summary.json`에 보관한다.

```bash
.venv/bin/python scripts/audit_extensions.py --protocol calculator_v5
.venv/bin/python scripts/audit_extensions.py --protocol matching_v1
.venv/bin/python scripts/report_extensions.py
```

## 다음 우선순위

후속 실험은 계산과 후보 선택을 분리하고, ESR/Q·부품 편차가 들어간 새 사례에서 결정적 기준선과 계산 보조 LLM을 다시 비교하는 것이 타당하다. 현재 사례의 결과를 본 뒤 정책을 바꾸면 개발 실험으로 기록하고 새로운 미사용 사례로 확인해야 한다. RAG나 LNA 확장보다 이러한 가정 변화가 현재 계산 기준선이 어디까지 유효한지 검증하는 데 직접적이다.

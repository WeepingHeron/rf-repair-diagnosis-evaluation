# 새 설계 사례에서 같은 최대 호출 예산의 피드백 비교

집계 시각: 2026-09-06T05:26:46.560790+00:00. 고정 프로토콜 v4의 72개 실행 경로가 모두 완료됐다.
최종 복구는 no-feedback 33/36, feedback 31/36으로 차이는 -2건(-5.6%p)이다.
이는 같은 이상적 필터 topology의 새 파라미터 4개·고장 12개에 대한 관찰이다.
모델은 `gpt-5.6-luna`, reasoning `low`이다. 중심주파수 83/117/149/173 MHz와 대역폭 비율 10/12/14/16%를 사용했다. 12개 사례 모두 API 호출 전에 정상 PASS·고장 FAIL·정답 수정 PASS를 확인했으며 사전 simulation 36회는 후보 비용에서 분리했다.

| 지표 | no-feedback | feedback |
|---|---:|---:|
| 최초 복구 /36 | 28 | 28 |
| 최종 복구 /36 | 33 | 31 |
| 재시도에서 추가 복구 | 5 | 3 |
| 최종 위치 진단 /36 | 30 | 32 |
| 최종 위치·방향 진단 /36 | 30 | 32 |
| 다른 부품을 수정한 보상 복구 | 4 | 3 |
| 실제 API 호출 | 46 | 51 |
| 후보 simulation | 45 | 51 |
| 응답 미완료 | 1 | 0 |
| 기타 API/schema 실패 | 0 | 0 |
| 마지막까지 specification 실패 | 2 | 5 |
| patch 거절 | 0 | 0 |
| 입력 토큰 (캐시 포함) | 49273 | 72906 |
| 캐시 입력 토큰 | 42725 | 32044 |
| 출력 토큰 (추론 포함) | 47227 | 45984 |
| 추론 토큰 | 43074 | 41155 |
| 추정 API 비용 (USD) | 0.05916 | 0.06603 |
| 호출 소요시간 합 (초) | 621.3 | 625.3 |

시간은 API와 로컬 처리 시간을 포함하며, 조건을 교대로 실행했으므로 조건별 독립 벽시계 시간이 아니다.
비용은 프로토콜에 기록한 공개 단가와 실제 usage로 계산한 추정값이며 청구서가 아니다. [단가 출처](https://developers.openai.com/api/docs/models/gpt-5.6-luna). Cache write가 일반 입력의 1.25배라는 요율을 반영해 이전 기본 단가 추정치를 보정했다. 고정 runner의 summary와 원시 usage는 보존했고, 독립 분석 JSON에 이전 추정치와 보정치를 함께 기록했다.

이번 조건에서는 피드백에 따른 최종 복구율 향상을 확인하지 못했다. 작은 표본의 낮은 관찰 비율을 일반적인 성능 저하의 증거로 확대하지 않는다.

## 설계별 최종 복구

| 설계 | no-feedback /9 | feedback /9 |
|---|---:|---:|
| design_1 | 8 | 8 |
| design_2 | 9 | 9 |
| design_3 | 7 | 6 |
| design_4 | 9 | 8 |

## 사례별 결과

| 사례 | MHz | 고장 부품·배율 | no-feedback 최초→최종 /3 | feedback 최초→최종 /3 |
|---|---:|---|---:|---:|
| transfer_d1_f1 | 83 | L58 ×0.62 | 2→2 | 2→3 |
| transfer_d1_f2 | 83 | C85 ×1.65 | 3→3 | 2→2 |
| transfer_d1_f3 | 83 | C16 ×2.3 | 3→3 | 3→3 |
| transfer_d2_f1 | 117 | C26 ×1.65 | 3→3 | 3→3 |
| transfer_d2_f2 | 117 | L25 ×2.3 | 3→3 | 3→3 |
| transfer_d2_f3 | 117 | L17 ×0.62 | 2→3 | 3→3 |
| transfer_d3_f1 | 149 | L91 ×2.3 | 3→3 | 3→3 |
| transfer_d3_f2 | 149 | L78 ×0.62 | 0→1 | 0→1 |
| transfer_d3_f3 | 149 | C73 ×1.65 | 0→3 | 1→2 |
| transfer_d4_f1 | 173 | C81 ×0.62 | 3→3 | 3→3 |
| transfer_d4_f2 | 173 | L71 ×1.65 | 3→3 | 3→3 |
| transfer_d4_f3 | 173 | C75 ×2.3 | 3→3 | 2→2 |

## 실패와 추가 복구의 원문 추적

- feedback / transfer_d1_f1 / repeat 3: SPECIFICATION_VIOLATION → ALL_CONSTRAINTS_MET.
- feedback / transfer_d1_f2 / repeat 1: SPECIFICATION_VIOLATION → SPECIFICATION_VIOLATION → SPECIFICATION_VIOLATION.
- feedback / transfer_d3_f2 / repeat 1: SPECIFICATION_VIOLATION → SPECIFICATION_VIOLATION → SPECIFICATION_VIOLATION.
- feedback / transfer_d3_f2 / repeat 2: SPECIFICATION_VIOLATION → SPECIFICATION_VIOLATION → SPECIFICATION_VIOLATION.
- feedback / transfer_d3_f2 / repeat 3: SPECIFICATION_VIOLATION → SPECIFICATION_VIOLATION → ALL_CONSTRAINTS_MET.
- feedback / transfer_d3_f3 / repeat 1: SPECIFICATION_VIOLATION → SPECIFICATION_VIOLATION → ALL_CONSTRAINTS_MET.
- feedback / transfer_d3_f3 / repeat 3: SPECIFICATION_VIOLATION → SPECIFICATION_VIOLATION → SPECIFICATION_VIOLATION.
- feedback / transfer_d4_f3 / repeat 1: SPECIFICATION_VIOLATION → SPECIFICATION_VIOLATION → SPECIFICATION_VIOLATION.
- no_feedback / transfer_d1_f1 / repeat 1: API_OR_SCHEMA_FAILURE.
- no_feedback / transfer_d2_f3 / repeat 3: SPECIFICATION_VIOLATION → ALL_CONSTRAINTS_MET.
- no_feedback / transfer_d3_f2 / repeat 1: SPECIFICATION_VIOLATION → SPECIFICATION_VIOLATION → SPECIFICATION_VIOLATION.
- no_feedback / transfer_d3_f2 / repeat 2: SPECIFICATION_VIOLATION → SPECIFICATION_VIOLATION → ALL_CONSTRAINTS_MET.
- no_feedback / transfer_d3_f2 / repeat 3: SPECIFICATION_VIOLATION → SPECIFICATION_VIOLATION → SPECIFICATION_VIOLATION.
- no_feedback / transfer_d3_f3 / repeat 1: SPECIFICATION_VIOLATION → ALL_CONSTRAINTS_MET.
- no_feedback / transfer_d3_f3 / repeat 2: SPECIFICATION_VIOLATION → ALL_CONSTRAINTS_MET.
- no_feedback / transfer_d3_f3 / repeat 3: SPECIFICATION_VIOLATION → ALL_CONSTRAINTS_MET.

## 원고에 반영할 해석

두 조건의 첫 성공은 각각 28/36과 28/36이었고, 최대 3회까지 실행한 추가 복구는 무피드백 5건, 피드백 3건이다. 따라서 반복 실행의 추가 복구를 피드백 자체의 효과로 간주하면 안 된다.
최종 위치·방향 진단은 무피드백 30/36, 피드백 32/36이다. 진단 지표와 성능 복구 지표의 순서가 달라질 수 있어 두 지표를 분리할 필요가 있다.
실패 추적에서는 올바른 부품을 찾고도 근삿값·보간으로 수치 제약을 놓친 경우 (`transfer_d3_f2`, feedback repeat 1/2)와 잘못된 부품 조정에 머문 경우 (`transfer_d4_f3`, feedback repeat 1)가 보였다. 이는 완료된 결과를 살펴본 사후 해석이며 새로운 검증 실험이 아니다.
후속 실험 후보는 공진식 등 결정적 수치 계산 도구를 결합하고 값 선택의 실패가 줄어드는지 확인하는 것이다. 현재 사례는 이미 결과를 확인했으므로 변경 방법의 최종 확인에는 별도의 미사용 사례가 필요하다. 기존 원고의 주 결과와 v4의 분모·사양은 분리해서 보고한다.

## 비교 계약과 해석 한계

두 조건은 같은 모델·prompt·초기 입력·스키마·출력 상한 2000토큰·최대 3회 호출을 사용했다. 성공하면 조기 종료하므로 실제 호출 수는 같지 않다. feedback의 후속 입력은 길어지므로 실제 입력 토큰·달러 비용까지 일치시킨 실험도 아니다.
no-feedback는 실패해도 이전 제안이나 측정 결과를 받지 않는다. feedback는 실패한 제안과 simulator/validator 결과를 받는다. 두 조건의 첫 요청은 동일한 정보이지만 서로 다른 API 표본이므로 첫 성공률 차이는 피드백 효과가 아니다.
API/schema 실패는 최대 3회 중 조기 종료되며 실패 분모에 포함했다. 응답 예산 변경이나 실패 응답 재발급은 없었다. 추가 복구는 각 조건의 최초 대비 최종 증가량으로 보고하며, 최종 비율 차이 하나만으로 인과 효과를 단정하지 않는다.
72개 경로는 12개 고장 ×3회 ×2조건이며 72개 독립 회로가 아니다. 고장은 4개 설계에 묶여 있다. 적은 설계 수와 반복 의존성을 고려해 유의성이나 넓은 일반화 주장을 하지 않는다.
설계별로 중심주파수와 대역폭을 함께 바꿨으므로 설계별 차이를 주파수 하나의 영향으로 해석하지 않는다. 최초 성공률이 높으면 후속 피드백의 효과를 관찰할 기회도 적다.
부품·노드 이름과 행 순서는 바꿨지만 Butterworth 구조와 값 대칭성 단서는 남아 있다. 새 topology, 실제 RF 부품, PCB/RFIC 또는 하드웨어 측정의 근거가 아니다.
최종 진단은 마지막 제안의 부품·고장 방향을 정답과 비교했다. 보상 복구는 성능 PASS이면서 실제 수정 부품이 주입 고장 부품과 다른 경우다.

## 재현 및 검증

입력·평가 코드 hash는 고정 프로토콜과 대조했다. final 기록을 iteration에서 독립 재구성하고 기존 runner 집계와 대조했다. 원시 요청·응답·수정 회로·ngspice 출력은 `build/experiments/budget_transfer_v4/`에 있다.
오프라인 감사는 응답 97개와 후보 재시뮬레이션 96개를 확인했고, 원문·회로·metric·판정의 불일치가 없었다.
```bash
.venv/bin/python scripts/audit_budget_transfer.py
.venv/bin/python scripts/report_budget_transfer.py
```
독립 집계 JSON: `build/experiments/budget_transfer_v4/independent_analysis.json`. 사례별 CSV: 같은 디렉터리의 `case_results.csv`. 새 결과는 기존 원고 수치에 자동으로 합산하지 않았다.

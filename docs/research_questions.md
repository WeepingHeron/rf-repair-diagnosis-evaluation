# 연구질문 및 평가 계약

## Research Questions

### RQ1a

최초 faulty SPICE metrics를 one-shot LLM 입력에 추가하면 netlist-only 조건보다
fault localization과 strict repair success rate가 향상되는가?

### RQ1b

실패한 repair의 simulator/validator feedback을 다음 iteration에 제공하는 closed-loop
Agent는 동일한 최대 호출 예산의 single-shot LLM보다 최종 strict repair success rate를
향상하는가?

### RQ2

동일한 simulation-feedback 조건에서 RF 지식 RAG는 fault localization 정확도와
repair 효율을 향상하는가?

RQ2는 일정상 선택적 연구질문이며, RAG 조건이 제외되면 후속 연구로 이동한다.

### RQ3

fault 유형, severity 및 미관측 회로 topology에 따라 진단과 복구 성능은 어떻게
달라지는가?

## 실험 가설

- H1a: 최초 SPICE metrics 조건은 netlist-only 조건보다 strict repair success가 높을 것이다.
- H1b: 반복적인 closed-loop SPICE feedback은 single-shot 조건보다 최종 strict repair
  success가 높을 것이다.
- H2: RF RAG는 localization 정확도를 높이고 필요한 simulation 반복을 줄일 것이다.
- H3: 연결 구조를 변경하는 fault는 단순 부품값 오류보다 어려울 것이다.

가설은 실험 결과가 아니며 현재 성능 주장으로 사용하지 않는다.

2026-09-02의 10-case preliminary comparison에서는 H1a가 지지되지 않았다. 이는 H1b의
closed-loop 효과와 별개이며 최종 평가 전 관찰로만 기록한다.

같은 날 수행한 10-trajectory closed-loop pipeline pilot에서는 first-attempt recovery
9/10이 feedback 후 10/10으로 증가했다. H1b를 일반적으로 지지하기에는 표본과 rescue
건수가 부족하며, closed-loop 구현 가능성을 확인한 결과로만 사용한다.

후속 30-trajectory 반복 실험에서는 first-attempt recovery 26/30이 최대 3 iterations 후
30/30으로 증가했고 네 trajectory가 feedback으로 추가 복구됐다. 이는 현재 value-fault
집합에서 추가 시도의 효과를 보여주지만, 당시 동일 호출 예산의 무피드백 반복 조건이
없어 H1b에 대한 인과적 근거는 아니다.

2026-09-06의 v4에서는 H1b를 최대 3회 호출의 무피드백 반복 조건과 피드백 조건으로
직접 비교했다. 새 설계 4개·고장 12개에서 첫 복구는 모두 28/36, 최종 복구는
무피드백 33/36과 피드백 31/36이었다. 이 설정에서는 피드백 우위가 확인되지 않았다.
이는 H1b가 모든 회로에서 거짓이라는 의미가 아니라 해당 사례의 관찰이다.

후속 우선순위는 선택적인 RAG에 앞서 공진값 계산 보조의 효과와 L형 정합회로에서의
제한된 전이 가능성을 확인하는 것이다. 전자는 새 8개 고장에서 일반 피드백과 계산
보조 피드백을 비교하고, 후자는 다른 topology의 8개 one-shot 파일럿으로 분리한다.
자세한 사전 계약은 `docs/priority_extensions_2026-09-06.md`를 따른다.

두 확장 후에는 비이상적 Q·기생·공차의 정상 설계 성립 조건을 확인했다.
320조건 중 정상 PASS 8개, 유한 Q 정상 PASS 0개이며 적격 고장 16개에서
결정적 공진 복구는 10개였다. 이는 LLM 비교가 아니고 기존 사양과 정상 설계의
적용 범위 확인이다. 손실을 반영한 정상 설계·사양을 먼저 정한 뒤 새 미사용
조건에서 복구 방법을 비교한다. `docs/nonideal_screen_v1_results.md`에 근거를 기록했다.

후속 lossy_repair_v1은 별도 합성 손실 모델·사양과 기생 보상 설계를 사전에 고정해
새 정상 설계 4개 모두를 통과시켰다. 고장 8개에서 이상적 공진 5/8, 수치 탐색 8/8,
같은 수치 후보를 받은 LLM 16/16 복구였다. 모든 LLM 응답이 최상위 수치 후보를
그대로 선택했고 위치·방향 진단은 8/16이었다. 추가 복구 이점은 확인되지 않았고
전부 첫 시도 성공이므로 후속 피드백 효과도 평가하지 못했다.
다음 질문은 보상 수정 후보의 선택과 실제 고장 위치의 진단을 분리했을 때의 효과다.
`docs/lossy_repair_v1_results.md`에 조건부 해석과 재현 근거를 기록했다.

diagnosis_visibility_v1은 새 8고장에서 같은 진단 전용 지시문·판단 보류 선택지를
사용하고 수치 후보 공개 여부만 바꿔 각각 16회 호출했다. 위치·방향 정답은 모두
0/16, 미공개 조건은 보류 15회·오진 1회, 공개 조건은 보류 16회였다.
이 설정에서는 후보 공개 시점에 따른 진단 정답률 개선이 확인되지 않았다.
고정된 공통 수정의 8/8 복구는 진단 결과와 독립적이다. 다음 연구에서는 고장 전
기준 측정이나 운용상 확보 가능한 부품 허용 범위 등 원인 식별 증거를 정의해야 한다.
`docs/diagnosis_visibility_v1_results.md`에 전체 결과와 한계를 기록했다.

reference_diagnosis_v1은 정상 정합 기준을 벗어난 257 MHz 설계 때문에 API 0회에서
중단했다. 사전 검증 뒤 적격 3설계·6고장만 고정한 별도 v2 탐색에서, 각 12회 진단
정답은 기준 측정 없음 3/12, 기준 측정 제공 3/12, 기준 측정+수치 역추정 제공 12/12였다.
기준 측정만 제공한 조건의 위치 오진은 6회, 보류 1회, 출력 한도 초과 2회였다.
같은 증거의 결정적 역추정 자체가 6/6을 진단·복구했고 LLM은 최상위 가설과 12/12회
일치했다. 현재 결과는 LLM의 독자적 원인 발견보다 수치 식별 결과를 반환한 효과로
해석한다. 기준 측정만의 정답률 개선은 확인되지 않았다.
정확한 현재 부품값·고정 모델·고장 전 측정·단일 값 변화라는 가정과 사전 검증 후
부분집합 선택을 명시하며, 기존 실험의 분모와 합산하지 않는다.
다음 질문은 잡음·계측 drift·모델 불일치에서 역추정이 언제 오진하거나 보류해야 하는가다.
`docs/reference_diagnosis_v2_results.md`에 원시 근거와 독립 감사를 기록했다.

reference_robustness_v1은 같은 고장 6개와 무고장 대조군 3개에 105개 고정 섭동을
적용해 API 없이 945건을 평가했다. 고장 630건에서 최상위 가설은 모두 정답이었지만
최종 진단은 정답 190·보류 440·오진 0이었다. 모든 고장 보류는 최선 잔차 0.02 dB
문턱 초과로 발생했다. 대조군 315건은 모두 보류해 단일 부품 오경보는 없었다.
잡음 σ=0.01 dB에서 60/60, 0.02 dB에서 33/60, 0.05/0.1 dB에서 0/60 정답이었다.
시험한 L/C drift ±0.1% 이상과 손실·기생 모델 불일치 ±10% 이상에서는 모두 보류했다.
이는 합성 스트레스 격자에서의 관찰이고 실제 오차 분포나 운용 허용치가 아니다.
다음 질문은 작은 값 고장·비균일 변화에서도 후보 순위와 잔차 분리가 유지되는지,
그리고 별도 개발/평가 집합에서 오진을 통제하며 보류 기준을 정할 수 있는지다.
`docs/reference_robustness_v1_results.md`에 native 69개 sweep과 독립 nodal 검증을 기록했다.

diagnosis_development_v1은 새 4설계의 주 부품 모두에 ±1/3/10% 변화를 주입하고 비균일
오차를 추가했다. 주입 변화 2,304건에서 최상위 후보 오답은 385건이었고 모두 보류됐다.
최종 진단은 정답 509·보류 1,795·오진 0, 무주입 대조군은 오경보 0/64였다.
무오차 ±1% 변화에서는 후보가 모두 맞아도 차선 문턱 때문에 34/48건을 보류했다.
반면 비균일 모델·환경 오차에서는 최선 잔차 문턱만 완화하면 오진이 통과하는 반례가 있었다.
기준 상태부터 규격 FAIL인 1설계도 제외하지 않았고 주입 변화와 성능 규격을 분리했다.
따라서 보류 기준은 적합 잔차·후보 간격·무고장/자연변화 모형과의 비교를 함께 검토하고,
개발/보정/미사용 평가 설계를 분리해 정해야 한다. 현재 문턱은 변경하지 않았다.
`docs/diagnosis_development_v1_results.md`에 해석과 보류 기준 설계 절차를 기록했다.

abstention_calibration_v1은 개발과 분리한 보정 4설계에서 36개 다중 기준 후보를 비교하고,
관찰 오진·오경보 0인 후보 중 정답이 가장 많은 설정을 고정했다. 미사용 4설계에서는
주입 변화 정답이 기존 487/2304에서 615/2304로 늘었고 기존 정답 손실은 없었다.
새 기준의 오진은 0, 무주입 대조군 오경보는 0/64였다. 최선 잔차 0.02 dB 상한을
유지하면서 간격 0.03 dB·비율 3·경험적 무고장 대조 점수·4회 안정성을 결합했다.
이 평가에서 대조·안정성 조건을 빼도 판정은 같아 추가 기여를 입증하지 못했다.
큰 drift·모델 불일치는 계속 보류했으며 개선은 주로 작은 변화의 구분에서 나타났다.
새 진단 명령에 적용했지만 실제 장비의 확률적 오류 보증은 아니고 추가 계산 비용이 있다.
`docs/abstention_calibration_v1_results.md`에 고정 절차와 독립 검증을 기록했다.

stability_extension_v1에서는 앞선 미사용 평가의 확정 615건을 대상으로 ±0.01 dB
재검사를 4→16회로 확대했다. 기존 2,460개를 재사용하고 추가 7,380개를 계산했으며,
615건 모두 최상위 부품·방향이 16/16회 일치했다. 새롭게 보류로 바뀔 확정 사례는
없었다. 이는 이미 확정된 입력에 대한 사후 반복 확인으로, 새로운 회로·오차 종류나
미사용 평가를 추가한 것이 아니다. 기본 정책의 4/4 조건은 그대로 유지한다.
`docs/stability_extension_v1_results.md`에 조건과 계산량을 기록했다.

## 핵심 지표

### 진단

- fault-type accuracy
- component localization Top-1 accuracy
- 필요할 경우 localization Top-3 accuracy
- joint diagnosis accuracy

### 복구

- strict repair success rate
- specification별 recovery rate
- normalized constraint violation 감소율
- simulation convergence rate
- invalid/prohibited edit rate

### 효율과 일관성

- Agent iteration 수
- 전체 simulator call 수
- input/output token 수와 API 비용
- wall-clock time
- 반복 실행별 성공률 분산
- 반복 실행 간 선택 부품 일치율

## 공정 비교 원칙

- 동일한 base model, specification, fault case와 실행 예산을 사용한다.
- simulation 실패와 invalid edit도 비용에 포함한다.
- Agent에게 정상 netlist, 정상 부품값 목록, fault manifest를 제공하지 않는다.
- RAG corpus에는 benchmark 정답이나 동일 회로의 repair 사례를 포함하지 않는다.
- 파일럿 결과를 확인한 뒤 protocol을 동결하고 최종 평가 case와 분리한다.

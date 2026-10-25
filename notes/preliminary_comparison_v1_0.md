# Preliminary one-shot comparison v1.0

실행일: 2026-09-02  
상태: `PRELIMINARY_NOT_FINAL_BENCHMARK`

## 비교 질문

동일한 faulty netlist와 목표 specification을 보는 one-shot LLM에 최초 고장 상태의
SPICE 측정값을 추가하면 단일 수정의 진단 및 복구 성능이 향상되는가?

이 비교는 반복적인 closed-loop feedback을 아직 시험하지 않는다. 두 조건 모두 한 번만
수정안을 생성하고, 외부 validator는 수정 후 결과를 판정하되 LLM에 다시 돌려주지 않는다.

## 통제된 설정

- 동일 모델: `gpt-5.6-luna`
- 동일 reasoning effort: `low`
- 동일 prompt/schema version: `value_one_edit_v1` / `agent_proposal_v1`
- 동일 10개 synthetic value fault, fault당 3회
- 동일 2,000-token output cap, 90-second timeout, automatic retry 0
- 동일 one-edit policy, ngspice simulator, 7-constraint validator
- 유일한 차이: 최초 faulty simulation metrics 포함 여부

두 조건 모두 API response와 schema-valid structured output을 30/30 확보했다.

## 결과

| 지표 | LLM only | + initial SPICE evidence | 차이(SPICE − only) |
|---|---:|---:|---:|
| Component localization | 26/30 (86.7%) | 24/30 (80.0%) | −6.7%p |
| Full diagnosis | 26/30 (86.7%) | 23/30 (76.7%) | −10.0%p |
| Patch acceptance | 28/30 (93.3%) | 26/30 (86.7%) | −6.7%p |
| Specification recovery | 27/30 (90.0%) | 24/30 (80.0%) | −10.0%p |
| Component consistency | 90.0% | 86.7% | −3.3%p |

| 기록된 token | LLM only | + SPICE evidence |
|---|---:|---:|
| Input | 26,799 | 40,917 |
| Output | 15,274 | 19,958 |
| Total | 42,073 | 60,875 |

현재 10-case preliminary comparison에서는 최초 SPICE metrics 추가가 성능을 높이지
않았고, 오히려 더 많은 token을 사용하면서 recovery가 3건 적었다.

## Fault별 specification recovery

| Fault | LLM only | + SPICE | SPICE 차이 |
|---|---:|---:|---:|
| `C1 ×0.5` | 3/3 | 2/3 | −1 |
| `C1 ×0.7` | 3/3 | 3/3 | 0 |
| `C1 ×1.3` | 3/3 | 3/3 | 0 |
| `C1 ×2.0` | 3/3 | 3/3 | 0 |
| `L1 ×0.5` | 3/3 | 3/3 | 0 |
| `L1 ×2.0` | 3/3 | 3/3 | 0 |
| `L2 ×0.5` | 1/3 | 1/3 | 0 |
| `L2 ×2.0` | 3/3 | 2/3 | −1 |
| `C2 ×0.5` | 3/3 | 1/3 | −2 |
| `C2 ×2.0` | 2/3 | 3/3 | +1 |

성능 차이는 주로 중앙 병렬 공진부 `L2/C2` fault에서 발생했다.

## 해석과 한계

이 결과만으로 SPICE feedback이 일반적으로 해롭다고 결론내릴 수 없다.

1. 현재 회로는 `L1/C1`과 `L3/C3`의 대칭 및 LC 공진 관계가 faulty netlist에 그대로
   드러난다. LLM only 조건도 다른 부품값과 목표 주파수로 정상값을 추론하기 쉽다.
2. SPICE 조건은 규칙별 원인 설명이 아니라 긴 raw metric 묶음을 받는다. 정보량 증가는
   localization signal 증가와 같지 않으며 오히려 잘못된 대체 부품을 고르게 할 수 있다.
3. 표본은 10개 value fault와 3회 반복뿐이며 동일 topology 내부 사례다.
4. 현재 비교는 simulator가 실패한 repair의 결과를 LLM에 반환하는 closed loop가 아니다.

따라서 현재 근거가 지지하는 좁은 결론은 다음과 같다.

> 이 synthetic filter pilot에서 raw initial SPICE metrics를 one-shot prompt에 추가하는
> 방식은 netlist-only 조건보다 진단 또는 복구를 개선하지 않았다.

## 다음 실험

첫 repair가 실패하면 다음 정보만 LLM에 추가해 최대 3회까지 재수정하는 closed-loop
조건을 구현한다.

- 직전 repair patch
- patch 거부 사유 또는 simulation convergence
- 실패한 validator constraint 이름, 측정값, threshold
- 수정 후 SPICE metrics

정상 netlist와 ground-truth fault는 계속 숨긴다. 이 실험은 initial metrics의 유무가 아니라
**실패에 근거한 simulator feedback이 최종 recovery와 iteration cost를 개선하는가**를
평가한다.

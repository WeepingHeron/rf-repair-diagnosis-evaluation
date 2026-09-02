# Value-fault repeat diagnostic v0.2

실행일: 2026-09-02  
상태: `DIAGNOSTIC_REPEAT_NOT_FINAL_BENCHMARK`

## 목적과 변경점

v0.1에서 12/30 응답이 구조화된 제안으로 변환되지 않은 원인을 분리하기 위해 동일한
10개 value fault를 각 3회 재실행했다. 모델, reasoning effort, 입력 evidence, one-edit
제약은 유지하고 출력 상한만 700에서 1,200 tokens로 높였다. 또한 parseable proposal이
없을 때 response status, incomplete reason, usage를 저장하도록 instrumentation을 보강했다.

## 관측 결과

| 지표 | 전체 planned attempts 기준 | 구조화 응답 기준 |
|---|---:|---:|
| Structured response | 26/30 (86.7%) | — |
| Component localization | 23/30 (76.7%) | 23/26 (88.5%) |
| Full diagnosis | 23/30 (76.7%) | 23/26 (88.5%) |
| Restricted patch acceptance | 24/30 (80.0%) | 24/26 (92.3%) |
| Simulation convergence | 24/30 (80.0%) | 24/24 accepted (100.0%) |
| Specification recovery | 24/30 (80.0%) | 24/26 (92.3%) |

- Component consistency across available structured responses: 93.3%
- Recorded API usage: input 39,202, output 19,116, total 58,318 tokens
- Structured proposal unavailable: 4/30
- Structured proposal returned but patch rejected: 2/30
- Patch accepted but simulation/spec failure: 0/24

## 구조화 응답이 없었던 4건

| 유형 | 건수 | 해석 |
|---|---:|---|
| `incomplete / max_output_tokens` | 3 | 1,200-token 상한에서도 최종 구조화 출력을 완성하지 못함 |
| Pydantic `ValidationError` | 1 | 응답이 요구 schema와 맞지 않아 SDK parse 단계에서 거부됨 |

따라서 출력 상한이 구조화 응답 누락을 일으킬 수 있다는 메커니즘은 v0.2에서 직접
확인됐다. 다만 v0.1은 실패 상세를 저장하지 않았으므로 v0.1의 12건 모두가 같은
원인이었다고 소급해 단정하지 않는다.

## 허용되지 않은 두 수정

두 응답은 형식 자체는 유효했지만 현재 netlist 값과 같은 값을 제안했다.

- `C2 ×0.5` fault에서 정상 상태인 L2의 현재값 `3.978873577n`을 그대로 제안
- 같은 fault에서 이미 잘못 들어 있는 C2의 현재값 `318.309886p`을 그대로 제안

코드는 이를 실제 변경이 없는 no-op으로 판단해 시뮬레이션 전에 거부했다. 즉 26개의
구조화 응답 중 실제 수정은 24개였으며, 이 24개는 모두 simulation convergence와 spec
recovery를 달성했다.

## 보상 수정

원인 부품과 다른 부품을 조정해 spec을 회복한 실행도 있었다.

- `L1 ×0.5`에서 C1 조정으로 복구
- `L2 ×2.0`에서 C2 조정으로 복구

이는 코드가 수정안을 만든 것이 아니다. LLM이 제안한 단일 edit를 코드가 허용 규칙에
따라 그대로 적용했고 ngspice와 validator가 기능 회복을 확인했다. 이런 실행은
`functional repair = success`, `causal localization = failure`로 분리 계산한다.

## v0.1 대비

| 지표 | v0.1 | v0.2 | 변화 |
|---|---:|---:|---:|
| Structured response | 60.0% | 86.7% | +26.7%p |
| Component localization / planned | 50.0% | 76.7% | +26.7%p |
| Specification recovery / planned | 53.3% | 80.0% | +26.7%p |
| Localization / structured | 83.3% | 88.5% | +5.1%p |
| Recovery / structured | 88.9% | 92.3% | +3.4%p |

v0.1의 실패 응답 usage가 저장되지 않았으므로 두 버전의 총 token 수나 비용은 직접
비교하지 않는다. 또한 LLM의 비결정성과 작은 표본 때문에 위 변화량을 모델 성능 향상으로
주장하지 않는다. v0.2는 출력 예산과 실패 관측 방법을 점검하는 diagnostic repeat다.

## 실행 중 프로토콜 보정

28개 논리 회차 저장 후 한 네트워크 요청이 장시간 응답 헤더를 반환하지 않아 수동으로
중단했다. 저장된 28개는 보존했고 마지막 두 논리 회차는 호출당 90초, SDK 자동 재시도
0회로 실행했다. 중단된 전송은 결과 행으로 계산하지 않았지만 실제 요청 수와 비용에는
영향을 줄 가능성이 있다. 따라서 v0.2 역시 최종 동결 benchmark가 아니다.

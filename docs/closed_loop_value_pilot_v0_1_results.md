# Closed-loop value-fault pilot v0.1

실행일: 2026-09-02  
상태: `CLOSED_LOOP_PIPELINE_PILOT_NOT_FINAL_BENCHMARK`

## 목적

최초 SPICE metrics를 단순히 one-shot prompt에 추가하는 것이 아니라, 실패한 repair의
deterministic simulator/validator evidence를 다음 Agent iteration에 제공했을 때 수정안이
실제로 개선될 수 있는지 확인한다.

- value fault 10개, fault당 trajectory 1개
- trajectory당 최대 3 Agent calls
- 각 후보는 누적 수정이 아니라 동일한 original faulty netlist에서 독립적으로 생성
- 성공 시 즉시 종료
- 정상 netlist와 ground-truth fault는 Agent에 비공개

## 결과

| 지표 | 첫 iteration | 최종 iteration |
|---|---:|---:|
| Component localization | 9/10 (90%) | 9/10 (90%) |
| Full diagnosis | 8/10 (80%) | 9/10 (90%) |
| Specification recovery | 9/10 (90%) | 10/10 (100%) |

- Feedback으로 추가 복구된 trajectory: 1/10
- 총 Agent calls: 11
- 평균 iterations: 1.1
- 기록된 총 token: 21,013
- 최대 iteration 도달 실패: 0

## 실제 feedback rescue

`C2 ×0.5` fault의 첫 iteration:

- localization: C2로 정확
- fault direction: `value_too_high`로 오진
- repair: `C2 = 63.6619772p`
- ngspice: 수렴
- validator: `SPECIFICATION_VIOLATION`

두 번째 iteration에는 첫 proposal, 수정 후 SPICE metrics, 실패한 constraint의 measured
value와 threshold만 제공했다. Agent는 다음처럼 수정했다.

- fault direction: `value_too_low`
- repair: `C2 = 636.619772p`
- ngspice: 수렴
- validator: `ALL_CONSTRAINTS_MET`

코드는 정답 부품이나 정상값을 알려주지 않았으며 두 번째 값을 계산하거나 보정하지 않았다.
실패 evidence를 구조화해 다시 전달하고 LLM의 새 patch를 동일 정책으로 실행했을 뿐이다.

## Causal diagnosis와 functional repair

`L2 ×2.0` trajectory는 첫 iteration에서 L2가 아닌 C2를 절반으로 조정해 spec을 통과했다.
따라서 최종 functional recovery는 10/10이지만 causal component localization은 9/10이다.
이 결과는 두 지표를 계속 분리해야 함을 재확인한다.

## 해석 한계

이 pilot은 trajectory가 fault당 한 개뿐이므로 100%를 일반적인 성능으로 주장할 수 없다.
또한 첫 iteration 9/10과 최종 10/10의 차이는 단 한 사례다. 현재 확인된 것은 다음의
좁은 파이프라인 사실이다.

> deterministic failure evidence를 다음 iteration에 제공했을 때, 최소 한 사례에서
> LLM이 잘못된 방향과 값을 수정하여 simulator-verified recovery를 달성했다.

후속 평가는 같은 fault당 여러 trajectory를 실행해 first-attempt와 final recovery의 paired
차이, 추가 API/simulator calls, token cost를 함께 보고해야 한다.

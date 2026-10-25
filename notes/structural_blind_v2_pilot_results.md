# Structural blind v2 pilot results

실행일: 2026-09-02  
상태: `PARTIAL_PILOT_6_OF_18_TRAJECTORIES`

## 목적과 조건

기존 structural 실험의 `RFAULTC1`, `RFAULTL2` 같은 이름이 정답 component를
노출하는 문제를 제거했다. 네 개의 reactive-component fault는 모두 중립 이름
`RFAULT1`로 제시했고, Agent는 netlist topology와 simulation metrics에서 원래
component를 추론했다.

- synthetic fault 유형: open/short 4개, port impedance mismatch 2개
- 이번 실행: fault당 1 trajectory, 총 6 trajectories
- trajectory당 최대 3 Agent iterations
- strict patch syntax: `nH`, `pF`, `ohm` 등의 단위 표기를 자동 변환하지 않음
- 성공 판정: Agent 주장이 아니라 ngspice 결과에 대한 deterministic validator
- 고정 protocol commit: `8afd4186801010a2bdcc76c4eb3e186c26f173cc`

## 예비 결과

| 지표 | 결과 |
|---|---:|
| Component localization | 6/6 (100.0%) |
| Full diagnosis | 3/6 (50.0%) |
| Simulator-verified specification recovery | 5/6 (83.3%) |
| API/schema completion | 8/8 (100.0%) |
| First-iteration recovery | 5/6 (83.3%) |

- Agent calls: 8
- accepted candidate simulations: 5
- initial faulty simulations: 6
- recorded tokens: input 12,367; output 2,828
- estimated API cost: USD 0.00648415

이 값은 총 18 trajectories 중 6개만 끝낸 예비 결과다. 반복 실행의 일관성이나
최종 성공률로 보고하려면 남은 12 trajectories를 완료해야 한다.

## 유형별 결과

| Fault | Localization | Fault type | Recovery | Iterations | 비고 |
|---|---:|---:|---:|---:|---|
| C1 open | PASS | PASS | PASS | 1 | 첫 시도에서 복구 |
| C1 short | PASS | FAIL | PASS | 1 | repair는 맞았지만 fault type을 open으로 기록 |
| L2 open | PASS | PASS | FAIL | 3 | 세 번 모두 `nH` 단위 표기로 strict parser가 거절 |
| C2 short | PASS | FAIL | PASS | 1 | evidence는 short를 설명했지만 JSON label은 open |
| input z0 25 ohm | PASS | PASS | PASS | 1 | VPORT1을 50으로 복구 |
| output z0 100 ohm | PASS | FAIL | PASS | 1 | VPORT2는 맞았지만 source mismatch로 잘못 분류 |

## 실패 해석

L2 open은 회로 추론 실패가 아니다. 세 iteration 모두 `L2`, `open`, 약
`3.978873577 nH`를 정확히 제안했다. 그러나 frozen strict 조건에서는 SPICE token
`3.978873577n`만 허용하고 사람이 읽는 단위가 붙은 `3.978873577nH`는 허용하지
않으므로 patch 적용 전에 거절됐다. 따라서 다음 세 층을 분리해서 보고한다.

- causal diagnosis: 성공
- repair intent: 성공
- strict executable interface: 실패
- simulator-verified recovery: 실패 처리

두 short 사례는 evidence 문장에서는 1 mOhm이 short임을 올바르게 설명했지만,
구조화된 `fault_type` 필드를 `open`으로 출력했다. VPORT2 사례도 고장 위치와 수정값은
맞았지만 `load_impedance_mismatch` 대신 `source_impedance_mismatch`를 선택했다.
이 때문에 functional recovery보다 full diagnosis가 낮다.

## 독립 점검

- 여덟 API 응답의 response ID가 모두 고유함을 확인했다.
- 저장한 output text와 SHA-256 hash가 여덟 건 모두 일치했다.
- 다섯 repaired S-parameter table을 다시 읽고 validator를 독립 실행했으며 모두 PASS였다.
- 네 reactive fault netlist에 component 이름을 포함한 `RFAULTC1`, `RFAULTL2`,
  `RFAULTC2`가 없고 `RFAULT1`만 있음을 확인했다.
- 전체 unit tests 34개가 통과했다.

## 주장 범위

이 결과는 ideal lumped 100 MHz filter의 합성 fault에 대한 SPICE 수준 예비 결과다.
실제 PCB, RFIC, 측정 잡음, 기생 성분 또는 하드웨어 복구 능력을 입증하지 않는다.

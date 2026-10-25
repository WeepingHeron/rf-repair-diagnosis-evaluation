# Structural closed-loop v1.0 results

실행일: 2026-09-02  
상태: `STRICT_SYNTAX_STRUCTURAL_RESULT`

## 범위

- synthetic open/short fault 4개
- source/load port impedance mismatch 2개
- fault당 3 trajectories, 총 18
- trajectory당 최대 3 Agent iterations
- 허용 연산: `restore_component`, `set_port_impedance`
- open/short는 각각 1 TΩ, 1 mΩ resistor replacement로 근사한 SPICE 합성 fault

## 결과

| 지표 | 첫 iteration | 최종 iteration |
|---|---:|---:|
| Component localization | 18/18 (100.0%) | 18/18 (100.0%) |
| Full diagnosis | 15/18 (83.3%) | 15/18 (83.3%) |
| Specification recovery | 16/18 (88.9%) | 16/18 (88.9%) |

- 총 Agent calls: 22
- 평균 iterations: 1.22
- accepted candidate simulations: 16
- initial faulty simulations: 6
- API/schema failure: 0
- 기록된 총 token: 39,570

## 미복구 두 trajectory

두 실패는 모두 `L2 open`이었다. Agent는 모든 iteration에서 L2와 open을 정확히
진단했지만 다음처럼 단위 기호가 포함된 값을 제안했다.

- `3.183098862uH`
- `3.978873577nH`
- `3978873577e-18 H`
- `3.9788736nH`
- `3.97887358nH`
- `3.978873577e-9 H`

현재 엄격한 patch parser는 ngspice element value token인 `3.978873577n` 또는
`3.978873577e-9`만 허용한다. 따라서 위 제안은 회로에 적용되기 전에 정책 거부됐고,
candidate simulation은 실행되지 않았다.

이 결과에서 두 실패는 다음처럼 분리해야 한다.

- causal diagnosis: 성공
- repair intent: L2 restoration으로 적절함
- executable patch syntax: 실패
- simulator-verified recovery: 미평가/실패 처리

## Fault-type 혼동

VPORT2 mismatch 세 trajectory는 모두 VPORT2를 50Ω으로 복구해 spec을 통과했지만,
fault type을 `load_impedance_mismatch`가 아니라 `source_impedance_mismatch`로 표시했다.
따라서 localization과 functional recovery는 성공, full diagnosis는 실패다.

## 해석 경계

값 표현을 사후에 임의 수정해 v1.0 성공으로 재분류하지 않는다. 다만 `nH`, `pF`, `ohm`
같은 명시적 물리 단위를 제한된 규칙으로 canonical SPICE token으로 변환하는 것은 일반적인
syntax adapter로 별도 버전에서 평가할 수 있다. 그 경우 새 프로토콜과 새 결과로 기록한다.

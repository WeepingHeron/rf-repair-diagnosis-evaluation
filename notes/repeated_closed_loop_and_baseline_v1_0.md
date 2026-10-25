# Repeated closed-loop and deterministic baseline v1.0

실행일: 2026-09-02  
상태: `REPEATED_VALUE_FAULT_RESULT`

## Repeated closed-loop protocol

- synthetic value fault 10개
- fault당 독립 trajectory 3개, 총 30 trajectories
- trajectory당 최대 3 Agent iterations
- 성공 시 즉시 종료
- 각 iteration은 original faulty netlist에서 후보 한 개를 생성
- 실패 시 직전 patch, patch 거부 코드 또는 수정 후 SPICE/validator evidence를 다음
  iteration에 제공
- 정상 netlist와 evaluator ground truth는 Agent에 비공개

## Closed-loop 결과

| 지표 | 첫 iteration | 최대 3 iterations 후 |
|---|---:|---:|
| Component localization | 24/30 (80.0%) | 27/30 (90.0%) |
| Full diagnosis | 24/30 (80.0%) | 27/30 (90.0%) |
| Specification recovery | 26/30 (86.7%) | 30/30 (100.0%) |

- Feedback rescue: 4/30 trajectories
- 최대 iteration 이후 미복구: 0/30
- 총 Agent calls: 35
- 평균 iterations: 1.17
- API/schema failure: 0
- Accepted candidate simulations: 34
- Initial faulty simulations: 10 (동일 fault의 3 trajectories에서 공유)
- 전체 ngspice calls: 44
- 기록된 총 token: 71,645

## 네 건의 feedback rescue

- `L2 ×0.5`: trajectory 1과 2에서 C2 오진 후 L2 정답 수정으로 복구
- `C2 ×0.5`: no-op C2 제안, 잘못된 L2 제안을 거쳐 세 번째 C2 수정으로 복구
- `C2 ×2.0`: L2 오진 후 두 번째 C2 수정으로 복구

모든 rescue는 정답 정보를 반환해서가 아니라, 이전 candidate의 deterministic 실패
evidence를 다음 iteration에 제공해 발생했다.

`L2 ×2.0`의 세 trajectory는 모두 C2를 절반으로 조정하는 보상 repair로 첫 시도에
통과했다. 따라서 functional recovery는 30/30이지만 최종 causal localization은 27/30이다.

## Deterministic ratio-grid baseline

baseline은 Agent나 정답 manifest를 사용하지 않는다. faulty netlist의 C1, C2, C3, L1,
L2, L3 각각에 다음 네 multiplier를 고정 순서로 적용하고 첫 specification PASS에서
종료한다.

```text
0.5, 1/1.3, 1/0.7, 2.0
```

이 후보는 benchmark fault severity 집합의 역수를 포함하므로 일반 목적 최적화기가 아니라
현재 value-fault benchmark에 맞춘 강한 탐색 baseline이다.

| 지표 | Deterministic grid |
|---|---:|
| Specification recovery | 10/10 (100%) |
| Causal component localization | 8/10 (80%) |
| Candidate ngspice calls | 65 |
| Mean calls per case | 6.5 |

## 비교 해석

두 방법 모두 현재 value-fault 집합에서 100% functional recovery를 달성했다. 그러나
비용과 동작 방식이 다르다.

- closed-loop Agent: 30 stochastic trajectories에 34 candidate simulations, 평균 1.17
  Agent calls, 별도의 API/token 비용 발생
- deterministic grid: 10 deterministic cases에 65 candidate simulations, API 비용 없음
- 두 방법 모두 보상 repair 때문에 functional recovery와 causal localization이 다름

trajectory와 case의 분모가 다르고 grid가 benchmark severity를 알고 있으므로 두 성공률을
통계적으로 동등 비교하지 않는다. 현재 결과는 Agent가 더 적은 candidate simulation으로
복구 후보를 제시할 수 있다는 효율성 신호와, grid search가 API 없이 완전 복구 가능한
강한 기준선임을 함께 보여준다.

## 주장 경계

이 결과는 하나의 ideal lumped filter와 자동 삽입한 value faults에 한정된다. 구조 fault,
새 topology, 실제 부품 오차, PCB/RFIC 및 하드웨어 동작으로 일반화하지 않는다.

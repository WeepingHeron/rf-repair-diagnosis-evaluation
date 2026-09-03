# Blind combined interface v2.3 results

실행 완료일: 2026-09-03  
상태: `COMPLETE_18_OF_18_TRAJECTORIES`

## 실험 목적

Blind structural fault에서 다음 두 interface 개선을 동시에 적용했다.

- fault label guidance: open/short와 source/load label의 의미를 공통 정의
- deterministic unit canonicalizer: 물리 단위를 SPICE value token으로 변환

모든 reactive fault 이름은 계속 `RFAULT1`로 유지했다. 현재 사례의 ground-truth
component나 healthy value는 Agent에게 제공하지 않았다.

## 결과

| 지표 | 첫 iteration | 최종 iteration |
|---|---:|---:|
| Component localization | 18/18 (100.0%) | 18/18 (100.0%) |
| Full diagnosis | 18/18 (100.0%) | 18/18 (100.0%) |
| Simulator-verified recovery | 17/18 (94.4%) | 17/18 (94.4%) |

- Agent calls: 20
- 평균 iterations: 1.11
- accepted candidate simulations: 17
- initial faulty simulations: 6
- API/schema failures: 0
- complete response provenance: 20/20
- input tokens: 31,534
- output tokens: 5,224
- estimated API cost: USD 0.00984554
- frozen protocol commit: `a138177`

## Fault별 결과

| Fault | Localization | Full diagnosis | Recovery |
|---|---:|---:|---:|
| C1 open | 3/3 | 3/3 | 3/3 |
| C1 short | 3/3 | 3/3 | 3/3 |
| L2 open | 3/3 | 3/3 | 3/3 |
| C2 short | 3/3 | 3/3 | 2/3 |
| input z0 25 ohm | 3/3 | 3/3 | 3/3 |
| output z0 100 ohm | 3/3 | 3/3 | 3/3 |

## 미복구 1건

`C2 short`, trajectory 3은 세 iteration 모두 다음 내용을 정확히 제안했다.

- component: `C2`
- fault type: `short`
- repair value: `636.619772 pF`

그러나 현재 deterministic canonicalizer는 `636.619772pF`는 허용하지만 숫자와 SI
prefix 사이에 공백이 있는 `636.619772 pF`는 허용하지 않는다. 세 patch는 simulation
전에 `PATCH_POLICY_REJECTED`로 종료됐다.

따라서 이 trajectory는 다음처럼 분리한다.

- component localization: 성공
- causal diagnosis: 성공
- repair value intent: 성공
- deterministic interface parsing: 실패
- simulator-verified recovery: 실패 처리

이 결과를 사후에 성공으로 재분류하지 않는다. 공백 표기 지원은 별도 버전의 parser와
protocol에서 평가해야 한다.

## 네 조건 비교

| 조건 | 최종 Localization | 최종 Full diagnosis | 최종 Recovery | Calls |
|---|---:|---:|---:|---:|
| Blind strict v2 | 18/18 | 10/18 | 16/18 | 22 |
| Unit adapter v2.1 | 18/18 | 11/18 | 17/18 | 21 |
| Label guidance v2.2 | 18/18 | 18/18 | 16/18 | 26 |
| Combined v2.3 | 18/18 | 18/18 | 17/18 | 20 |

Combined 조건은 strict 대비 full diagnosis를 55.6%에서 100.0%로, recovery를
88.9%에서 94.4%로 개선했다. 다만 같은 fault set을 사용한 development comparison이며,
새 회로나 실제 하드웨어에 대한 일반화를 입증하지 않는다.

## 독립 검증

- 20개 response ID가 모두 고유함을 확인했다.
- 20개 output text와 SHA-256 hash가 모두 일치했다.
- 17개 accepted repair의 S-parameter evidence를 다시 읽고 validator를 독립 실행했으며
  17개 모두 PASS였다.
- 미복구 trajectory의 세 patch는 모두 simulation 전에 parser가 거절했음을 확인했다.
- unit tests 36개가 통과했다.

## 비용

2026-09-03 GPT-5.6 Luna 공개 단가와 응답 usage로 계산한 v2.3 비용은
USD 0.00984554다. Blind strict와 세 interface 조건을 모두 합친 추정 비용은
USD 0.05218247이다. 이는 API 청구서가 아니라 공개 단가 기반 계산값이다.

## 주장 범위

이 결과는 ideal lumped 100 MHz filter의 합성 fault에 대한 simulator-level 결과다.
실제 PCB, RFIC, 기생 성분, 측정 잡음 또는 하드웨어 복구 성능을 입증하지 않는다.

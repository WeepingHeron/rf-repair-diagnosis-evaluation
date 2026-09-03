# Paper-ready result tables

상태: `CURRENT_SIMULATOR_ONLY_RESULTS`  
주장 범위: 하나의 ideal lumped 100 MHz band-pass filter에 자동 삽입한 synthetic faults

## 표 1. Value-fault 조건 비교

| 조건 | Trajectories | Causal localization | Full diagnosis | Spec recovery | Agent calls | Candidate simulations | Recorded tokens |
|---|---:|---:|---:|---:|---:|---:|---:|
| LLM only, one-shot | 30 | 26/30 (86.7%) | 26/30 (86.7%) | 27/30 (90.0%) | 30 | 28 | 42,073 |
| LLM + initial SPICE, one-shot | 30 | 24/30 (80.0%) | 23/30 (76.7%) | 24/30 (80.0%) | 30 | 26 | 60,875 |
| LLM + iterative SPICE/validator feedback | 30 | 27/30 (90.0%) | 27/30 (90.0%) | 30/30 (100.0%) | 35 | 34 | 71,645 |
| Deterministic ratio grid | 10 | 8/10 (80.0%) | N/A | 10/10 (100.0%) | 0 | 65 | 0 |

주의: deterministic grid는 fault severity 집합의 역수 후보를 사용하며 Agent 조건보다
simulation budget이 크다. 10 deterministic cases와 30 stochastic trajectories를 동일
표본으로 간주하지 않는다.

## 표 2. Closed-loop fault-family 결과

| Fault family | Fault cases | Trajectories | First recovery | Final recovery | Final localization | Final diagnosis | Agent calls | Candidate simulations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Component value | 10 | 30 | 26/30 (86.7%) | 30/30 (100.0%) | 27/30 (90.0%) | 27/30 (90.0%) | 35 | 34 |
| Open/short/port mismatch, strict syntax | 6 | 18 | 16/18 (88.9%) | 16/18 (88.9%) | 18/18 (100.0%) | 15/18 (83.3%) | 22 | 16 |
| **합계** | **16** | **48** | **42/48 (87.5%)** | **46/48 (95.8%)** | **45/48 (93.8%)** | **42/48 (87.5%)** | **57** | **50** |

합계는 현재 두 frozen protocol의 단순 micro-average다. fault family와 난이도가 균등하지
않으므로 전체 일반화 성능으로 해석하지 않는다.

## 표 2a. Post-hoc structural interface remediation

| 조건 | Trajectories | First recovery | Final recovery | Final localization | Final diagnosis | Agent calls | Candidate simulations |
|---|---:|---:|---:|---:|---:|---:|---:|
| Structural strict syntax v1.0 | 18 | 16/18 (88.9%) | 16/18 (88.9%) | 18/18 (100.0%) | 15/18 (83.3%) | 22 | 16 |
| Structural normalized + port-role prompt v1.1 | 18 | 16/18 (88.9%) | 18/18 (100.0%) | 18/18 (100.0%) | 18/18 (100.0%) | 21 | 21 |
| Value v1.0 + normalized structural v1.1 | 48 | 42/48 (87.5%) | 48/48 (100.0%) | 45/48 (93.8%) | 45/48 (93.8%) | 56 | 55 |

v1.1은 strict 결과를 본 뒤 단위 canonicalization과 port-role 설명을 함께 변경한 post-hoc
실험이다. 마지막 합계는 시스템 동작 요약이며 독립적인 최종 benchmark로 사용하지 않는다.

## 표 3. 실패 및 복구 메커니즘

| 구분 | 건수 | 처리 |
|---|---:|---|
| Value trajectory first-attempt failure | 4 | 모두 feedback 후 복구 |
| Structural final failure | 2 | L2/open은 정확히 진단했으나 `nH`/`H` 표기가 strict patch syntax에서 거부됨 |
| Structural v1.1 feedback rescue | 2 | 단위 canonicalization 후 잘못된 값 후보를 simulator feedback으로 교정 |
| Value final compensatory repair | 3 | L2 fault를 C2 조정으로 복구; localization 실패, functional recovery 성공 |
| VPORT2 fault-type confusion | 3 | 위치와 repair 성공, source/load label 오분류 |
| Combined holdout numeric error | 1 | L2의 nH 값을 μH로 제안한 1000배 오류; simulation은 수렴했지만 validator가 FAIL 판정 |
| API/schema failure | 0 | 현재 v1.0 value/structural closed-loop에서 관측되지 않음 |

## 표 4. Interface improvement ablation

`Ablation`은 여러 변경을 한꺼번에 평가하지 않고 한 요인씩 분리하는 실험이다.

| 조건 | 단위 변환 | 포트 역할 설명 | Final recovery | Final diagnosis | Agent calls |
|---|---|---|---:|---:|---:|
| Strict v1.0 | Off | Off | 16/18 (88.9%) | 15/18 (83.3%) | 22 |
| Unit-only v1.2 | On | Off | 18/18 (100.0%) | 15/18 (83.3%) | 21 |
| Port-role-only v1.4 | Off | On | 17/18 (94.4%) | 16/18 (88.9%) | 24 |
| Combined v1.1 | On | On | 18/18 (100.0%) | 18/18 (100.0%) | 21 |

## 표 5. Blind holdout strict-vs-combined confirmation

`Holdout`은 개선 과정에서 사용하지 않고 별도 확인용으로 남겨둔 사례다.

| 조건 | Fault cases | Trajectories | First recovery | Final recovery | Final localization | Final diagnosis | Agent calls |
|---|---:|---:|---:|---:|---:|---:|---:|
| Strict holdout | 6 | 18 | 13/18 (72.2%) | 14/18 (77.8%) | 18/18 (100.0%) | 9/18 (50.0%) | 27 |
| Combined holdout | 6 | 18 | 17/18 (94.4%) | 17/18 (94.4%) | 18/18 (100.0%) | 18/18 (100.0%) | 20 |

Holdout은 같은 회로 topology 안의 새 합성 fault이므로 arbitrary RF circuits에 대한 외부
일반화 결과가 아니다. 모든 holdout fault는 LLM 실행 전에 고장 상태가 specification을
위반하고 정확한 one-edit repair가 이를 회복함을 deterministic하게 확인했다. Combined의
유일한 미복구는 `L2 = 3.9788736 uH`를 제안한 사례로, 정상값 `3.978873577 nH`보다
1000배 컸다. parser와 ngspice는 실행했지만 validator가 specification 미회복으로
판정했다. 중단된 port-role v1.3의 부분 실행 7건은 모든 표에서 제외했다.

## 논문용 핵심 관찰

1. Raw initial SPICE metrics를 one-shot 입력에 추가하는 것만으로는 현재 value-fault
   benchmark 성능이 개선되지 않았다.
2. 실패한 patch의 deterministic evidence를 다음 iteration에 제공하면 value fault 네 건이
   추가 복구됐다.
3. Functional recovery는 causal diagnosis보다 높을 수 있으며 보상 repair를 별도 집계해야
   한다.
4. Structural fault에서는 회로 진단과 실행 가능한 SPICE syntax 사이의 interface failure가
   최종 성공률을 제한했다.
5. 제한된 단위 canonicalization과 fault-label 명시는 development ablation에서 각 요인의
   역할을 분리했으며, 결합 조건은 recovery와 full diagnosis 모두 18/18이었다.
6. 같은 회로의 미관측 holdout에서 결합 인터페이스는 strict 대비 final diagnosis를
   9/18에서 18/18로, recovery를 14/18에서 17/18로 높였다. 그러나 1000배 수치 오류 한
   건은 구조화 응답만으로 걸러지지 않아 deterministic SPICE 검증이 여전히 필요했다.

모든 수치는 simulator-only 결과다. 실제 부품, PCB, RFIC 또는 계측 성능을 의미하지 않는다.

# Interface-improvement experiment results

상태: `COMPLETE_SIMULATOR_ONLY_RESULTS`

## 용어

- **주 결과**: 결과를 보기 전에 정한 규칙으로 측정한 핵심 성능.
- **인터페이스 개선**: LLM 출력과 SPICE 실행기 사이의 형식 전달을 개선하는 변경.
- **Ablation(요인 분리 실험)**: 여러 변경 중 하나만 적용해 어떤 변경이 영향을 주었는지
  살펴보는 실험.
- **Holdout(별도 시험 사례)**: 개선 설계에 사용하지 않고 마지막 확인용으로 남겨둔 사례.

## 1. 주 결과

주 결과에는 결과 확인 후 만든 인터페이스 개선을 포함하지 않는다.

| Fault family | Trajectories | Final recovery | Final localization | Final diagnosis |
|---|---:|---:|---:|---:|
| Value, frozen v1.0 | 30 | 30/30 (100.0%) | 27/30 (90.0%) | 27/30 (90.0%) |
| Structural, strict frozen v1.0 | 18 | 16/18 (88.9%) | 18/18 (100.0%) | 15/18 (83.3%) |
| **Primary total** | **48** | **46/48 (95.8%)** | **45/48 (93.8%)** | **42/48 (87.5%)** |

## 2. 기존 structural 사례에서의 요인 분리 실험

| Condition | Unit conversion | Port-role explanation | First recovery | Final recovery | Final diagnosis | Agent calls |
|---|---|---|---:|---:|---:|---:|
| Strict v1.0 | Off | Off | 16/18 (88.9%) | 16/18 (88.9%) | 15/18 (83.3%) | 22 |
| Unit-only v1.2 | On | Off | 15/18 (83.3%) | 18/18 (100.0%) | 15/18 (83.3%) | 21 |
| Port-role-only v1.4 | Off | On | 14/18 (77.8%) | 17/18 (94.4%) | 16/18 (88.9%) | 24 |
| Combined v1.1 | On | On | 16/18 (88.9%) | 18/18 (100.0%) | 18/18 (100.0%) | 21 |

관측된 결과에서 단위 변환은 strict 조건의 최종 복구 실패 2건을 제거했다. 포트 역할
설명만 추가한 조건은 최종 진단이 15/18에서 16/18로 변했으며, 결합 조건은 18/18이었다.
그러나 각 조건은 18 trajectories의 독립적인 LLM 실행이므로, 작은 차이는 확정적인 인과
효과가 아니라 관측 차이로 해석한다.

Port-role v1.3은 의도와 달리 단위 허용 안내까지 포함한 것을 실행 중 발견해 중단했다.
완료된 7 trajectories는 모든 공식 집계에서 제외했고, 이유와 대체 프로토콜 v1.4를 Git
기록에 남겼다.

## 3. 개선 인터페이스의 holdout 확인

| Cases | Trajectories | First recovery | Final recovery | Final localization | Final diagnosis | Agent calls | Candidate simulations |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 6 | 18 | 18/18 (100.0%) | 18/18 (100.0%) | 18/18 (100.0%) | 17/18 (94.4%) | 18 | 18 |

모든 holdout repair는 첫 iteration에 specification을 회복했다. 한 trajectory는 VPORT2를
정확히 찾아 50 ohm으로 복구했지만 fault type을 source mismatch로 잘못 분류하여, 기능적
복구와 원인 진단을 별도로 집계했다.

## 해석 경계

Holdout은 C3/L1/L3과 반대 방향 port impedance를 포함하지만 같은 100 MHz ideal lumped
filter topology 안에 있다. 따라서 이 결과는 기존 여섯 사례에만 맞춘 규칙이 아니라는
제한적인 근거이며, 다른 filter topology, LNA, 실제 PCB 또는 RFIC에 대한 일반화 증거는
아니다.

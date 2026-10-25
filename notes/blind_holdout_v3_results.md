# Blind structural holdout v3.0 결과

실행 완료일: 2026-09-03  
상태: `COMPLETE_36_OF_36_TRAJECTORIES`

## 실험 목적

개발 실험에서 사용하지 않은 여섯 fault tuple에 대해 strict interface와 combined
interface를 비교했다. 여기서 holdout은 prompt와 parser를 개선할 때 결과를 보지 않고
마지막 확인용으로 남겨 둔 사례를 뜻한다.

- strict: 기존 구조화 응답 규칙만 적용
- combined: fault label guidance와 robust unit canonicalization을 함께 적용
- fault label guidance: open/short 및 source/load mismatch의 의미를 prompt에 명시
- unit canonicalization: `795.77 nH` 같은 표현을 ngspice가 읽는 표준 value token으로 변환

두 조건 모두 같은 모델, 회로, fault, 반복 횟수와 최대 iteration을 사용했다. 반응성
부품 fault는 원래 부품명을 감추기 위해 공통 이름 `RFAULT1`로 표현했다.

## Holdout 구성과 사전 검사

Holdout은 기존 development set과 `(component, fault_type, faulty_z0)` 조합이 겹치지
않는 여섯 사례로 구성했다.

| Holdout fault | Ground-truth repair |
|---|---|
| L1 open | `L1 = 795.774715 nH` 복원 |
| C3 open | `C3 = 3.183098862 pF` 복원 |
| L3 short | `L3 = 795.774715 nH` 복원 |
| L2 short | `L2 = 3.978873577 nH` 복원 |
| input z0 100 ohm | source impedance를 50 ohm으로 복원 |
| output z0 25 ohm | load impedance를 50 ohm으로 복원 |

LLM을 사용하지 않은 deterministic pre-screening에서 6/6 fault가 frozen specification을
위반했고, 각 ground-truth one-edit repair는 6/6 모두 specification을 회복했다. 따라서
실험 대상은 한 번의 정확한 수정으로 복구 가능한 합성 fault로 제한된다.

## 주 결과

각 조건은 6 fault × 3회 독립 trajectory, 총 18 trajectory로 실행했다.

| 지표 | Strict holdout | Combined holdout | 차이 |
|---|---:|---:|---:|
| Component localization | 18/18 (100.0%) | 18/18 (100.0%) | 0.0%p |
| Full diagnosis | 9/18 (50.0%) | 18/18 (100.0%) | +50.0%p |
| Simulator-verified recovery | 14/18 (77.8%) | 17/18 (94.4%) | +16.7%p |
| Agent calls | 27 | 20 | -7 |
| 평균 iterations | 1.50 | 1.11 | -0.39 |
| API/schema failures | 0 | 0 | 0 |

`Full diagnosis`는 고장 부품과 고장 유형을 모두 맞힌 경우다. `Simulator-verified
recovery`는 제안이 그럴듯한지를 LLM이 판단한 값이 아니라, 수정 netlist를 ngspice로
다시 실행한 뒤 frozen specification을 모두 통과한 경우만 센 값이다.

## Fault별 결과

| Fault | Strict localization | Strict diagnosis | Strict recovery | Combined localization | Combined diagnosis | Combined recovery |
|---|---:|---:|---:|---:|---:|---:|
| C3 open | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| input z0 100 ohm | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| L1 open | 3/3 | 3/3 | 1/3 | 3/3 | 3/3 | 3/3 |
| L2 short | 3/3 | 0/3 | 1/3 | 3/3 | 3/3 | 2/3 |
| L3 short | 3/3 | 0/3 | 3/3 | 3/3 | 3/3 | 3/3 |
| output z0 25 ohm | 3/3 | 0/3 | 3/3 | 3/3 | 3/3 | 3/3 |

## 실패 원인 분리

Strict 조건의 L1 open 미복구 2건은 부품, 고장 유형과 수정값의 물리적 의도는 맞았지만
`795.774715 nH`, `795.774715nH`, `7.95774715e-7 H` 같은 표기를 strict parser가
거절했다. L2 short에서도 부품은 맞혔으나 고장 유형을 open으로 잘못 분류했고, 일부
제안은 단위 표기 문제 또는 잘못된 크기 때문에 복구되지 않았다. 즉 strict 실패에는
인터페이스 표현 한계와 진단 오류가 함께 포함된다.

Combined 조건의 유일한 미복구는 `holdout_l2_short`, trajectory 2였다. 세 iteration
모두 부품 `L2`와 고장 유형 `short`는 정확했지만 `3.9788736 uH`를 제안했다. 실제 정상
값은 `3.978873577 nH`이므로 1000배 큰 값이다. 이 표현은 문법적으로 유효해 parser가
정상 수용했고 ngspice도 수렴했지만, specification은 세 번 모두 FAIL이었다.

따라서 combined의 1건은 구조화 응답 실패나 parser 문제가 아니라 실제 수치 추론
오류다. 이 사례는 진단 label이 정확하고 confidence가 높더라도 최종 판정은 독립적인
시뮬레이터와 validator가 맡아야 한다는 연구 설계를 뒷받침한다.

## 실행량과 비용

| 항목 | Strict holdout | Combined holdout | 합계 |
|---|---:|---:|---:|
| Agent calls | 27 | 20 | 47 |
| Recorded tokens | 50,673 | 39,627 | 90,300 |
| Simulator calls | 20 | 26 | 46 |
| 추정 API 비용 | USD 0.01635533 | USD 0.01134234 | USD 0.02769767 |

비용은 응답 usage와 2026-09-03 [GPT-5.6 Luna 공개 단가](https://developers.openai.com/api/docs/models/gpt-5.6-luna)로
계산했으며 실제 청구서가 아니다. 기존 development 네 조건과 이번 holdout 두 조건의
기록상 추정 비용 합계는 USD 0.07988014다.

## 무결성 점검

- strict의 27개, combined의 20개 response ID는 조건별로 모두 고유했다.
- 저장된 output text를 다시 SHA-256으로 계산해 기록된 hash와 모두 일치함을 확인했다.
- strict의 accepted simulation 14건은 독립 validator 재실행에서 14건 모두 PASS였다.
- combined의 accepted simulation 20건은 독립 validator 재실행에서 기록과 동일하게
  17건 PASS, 3건 FAIL이었다.
- 전체 unit tests 37개가 통과했다.
- protocol과 holdout manifest는 API 실행 전에 commit `c0e3cda`로 고정했다.

## 해석과 주장 범위

Combined interface는 같은 회로 안의 미관측 fault tuple에서 strict 대비 full diagnosis를
50.0%p, simulator-verified recovery를 16.7%p 높였고 호출 수도 7회 줄였다. 따라서
개발 사례에서 관찰된 interface 개선이 이 holdout 범위에서도 재현되었다고 해석할 수
있다.

다만 표본은 조건당 18 trajectory로 작고, 모두 같은 100 MHz 이상적 lumped filter에서
생성된 합성 fault다. 정확한 통계적 유의성이나 새로운 회로 topology로의 일반화, 실제
PCB/RFIC 및 측정 잡음 환경의 복구 성능은 주장하지 않는다. 논문의 안전한 결론은
“simulator-screened synthetic faults에 대해 interface 개선이 within-circuit holdout에서도
회복률을 높였으며, 최종 성공은 deterministic SPICE validator로 확인했다”이다.

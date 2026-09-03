# Blind structural interface ablation v2 results

실행 완료일: 2026-09-03  
상태: `COMPLETE_3_CONDITIONS_X_18_TRAJECTORIES`

## 실험 질문

Blind strict 결과에서 나타난 두 실패 원인을 분리해 확인했다.

1. Agent가 원인을 알아도 `nH`, `pF` 같은 표현 때문에 실행이 거절되는가?
2. Agent가 회로를 이해해도 `open/short`, `source/load` label의 뜻이 불명확해
   full diagnosis가 낮아지는가?

여기서 ablation은 한 번에 조건 하나만 바꿔 그 조건의 영향을 비교하는 실험이다.
모든 조건에서 reactive fault 이름은 `RFAULT1`로 유지해 원래 component를 숨겼다.

## 비교 조건

| 조건 | 변경점 | 단위 자동 변환 | Label 정의 |
|---|---|---:|---:|
| Blind strict v2 | 기준 조건 | OFF | OFF |
| Unit adapter v2.1 | deterministic unit canonicalizer만 추가 | ON | OFF |
| Label guidance v2.2 | fault-type 용어 정의만 추가 | OFF | ON |

Unit canonicalizer는 Agent가 제안한 수치의 의미를 바꾸지 않는다. 예를 들어
`3.978873577nH`를 ngspice가 읽을 수 있는 `3.978873577n`으로 바꾸는 코드 기반
변환기다. Label guidance는 현재 사례의 정답을 알려 주지 않고, 모든 사례에 동일하게
`open`, `short`, `source_impedance_mismatch`, `load_impedance_mismatch`의 의미를
정의한다.

## 전체 결과

| 조건 | 첫 Localization | 최종 Localization | 첫 Full diagnosis | 최종 Full diagnosis | 첫 Recovery | 최종 Recovery | Calls |
|---|---:|---:|---:|---:|---:|---:|---:|
| Blind strict v2 | 18/18 | 18/18 | 10/18 | 10/18 | 16/18 | 16/18 | 22 |
| Unit adapter v2.1 | 18/18 | 18/18 | 11/18 | 11/18 | 16/18 | 17/18 | 21 |
| Label guidance v2.2 | 17/18 | 18/18 | 17/18 | 18/18 | 14/18 | 16/18 | 26 |

세 조건 모두 API/schema failure는 0건이었다.

## 결과 해석

### 1. 단위 변환 효과

Unit adapter 조건에서는 기존에 `nH` 표현 때문에 실패했던 L2 open이 3/3 모두
복구됐다. 이는 deterministic adapter가 의도한 역할을 수행했다는 근거다.

하지만 전체 복구는 18/18이 아니라 17/18이었다. C2 short의 한 trajectory에서
Agent가 건강값보다 10배 작은 `63.66197724p`를 세 번 반복 제안했다. 세 수정안은
문법적으로 유효해 모두 simulation까지 진행됐지만 specification을 회복하지 못했다.
따라서 unit adapter는 표현 문제는 해결하지만 잘못된 수치 추론까지 고치지는 않는다.

Full diagnosis는 10/18에서 11/18로 한 건만 달라졌다. Unit adapter는 diagnosis
label에 관여하지 않으므로, 이 차이는 모델의 반복 실행 변동으로 보는 것이 안전하다.

### 2. Label 정의 효과

Label guidance 조건에서는 최종 full diagnosis가 18/18로 개선됐다. C1/C2의
1 milliohm fault는 short로, VPORT1/VPORT2 mismatch는 각각 source/load로 정확히
구분했다. 첫 iteration에서 틀린 한 사례도 feedback 이후 올바른 component와 label로
수정됐다.

이 결과는 기존 10/18이 순수한 회로 추론 한계만은 아니며, 구조화 출력 필드의 의미를
충분히 정의하지 않은 interface 설계가 큰 영향을 주었음을 보여 준다.

Recovery는 strict와 같은 16/18이었다. 실패한 C1 short와 C2 short는 component,
fault type, repair value의 물리적 의미를 정확히 제안했지만 각각 `pF` 또는 공백과
단위가 포함된 값 때문에 strict parser에서 거절됐다. 즉 이 조건은 diagnosis 문제는
해결했지만 syntax 문제는 의도적으로 그대로 남겼다.

### 3. Closed-loop feedback 효과

Label guidance 조건에서 2개 trajectory가 첫 시도 실패 후 최종 복구됐다. 반면 unit
adapter 조건에서는 1개만 feedback 이후 회복했고, C2 short의 잘못된 값은 세 번
반복됐다. 현재 feedback은 simulation constraint 위반은 전달하지만 동일 제안을
강제로 차단하지 않는다. 따라서 feedback이 항상 새롭고 올바른 후보를 만든다고
주장할 수는 없다.

## Fault별 최종 결과

### Unit adapter v2.1

| Fault | Localization | Full diagnosis | Recovery |
|---|---:|---:|---:|
| C1 open | 3/3 | 3/3 | 3/3 |
| C1 short | 3/3 | 0/3 | 3/3 |
| L2 open | 3/3 | 3/3 | 3/3 |
| C2 short | 3/3 | 1/3 | 2/3 |
| input z0 25 ohm | 3/3 | 3/3 | 3/3 |
| output z0 100 ohm | 3/3 | 1/3 | 3/3 |

### Label guidance v2.2

| Fault | Localization | Full diagnosis | Recovery |
|---|---:|---:|---:|
| C1 open | 3/3 | 3/3 | 3/3 |
| C1 short | 3/3 | 3/3 | 2/3 |
| L2 open | 3/3 | 3/3 | 3/3 |
| C2 short | 3/3 | 3/3 | 2/3 |
| input z0 25 ohm | 3/3 | 3/3 | 3/3 |
| output z0 100 ohm | 3/3 | 3/3 | 3/3 |

## 비용과 실행 기록

| 조건 | Input tokens | Output tokens | 추정 비용 |
|---|---:|---:|---:|
| Blind strict v2 | 33,787 | 6,622 | USD 0.01431111 |
| Unit adapter v2.1 | 34,771 | 5,708 | USD 0.01138448 |
| Label guidance v2.2 | 41,796 | 8,750 | USD 0.01664134 |
| 합계 | 110,354 | 21,080 | USD 0.04233693 |

비용은 API 응답의 usage와 2026-09-03 GPT-5.6 Luna 공개 단가로 계산한 추정치다.
실제 청구서 금액과 미세한 차이가 있을 수 있다. 두 추가 ablation의 합계는
USD 0.02802582다.

## 독립 검증

- Unit adapter: 21/21 response hashes 일치, response IDs 모두 고유
- Label guidance: 26/26 response hashes 일치, response IDs 모두 고유
- Unit adapter의 accepted simulations 21개를 재검증해 PASS 17개, FAIL 4개 확인
- Label guidance의 accepted simulations 16개를 재검증해 16개 모두 PASS 확인
- 두 protocol 모두 사전 고정 commit `36929a56273227f0d4eedc6bf90eade9870a3388`에서 실행
- 공통 blind fault manifest SHA-256 일치
- unit tests 36개 통과

## 결론과 다음 실험

고장 위치 탐지는 blind 조건에서도 매우 안정적이었다. Full diagnosis의 주된 약점은
회로 자체보다 label semantics가 불명확했던 interface에 있었고, repair failure의 큰
부분은 물리적 의도보다 값 표현 형식에 있었다.

다만 두 개선을 동시에 적용한 조건은 아직 측정하지 않았다. 따라서 현재 결과만으로
“두 개선을 합치면 diagnosis와 recovery가 모두 18/18이 된다”고 주장해서는 안 된다.
필요하면 `label guidance + unit adapter` 결합 조건을 별도 frozen protocol로 평가한다.

## 주장 범위

이 결과는 ideal lumped 100 MHz filter의 합성 fault에 대한 simulator-level
interface ablation이다. 실제 PCB/RFIC의 결함 진단 또는 하드웨어 복구 성능을
입증하지 않는다.

# Structural normalized-interface v1.1 results

실행일: 2026-09-02  
상태: `POST_HOC_INTERFACE_REMEDIATION_NOT_FINAL_BENCHMARK`

## 변경점

strict-syntax v1.0에서 관측된 실행 인터페이스 실패를 확인한 뒤 다음 두 변경을 적용했다.

1. 제한된 engineering unit canonicalization
   - `nH → n`, `pF → p`, `50 ohm → 50`
   - 숫자와 단위의 의미는 바꾸지 않음
   - 부품 종류와 맞지 않는 단위 및 자유 형식 표현은 거부
2. prompt에 VPORT1은 source/input, VPORT2는 load/output이라고 명시

두 변경을 동시에 적용했으므로 v1.0 대비 차이를 한 변경의 인과 효과로 분해할 수 없다.

## 결과

| 지표 | 첫 iteration | 최종 iteration |
|---|---:|---:|
| Component localization | 18/18 (100.0%) | 18/18 (100.0%) |
| Full diagnosis | 18/18 (100.0%) | 18/18 (100.0%) |
| Specification recovery | 16/18 (88.9%) | 18/18 (100.0%) |

- Feedback rescue: 2/18
- 총 Agent calls: 21
- 평균 iterations: 1.17
- accepted candidate simulations: 21
- initial faulty simulations: 6
- API/schema failure: 0
- 기록된 총 token: 41,328

## Feedback rescue

- `C2 short`: 첫 값 `6.366pF`가 실패한 뒤 `636.620pF`로 수정해 2회차 복구
- `L2 open`: 두 번의 과대 인덕턴스가 실패한 뒤 `3.9789nH`로 수정해 3회차 복구

canonicalizer는 위 숫자를 선택하지 않았다. LLM이 제안한 명시적 단위를 SPICE token으로만
변환했고, 값 선택과 재수정은 feedback을 받은 LLM이 수행했다.

## v1.0 대비

| 지표 | Strict v1.0 | Normalized v1.1 |
|---|---:|---:|
| Final localization | 18/18 | 18/18 |
| Final full diagnosis | 15/18 | 18/18 |
| Final spec recovery | 16/18 | 18/18 |
| Agent calls | 22 | 21 |
| Candidate simulations | 16 | 21 |

v1.1은 v1.0 실패를 관찰한 뒤 설계된 post-hoc remediation이다. 따라서 v1.1의 100%를
독립적인 최종 평가 성능으로 주장하지 않는다. 고정된 adapter를 새로운 fault case 또는
새 topology에 적용하는 평가가 필요하다.

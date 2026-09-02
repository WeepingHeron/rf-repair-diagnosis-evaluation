# Value-fault repeat pilot v0.1

실행일: 2026-09-02  
상태: `PIPELINE_PILOT_NOT_FINAL_BENCHMARK`

## 프로토콜

- 회로: ideal lumped 100 MHz third-order Butterworth band-pass filter
- 조건: faulty netlist + initial SPICE metrics를 받은 LLM Agent의 one-edit repair
- 모델: `gpt-5.6-luna`, reasoning effort `low`
- 사례: 단일 부품 값 fault 10개
- 반복: 사례당 3회, 총 30 planned attempts
- 출력 상한: 호출당 700 tokens
- 최종 판정: ngspice + deterministic 7-constraint validator

## 관측 결과

| 지표 | 전체 planned attempts 기준 | 구조화 응답 완료 기준 |
|---|---:|---:|
| API/structured response | 18/30 (60.0%) | — |
| Component localization | 15/30 (50.0%) | 15/18 (83.3%) |
| Full diagnosis | 15/30 (50.0%) | 15/18 (83.3%) |
| Simulation convergence after patch | 18/30 (60.0%) | 18/18 (100.0%) |
| Specification recovery | 16/30 (53.3%) | 16/18 (88.9%) |

- Component consistency across available structured responses: 90.0%
- Observed API usage: input 24,328, output 9,363, total 33,691 tokens
- API-stage unusable responses: 12/30
- Completed-but-not-recovered repairs: 2/18

v0.1 runner는 parseable proposal이 없을 때 상세 response status를 보존하지 않았으므로,
12건의 API-stage failure 원인을 이 결과만으로 확정할 수 없다. 700-token 상한에 따른
불완전 출력 가능성이 있으나 이는 현재 **가설**이다. 후속 runner는 response status와
incomplete reason을 안전한 메타데이터로 저장하도록 보강한다.
완료된 응답의 output token은 374~680 범위였고 상한에 가까운 사례가 여러 건 있어 이
가설과 양립하지만, 실패 응답의 상태가 없으므로 원인 증거로 확정하지 않는다.

## 사례별 관찰

| Fault | API 완료 | 정답 부품 | Spec 복구 | 제안 부품 순서 |
|---|---:|---:|---:|---|
| `C1 ×0.5` | 1/3 | 1/3 | 1/3 | API_FAIL, API_FAIL, C1 |
| `C1 ×0.7` | 3/3 | 3/3 | 3/3 | C1, C1, C1 |
| `C1 ×1.3` | 3/3 | 3/3 | 3/3 | C1, C1, C1 |
| `C1 ×2.0` | 1/3 | 1/3 | 1/3 | API_FAIL, C1, API_FAIL |
| `L1 ×0.5` | 2/3 | 2/3 | 2/3 | L1, API_FAIL, L1 |
| `L1 ×2.0` | 2/3 | 1/3 | 1/3 | L1, L3, API_FAIL |
| `L2 ×0.5` | 1/3 | 1/3 | 1/3 | L2, API_FAIL, API_FAIL |
| `L2 ×2.0` | 2/3 | 2/3 | 2/3 | API_FAIL, L2, L2 |
| `C2 ×0.5` | 2/3 | 0/3 | 1/3 | API_FAIL, C1, L2 |
| `C2 ×2.0` | 1/3 | 1/3 | 1/3 | C2, API_FAIL, API_FAIL |

`C2 ×0.5`의 한 실행은 ground-truth 부품 C2 대신 L2를 보상 조정했지만 모든 spec을
회복했다. 따라서 이 benchmark는 다음을 별도 지표로 유지해야 한다.

1. **Causal diagnosis/localization:** 삽입한 실제 fault를 찾았는가.
2. **Functional repair:** 원인 부품과 무관하게 deterministic spec을 회복했는가.

보상 수정은 기능적으로 유효할 수 있지만 원인 진단 성공으로 계산하지 않는다. 반대로
정답 부품을 찾더라도 spec을 회복하지 못하면 repair 성공으로 계산하지 않는다.

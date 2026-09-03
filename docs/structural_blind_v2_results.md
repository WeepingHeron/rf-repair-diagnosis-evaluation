# Structural blind v2 final results

실행 완료일: 2026-09-03  
상태: `COMPLETE_18_OF_18_TRAJECTORIES`

## 목적과 고정 조건

기존 structural 실험에서는 `RFAULTC1`, `RFAULTL2`처럼 fault resistor 이름이
원래 component를 직접 알려 주었다. 이번 실험은 네 reactive-component fault를 모두
중립 이름 `RFAULT1`로 바꿔, Agent가 netlist topology와 simulation metrics를 통해
고장 위치를 추론하도록 했다.

- fault 유형: synthetic open/short 4개, port impedance mismatch 2개
- fault당 3 trajectories, 총 18 trajectories
- trajectory당 최대 3 Agent iterations
- strict patch syntax: `nH`, `pF`, `ohm` 등의 단위 표기를 자동 변환하지 않음
- 성공 판정: ngspice 결과를 deterministic validator가 판정
- 고정 protocol commit: `8afd4186801010a2bdcc76c4eb3e186c26f173cc`
- 모델: `gpt-5.6-luna`, reasoning effort `low`

## 전체 결과

| 지표 | 첫 iteration | 최종 iteration |
|---|---:|---:|
| Component localization | 18/18 (100.0%) | 18/18 (100.0%) |
| Full diagnosis | 10/18 (55.6%) | 10/18 (55.6%) |
| Simulator-verified specification recovery | 16/18 (88.9%) | 16/18 (88.9%) |

- Agent calls: 22
- 평균 iterations: 1.22
- accepted candidate simulations: 16
- initial faulty simulations: 6
- API/schema failures: 0
- API responses with complete provenance: 22/22
- recorded tokens: input 33,787; output 6,622; total 40,409
- estimated API cost: USD 0.01431111

## Fault별 반복 결과

| Fault | Localization | Full diagnosis | Recovery | Agent calls | 관찰 |
|---|---:|---:|---:|---:|---|
| C1 open | 3/3 | 3/3 | 3/3 | 3 | 세 번 모두 첫 시도 성공 |
| C1 short | 3/3 | 0/3 | 3/3 | 3 | 모두 component와 repair는 맞았지만 open으로 분류 |
| L2 open | 3/3 | 3/3 | 1/3 | 7 | 두 trajectory가 `nH` 표기로 strict parser에서 거절 |
| C2 short | 3/3 | 0/3 | 3/3 | 3 | 모두 evidence에서는 short를 설명했지만 open으로 분류 |
| input z0 25 ohm | 3/3 | 3/3 | 3/3 | 3 | 세 번 모두 VPORT1을 50으로 복구 |
| output z0 100 ohm | 3/3 | 1/3 | 3/3 | 3 | VPORT2와 복구값은 맞았으나 두 번 source mismatch로 분류 |

## 일관성 해석

Component localization은 모든 fault에서 3/3으로 같아 100% 일관적이었다. 즉
`RFAULT1`로 이름을 가려도 이 회로에서는 topology만으로 C1, L2, C2를 일관되게
찾았다.

반면 full diagnosis는 fault별로 편향이 나타났다. C1/C2 short는 여섯 번 모두
구조화된 `fault_type`을 open으로 선택했다. 일부 evidence 문장은 1 milliohm이
short임을 명시했으므로, 회로 현상 이해와 최종 label 선택이 서로 어긋난 사례다.
VPORT2도 위치와 repair는 세 번 모두 맞았지만 load/source label은 1/3만 맞았다.

Recovery가 16/18인 이유는 L2 open의 strict interface 때문이다. 세 trajectory 모두
L2와 open을 정확히 진단하고 약 3.978873577 nH를 제안했다. 이 중 한 번은 허용되는
SPICE token `3.978873577n`을 내어 PASS했고, 두 번은 `nH`가 붙은 값을 반복해 patch
적용 전에 거절됐다. 따라서 다음을 분리해 해석해야 한다.

- causal diagnosis: 3/3 성공
- repair intent: 3/3 적절함
- strict executable interface: 1/3 성공
- simulator-verified recovery: 1/3 성공

실패 feedback 이후 회복한 trajectory는 0개였다. 현재 feedback에는 일반적인
`PATCH_POLICY_REJECTED` 코드만 들어가므로, Agent가 “단위 기호 H를 제거해야 한다”는
구체적인 원인을 알 수 없었다. 이 부분은 frozen strict 주 결과를 바꾸지 않고,
별도의 interface-improvement 조건에서 평가해야 한다.

## 기존 이름 노출 조건과 비교

| 조건 | Localization | Full diagnosis | Recovery | Calls |
|---|---:|---:|---:|---:|
| 이름 노출 structural v1.0 | 18/18 (100.0%) | 15/18 (83.3%) | 16/18 (88.9%) | 22 |
| 이름 비노출 blind v2 | 18/18 (100.0%) | 10/18 (55.6%) | 16/18 (88.9%) | 22 |

이 비교에서는 component 이름을 숨겨도 localization과 recovery는 떨어지지 않았다.
다만 full diagnosis는 5건 감소했다. blind prompt는 component 이름뿐 아니라 기존의
open/short 값 매핑 설명도 제거했으므로, 감소분 전체를 component-name leakage의
영향이라고 단정할 수는 없다. 정확한 원인 분리는 추가 ablation이 필요하다.

## 비용 계산

실제 사용량은 regular input 66, cached input 9,038, cache-write input 24,683,
output 6,622 tokens였다. 2026-09-03 GPT-5.6 Luna 공개 단가를 적용한 추정 비용은
USD 0.01431111이다. 이는 API 청구서 자체가 아니라 응답 usage와 공개 단가로 계산한
값이다.

## 독립 점검

- 22개 response ID가 모두 고유함을 확인했다.
- 22개 output text와 저장된 SHA-256 hash가 모두 일치했다.
- 16개 accepted repair의 S-parameter table을 다시 읽어 validator를 독립 실행했고
  16개 모두 PASS였다.
- 네 reactive fault netlist에는 `RFAULTC1`, `RFAULTL2`, `RFAULTC2`가 없고
  중립 이름 `RFAULT1`만 있었다.
- unit tests 34개가 통과했다.

## 주장 범위

이 결과는 ideal lumped 100 MHz filter의 합성 fault에 대한 SPICE 수준 결과다.
실제 PCB, RFIC, 측정 잡음, 기생 성분 또는 하드웨어 복구 능력을 입증하지 않는다.

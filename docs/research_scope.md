# 연구 범위 결정 기록

## 작업 제목

**SPICE-Grounded LLM Agent for Fault Diagnosis and Repair of Lumped RF Circuits**

국문 가제: **SPICE 피드백 기반 LLM 에이전트의 집중소자 RF 회로 고장 진단 및 복구**

## 문제 정의

정상 회로 `C*`에 알려진 fault `f`를 삽입해 고장 회로 `Cf = f(C*)`를 만든다.
Agent는 정상 회로나 fault 정답을 보지 않고 다음 정보만 관찰한다.

- 고장 회로 netlist
- 목표 specification
- 최초 및 반복 단계별 simulation 결과

Agent는 고장 유형, 의심 부품과 구조화된 repair patch를 제안한다. 독립 평가기는
patch를 검증하고 ngspice를 실행한 뒤 모든 필수 specification을 만족했을 때만
repair 성공으로 판정한다.

## ACK MVP 범위

### 포함

- 수동 2-port band-pass filter를 주 실험 회로로 사용
- 시간이 허용되면 matching network를 미관측 topology 평가에 사용
- single-fault injection
- 구조화된 component patch
- 최대 2개 부품 수정
- 최대 3회의 Agent 반복
- simulator call, token, invalid edit를 포함한 실패 비용 기록

### 초기 fault 유형

1. capacitor/inductor 값 증가
2. capacitor/inductor 값 감소
3. open fault
4. short 또는 unintended shunt
5. source/load impedance mismatch

실제 MVP case 구성에서는 validator가 명확한 위반을 생성하고 안정적으로 복구할 수
있는 유형만 선택한다.

### 제외

- LNA와 transistor/PDK 기반 실험
- 복합 fault
- 실제 하드웨어 및 계측
- PCB layout, 기생성분, fabrication sign-off
- Agent가 전체 netlist를 임의로 재작성하는 방식

## 성공 판정

Strict repair success는 다음을 모두 만족해야 한다.

1. repair patch가 schema와 허용 정책을 통과한다.
2. 수정 netlist가 문법적으로 유효하다.
3. ngspice simulation이 timeout 없이 정상 종료한다.
4. 모든 필수 specification을 만족한다.
5. 수정 개수와 반복 예산을 초과하지 않는다.

정상 부품값과 정확히 동일하게 돌아오는 것은 필수 조건이 아니다. 복수의 성능 동등
해가 가능하므로 진단은 ground truth로, repair는 specification 회복으로 평가한다.

## 현재 비교군 우선순위

1. LLM single-shot
2. LLM Agent + SPICE feedback
3. deterministic sensitivity/grid-search baseline
4. 여유가 있을 때 LLM Agent + RF RAG + SPICE

RAG가 본 실험의 완결성을 방해하면 제외하고 SPICE feedback 효과에 집중한다.

## 범위 변경 조건

- `.SP` 자동화가 불안정하면 native ngspice CLI를 유지하고 AC frequency-response
  지표로 축소한다.
- 파일럿이 2026-09-06까지 안정화되지 않으면 RAG를 제외한다.
- 40개 사례의 품질을 확보하지 못하면 검증된 24~30개 사례로 축소한다.
- LNA는 ACK 제출 이후 확장 연구로만 검토한다.


# 연구질문 및 평가 계약

## Research Questions

### RQ1a

최초 faulty SPICE metrics를 one-shot LLM 입력에 추가하면 netlist-only 조건보다
fault localization과 strict repair success rate가 향상되는가?

### RQ1b

실패한 repair의 simulator/validator feedback을 다음 iteration에 제공하는 closed-loop
Agent는 동일한 최대 호출 예산의 single-shot LLM보다 최종 strict repair success rate를
향상하는가?

### RQ2

동일한 simulation-feedback 조건에서 RF 지식 RAG는 fault localization 정확도와
repair 효율을 향상하는가?

RQ2는 일정상 선택적 연구질문이며, RAG 조건이 제외되면 후속 연구로 이동한다.

### RQ3

fault 유형, severity 및 미관측 회로 topology에 따라 진단과 복구 성능은 어떻게
달라지는가?

## 실험 가설

- H1a: 최초 SPICE metrics 조건은 netlist-only 조건보다 strict repair success가 높을 것이다.
- H1b: 반복적인 closed-loop SPICE feedback은 single-shot 조건보다 최종 strict repair
  success가 높을 것이다.
- H2: RF RAG는 localization 정확도를 높이고 필요한 simulation 반복을 줄일 것이다.
- H3: 연결 구조를 변경하는 fault는 단순 부품값 오류보다 어려울 것이다.

가설은 실험 결과가 아니며 현재 성능 주장으로 사용하지 않는다.

2026-09-02의 10-case preliminary comparison에서는 H1a가 지지되지 않았다. 이는 H1b의
closed-loop 효과와 별개이며 최종 평가 전 관찰로만 기록한다.

## 핵심 지표

### 진단

- fault-type accuracy
- component localization Top-1 accuracy
- 필요할 경우 localization Top-3 accuracy
- joint diagnosis accuracy

### 복구

- strict repair success rate
- specification별 recovery rate
- normalized constraint violation 감소율
- simulation convergence rate
- invalid/prohibited edit rate

### 효율과 일관성

- Agent iteration 수
- 전체 simulator call 수
- input/output token 수와 API 비용
- wall-clock time
- 반복 실행별 성공률 분산
- 반복 실행 간 선택 부품 일치율

## 공정 비교 원칙

- 동일한 base model, specification, fault case와 실행 예산을 사용한다.
- simulation 실패와 invalid edit도 비용에 포함한다.
- Agent에게 정상 netlist, 정상 부품값 목록, fault manifest를 제공하지 않는다.
- RAG corpus에는 benchmark 정답이나 동일 회로의 repair 사례를 포함하지 않는다.
- 파일럿 결과를 확인한 뒤 protocol을 동결하고 최종 평가 case와 분리한다.

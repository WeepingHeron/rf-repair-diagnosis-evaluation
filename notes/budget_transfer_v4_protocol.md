# 새로운 설계 파라미터에서 동일 예산 피드백 비교

기존 주 실험을 보존하고 별도 v4 실험을 수행한다. 프로토콜은 API 실행 전에
`experiments/budget_transfer_v4.json`에 입력·평가 코드의 SHA-256과 함께 고정한다.

## 사전 결정

- 동일 Butterworth topology의 새 설계 4개: 중심주파수 83/117/149/173 MHz,
  fractional bandwidth 10/12/14/16%.
- 각 설계에서 값 고장 3개, 총 12개. 고장 배율은 0.62, 1.65, 2.3.
- 각 사례 3회 반복, no-feedback와 feedback 두 조건: 총 72 trajectory.
- 두 조건 모두 같은 초기 netlist·spec·SPICE metrics, prompt, 모델, schema,
  단위 정책과 최대 3회 호출 예산을 사용한다. 총 호출 상한 216회.
- 모델은 기존 실험과 같은 `gpt-5.6-luna`, reasoning low, 출력 상한 2000 tokens,
  자동 API 재시도 0, 원격 response 저장 off.
- 사례와 반복 순서대로 실행하되 두 조건의 선후 순서는 번갈아 배정한다.
- 평가기는 매 후보를 검증하고 성공하면 종료한다. no-feedback의 다음 요청에는
  이전 후보, 성공/실패, iteration 번호를 포함하지 않는다. feedback에는 실패 제안과
  simulator/validator 결과를 전달한다. 첫 요청의 정보는 두 조건에서 동일하다.
- 임의 부품·노드 이름과 섞인 element 순서를 사용한다. 스키마 후보는 현재 고장
  netlist에 실제 존재하는 부품뿐이다. 원래 topology와 값 대칭성의 단서까지 제거한
  것은 아니므로 완전한 blind 또는 다른 회로 topology 평가로 주장하지 않는다.

## 성공 및 비용

각 설계는 중심 오차 2%, 중심 S21 ≥ -0.25 dB, S11 ≤ -20 dB, 대역 양끝
S21 ≥ -4 dB, 0.7f0/1.4f0의 S21 ≤ -15 dB를 요구한다. 새 대역폭들에 동일한
규칙을 적용하며 기존 v1~v3의 -3.5 dB 사양과는 별도다. 모든 측정점은
2001점 sweep에 포함되고 측정 주파수 오차 허용치는 1 Hz다.

모든 후보를 LLM 호출 전에 정상 PASS, 고장 FAIL, 정답 one-edit 복구 PASS로
검사한다. 결과를 보고 쉬운 사례만 선택하지 않으며, 사전 정의한 12개 중 하나라도
계약을 통과하지 못하면 전체 동결을 중단한다. 초기 metric은 이 단계에서 한 번
계산해 두 조건이 공유한다. 사전 검사 36회 simulation은 후보 simulation 비용과
분리해 기록한다.

success@1, success@3, 진단·위치, 실제 API 시도, 후보 simulation, 토큰, 실행시간,
fault별 결과를 보고한다. API/schema 실패도 계획 분모에서 제외하지 않는다.
진단과 실제 수정 대상이 달라도 성능 복구는 허용하며 보상 복구로 구분한다.
12개 고장은 4개 설계에 묶여 있으므로 72회를 독립적인 회로 표본으로 해석하지 않는다.

매 API 요청 전에 원문 입력 및 hash를 기록하고, 응답 원문·ID·usage를 즉시 저장한다.
완료된 iteration은 재사용한다. 응답 처리 도중 중단된 요청은 자동 재호출하지 않고
중단 상태를 알린다. transport 오류는 기록한 뒤 전체 실행을 멈춘다. 재개 시
입력·평가 코드·프로토콜 변경을 거부한다. 동일한 실패 제안을 자동 삭제하거나
교정하지 않는다. 이는 feedback 유무 외의 개입을 피하기 위한 결정이다.

API 공개 단가 확인: 2026-09-06 기준 백만 토큰당 input $0.20, cached input $0.02,
output $1.20. 비용 표시는 저장 usage 기반 추정이며 실제 청구서가 아니다.
[공식 모델 문서](https://developers.openai.com/api/docs/models/gpt-5.6-luna).

## 실행

```bash
# 사전 검사와 동결: 최초 한 번만 실행, 기존 프로토콜 덮어쓰기 금지
PYTHONPATH=src .venv/bin/python scripts/prepare_budget_transfer.py
# 실제 API 실행. 완료된 iteration을 보존하며 최대 호출 수로 중단 가능
PYTHONPATH=src .venv/bin/python scripts/run_budget_transfer.py --max-new-calls 216
# API 없이 진행 상황 집계
PYTHONPATH=src .venv/bin/python scripts/run_budget_transfer.py --summary-only
```

초기 결과가 기존 가설에 불리하더라도 prompt·사례·parser를 바꾸지 않고 기록한다.
v4 결과를 확인한 뒤 바꾼 방법은 새 개발 실험이며 별도의 미사용 확인군이 필요하다.

실행 후 기록: 2026-09-06에 고정 설정 그대로 72개 경로를 완료했다. API 호출은
97회이며 [최종 결과](budget_transfer_v4_results.md)에 독립 재집계와 재시뮬레이션을 기록했다.

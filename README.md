# SPICE-Grounded RF Circuit Fault Diagnosis and Repair

LLM Agent가 집중소자 RF 회로의 고장을 진단하고 제한된 수정안을 제안한 뒤,
ngspice와 결정적 검증기가 성능 복구 여부를 판정하는 연구 프로젝트입니다.

## 연구 범위

- 주 회로: 수동 2-port band-pass filter
- 선택적 일반화 회로: matching network
- 초기 fault 범위: 단일 부품 값 오류, open, short/shunt, source/load mismatch
- 최종 판정 권한: LLM이 아닌 ngspice 출력과 rule-based validator
- 주장 범위: SPICE로 정의된 집중소자 RF 회로의 simulator-verified repair
- 제외 범위: 실제 PCB/RFIC 동작, 하드웨어 측정, fabrication sign-off

상세한 범위와 연구질문은 [docs/research_scope.md](docs/research_scope.md)와
[docs/research_questions.md](docs/research_questions.md)에 기록합니다. 합성 fault의
정확한 의미와 한계는 [docs/fault_model.md](docs/fault_model.md)를 따릅니다.

## 현재 상태

`2026-09-02`: 정상 baseline, 16개 fault 후보, 16개 one-edit oracle repair를
결정적으로 검증했습니다. 실제 LLM 호출 1건도 전체 closed loop를 통과했지만,
이는 파이프라인 smoke pilot이며 아직 benchmark 결과나 과학적 성능을 주장하지
않습니다. 상세 기록은 [docs/live_pilot_log.md](docs/live_pilot_log.md)에 있습니다.

## 환경 확인

필수 도구:

- Python 3.12 이상
- ngspice 47
- OpenAI Python SDK 3.7.0 (LLM pilot만 필요)

저장소 전용 환경 설치:

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
```

Smoke test:

```bash
python3 scripts/run_smoke.py
```

성공하면 `build/smoke/` 아래에 ngspice 로그와 raw 결과가 생성됩니다.

100 MHz band-pass baseline과 결정적 specification 검사:

```bash
python3 scripts/run_bpf_baseline.py
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

baseline은 이상적인 집중소자 시뮬레이션이며 실제 RF 부품 또는 하드웨어 측정값이
아닙니다. 현재 specification은 fault pilot 이전의 draft 상태입니다.

실제 LLM pilot은 저장소 루트의 `.env.local`에 `OPENAI_API_KEY`가 있을 때만
명시적으로 실행합니다. 정상 netlist와 fault manifest는 Agent 입력에서 제외되며,
응답은 한 번의 부품 값 수정으로 제한됩니다.

```bash
PYTHONPATH=src .venv/bin/python scripts/run_llm_fault_pilot.py
```

현재 pilot 모델은 `gpt-5.6-luna`, reasoning effort는 `low`, 출력 상한은 700 token,
API 저장은 비활성화합니다. 단일 호출 결과는 benchmark 성능으로 주장하지 않습니다.

동결된 10개 value fault를 각각 3회 실행하는 반복 파일럿:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_value_fault_repeat.py
```

프로토콜은 `experiments/value_fault_repeat_v0_1.json`에 고정되어 있습니다. 실행 결과는
`build/experiments/value_fault_repeat_v0_1/`에 저장되며, 중단 후 같은 명령을 실행하면
완료된 호출은 재사용하고 누락된 호출만 이어서 수행합니다.

2026-09-02에 수행한 30회 파이프라인 파일럿의 결과와 해석 한계는
[docs/value_fault_repeat_v0_1_results.md](docs/value_fault_repeat_v0_1_results.md)에
기록합니다. API 운영 실패가 포함되어 있으므로 이를 최종 모델 성능으로 사용하지 않습니다.

## 재현성과 신뢰성 원칙

1. Agent는 구조화된 repair patch만 제안합니다.
2. 정상 netlist와 fault manifest는 평가기에만 보관합니다.
3. 문법, 허용된 수정, simulation convergence, specification 만족 여부를 각각 검사합니다.
4. 실패한 simulator call도 실험 비용에 포함합니다.
5. 파일럿 이후 prompt, specification, validator를 동결하고 최종 평가와 분리합니다.

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
[docs/research_questions.md](docs/research_questions.md)에 기록합니다.

## 현재 상태

`2026-09-02`: 연구 범위와 초기 연구질문을 동결하고 ngspice 실행 환경을
검증하는 단계입니다. 아직 benchmark 결과나 과학적 성능을 주장하지 않습니다.

## 환경 확인

필수 도구:

- Python 3.12 이상
- ngspice 47

Smoke test:

```bash
python3 scripts/run_smoke.py
```

성공하면 `build/smoke/` 아래에 ngspice 로그와 raw 결과가 생성됩니다.

## 재현성과 신뢰성 원칙

1. Agent는 구조화된 repair patch만 제안합니다.
2. 정상 netlist와 fault manifest는 평가기에만 보관합니다.
3. 문법, 허용된 수정, simulation convergence, specification 만족 여부를 각각 검사합니다.
4. 실패한 simulator call도 실험 비용에 포함합니다.
5. 파일럿 이후 prompt, specification, validator를 동결하고 최종 평가와 분리합니다.


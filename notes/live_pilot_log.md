# Live LLM pilot log

## 2026-09-02 — `bpf_c1_x2`

상태: `SINGLE_LIVE_PILOT_NOT_BENCHMARK`

이 실행은 전체 benchmark 이전에 API, 구조화 출력, 제한된 netlist patch,
ngspice 재시뮬레이션, 결정적 validator가 하나의 파이프라인으로 연결되는지만
확인한 smoke-level 실험이다.

- Agent-visible evidence: faulty netlist, target specification, faulty simulation metrics
- Evaluator-only evidence: healthy netlist, injected-fault manifest, ground truth
- Model: `gpt-5.6-luna`
- Reasoning effort: `low`
- Output limit: 700 tokens
- API response storage: disabled
- Observed usage: input 1,349 tokens, output 370 tokens, total 1,719 tokens
- Ground-truth diagnosis match: yes (`C1`, `value_too_high`)
- Proposed repair: `C1 = 3.183098862p`
- Repaired simulation convergence: yes
- Deterministic validation: `PASS` (7/7 constraints)

이 결과는 한 사례의 단일 실행이므로 diagnosis accuracy, repair success rate,
반복 일관성 또는 모델 간 우열을 추정하지 않는다. 해당 지표는 prompt와 실험 설정을
동결한 뒤 별도 benchmark split과 반복 실행으로 계산한다. 실행별 원시 evidence는
Git에서 제외된 `build/llm_fault_pilot/`에 생성되며 동일 스크립트로 재생성할 수 있다.

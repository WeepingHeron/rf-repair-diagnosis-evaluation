# 집중소자 RF 회로에서 LLM 기반 복구와 원인 진단의 분리 평가

**KIPS_C2026B0047 · ACK 2026**
Separate Evaluation of LLM-Based Repair and Fault Diagnosis in Lumped RF Circuits

## 연구 개요

LLM이 제안한 수정으로 RF 성능이 복구되었는지와 주입한 고장 원인을 정확히 진단했는지를 같은 실행에서 따로 평가하는 연구다. 복구 여부는 ngspice와 결정적 검증기가, 진단 정답 여부는 평가기가 보관한 주입 고장 정보와의 대조로 판정한다.

## 연구 목적

성능 복구 성공률만으로 원인 진단의 정확성을 판단할 수 있는지 확인한다. 복구 성공·실패와 진단 정답·오답을 교차 집계하고, 동일 예산 비교·결정적 기준선·진단 보류 정책을 통해 LLM의 기여와 한계를 구분한다.

## 접근법

- 주 회로는 수동 2-port band-pass filter이며 L형 matching network는 보조 탐색이다.
- 합성 단일 부품 값 오류, open, short/shunt, source/load mismatch를 주입한다.
- Agent는 제한된 repair patch를 제안하고 ngspice 출력과 rule-based validator가 판정한다.
- 정상 netlist와 주입 고장 정답은 주 실험의 Agent 입력에서 제외한다. 후속 실험의 공개 정보는 각 프로토콜을 따른다.
- 실제 PCB/RFIC 동작, 하드웨어 측정, fabrication sign-off는 평가 범위에 포함하지 않는다.

[연구 범위](notes/research_scope.md), [연구질문](notes/research_questions.md), [고장 모델](notes/fault_model.md)에 정의와 가정을 기록했다.

## 검증된 결과와 한계

주 실험 48회에서 복구 46회, 전체 진단 정답 37회였고 **복구에 성공했지만 진단은 틀린 실행은 11회**였다.

| 같은 실행의 결과 | 진단 정답 | 진단 오답 | 합계 |
|---|---:|---:|---:|
| 복구 성공 | 35 | 11 | 46 |
| 복구 실패 | 2 | 0 | 2 |
| 합계 | 37 | 11 | 48 |

같은 회로의 고장별 반복 결과이며 서로 독립인 48개 회로의 성능을 뜻하지 않는다. 복구만 성공한 11회는 위치 오진 3회와 위치는 맞지만 유형이 틀린 8회로 나뉜다. [최종 내용 점검](notes/final_submission_review_2026-09-14.md)은 당시 원고와 수치의 대조 근거다.

아래 결과는 서로 다른 조건과 평가 집합에서 얻었으며 하나의 성공률로 합산하지 않습니다.
주 실험의 전체 진단 정답과 보조 탐색의 위치·방향 정답도 구분합니다.

### 주 실험과 검증

기존 주 실험은 복구 46/48, 위치 진단 45/48, 전체 진단 37/48입니다.
같은 회로의 holdout에서는 strict 14/18, 결합 인터페이스 17/18 복구를 기록했습니다.
2026-09-06 점검에서는 주요 7개 실험의 138개 trajectory와 총 185회 재시뮬레이션으로
기존 판정을 확인했습니다. 단위·허용값·측정 주파수 검증을 보강했고 표 생성기는
해당 Blind 실험을 사용합니다. [프로젝트 점검](notes/project_review_2026-09-06.md)과
[2026-09-14 내용 점검](notes/final_submission_review_2026-09-14.md)에 검증 범위를 기록했습니다.
후자는 문구 수정 전 PDF를 대상으로 한 기록이며, 최신 파일 검증은 위 링크를 따릅니다.

### 동일 예산 비교와 회로 확장

새 설계 파라미터의 동일 예산 비교는 [notes/budget_transfer_v4_protocol.md](notes/budget_transfer_v4_protocol.md)를
따릅니다. 기존 주 결과와 별도로 집계하며 다른 topology 일반화를 뜻하지 않습니다.
새 사례의 동일 최대 호출 예산 비교 72개 경로를 완료했습니다. 무피드백은 33/36,
피드백은 31/36 복구했으며, 첫 시도는 모두 28/36입니다. 이번 조건에서 피드백의
복구율 향상은 확인하지 못했습니다. 실제 API 호출 97회와 후보 재시뮬레이션 96회를
검증했으며, 상세 결과는 [notes/budget_transfer_v4_results.md](notes/budget_transfer_v4_results.md)에 있습니다.

후속 공진 계산 보조 비교는 일반 피드백 12/16, 계산 보조 15/16 복구였으며 실제 API
호출은 각각 25회입니다. 같은 계산의 결정적 기준선은 API 없이 11회 시뮬레이션으로
8/8을 복구했습니다. 별도의 L형 정합회로 one-shot 파일럿은 5/8 복구입니다.
두 확장의 근거와 한계는 [notes/priority_extensions_results.md](notes/priority_extensions_results.md)에
정리했으며, 최신 원고에는 v4와 탐색적 후속 결과를 구분해서 반영했습니다.

### 비이상적 소자와 손실 모델

비이상적 소자 조건 확인도 완료했습니다. 새 설계 4개의 Q·기생·공차 320조건 중
기존 기준을 만족한 정상 상태는 8개였고, 유한 Q에서는 정상 PASS가 없었습니다.
적격 고장 16개에서 결정적 공진 기준선은 10개를 복구했습니다(공차 0% 8/8,
공차 포함 2/8). API 없이 원시 시뮬레이션 1,628개와 별도 ABCD 계산을 검증했습니다.
[조건 확인 결과](notes/nonideal_screen_v1_results.md)에 탈락 조건과 모델 한계를 모두 기록했습니다.
이 단계는 원고의 LLM 복구율에 합산하지 않으며, 다음 비교 전에 손실을 반영한 정상
설계와 성능 기준을 먼저 고정해야 합니다.

그 후 별도의 손실 모델·탐색적 사양으로 기생 성분을 보상한 정상 설계 4개를 만들고,
모두 사전 검증을 통과했습니다. 새 고장 8개에서 이상적 공진 계산 5/8, 손실 모델
수치 탐색 8/8, 같은 후보를 받은 LLM은 각 2회 반복에서 16/16 복구했습니다.
LLM은 16번 모두 수치 탐색의 최상위 후보를 그대로 골랐고 위치·방향 진단은 8/16이었습니다.
추가 복구 이점은 확인되지 않았으며 성능 복구와 고장 원인 진단을 분리해야 합니다.
[손실 보상 설계 비교 결과](notes/lossy_repair_v1_results.md)에 예산과 독립 검증을 기록했습니다.

### 진단 전용 비교와 고장 전 측정

후속 진단 전용 비교는 새 8고장에서 후보 미공개/공개를 각각 16회 평가했습니다.
두 조건 모두 위치·방향 정답은 0/16이었고, 미공개는 판단 보류 15회·오진 1회,
공개는 판단 보류 16회였습니다. 같은 지시문과 판단 보류 선택지에서 후보 공개 여부만
바꾼 결과이며, 이전 진단+수정 출력 실험과 직접 비교하지 않습니다.
공통 결정적 수정은 별도로 8/8 복구했습니다. [진단 비교 결과](notes/diagnosis_visibility_v1_results.md)에
판단 보류·오진과 검증 기록을 분리해 정리했습니다.

고장 전 기준 측정 비교도 완료했습니다. 원래 8사례 계획은 257 MHz 정상 설계의
정합 기준 미달로 API 호출 전에 중단했고, 통과한 3설계·6고장만 별도 탐색으로
고정했습니다. 각 조건 12회에서 위치·방향 정답은 기준 측정 없음 3/12, 기준 측정만
제공 3/12, 기준 측정과 수치 역추정 제공 12/12였습니다. 기준만 제공하면 위치 오진이
1회에서 6회로 늘었고 출력 한도 초과 2회도 실패로 포함했습니다.
LLM 없는 역추정도 6/6을 진단·복구했으므로 LLM의 독자적 기여로 해석하지 않습니다.
원본 API 36응답과 native SPICE 30기록을 검증했으며,
[기준 측정 비교 결과](notes/reference_diagnosis_v2_results.md)에 제외 사유와 비용을 기록했습니다.
이는 잡음·환경 변화가 없는 합성 실험이며, 측정·모델 오차에 대한 진단 및 보류 경계는
아래 후속 실험에서 별도로 확인했습니다.

### 오차 민감도와 진단 보류 기준

이어진 [오차 민감도 확인](notes/reference_robustness_v1_results.md)은 API 없이 945건을
완료했습니다. 같은 6고장을 반복한 630건 중 정답 190·보류 440·오진 0이었고,
무고장 대조군 315건의 단일 부품 오경보는 0이었습니다. 잡음 σ=0.01 dB는 60/60,
0.02 dB는 33/60 진단했지만 0.05 dB부터 모두 보류했습니다. L/C 동시 변화 ±0.1%,
손실 또는 기생 모델 불일치 ±10%부터도 모두 보류했습니다. 최상위 가설 순위는
630/630 정답이었으나 440건이 기존 잔차 문턱을 넘었습니다. 이 관찰은 실제 운용
허용치를 뜻하지 않습니다. 이후 별도 개발 집합에서 작은 고장·비균일 오차를 확인하고,
보류 기준의 보정과 미사용 설계 평가를 분리해 수행했습니다.

별도 개발 집합의 [작은 값 변화·비균일 오차 확인](notes/diagnosis_development_v1_results.md)도
완료했습니다. 새 4설계에서 ±1/3/10% 변화를 주입한 2,304건은 정답 509·보류 1,795·
오진 0이었고, 무주입 대조군 64건의 오경보는 0이었습니다. 최상위 후보가 틀린 385건은
모두 기존 기준에서 보류됐습니다. 무오차 ±1% 변화는 후보 순위 48/48 정답이지만
차선 문턱 때문에 확정 진단은 14/48이었습니다. 최선 잔차 허용치만 늘리면 오진과
오경보를 통과시키는 반례도 확인했습니다. 기준 상태부터 규격 FAIL인 설계 1개도
사전 계획대로 포함한 값 변화 진단 개발 실험이며, 기존 보류 기준은 변경하지 않았습니다.
보고서에 보류 기준의 의미와 개발·보정·최종 평가를 분리하는 절차를 정리했습니다.

다중 보류 기준은 별도 보정 4설계에서 선택한 뒤 미사용 4설계에서 검증해
새 진단 명령의 기본 정책으로 연결했습니다. 최선 잔차≤0.02 dB, 후보 간격≥0.03 dB,
차선/max(최선,0.01)≥3, 무고장 대조 점수≥8.054607, 측정 재검사 4/4 일치를 요구합니다.
미사용 주입 변화 2,304건에서 기존 487건을 유지하고 128건을 추가해 615건을 진단했으며,
오진 0·무주입 대조군 오경보 0/64였습니다. 이번 개선은 후보 구분 기준 변경에서 관찰됐고
무고장 대조·안정성 조건의 추가 이점은 확인하지 못했습니다. 추가 계산을 사용하는 합성
진단 평가이며 실제 장비의 오류 보증은 아닙니다.
[기준·보정·평가 및 사용법](notes/abstention_calibration_v1_results.md)에 범위를 기록했습니다.

```bash
.venv/bin/python code/scripts/diagnose_reference.py --input input.json --output diagnosis.json
```

입력은 현재 회로 `source`, 공개 모델 `public`, 고장 전 측정 `reference`를 가진 JSON입니다.
기본 설정은 `code/configs/diagnosis_abstention.json`이며, 기존 동결 실험의 기준은 보존합니다.

확정 615건에 대해 같은 ±0.01 dB 측정 변화의 재검사를 4회에서 16회로 늘려,
추가 7,380회의 역추정을 수행했습니다. 모두 16/16회 같은 부품·방향을 유지해
새 불안정 사례는 없었습니다. [추가 재검사 결과](notes/stability_extension_v1_results.md)에
반복 비용과 조건부 해석을 기록합니다. 확정 입력만 대상으로 한 사후 확인이며,
기본 재검사 4회는 유지합니다.

## 폴더 구조

| 경로 | 내용 |
|---|---|
| `notes/` | 연구 계획·프로토콜·결과 해석·검토 기록 |
| `references/specs/` | 회로 성능 기준 사양 |
| `code/` | 구현·실행 스크립트·테스트·실험 설정·진단 정책 |
| `data/circuits/`, `data/faults/` | 회로와 주입 고장 정의 |
| `results/` | 원시 API 응답·SPICE 로그·분석·렌더링 등 로컬 산출물 |
| `paper/` | 원고 편집 자료·그림·표 |
| `submissions/2026_ACK/` | 최종 제출 PDF·검증용 SHA-256 |
| `submissions/archive/` | 이전 날짜별 원고·제출 이력 |

루트의 `src`, `scripts`, `tests`, `docs`, `build`, `submission` 등은 기존 실행 경로를 위한 호환 링크다. `code/`의 입력·결과 링크는 기존 스크립트의 부모 경로 계산을 유지한다. 루트 `pyproject.toml`은 `code/src`에서 패키지를 찾는다.

## 환경과 재현 방법

Python 3.12 이상, ngspice 47, OpenAI Python SDK 3.7.0 및 pydantic 2.13.5를 사용한다. Python 의존성은 [pyproject.toml](pyproject.toml)을 따른다. 다음은 설치 예시이며 이번 README 점검에서 네트워크 설치는 수행하지 않았다.

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
```

저장소 루트에서 실행하는 오프라인 단위 테스트와 CLI 확인:

```bash
PYTHONPATH=code/src .venv/bin/python -B -m unittest discover -s code/tests -v
.venv/bin/python -B code/scripts/diagnose_reference.py --help
```

ngspice 스모크와 100 MHz 결정적 baseline은 로컬 결과 파일을 생성한다. 기존 산출물을 보존한 뒤 실행한다.

```bash
mkdir -p results/build results/work
.venv/bin/python code/scripts/run_smoke.py
.venv/bin/python code/scripts/run_bpf_baseline.py
```

출력은 호환 `build/` 경로를 통해 `results/build/`에 저장된다. baseline은 이상적인 집중소자 시뮬레이션이며 실제 RF 측정값이 아니다. `references/specs/bpf_100mhz.json`의 초기 baseline용 draft 표기를 유지한다.

Git에 포함되지 않은 원시 API 응답·시뮬레이션 로그·렌더링은 새 clone에 없으므로 전체 결과의 해시 재검증에는 별도 보관 산출물이 필요하다. 각 실험의 선행 자료와 프로토콜을 확인한다. `.env.local`의 자격 증명 원문은 제외하며 실제 API 실행 시에는 `OPENAI_API_KEY` 환경변수를 별도로 설정한다. 실제 LLM 실행은 인증 설정과 비용이 필요하고 과거 응답의 재현을 보장하지 않는다.

## 논문 및 제출 상태

이 논문은 ACK 2026 발표 명단에 편성되었으며, 논문·발표 영상 제출 완료는 사용자 확인에 따른 상태다. 수상은 발표 편성·제출 완료와 별개이며 확인된 수상 정보는 기재하지 않는다.

최종 제출 PDF와 원본의 SHA-256이 같음을 확인했다. 제출 PDF 바이트는 변경하지 않았다. 영상과 발표 자료는 공개 저장소에 포함하지 않는 로컬 보관 자료다.

- [최종 제출 PDF](submissions/2026_ACK/KIPS_C2026B0047%28김태훈%29.pdf)
- [최종 PDF SHA-256](submissions/2026_ACK/SHA256SUMS)
- 이전 편집용 원고: [2026-09-14 DOCX](submissions/archive/ACK2026_2026-09-14_clarity/ACK2026_KimTaehoon_RF_Circuit_Repair.docx), [당시 수정 내역](submissions/archive/ACK2026_2026-09-14_clarity/README.md), [당시 파일 검증](submissions/archive/ACK2026_2026-09-14_clarity/verification.json). 이력 원고는 최종 제출 PDF를 대체하지 않는다. DOCX 분량은 편집기에 따라 달라질 수 있다.

## 연구 이력과 보존 원칙

### 보존과 공개 범위

Git에 기록된 연구 이력과 동결 실험 자료를 보존한다. 자격 증명 원문·가상환경·영상·미추적 발표 자료·개인 작업 기록·백업은 공개 저장소에 포함하지 않는다. 표준 원문 PDF는 별도로 확보해야 하며, Git에 포함되지 않은 로컬 산출물은 해당 매니페스트와 대조해 준비한다.

새 라이선스를 부여하지 않았다. 제3자 표준·양식·참고자료의 이용 조건은 각 출처를 확인한다. 폴더 구조를 변경할 때는 호환 경로와 동결 자료의 해시를 함께 검증한다.

### 재현성과 신뢰성 원칙

1. Agent는 구조화된 repair patch만 제안합니다.
2. 주 실험의 정상 netlist와 fault 정답은 평가기에만 보관합니다. 보조 탐색에서 제공한 기준 측정·공개 모델·수치 후보는 각 프로토콜에 명시합니다.
3. 문법, 허용된 수정, simulation convergence, specification 만족 여부를 각각 검사합니다.
4. 실패한 simulator call도 실험 비용에 포함합니다.
5. 파일럿 이후 prompt, specification, validator를 동결하고 최종 평가와 분리합니다.

<details>
<summary>초기 파일럿 실행과 이력 펼치기</summary>

아래 생성 명령은 과거 실험 실행 방법이다. API 비용이 발생할 수 있으므로 오프라인 검증과 구분한다.

아래는 초기 파이프라인 검증용 명령과 결과입니다. 최신 원고의 주 실험·보조 탐색과 구분합니다.

실제 LLM pilot은 저장소 루트의 `.env.local`에 `OPENAI_API_KEY`가 있을 때만
명시적으로 실행합니다. 정상 netlist와 fault manifest는 Agent 입력에서 제외되며,
응답은 한 번의 부품 값 수정으로 제한됩니다.

```bash
PYTHONPATH=code/src .venv/bin/python code/scripts/run_llm_fault_pilot.py
```

초기 pilot 스크립트의 기본 모델은 `gpt-5.6-luna`, reasoning effort는 `low`, 출력 상한은 700 token,
API 저장은 비활성화합니다. 단일 호출 결과는 benchmark 성능으로 주장하지 않습니다.

동결된 10개 value fault를 각각 3회 실행하는 반복 파일럿:

```bash
PYTHONPATH=code/src .venv/bin/python code/scripts/run_value_fault_repeat.py
```

프로토콜은 `code/experiments/value_fault_repeat_v0_1.json`에 고정되어 있습니다. 실행 결과는
`build/code/experiments/value_fault_repeat_v0_1/`에 저장되며, 중단 후 같은 명령을 실행하면
완료된 호출은 재사용하고 누락된 호출만 이어서 수행합니다.

2026-09-02에 수행한 30회 파이프라인 파일럿의 결과와 해석 한계는
[notes/value_fault_repeat_v0_1_results.md](notes/value_fault_repeat_v0_1_results.md)에
기록합니다. API 운영 실패가 포함되어 있으므로 이를 최종 모델 성능으로 사용하지 않습니다.

v0.2 diagnostic repeat는 1,200-token 출력 상한과 incomplete-response metadata를
사용하며 v0.1 결과를 덮어쓰지 않습니다.

```bash
PYTHONPATH=code/src .venv/bin/python code/scripts/run_value_fault_repeat.py \
  --protocol code/experiments/value_fault_repeat_v0_2.json
```

v0.2 결과는 [notes/value_fault_repeat_v0_2_results.md](notes/value_fault_repeat_v0_2_results.md)에
기록합니다. 30회 중 26회가 구조화 응답을 반환했고 24회가 제한된 patch 적용 후 모든
결정적 spec을 회복했습니다. 이 역시 diagnostic repeat이며 최종 benchmark가 아닙니다.

동일 설정에서 수행한 one-shot `LLM only` 대 `+ initial SPICE evidence` 비교는
[notes/preliminary_comparison_v1_0.md](notes/preliminary_comparison_v1_0.md)에 기록합니다.
이 10-case pilot에서는 raw SPICE metrics 추가가 성능을 높이지 않았습니다.
이후 실패한 repair 결과를 다시 제공하는 최대 3-iteration closed loop를 평가했습니다.

최대 3-iteration closed-loop pipeline pilot 결과는
[notes/closed_loop_value_pilot_v0_1_results.md](notes/closed_loop_value_pilot_v0_1_results.md)에
기록합니다. 10개 trajectory 중 첫 시도는 9개를 복구했고, 실패 evidence를 받은 두 번째
iteration이 나머지 1개를 복구했습니다. 이는 구현 검증이며 최종 성능 주장이 아닙니다.

fault당 3개 trajectory의 반복 closed-loop 결과와 deterministic ratio-grid baseline은
[notes/repeated_closed_loop_and_baseline_v1_0.md](notes/repeated_closed_loop_and_baseline_v1_0.md)에
정리합니다. closed loop는 first-attempt 26/30에서 최종 30/30으로 네 건을 추가 복구했고,
grid baseline도 10/10을 복구했지만 65회의 candidate simulation을 사용했습니다.

open/short/port mismatch용 제한 스키마와 strict-syntax 결과는
[notes/structural_closed_loop_v1_0_results.md](notes/structural_closed_loop_v1_0_results.md),
현재 논문용 통합 표는 [notes/paper_results_tables.md](notes/paper_results_tables.md)에
기록합니다.

strict syntax 실패 후 별도로 수행한 단위-normalized structural v1.1 결과는
[notes/structural_normalized_v1_1_results.md](notes/structural_normalized_v1_1_results.md)에
기록합니다. 이는 두 interface 변경을 함께 적용한 post-hoc 결과이므로 최종 benchmark와
구분합니다.

</details>

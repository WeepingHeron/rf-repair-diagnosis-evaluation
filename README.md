[English](README.md) | [한국어](README.ko.md)

# Separate Evaluation of LLM-Based Repair and Fault Diagnosis in Lumped RF Circuits

**KIPS_C2026B0047 · ACK 2026**
Separate Evaluation of LLM-Based Repair and Fault Diagnosis in Lumped RF Circuits

## Overview

This study separately evaluates, within the same run, whether an LLM-proposed modification restores RF performance and whether the injected fault's cause is correctly diagnosed. Repair is assessed by ngspice and a deterministic validator; diagnosis correctness is assessed against the injected-fault information held by the evaluator.

## Research objectives

The study asks whether performance-recovery success rates alone can establish the accuracy of causal diagnosis. It cross-tabulates repair success/failure with correct/incorrect diagnosis and distinguishes the LLM's contribution and limitations through equal-budget comparisons, deterministic baselines, and diagnostic abstention policies.

## Approach

- The main circuit is a passive 2-port band-pass filter; an L-type matching network is an auxiliary exploration.
- Synthetic single-component value errors, open faults, short/shunt faults, and source/load mismatches are injected.
- The agent proposes constrained repair patches, which are assessed using ngspice output and a rule-based validator.
- The healthy netlist and injected-fault ground truth are excluded from the agent's input in the main experiment. Information disclosed in follow-up experiments is defined by each protocol.
- Actual PCB/RFIC operation, hardware measurements, and fabrication sign-off are outside the evaluation scope.

Definitions and assumptions are recorded in the [research scope](notes/research_scope.md), [research questions](notes/research_questions.md), and [fault model](notes/fault_model.md).

## Verified results and limitations

Across 48 main-experiment runs, repair succeeded in 46 and full diagnosis was correct in 37. **In 11 runs, repair succeeded but diagnosis was incorrect.**

| Outcome within the same run | Correct diagnosis | Incorrect diagnosis | Total |
|---|---:|---:|---:|
| Successful repair | 35 | 11 | 46 |
| Failed repair | 2 | 0 | 2 |
| Total | 37 | 11 | 48 |

These are repeated fault-specific results on the same circuit, not performance on 48 independent circuits. The 11 repair-only successes comprise 3 incorrect-location diagnoses and 8 diagnoses with the correct location but incorrect fault type. The [final content review](notes/final_submission_review_2026-09-14.md) documents the comparison of the manuscript and figures at that time.

The results below were obtained under different conditions and evaluation sets and are not pooled into a single success rate. Full diagnosis correctness in the main experiment is also distinguished from location/direction correctness in auxiliary explorations.

### Main experiment and verification

The existing main experiment achieved repair in 46/48, correct location diagnosis in 45/48, and correct full diagnosis in 37/48. On the same circuit's holdout set, repair was 14/18 with the strict interface and 17/18 with the combined interface. The 2026-09-06 review confirmed existing judgments using 138 trajectories from 7 main experiments and a total of 185 resimulations. Checks of units, allowed values, and measurement frequencies were strengthened, and the table generator uses the corresponding Blind experiments. Verification scope is recorded in the [project review](notes/project_review_2026-09-06.md) and [2026-09-14 content review](notes/final_submission_review_2026-09-14.md). The latter concerns the PDF before wording revisions; refer to the linked records for the latest file verification.

### Equal-budget comparisons and circuit extensions

The equal-budget comparison with new design parameters follows [notes/budget_transfer_v4_protocol.md](notes/budget_transfer_v4_protocol.md). It is aggregated separately from the existing main results and does not establish generalization to other topologies. The comparison on new cases completed 72 trajectories with the same maximum call budget. Repair was 33/36 without feedback and 31/36 with feedback; both achieved 28/36 on the first attempt. Feedback did not show improved repair rates under these conditions. The 97 actual API calls and 96 candidate resimulations were verified; details are in [notes/budget_transfer_v4_results.md](notes/budget_transfer_v4_results.md).

A follow-up comparison of resonance-calculation assistance achieved repair in 12/16 with ordinary feedback and 15/16 with calculation assistance, using 25 actual API calls each. A deterministic baseline using the same calculation repaired 8/8 with 11 simulations and no API calls. A separate one-shot L-type matching-network pilot repaired 5/8. Evidence and limitations for both extensions are in [notes/priority_extensions_results.md](notes/priority_extensions_results.md); the latest manuscript distinguishes v4 from these exploratory follow-up results.

### Nonideal components and loss models

Screening of nonideal component conditions was also completed. Across 320 Q, parasitic, and tolerance conditions for 4 new designs, 8 healthy states met the existing criteria; none passed under finite Q. Of 16 eligible faults, the deterministic resonance baseline repaired 10 (8/8 at 0% tolerance and 2/8 with tolerance). The 1,628 raw simulations and separate ABCD calculations were verified without API calls. The [screening results](notes/nonideal_screen_v1_results.md) record excluded conditions and model limitations. This stage is not pooled with the manuscript's LLM repair rate; healthy designs accounting for loss and their performance criteria must be fixed before the next comparison.

Subsequently, 4 healthy designs compensating for parasitics were created under a separate loss model and exploratory specifications; all passed prevalidation. On 8 new faults, ideal resonance calculation repaired 5/8 and numerical search with a loss model repaired 8/8; an LLM given the same candidates repaired 16/16 across 2 repetitions each. In all 16 cases, the LLM selected the numerical search's top candidate unchanged, and location/direction diagnosis was correct in 8/16. No additional repair benefit was established, and performance recovery must be separated from fault-cause diagnosis. Budgets and independent verification are recorded in the [loss-compensated design comparison](notes/lossy_repair_v1_results.md).

### Diagnosis-only comparisons and pre-fault measurements

The follow-up diagnosis-only comparison evaluated 8 new faults in 16 runs each with candidates hidden or disclosed. Location/direction correctness was 0/16 in both conditions. With candidates hidden, there were 15 abstentions and 1 misdiagnosis; with candidates disclosed, there were 16 abstentions. Only candidate visibility changed, with the same instructions and abstention option; this is not directly compared with the earlier experiment that output diagnosis plus repair. The common deterministic modification separately repaired 8/8. The [diagnosis comparison](notes/diagnosis_visibility_v1_results.md) separates abstentions, misdiagnoses, and verification records.

The pre-fault reference-measurement comparison was also completed. The original 8-case plan was stopped before API calls because the healthy 257 MHz design failed the matching criterion. Only the passing 3 designs and 6 faults were frozen as a separate exploration. Across 12 runs per condition, location/direction correctness was 3/12 without reference measurements, 3/12 with reference measurements alone, and 12/12 with reference measurements plus numerical inverse estimation. Providing reference measurements alone increased location misdiagnoses from 1 to 6; 2 output-limit exceedances were also counted as failures. Inverse estimation without an LLM also diagnosed and repaired 6/6, so these results are not interpreted as an independent LLM contribution. The 36 original API responses and 30 native SPICE records were verified; exclusions and costs are recorded in the [reference-measurement comparison](notes/reference_diagnosis_v2_results.md). This was a synthetic experiment without noise or environmental changes. Diagnosis and abstention boundaries under measurement/model errors were examined separately in the follow-up experiments below.

### Error sensitivity and diagnostic abstention criteria

The subsequent [error-sensitivity study](notes/reference_robustness_v1_results.md) completed 945 cases without API calls. Among 630 repetitions of the same 6 faults, there were 190 correct diagnoses, 440 abstentions, and 0 misdiagnoses. There were 0 single-component false alarms in 315 no-fault controls. Diagnosis succeeded in 60/60 at noise σ=0.01 dB and 33/60 at 0.02 dB, but all cases were withheld from 0.05 dB onward. All cases were also withheld from simultaneous L/C changes of ±0.1% or loss/parasitic model mismatches of ±10% onward. The top-ranked hypothesis was correct in 630/630, but 440 cases exceeded the existing residual threshold. These observations do not establish real operating tolerances. Later work examined small faults and nonuniform errors on a separate development set, separating abstention-threshold calibration from evaluation on unused designs.

The [small-value-change and nonuniform-error study](notes/diagnosis_development_v1_results.md) on a separate development set was also completed. In 2,304 cases injecting ±1/3/10% changes into 4 new designs, there were 509 correct diagnoses, 1,795 abstentions, and 0 misdiagnoses; the 64 no-injection controls had 0 false alarms. All 385 cases with an incorrect top candidate were withheld under the existing criteria. For error-free ±1% changes, candidate ranking was correct in 48/48, but the runner-up threshold limited confirmed diagnoses to 14/48. Counterexamples also showed that increasing only the best-residual tolerance could admit misdiagnoses and false alarms. This value-change diagnosis development experiment included 1 design that already failed specifications at baseline, as planned; existing abstention criteria were unchanged. The report explains the criteria and the procedure separating development, calibration, and final evaluation.

Multiple abstention criteria were selected on 4 separate calibration designs, verified on 4 unused designs, and connected as the default policy for the new diagnosis command. The criteria require best residual ≤0.02 dB, candidate gap ≥0.03 dB, runner-up/max(best,0.01) ≥3, no-fault control score ≥8.054607, and agreement in 4/4 measurement rechecks. Across 2,304 injected-change cases on unused designs, the policy retained the existing 487 diagnoses and added 128, diagnosing 615 cases with 0 misdiagnoses and 0/64 false alarms in no-injection controls. The improvement was observed from changing the candidate-separation criteria; additional benefit from the no-fault-control and stability conditions was not established. This is a synthetic diagnostic evaluation using additional computation, not a guarantee against errors in real equipment. Scope is recorded in the [criteria, calibration, evaluation, and usage guide](notes/abstention_calibration_v1_results.md).

```bash
.venv/bin/python code/scripts/diagnose_reference.py --input input.json --output diagnosis.json
```

Input is JSON containing the current circuit `source`, public model `public`, and pre-fault measurements `reference`. The default configuration is `code/configs/diagnosis_abstention.json`; criteria for existing frozen experiments are preserved.

For the 615 confirmed cases, rechecks under the same ±0.01 dB measurement variation were increased from 4 to 16, adding 7,380 inverse estimations. All retained the same component and direction in 16/16 rechecks, with no newly unstable cases. Repetition costs and conditional interpretation are recorded in the [extended recheck results](notes/stability_extension_v1_results.md). This is a post hoc check restricted to confirmed inputs; the default remains 4 rechecks.

## Repository structure

| Path | Contents |
|---|---|
| `notes/` | Research plans, protocols, result interpretations, and review records |
| `references/specs/` | Circuit performance specifications |
| `code/` | Implementation, execution scripts, tests, experiment configurations, and diagnosis policies |
| `data/circuits/`, `data/faults/` | Circuit and injected-fault definitions |
| `results/` | Local artifacts, including raw API responses, SPICE logs, analyses, and rendered outputs |
| `paper/` | Manuscript editing materials, figures, and tables |
| `submissions/2026_ACK/` | Final submitted PDF and verification SHA-256 |
| `submissions/archive/` | Earlier dated manuscripts and submission history |

Root paths such as `src`, `scripts`, `tests`, `docs`, `build`, and `submission` are compatibility links for existing execution paths. Input/output links under `code/` preserve parent-path calculations in existing scripts. The root `pyproject.toml` discovers packages under `code/src`.

## Environment and reproduction

The project uses Python 3.12 or later, ngspice 47, OpenAI Python SDK 3.7.0, and pydantic 2.13.5. Python dependencies follow [pyproject.toml](pyproject.toml). The following is an installation example; no network installation was performed during this README review.

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
```

Offline unit tests and CLI checks, run from the repository root:

```bash
PYTHONPATH=code/src .venv/bin/python -B -m unittest discover -s code/tests -v
.venv/bin/python -B code/scripts/diagnose_reference.py --help
```

The ngspice smoke check and 100 MHz deterministic baseline create local output files. Preserve existing artifacts before running them.

```bash
mkdir -p results/build results/work
.venv/bin/python code/scripts/run_smoke.py
.venv/bin/python code/scripts/run_bpf_baseline.py
```

Output is stored in `results/build/` through the compatibility path `build/`. The baseline simulates ideal lumped components; it is not an actual RF measurement. The initial-baseline draft designation in `references/specs/bpf_100mhz.json` is retained.

Raw API responses, simulation logs, and rendered outputs excluded from Git are absent from a fresh clone, so hash reverification of the complete results requires separately stored artifacts. Check each experiment's prerequisites and protocol. Raw credentials in `.env.local` are excluded; set the `OPENAI_API_KEY` environment variable separately for actual API execution. Actual LLM runs require authentication and incur costs, and do not guarantee reproduction of past responses.

## Paper and submission status

The paper is listed in the ACK 2026 presentation program. Completion of the paper and presentation-video submissions is based on the user's confirmation. Awards are separate from presentation scheduling and submission completion; no confirmed award information is stated.

The final submitted PDF and the original were confirmed to have the same SHA-256. The submitted PDF bytes were not changed. Videos and presentation materials are stored locally and are not included in the public repository.

- [Final submitted PDF](submissions/2026_ACK/KIPS_C2026B0047%28김태훈%29.pdf)
- [Final PDF SHA-256](submissions/2026_ACK/SHA256SUMS)
- Earlier editable manuscript: [2026-09-14 DOCX](submissions/archive/ACK2026_2026-09-14_clarity/ACK2026_KimTaehoon_RF_Circuit_Repair.docx), [changes at that time](submissions/archive/ACK2026_2026-09-14_clarity/README.md), and [file verification at that time](submissions/archive/ACK2026_2026-09-14_clarity/verification.json). Historical manuscripts do not replace the final submitted PDF. DOCX page counts may vary by editor.

## Research history and preservation principles

### Preservation and public scope

Research history recorded in Git and frozen experimental materials are preserved. Raw credentials, virtual environments, videos, untracked presentation materials, personal work records, and backups are excluded from the public repository. Source-standard PDFs must be obtained separately; local artifacts absent from Git should be prepared against their manifests.

No new license has been granted. Check each source for the terms governing third-party standards, templates, and reference materials. When changing the folder structure, verify both compatibility paths and the hashes of frozen materials.

### Reproducibility and reliability principles

1. The agent proposes only structured repair patches.
2. The healthy netlist and fault ground truth in the main experiment are held only by the evaluator. Reference measurements, public models, and numerical candidates disclosed in auxiliary explorations are specified in each protocol.
3. Syntax, allowed modifications, simulation convergence, and specification satisfaction are checked separately.
4. Failed simulator calls are also counted in experimental costs.
5. Prompts, specifications, and validators are frozen after the pilot and kept separate from final evaluation.

<details>
<summary>Expand early pilot execution and history</summary>

The generation commands below describe how historical experiments were run. They may incur API costs and are distinct from offline verification.

The following commands and results concern early pipeline validation, separate from the latest manuscript's main experiment and auxiliary explorations.

The actual LLM pilot is run explicitly only when `OPENAI_API_KEY` is available in `.env.local` at the repository root. The healthy netlist and fault manifest are excluded from the agent's input, and each response is constrained to a single component-value modification.

```bash
PYTHONPATH=code/src .venv/bin/python code/scripts/run_llm_fault_pilot.py
```

The early pilot script defaults to model `gpt-5.6-luna`, reasoning effort `low`, and an output limit of 700 tokens, with API storage disabled. A single call's result is not claimed as benchmark performance.

Repeated pilot running each of 10 frozen value faults 3 times:

```bash
PYTHONPATH=code/src .venv/bin/python code/scripts/run_value_fault_repeat.py
```

The protocol is fixed in `code/experiments/value_fault_repeat_v0_1.json`. Results are saved in `build/code/experiments/value_fault_repeat_v0_1/`; rerunning the same command after interruption reuses completed calls and executes only missing ones.

Results and interpretation limits for the 30-run pipeline pilot conducted on 2026-09-02 are recorded in [notes/value_fault_repeat_v0_1_results.md](notes/value_fault_repeat_v0_1_results.md). Because it includes API operational failures, it is not used as final model performance.

The v0.2 diagnostic repeat uses a 1,200-token output limit and incomplete-response metadata; it does not overwrite v0.1 results.

```bash
PYTHONPATH=code/src .venv/bin/python code/scripts/run_value_fault_repeat.py \
  --protocol code/experiments/value_fault_repeat_v0_2.json
```

The v0.2 results are recorded in [notes/value_fault_repeat_v0_2_results.md](notes/value_fault_repeat_v0_2_results.md). Of 30 runs, 26 returned structured responses, and 24 restored all deterministic specifications after applying a constrained patch. This too is a diagnostic repeat, not a final benchmark.

The one-shot comparison of `LLM only` versus `+ initial SPICE evidence` under identical settings is recorded in [notes/preliminary_comparison_v1_0.md](notes/preliminary_comparison_v1_0.md). Adding raw SPICE metrics did not improve performance in this 10-case pilot. A closed loop of up to 3 iterations, feeding back failed repair results, was evaluated afterward.

The results of the closed-loop pipeline pilot with up to 3 iterations are recorded in [notes/closed_loop_value_pilot_v0_1_results.md](notes/closed_loop_value_pilot_v0_1_results.md). Of 10 trajectories, 9 were repaired on the first attempt; the second iteration, given failure evidence, repaired the remaining 1. This validates the implementation and is not a final performance claim.

Repeated closed-loop results with 3 trajectories per fault and the deterministic ratio-grid baseline are summarized in [notes/repeated_closed_loop_and_baseline_v1_0.md](notes/repeated_closed_loop_and_baseline_v1_0.md). The closed loop improved from 26/30 on the first attempt to 30/30 finally, repairing four additional cases. The grid baseline also repaired 10/10 but used 65 candidate simulations.

The constrained schema and strict-syntax results for open/short/port mismatches are recorded in [notes/structural_closed_loop_v1_0_results.md](notes/structural_closed_loop_v1_0_results.md); the current consolidated tables for the paper are in [notes/paper_results_tables.md](notes/paper_results_tables.md).

Results for the unit-normalized structural v1.1 experiment performed separately after strict-syntax failures are recorded in [notes/structural_normalized_v1_1_results.md](notes/structural_normalized_v1_1_results.md). These are post hoc results applying two interface changes together, distinct from a final benchmark.

</details>

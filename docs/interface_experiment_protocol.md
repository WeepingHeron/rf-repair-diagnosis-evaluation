# Main-result and interface-improvement experiment protocol

## Terms

- **Main result**: performance measured under rules fixed before examining the result.
- **Interface improvement**: a change that helps the LLM output and deterministic SPICE
  executor communicate without changing the circuit success criteria.
- **Ablation**: an experiment that changes one factor at a time to identify which change
  caused a performance difference.
- **Holdout**: cases not used to design the improvement and reserved for a later check.

## Primary result

The primary result remains the two completed frozen protocols:

1. component-value closed loop v1.0;
2. structural strict-syntax closed loop v1.0.

Their aggregate remains 46/48 final specification recovery. No post-result interface
change is included in this primary number.

## Interface ablation on the original structural cases

The original structural experiment changed neither factor. Three comparison arms are
used to separate the two interface changes:

| Arm | Unit canonicalization | Explicit VPORT role guidance |
|---|---|---|
| Strict v1.0 | Off | Off |
| Unit-only v1.2 | On | Off |
| Port-role-only v1.4 | Off | On |
| Combined v1.1 | On | On |

All four arms use the same six cases, three trajectories per case, validator, model,
reasoning effort, and three-iteration limit. These same-case ablations explain the
observed interface failures; they are not an independent final benchmark.

## Holdout confirmation

The combined interface is frozen and evaluated on six cases that were not used to design
the remediation: C3 open, C3 short, L1 open, L3 short, VPORT1 z0=100 ohm, and VPORT2
z0=25 ohm. All six were screened before the Agent run and satisfy the deterministic
benchmark validity rules. The holdout remains on the same ideal filter topology, so it
tests limited transfer to new cases rather than generalization to arbitrary RF circuits.

## Reporting rule

Report the primary result, same-case interface ablation, and holdout confirmation in
separate table sections. Do not replace the primary 46/48 result with a combined
post-improvement total.

## Withdrawn run

Port-role protocol v1.3 was stopped after seven completed trajectories. Its selected
prompt version also told the model that engineering-unit strings were accepted, while
the executor intentionally retained strict syntax. This contradicted the intended
single-factor comparison. Its partial outputs are excluded, and v1.4 replaces it with
a prompt that adds only the VPORT role sentence.

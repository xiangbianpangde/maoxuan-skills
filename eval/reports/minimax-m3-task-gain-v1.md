# MiniMax M3 Task Gain v1 — Result

- GitHub Actions run: `36325749864`
- Commit evaluated: `86749a3213d136a317fdfbea8561faed90f24d3a`
- Generation model: `minimax-m3`
- Judge model: `minimax-m3`
- Same-model judge: **yes**
- Frozen tasks SHA-256: `ba0c392f9471714c1092510423c172d8ed58299362d641cc32ea5fb6157fd55a`
- Frozen rubric SHA-256: `2822a281356a11c827de81a0f773b85e1ce82fcf8302f2f45f37fe53c04180b3`
- Cases: 30

## Pre-registered primary result

| Variant | Mean score (0–100) |
|---|---:|
| Vanilla | 87.433 |
| Retrieval-only | **96.726** |
| Atomic | 86.089 |
| Framework + Atomic | 84.389 |
| Full System | 88.386 |

Primary comparison, `Full System - Vanilla`:

- mean difference: **+0.953 points**
- paired bootstrap 95% CI: **[-9.372, +10.648]**
- pre-registered practically meaningful threshold: **+5.0 points**
- threshold met: **NO**

The v1 experiment therefore does **not** establish a practically meaningful overall Full-System gain over Vanilla.

## Ablation findings

- `Retrieval-only - Vanilla`: **+9.293**, 95% CI **[+2.664, +17.135]**.
- `Atomic - Vanilla`: **-1.343**, 95% CI **[-5.849, +2.971]**.
- `Framework+Atomic - Atomic`: **-1.700**, 95% CI **[-6.089, +2.360]**.
- `Full System - Framework+Atomic`: **+3.997**, 95% CI **[-6.043, +13.382]**.

The only ablation with a clearly positive paired interval in this run is retrieval.

## Category results

| Category | Vanilla | Retrieval-only | Atomic | Framework+Atomic | Full System |
|---|---:|---:|---:|---:|---:|
| engineering-project | 98.231 | 94.806 | 95.662 | 94.806 | 92.009 |
| learning-strategy | 93.113 | 98.380 | 88.194 | 86.864 | 91.898 |
| organization | 93.037 | 94.578 | 91.952 | 94.863 | 91.381 |
| research-decision | 96.667 | 99.226 | 95.833 | 86.607 | 70.000 |
| source-evidence | 56.116 | **96.640** | 58.804 | 58.804 | **96.640** |

The overall Full-System score is primarily rescued by source/evidence tasks. On the 24 non-source tasks, Full System averages approximately **8.94 points below Vanilla**. Excluding the one Full-System generation failure described below, the non-source paired difference is still approximately **-5.85 points**.

## Source/evidence layer

Retrieval produced the clearest verified gain:

- Retrieval-only: valid local Source ID on **6/6** source tasks; citation precision **45/45 = 100%**.
- Full System: valid local Source ID on **6/6** source tasks; citation precision **43/43 = 100%**.
- Vanilla / Atomic / Framework+Atomic: no valid local Source IDs on the six source tasks.

This supports keeping the Retrieval / Evidence layer frozen.

## One generation failure and sensitivity analysis

`rd-new-market` / Full System returned no answer because MiniMax rejected generation with:

`HTTP 422: output new_sensitive (1027)`

The judge correctly assigned the empty answer zero. This is part of the observed end-to-end result and is not removed from the pre-registered primary metric.

As a sensitivity analysis only, excluding this single failed case gives approximately:

- Full System mean: **91.434**
- paired `Full System - Vanilla`: **+3.745 points** across the remaining 29 cases

This still does not reach the pre-registered +5 point threshold.

## Runtime/context diagnosis

Current method variants inject the upstream Atomic `SKILL.md` bodies directly into the model context. Observed average system-context sizes in this run were approximately:

- Vanilla: 717 characters
- Retrieval-only: 1,364 characters (only source tasks receive excerpts)
- Atomic: 11,032 characters
- Framework+Atomic: 11,120 characters
- Full System: 12,291 characters

Judge notes on several low-scoring modern tasks repeatedly identify the same failure pattern: historical/methodology terminology becomes decorative or template-like, crowds out engineering-specific detail, and reduces direct actionability. Examples include the sensor-validation, model-deployment, benchmark-validation, resource-focus, collaboration, and workload-balancing tasks.

The Full-System `rd-new-market` failure also shows that the large method context can interact badly with provider content filtering even though the user task itself is ordinary B2B product research.

## Interpretation

Task Gain v1 supports a narrower conclusion than the original project hypothesis:

1. **Retrieval + evidence binding is strongly useful for source-grounded tasks.**
2. **The current raw Skill-context injection does not show positive general task gain.**
3. **Framework layering does not improve the current Atomic runtime and can add prompt overhead.**
4. **Full System does not pass the pre-registered overall gain threshold.**
5. This does not show that the underlying methods are useless; it shows that the present runtime representation — large upstream Skill documents placed directly in the system context — is not an effective delivery mechanism on this model/task set.

## Experimental limitations

- Generation and judging both used MiniMax M3. Answers were blinded as A–E, but same-model judging can still introduce model-specific preference or calibration bias.
- There is stochastic generation variance. On non-retrieval tasks, Retrieval-only receives essentially the same project context as Vanilla, so small score differences there should be treated as run noise rather than retrieval benefit.
- Task Gain v1 is now observed/frozen and must not be used as a clean acceptance suite for a redesigned runtime.

## Next phase

Do **not** tune against individual v1 tasks and rerun v1 as a fresh acceptance test.

Use v1 only as development evidence to redesign method delivery, then create a new frozen `task-gain-v2` suite before evaluating it. The recommended architecture direction is:

- keep the accepted `catalog-single` Router;
- keep Retrieval/Evidence unchanged;
- for `source_lookup`, use retrieval directly and avoid unnecessary method context;
- replace raw upstream `SKILL.md` injection with compact, modern, non-political runtime method cards containing only: objective, trigger, 3–5 executable steps, checks, and avoid conditions;
- inject only the minimum selected cards;
- reserve Composite context for genuinely multi-stage tasks;
- record generation failures explicitly in future summaries;
- replicate the final result with an independent judge when available.

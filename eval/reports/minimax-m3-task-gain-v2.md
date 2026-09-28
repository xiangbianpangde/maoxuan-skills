# MiniMax M3 Task Gain v2 — Result

- GitHub Actions run: `36406078155`
- Commit evaluated: `52f31700af827fb66c68077ddb517e7e93244c54`
- Generation model: `minimax-m3`
- Judge model: `minimax-m3`
- Same-model judge: **yes**
- Cases: 40 total, including 32 non-source method tasks and 8 source/evidence tasks
- Frozen task Git blob: `8cdf445e7fa1731e821467394abbd7cd6ed1c5f0`
- Frozen rubric Git blob: `74e9aed964afb98d893078ac81b67788ff96c43f`
- Frozen Runtime Cards Git blob: `bbaf1a971280b90ce39d5569beccf2f943cf84c3`
- Frozen Composite Cards Git blob: `fee8c507153e9dd30b8346edbc85f383dfe75f88`

## Pre-registered primary result

The primary comparison was defined before the first scored run as `Compact Atomic - Vanilla` on the 32 non-source method tasks, with success requiring both:

1. mean difference >= **+5.0 points**; and
2. paired bootstrap 95% CI lower bound > 0.

Observed method-task means:

| Variant | Mean score (0–100) |
|---|---:|
| Vanilla | **96.250** |
| Retrieval-only | 93.797 |
| Legacy Raw | 90.125 |
| Compact Atomic | 95.250 |
| Full-v2 | 93.367 |

Primary comparison:

- `Compact Atomic - Vanilla`: **-1.000 points**
- 95% CI: **[-3.547, +1.680]**
- pre-registered threshold met: **NO**

Task Gain v2 therefore does **not** establish a positive method-task gain over Vanilla.

## Important ceiling effect

Vanilla scored **96.25/100** on the 32 method tasks. On this realized sample, even a hypothetical perfect 100/100 Compact Atomic score could improve the mean by only **+3.75 points**, below the pre-registered +5 threshold.

This does not retroactively change the acceptance rule; the primary result remains a failure. It does show that the method-task suite was too easy for MiniMax M3 to provide adequate headroom for the intended +5-point effect-size criterion. Future acceptance suites must avoid this ceiling saturation without selecting tasks post-hoc based on observed Vanilla errors.

## Strongest v2 finding: Compact Cards beat Raw Skill injection

On the same 32 method tasks:

- `Legacy Raw - Vanilla`: **-6.125**, 95% CI **[-9.656, -2.852]**.
- `Compact Atomic - Legacy Raw`: **+5.125**, 95% CI **[+1.781, +8.578]**.

Thus the compact runtime representation produces a clear improvement over direct upstream `SKILL.md` injection, even though it does not beat Vanilla overall.

Method-task win/tie/loss counts:

- Compact Atomic vs Vanilla: **5 wins / 18 ties / 9 losses**.
- Compact Atomic vs Legacy Raw: **21 wins / 5 ties / 6 losses**.
- Full-v2 vs Vanilla: **5 wins / 14 ties / 13 losses**.

## Context and cost

Average system-context size:

| Variant | Avg system chars |
|---|---:|
| Vanilla | 708 |
| Retrieval-only | 1,336 |
| Legacy Raw | 9,553 |
| Compact Atomic | 1,501 |
| Full-v2 | 2,123 |

Generation tokens:

| Variant | Tokens |
|---|---:|
| Vanilla | 70,869 |
| Retrieval-only | 81,052 |
| Legacy Raw | 262,497 |
| Compact Atomic | 89,051 |
| Full-v2 | 98,398 |

Compact Atomic therefore reduced average method context by about **84%** relative to Legacy Raw and reduced generation tokens by about **66%**, while improving method-task quality by +5.125 points.

## Dimension diagnosis

Average judge dimension scores on the 32 method tasks (0–4):

| Dimension | Vanilla | Legacy Raw | Compact Atomic | Full-v2 |
|---|---:|---:|---:|---:|
| factual correctness | 3.844 | 3.625 | **3.875** | 3.781 |
| method fit | 3.906 | 3.625 | **3.938** | 3.781 |
| analysis structure | 3.812 | 3.625 | **3.844** | 3.781 |
| actionability | **3.906** | 3.656 | 3.656 | 3.688 |
| evidence fidelity | 3.438 | 3.375 | 3.406 | 3.438 |
| boundary compliance | 4.000 | 3.688 | **4.000** | **4.000** |
| overall utility | **3.812** | 3.500 | 3.781 | 3.594 |

Compact Cards slightly improve factual correctness, method fit, and analytical structure relative to Vanilla, but lose substantially on **actionability**. Judge notes repeatedly show the same pattern: method-aware answers are often well structured but replace task-native commitments with abstract conditions, placeholder thresholds, or less detailed implementation steps.

Examples of large Compact gains include `ls-perfect-start`, `rd-feature-demand`, `org-goal-tradeoff`, and `eng-benchmark-drift`. Large Compact losses include `eng-streaming-race`, `ls-strategy-tactics`, `org-conflict-safety`, `rd-small-experiment`, and `org-pilot-rollout`.

The exploratory subset of seven method tasks where observed Vanilla score was below 95 shows a +6.29 average Compact-vs-Vanilla difference, but this is **post-hoc selection on the outcome and is not valid acceptance evidence**. It is only a hypothesis for designing harder future tasks.

## Full-v2 result

Across all 40 tasks:

- Vanilla: 90.094
- Compact Atomic: 90.856
- Full-v2: **92.287**

But the paired `Full-v2 - Vanilla` all-task difference is only **+2.194**, 95% CI **[-3.819, +9.425]**.

On the 32 method tasks specifically:

- `Full-v2 - Vanilla`: **-2.883**, 95% CI **[-5.555, -0.266]**.

Full-v2 therefore should **not** become the default method runtime. The extra orchestration/context helps some research-decision tasks but hurts engineering, learning, and organization tasks often enough to create a statistically negative method-task difference in this run.

## Source/evidence layer

Source-task means:

- Vanilla: 65.469
- Retrieval-only: 86.562
- Full-v2: **87.969**

Deterministic citation validation:

- Retrieval-only: valid local Source ID on **7/8** tasks; **47/47** detected full Source IDs valid.
- Full-v2: valid local Source ID on **8/8** tasks; **45/45** detected full Source IDs valid.

The one Retrieval-only miss used paragraph shorthand such as `P0001` rather than the required full `MX-Vxx-Axxx-Pxxxx` identifier. The LLM judge nevertheless gave high evidence credit, showing that deterministic citation validation is more reliable than asking the judge to infer identifier validity.

The source sample is only n=8, so the retrieval-vs-vanilla bootstrap interval is wide; the deterministic citation evidence remains the stronger verification signal.

## Evaluation contamination discovered after the run

All 200 generated answers in the artifact contain provider-emitted `<think>...</think>` sections. The current judge receives the full generated text, so it can see reasoning that the benchmark intended not to expose.

This affects all variants and does not justify changing the pre-registered v2 primary result, but future benchmark runners must strip provider reasoning blocks before judging, citation checking, and user-visible quality measurement. The v2 outputs must not be silently re-scored and presented as a clean new acceptance run after inspecting the results.

## Interpretation

Task Gain v2 supports four conclusions:

1. **Raw upstream Skill injection is rejected.** It is materially worse than Vanilla and much more expensive.
2. **Compact Runtime Cards are a successful representation improvement over Raw injection.** They recover about five quality points while sharply reducing context and token cost.
3. **Compact Runtime Cards still do not demonstrate general capability gain over a strong Vanilla MiniMax M3 baseline.** On this ceiling-saturated suite they are approximately parity, not a verified improvement.
4. **Full-v2 orchestration is NO-GO as the default method runtime.** Retrieval remains valuable for source-grounded tasks, but broad method orchestration reduces method-task quality in this run.

## Runtime decision

Recommended project status after v2:

- Corpus: **FROZEN / PASS**
- Retrieval: **FROZEN / PASS**
- Evidence binding: **FROZEN / PASS**
- Router `catalog-single`: **FROZEN / PASS**
- Raw `SKILL.md` runtime injection: **DEPRECATED / NO-GO**
- Compact Runtime Cards: **KEEP as experimental method representation**
- Full-v2 automatic orchestration on general method tasks: **NO-GO**

The safe default remains task-native generation, with Retrieval/Evidence automatically enabled for source-grounded tasks. Method Cards should not yet be automatically injected into every routed modern task.

## Next experiment

Task Gain v2 is now observed and must not be reused as a clean acceptance suite for further runtime changes.

A v3 experiment should test a different delivery mechanism rather than merely rewriting the same cards against these 40 tasks:

1. **Planner -> Executor separation:** use selected cards only in a short planning stage, then pass a task-native plan—not card definitions or historical terminology—to the final answer generator.
2. **Actionability materialization:** the plan must convert abstract method steps into domain-specific actions, measurements, owners, stop/rollback conditions, and evidence gaps. Do not use placeholder thresholds when the task provides enough information; when it does not, specify how to calibrate them rather than inventing numbers.
3. **Minimum method injection:** one primary method by default; add a secondary method only when it contributes a distinct function.
4. **Reasoning sanitization:** strip `<think>...</think>` or equivalent provider reasoning before judge/evaluation surfaces.
5. **Deterministic evidence scoring:** pass citation-validity results into the source score instead of relying on the LLM judge to validate Source IDs.
6. **Harder but pre-specified acceptance tasks:** design a new suite with multi-constraint decisions, incomplete evidence, competing objectives, phase changes, or repeated feedback loops. Difficulty must be specified structurally before any scored Vanilla comparison, not selected after seeing Vanilla failures.
7. **Independent judge replication:** after the first clean v3 run, repeat final judging with a different model/provider if available.

The next hypothesis is therefore narrower: **methods may help on genuinely hard decision tasks if they are used as a hidden planning scaffold and then materialized into task-native execution details, rather than being shown directly to the final answer generator.**

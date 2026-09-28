# MiniMax M3 Task Gain v4 — Final Attribution Report

## Status

**Final runtime conclusion: Generic Planner candidate; no verified incremental gain from automatic Method-Card injection.**

Run: `task-gain-v4-benchmark` #2 (`36433686559`), commit `e79516e815a9825b66f6b770349f0c1fa8227181`.

The v4 held-out inputs, rubric, Planner Contract, reliability policy, Router and v2 Runtime Cards were frozen before this scored run. This run is the terminal attribution experiment for the automatic Runtime-Skill task-gain line; no v5 prompt-tuning loop is planned from these results.

## Reliability gate

Before touching the fresh v4 held-out, the workflow reran both planners on the frozen v3 development suite:

- tasks: 36
- planner calls: 72
- Generic Planner errors: **0**
- Method Planner errors: **0**
- model repairs: 4
- deterministic normalizations: 38

The reliability gate therefore passed, and v4 held-out scoring proceeded. On the v4 held-out itself, all three variants had **0 generation failures**, both planners had **0 fallbacks**, Router errors were **0**, and Judge errors were **0**.

## Frozen v4 result

| Variant | Mean score (0–100) |
| --- | ---: |
| Vanilla | 87.969 |
| Generic Planner | **97.383** |
| Method Planner | 94.922 |

### H1 — Does structured planning help beyond Vanilla?

Pre-registered rule: `Generic Planner - Vanilla >= +2.0` and bootstrap 95% CI lower bound > 0.

Observed:

- mean difference: **+9.414**
- 95% CI: **[+5.469, +13.320]**
- win / tie / loss: **23 / 5 / 4**

**PASS.** Within this frozen MiniMax M3 evaluation, structured Planner → Executor delivery produces a large, statistically separated gain over direct Vanilla answering.

### H2 — Do the frozen Method Cards add value beyond the compute-matched Generic Planner?

Pre-registered rule: `Method Planner - Generic Planner >= +1.5` and bootstrap 95% CI lower bound > 0, with actionability guardrail >= -0.10 / 4.

Observed:

- mean difference: **-2.461**
- 95% CI: **[-5.586, +0.586]**
- win / tie / loss: **8 / 13 / 11**
- actionability delta vs Generic: **-0.219 / 4**

**FAIL.** The frozen Method Cards do not demonstrate incremental task gain beyond generic structured planning. The actionability guardrail also fails.

Method Planner still beats Vanilla overall (`+6.953`, 95% CI `[+2.852, +10.977]`), but v4 isolates the source of that gain: the evidence supports the planning stage, not the automatic Method-Card injection.

## Category decomposition

| Category | Vanilla | Generic Planner | Method Planner | Generic − Vanilla | Method − Generic |
| --- | ---: | ---: | ---: | ---: | ---: |
| Engineering project | 85.312 | 97.812 | **99.219** | +12.500 | +1.407 |
| Learning strategy | 82.500 | **96.875** | 93.906 | +14.375 | -2.969 |
| Organization | **97.344** | 95.781 | 93.594 | -1.563 | -2.187 |
| Research decision | 86.719 | **99.062** | 92.969 | +12.343 | -6.093 |

The Method Planner has a small engineering-only advantage in this sample, but that was not a pre-registered subgroup claim and should not be promoted to a general routing rule without a separate fresh test. In the other three categories it is worse than Generic Planner.

## Task-level Method-Card behavior

Method Cards are not uniformly harmful, but their incremental effect is unstable.

Largest Method-over-Generic gains included:

- `org4-review-backlog`: **+15.0**
- `org4-support-product`: **+11.25**
- `eng4-cache-stale`: **+11.25**
- `ls4-language-transfer`: **+8.75**
- `eng4-flag-drift`: **+5.0**

Largest losses included:

- `ls4-literature-map`: **-22.5**
- `rd4-vendor-lockin`: **-18.75**
- `org4-interruptions`: **-17.5**
- `rd4-pricing-pilot`: **-15.0**
- `org4-metric-gaming`: **-15.0**
- `org4-vendor-knowledge`: **-13.75**

This is consistent with the aggregate 8 / 13 / 11 win-tie-loss pattern: automatic specialized-method injection can occasionally sharpen a task, but can also displace an already strong task-native generic plan.

The same caveat applies to per-card averages. Some cards appear positive or negative in this run, but most card-level sample sizes are too small and heavily confounded by task selection and card combinations to support individual-card quality claims.

## Hardness-feature decomposition

Generic Planner improved over Vanilla across almost every difficult-task feature, including:

- conflicting evidence: +11.786
- measurement noise: +13.056
- rollback: +11.250
- uncertainty: +11.053
- resource constraint: +9.205
- feedback loop: +9.598
- distribution shift: +18.333 (n=3; exploratory)

Method Planner was below Generic Planner for almost all common features. The only positive feature-level result was `safety_or_compliance` (+3.125, n=4), which is exploratory and too small to justify a new default rule.

## Quality dimensions

| Dimension | Vanilla | Generic Planner | Method Planner |
| --- | ---: | ---: | ---: |
| factual correctness | 3.438 | **3.812** | 3.719 |
| method fit | 3.625 | **3.938** | 3.844 |
| analysis structure | 3.562 | **3.938** | 3.906 |
| actionability | 3.438 | **3.938** | 3.719 |
| evidence fidelity | 3.250 | 3.656 | **3.781** |
| boundary compliance | 3.969 | 3.938 | **4.000** |
| overall utility | 3.375 | **3.875** | 3.719 |

The v2 concern about actionability is now cleanly resolved for Generic Planner: it improves actionability by +0.500 / 4 over Vanilla. Adding Method Cards gives some evidence-fidelity/boundary gains but loses task-level actionability and overall utility relative to Generic Planner.

## Cost

| Variant | Total generation/planner tokens | Relative to Vanilla | Avg total latency |
| --- | ---: | ---: | ---: |
| Vanilla | 89,257 | 1.00× | 19.941 s |
| Generic Planner | 233,550 | **2.62×** | 37.564 s (**1.88×**) |
| Method Planner | 247,341 | **2.77×** | 46.572 s (**2.34×**) |

Generic Planner is therefore a quality/cost tradeoff, not a universal replacement for direct answering. The evidence supports using it selectively for complex, multi-constraint tasks rather than paying the planning cost for every request.

## Final project interpretation

The four Task Gain generations now support the following evidence-based status:

- **Corpus / Source IDs / Retrieval / Evidence binding:** PASS / FROZEN.
- **Frozen `catalog-single` Router:** retained as the routing/evaluation mechanism.
- **Raw upstream `SKILL.md` runtime injection:** DEPRECATED; v2 showed long raw documents were worse than compact representation and substantially more expensive.
- **Compact Runtime Cards:** KEEP as an explicit/optional method library and research representation.
- **Automatic Method-Card injection as default runtime:** NO-GO; v4 does not verify incremental gain beyond compute-matched generic planning.
- **Generic Planner → Executor:** CANDIDATE for complex tasks; v4 verifies a substantial gain over Vanilla in this evaluation.
- **Vanilla direct path:** retain for simple or latency/cost-sensitive requests.

Recommended runtime policy:

```text
source / quotation / historical explanation
    -> Retrieval + Evidence

simple or low-stakes task
    -> Vanilla direct answer

complex multi-constraint task where planning quality justifies extra cost
    -> Generic Planner -> Executor

explicit request to apply / inspect a Mao-derived method
    -> Router -> optional Runtime Card(s)
       (do not claim general automatic task-gain superiority)
```

## Study limitations

1. Generation and blind judging both used `minimax-m3`. Blinding and deterministic label shuffling reduce presentation bias, but an independent judge/model replication would strengthen an external publication claim.
2. v4 has 32 held-out tasks. It is sufficient for the pre-registered project decision, not for fine-grained claims about every individual Atomic Skill.
3. Category and hardness-feature breakdowns are secondary/exploratory; only the pre-registered H1/H2 and guardrails determine the runtime conclusion.
4. This experiment evaluates task quality and runtime behavior, not the historical or scholarly validity of every methodological interpretation. Source claims remain governed by the independent Retrieval/Evidence layer.

## Closeout decision

**Stop the automatic Runtime-Skill task-gain tuning line here. Do not create v5 solely to tune prompts against these results.**

The strongest supported product architecture is now:

> **Evidence-grounded Mao corpus and method library + reliable Retrieval/Source IDs + frozen Router + optional explicit Method Cards, with a generic Planner → Executor path for complex modern tasks.**

This preserves the project's distinctive source/method assets without making an unsupported claim that automatic Mao-derived Method-Card injection generally improves a strong LLM.
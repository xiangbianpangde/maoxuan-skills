# MiniMax M3 Task Gain v3 — Result

- GitHub Actions run: `36415735997`
- Commit evaluated: `7fffd7bae0e5122ddfbed83ddcb870d535b369e8`
- Generation model: `minimax-m3`
- Judge model: `minimax-m3`
- Same-model judge: **yes**
- Cases: **36** frozen hard method tasks
- Architecture: **Planner -> Executor v3**

## Pre-registered decision

Overall v3 success required all three:

1. `Method Planner - Vanilla >= +3.0` points and paired bootstrap 95% CI lower bound > 0.
2. `Method Planner - Generic Planner >= +1.5` points and paired bootstrap 95% CI lower bound > 0.
3. Method Planner mean actionability no more than 0.10 points below Vanilla on the 0-4 scale.

Observed:

| Variant | Mean score (0-100) |
|---|---:|
| Vanilla | **92.500** |
| Compact Direct | 89.861 |
| Generic Planner | 88.438 |
| Method Planner | 79.514 |

Primary comparisons:

- `Method Planner - Vanilla`: **-12.986**, 95% CI **[-27.083, -0.556]** -> FAIL.
- `Method Planner - Generic Planner`: **-8.924**, 95% CI **[-20.590, +2.465]** -> FAIL.
- Actionability delta: **-0.527 / 4** -> FAIL.

**Pre-registered overall result: NO-GO.**

## Reliability failure discovered

The run also exposed a runtime reliability problem in both planner variants:

- Generic Planner: **3 / 36** planner failures.
- Method Planner: **6 / 36** planner failures.

All six Method Planner failures were planner-schema validation failures rather than domain-answer failures. The observed failure messages were limited to:

- `ValueError: answer_focus: list required`
- `ValueError: answer_focus too long`

The affected Method Planner cases were:

- `eng3-sse-race`
- `eng3-depth-repeatability`
- `eng3-rag-latency`
- `eng3-queue-idempotency`
- `ls3-resource-balance`
- `rd3-pilot-expansion`

Failed planner calls never reached the Executor, so those variants received empty answers and score 0. This is still a legitimate end-to-end runtime failure and therefore remains part of the pre-registered NO-GO result.

## Sensitivity analysis — not acceptance evidence

Because failures were observed after the scored run, the following is exploratory only and must not replace the pre-registered result.

On the **30 cases where Method Planner completed successfully**:

- Method Planner mean: **95.417**
- Vanilla mean: **91.292**
- `Method Planner - Vanilla`: **+4.125** points
- win/tie/loss: **18 / 3 / 9**
- Method actionability: **3.800 / 4**
- Vanilla actionability on the same subset: **3.633 / 4**

This shows that the successful Method Planner executions were not intrinsically low-quality; the large all-suite regression is heavily affected by planner reliability failures.

However, on the stricter **29-case subset where both Generic Planner and Method Planner completed successfully**:

- Method Planner: **95.259**
- Generic Planner: **96.509**
- Vanilla: **91.034**
- `Method Planner - Vanilla`: **+4.224**
- `Generic Planner - Vanilla`: **+5.474**
- `Method Planner - Generic Planner`: **-1.250**

Thus the successful planner architecture appears useful on this exploratory subset, but the compact Skills do **not** show extra value beyond a generic planning stage. The stronger observed uplift is explained by planning itself, not by Method Cards.

## Category diagnosis

All-task category means:

| Category | Vanilla | Compact Direct | Generic Planner | Method Planner |
|---|---:|---:|---:|---:|
| Engineering / project | 89.861 | 87.500 | 77.639 | **54.028** |
| Learning / strategy | 91.806 | 92.500 | **95.556** | 85.694 |
| Organization | 95.278 | 91.667 | 85.972 | **95.556** |
| Research / decision | 93.056 | 87.778 | **94.583** | 82.778 |

Method Planner failures were concentrated in engineering tasks (4 of the 9 engineering cases), which explains the catastrophic engineering mean. On successful Method Planner executions only, engineering shows a large exploratory positive difference versus Vanilla; this is not acceptance evidence because the subset is selected on runtime success.

## Cost

Total generation + planner tokens:

- Vanilla: **109,219**
- Compact Direct: **129,593**
- Generic Planner: **300,820**
- Method Planner: **293,891**

Average total latency:

- Vanilla: **23.938 s**
- Compact Direct: **21.650 s**
- Generic Planner: **47.845 s**
- Method Planner: **41.739 s**

Planner -> Executor therefore costs roughly 2.7x Vanilla generation tokens while also adding substantial latency. Without verified quality gain, it cannot be the default runtime.

## Reasoning sanitization

The v3 runner successfully stripped provider-emitted reasoning blocks before judge scoring. Removed characters:

- Vanilla: 200,524
- Compact Direct: 199,232
- Generic Planner: 286,700
- Method Planner: 245,565

This fixes the v2 reasoning-contamination problem and should be retained.

## Interpretation

Task Gain v3 supports these conclusions:

1. **Planner -> Executor v3 is NO-GO as the default runtime under the pre-registered rules.**
2. **The implementation is not reliable enough:** 6/36 Method Planner runs failed before Executor generation due schema strictness.
3. **Planner execution may help when it succeeds**, but this is exploratory because success-conditioned analysis is post-hoc.
4. **Method Cards still have no demonstrated incremental gain over a generic planner.** On the clean both-planners-success subset, Generic Planner performed better than Method Planner.
5. **Compact Direct remains approximately parity / slightly below Vanilla** on this harder suite (`-2.639`, CI crosses zero), consistent with v2's conclusion that Compact Cards are much better than Raw injection but not proven superior to Vanilla.
6. **Reasoning sanitization works and should remain frozen.**

## Runtime decision

Recommended status after v3:

- Corpus: **PASS / FROZEN**
- Retrieval: **PASS / FROZEN**
- Evidence binding: **PASS / FROZEN**
- Router `catalog-single`: **PASS / FROZEN**
- Raw `SKILL.md` injection: **DEPRECATED / NO-GO**
- Compact Runtime Cards: **KEEP as optional/experimental representation**
- Compact Direct automatic injection: **NO verified general gain**
- Generic Planner: **experimental; not default**
- Method Planner v3: **NO-GO**
- Planner schema validator / fallback policy: **must be fixed before any further planner experiment**

## Recommended final iteration

If one additional runtime experiment is undertaken, it should be narrowly scoped as **v3.1/v4 reliability + attribution**, not another broad rewrite:

1. Normalize planner JSON instead of failing for harmless shape/length deviations (`answer_focus` string -> one-item list; truncate bounded lists).
2. Add fail-open fallback: if planner remains invalid after one repair, execute Vanilla or Generic-Plan path rather than return an empty answer.
3. Keep the same frozen Runtime Cards; do not rewrite cards against these observed cases.
4. Use a fresh held-out suite for any new acceptance claim; the 36 v3 tasks are now development/regression only.
5. Keep `Generic Planner` as the compute-matched control.
6. Require Method Planner to beat Generic Planner, otherwise attribute any gain to planning rather than Skills.

If that final experiment still fails to show incremental Method-Card gain, stop runtime iterations and publish the project as a strong **Corpus + Retrieval + Evidence + Router** system with optional experimental Method Cards, rather than claiming a general task-gain benefit from Skills.

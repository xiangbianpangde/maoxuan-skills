# Task Gain v3 — Planner → Executor

Task Gain v3 tests a narrower hypothesis than v1/v2:

> Compact methods may improve genuinely hard decision tasks when they are used only inside a hidden planning compiler and are translated into a task-native execution plan before final-answer generation.

## What changed

v3 does **not** rewrite the 25 Runtime Cards against previously observed v2 failures. It changes the delivery mechanism:

1. the frozen `catalog-single` Router selects Atomic Skills;
2. at most two Compact Runtime Cards are available to the hidden Method Planner;
3. the Planner emits a constrained task-native JSON plan;
4. the Executor receives the original task plus the task-native plan only;
5. the Executor never sees card names, historical terminology, framework names, or routing metadata.

Provider reasoning blocks such as `<think>...</think>` are stripped before judging.

## Frozen task suite

The suite contains 36 new method tasks, 9 each in:

- research-decision
- engineering-project
- organization
- learning-strategy

Every task has at least five structurally declared `hardness_features` such as conflicting evidence, incomplete information, multi-objective constraints, phase changes, rollback requirements, noisy measurement, or feedback loops.

No v2 task ID is reused. Difficulty is defined before any scored Vanilla run; tasks must not be selected after observing which questions Vanilla misses.

## Variants

- `vanilla`: one normal answer call, no project method context.
- `compact-direct`: v2-style Compact Cards injected directly into final generation.
- `generic-planner`: hidden Planner → Executor with the same two-call architecture but **no Method Cards**.
- `method-planner`: hidden Planner → Executor with at most two selected Compact Method Cards.

`generic-planner` is the critical compute/control condition. A gain over Vanilla alone is insufficient to attribute improvement to Skills if the same gain is explained by an extra planning call.

## Pre-registered acceptance rule

Overall v3 success requires all three conditions:

1. `Method Planner - Vanilla >= +3.0` points and paired bootstrap 95% CI lower bound > 0;
2. `Method Planner - Generic Planner >= +1.5` points and paired bootstrap 95% CI lower bound > 0;
3. Method Planner mean `actionability` is no more than 0.10 points below Vanilla on the 0–4 dimension scale.

Secondary analyses include Generic Planner vs Vanilla, Method Planner vs Compact Direct, per-category results, per-hardness-feature results, planner validity/repairs, selected-card count, sanitized reasoning volume, tokens, context size and latency.

## Experimental discipline

After the first scored v3 run, the frozen tasks, rubric, Planner Contract, Runtime Cards, Router prompt and acceptance criteria must not be modified and then presented as a fresh clean v3 acceptance result.

Task Gain v1 and v2 remain development evidence only.

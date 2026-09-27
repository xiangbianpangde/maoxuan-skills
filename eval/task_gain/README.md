# Task Gain Benchmark v1

This benchmark measures whether the `maoxuan-skills` system improves **final task quality**, not just routing accuracy.

## Frozen inputs

- Tasks: `tasks-v1.jsonl`
- Cases: 30 (6 each across source/evidence, research/decision, engineering/project, organization, learning/strategy)
- Tasks SHA-256: `ba0c392f9471714c1092510423c172d8ed58299362d641cc32ea5fb6157fd55a`
- Rubric SHA-256: `2822a281356a11c827de81a0f773b85e1ce82fcf8302f2f45f37fe53c04180b3`
- Router: frozen `catalog-single` from `router/ROUTER_FREEZE.json`

The dataset, requirements, weights, rubric, routing policy, and judge protocol are frozen before the first scored run.

## Controlled variants

1. `vanilla` — base model, no local corpus or methodology context.
2. `retrieval-only` — local corpus evidence only when the task requires source evidence; no methodology Skills.
3. `atomic` — frozen router + selected Atomic Skills; no Framework, Composite, or source retrieval.
4. `framework-atomic` — Atomic context plus selected Framework.
5. `full-system` — frozen router + Atomic + Framework + Composite when selected + local retrieval when required + evidence-separation rules.

All routed variants reuse the **same route result per task** so the ablation measures context/system gain rather than independent routing randomness.

## Blind judge

For each task, the five answers are deterministically shuffled into anonymous labels A–E before judging. The judge never sees the variant names.

Scores are 0–4 on:

- factual correctness
- method fit
- visible analysis structure
- actionability
- evidence fidelity
- boundary compliance
- overall utility

Task-specific weights are stored directly in the frozen task rows. The weighted result is normalized to 0–100.

The primary statistic is:

`mean(full-system) - mean(vanilla)`

A gain of **>= 5.0 points** is pre-registered as a practically meaningful primary gain threshold. Paired bootstrap 95% intervals are reported as uncertainty estimates.

## Important interpretation rule

Do **not** reward historical vocabulary, Mao-style roleplay, or quoting for its own sake. A Skill variant should score higher only if it makes the answer more correct, better structured, better matched to the problem, more actionable, or more evidence-grounded.

## Source evidence

The six source/evidence tasks require local corpus grounding. Retrieved excerpts carry stable `MX-V..-A...-P....` Source IDs. Citation validity is reported separately as a deterministic secondary metric.

## Running

Use GitHub Actions workflow `task-gain-benchmark`.

Inputs:
- `base_url`
- `model`
- optional `judge_model` (blank = same model)
- `workers`
- `judge_workers`
- `no_response_format`

Secret:
- `MAOXUAN_BENCH_API_KEY`

One run generates all five variants for the same 30 frozen tasks and judges them blind.

## After the first scored run

Do not tune against `task-gain-v1`. Record the result. If a redesign is needed, use development evidence and create a new frozen `task-gain-v2` before another acceptance-style measurement.

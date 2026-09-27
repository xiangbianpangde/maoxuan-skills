# Router Held-out v1

This directory contains the first **one-shot held-out acceptance suite** for the router.

## Freeze rule

`router-heldout-v1.jsonl` is frozen before any scored model run. Its SHA-256 is:

`3ff1154048f2f2c3c218074d66bb8ece3d95257a0557c7c5a5c45f9c9d23cdfb`

Do not modify prompts, labels, scoring, router prompts, candidate rules, or routing profiles after inspecting model results from this suite. If a later architecture needs another clean acceptance test, create `router-heldout-v2` with new prompts and pre-register a new hash before running it.

## Composition

60 scored cases:

- 25 atomic-positive cases: one fresh positive for each Atomic Skill.
- 15 contrast cases: require one Skill while explicitly forbidding a nearby confounder.
- 10 system cases: direct, source lookup, mixed source+method, composites, and the current-politics neutrality boundary.
- 10 hard-negative cases: ordinary tasks that should stay `direct` and must not trigger specified methodology Skills.

These prompts are not copied from the upstream `test-prompts.json` regression suite.

## Architectures compared

The held-out workflow evaluates the same 60 cases against:

1. `catalog-single`: single-pass router using the compact Atomic catalog summaries, route rules, frameworks and composites, without loading all detailed routing profiles.
2. `two-stage-v5`: Stage 1 coarse shortlist followed by Stage 2 selective detailed-profile routing.

## Pre-registered selection rule

Accuracy is primary, but efficiency is part of the runtime decision.

Prefer `catalog-single` as the default unless `two-stage-v5` satisfies at least one of the following on this same held-out suite:

- improves total held-out accuracy by **>= 3 percentage points**, or
- produces a material system-routing improvement,

and does so without exceeding **1.5x** the token cost of `catalog-single`.

If neither architecture demonstrates adequate generalization, do not tune against this held-out suite. Record the result, keep the suite frozen, and redesign the router using only development/regression evidence before creating a new held-out version.

## Running

Use the manual GitHub Actions workflow `router-heldout-benchmark`. One dispatch runs both architectures against the same model and API configuration.

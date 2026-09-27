# MiniMax M3 Router Held-out v1 — Acceptance Result

- Date: 2026-09-27
- GitHub Actions run: `36323107790`
- Commit evaluated: `ce4cc25941077ad310483e0b866981844e24b9ea`
- Model: `minimax-m3`
- Base URL: `https://api.minimaxi.com/v1`
- Frozen suite: `router-heldout-v1`
- Frozen SHA-256: `3ff1154048f2f2c3c218074d66bb8ece3d95257a0557c7c5a5c45f9c9d23cdfb`

## Pre-registered selection rule

Prefer `catalog-single` unless `two-stage-v5` improves held-out accuracy by at least 3 percentage points or materially improves system routing, and does so without exceeding 1.5x the token cost of `catalog-single`.

## Results

| Architecture | Overall | Atomic positive | Contrast | Hard negative | System | Tokens | Avg latency | Repairs | Normalizations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **catalog-single** | **59/60 = 98.33%** | **24/25 = 96%** | **15/15 = 100%** | **10/10 = 100%** | **10/10 = 100%** | **194,928** | **5.433 s** | **0** | **0** |
| two-stage-v5 | 55/60 = 91.67% | 22/25 = 88% | 13/15 = 86.67% | 10/10 = 100% | 10/10 = 100% | 359,954 | 11.608 s | 1 | 2 |

Token-cost ratio: `two-stage-v5 / catalog-single = 1.8466x`.
Latency ratio: `two-stage-v5 / catalog-single = 2.1366x`.
Accuracy difference: `catalog-single - two-stage-v5 = 6.66 percentage points`.

## Catalog-single single failure

Case `hp-diaocha-yanjiu` asked for structured interviews, observation, and recording before redesigning a laboratory reservation system.

The router selected the correct target Atomic Skill `diaocha-yanjiu`, plus related research methods, but promoted the route from the expected `method_application` to `composite_task`. Therefore the failure is a route-contract over-promotion rather than an Atomic Skill miss. No prompt change is made from this observation because the suite is held out and frozen.

## Two-stage-v5 failure pattern

Five cases failed. In four of them the correct Atomic Skill was already present in the Stage-2 candidate pool, but Stage 2 failed to retain it in the final selection. This indicates that the extra discrimination stage can introduce errors even after successful coarse recall. The held-out result does not support the added complexity or runtime cost.

## Acceptance decision

`catalog-single` is frozen as the default Router.

Reasons:

1. It has higher held-out accuracy: 98.33% vs 91.67%.
2. System routing is tied at 10/10, so `two-stage-v5` has no system-routing advantage.
3. `two-stage-v5` uses 1.85x the tokens, exceeding the pre-registered 1.5x cost bound.
4. `catalog-single` is also materially faster and required no repair or normalization.

The prior 156-case suite remains development/regression-only. `router-heldout-v1` must not be used for further Router prompt tuning.

## Next phase

Freeze Router work and move to Task Gain evaluation. Compare answer quality across controlled variants such as Vanilla, Retrieval-only, Atomic, Framework+Atomic, and the Full System while keeping the selected `catalog-single` Router fixed for routed variants.

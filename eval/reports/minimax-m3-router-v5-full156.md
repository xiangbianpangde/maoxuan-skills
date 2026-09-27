# MiniMax M3 Router v5 — Full 156-case Regression

- Date: 2026-09-27
- GitHub Actions run: `36319818216`
- Commit: `cbbb6e5a89e1fb12efdd9ff9aea0982e2a13e583`
- Model: `minimax-m3`
- Base URL: `https://api.minimaxi.com/v1`
- Architecture: `two-stage-v5`
- Suite: 75 should-trigger + 50 should-not-trigger + 25 edge + 6 system-router = 156

## Result

- Scored: **131**
- Passed: **103 / 131 = 78.63%**
- Atomic: **100 / 125 = 80.0%**
- Should-trigger recall: **58 / 75 = 77.33%**
- Should-not-trigger specificity: **42 / 50 = 84.0%**
- System-router exact contract: **3 / 6 = 50.0%**
- API errors: **0**
- Repairs: **3**
- Slug normalizations: **6**
- Stage-2 calls: **141 / 156**
- Average candidate pool: **9.96**
- Average model calls per case: **1.92**
- Average latency: **18.801 s**
- Total tokens: **1,159,115**

## Candidate analysis

For the 75 should-trigger atomic cases:

- Target atomic skill was present in the Stage-2 candidate pool for **69 / 75 = 92.0%**.
- Given that the target was in the candidate pool, Stage 2 selected it in **58 / 69 = 84.06%**.
- Therefore **6** positive misses originated in Stage 1 candidate generation and **11** originated in Stage 2 discrimination.

Stage-1 target misses occurred once each for:

- `shijian-renshilun`
- `diaocha-yanjiu`
- `zhanlue-miaoshi-zhanshu-zhongshi`
- `lianglei-maodun`
- `chengqianbihou-zhibing-jiuren`
- `yiban-gebie-zhidao`

The strongest Stage-2 discrimination failures were:

- `zhanlue-zhanshu-bianzheng`: 0/3 final hits despite 3/3 candidate recall.
- `bianzheng-pingheng`: 0/3 final hits despite 3/3 candidate recall.
- `shijian-renshilun`: 0/3 final hits, with 2/3 candidate recall.

## Four-run comparison

| Variant | Overall | Trigger | Negative | System router | Tokens | Avg latency |
|---|---:|---:|---:|---:|---:|---:|
| Router v3 baseline | 68.70% | 60.00% | 84.00% | 50.00% | 439,755 | ~7 s |
| Catalog-enhanced single-stage | 77.86% | 73.33% | **88.00%** | 50.00% | 595,359 | ~7 s |
| true v4, all profiles in one prompt | 76.34% | 69.33% | **88.00%** | **66.67%** | 953,866 | 8.144 s |
| **v5 two-stage** | **78.63%** | **77.33%** | 84.00% | 50.00% | **1,159,115** | **18.801 s** |

## Interpretation

Two-stage routing produced the best regression-set overall score and the best positive recall so far, but only narrowly exceeded the catalog-enhanced single-stage router on overall accuracy (**+0.77 percentage points**). That small gain came with approximately **1.95x** the token usage of the catalog-enhanced run and much higher latency.

The candidate mechanism is useful: Stage 1 retained the correct target in 92% of positive cases. However, the average candidate pool remained close to 10 skills, and 141/156 cases invoked Stage 2, so the architecture did not realize the intended efficiency benefit.

## Decision

- The 156-case suite is now **closed as a development/regression set**. Do not tune prompts, profiles, candidate rules, or scoring against individual failures from this suite.
- Retrieval and evidence layers remain frozen.
- Do **not** select a production-default router solely from this regression set.
- Compare the two plausible runtime candidates on a fresh held-out suite:
  1. `catalog-single` — cheaper and nearly as accurate on the regression suite.
  2. `two-stage-v5` — slightly higher regression accuracy but materially more expensive.
- Pre-register the selection rule before the held-out run: prefer the simpler `catalog-single` unless `two-stage-v5` improves held-out scored accuracy by at least **3 percentage points** or delivers a material system-routing advantage without more than **1.5x** token cost.
- After the held-out comparison, freeze the winning router and move to Task Gain evaluation rather than further route-prompt tuning.

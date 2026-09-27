# MiniMax M3 Router true v4 — Full 156-case Regression

- Date: 2026-09-27
- GitHub Actions run: `36316991868`
- Commit: `4ce8fd4c7add41a2040bee509eaac0ee3356f66e`
- Model: `minimax-m3`
- Base URL: `https://api.minimaxi.com/v1`
- Suite: 75 should-trigger + 50 should-not-trigger + 25 edge + 6 system-router = 156

## Result

- Scored: **131**
- Passed: **100 / 131 = 76.34%**
- Atomic: **96 / 125 = 76.8%**
- Should-trigger recall: **52 / 75 = 69.33%**
- Should-not-trigger specificity: **44 / 50 = 88.0%**
- System-router exact contract: **4 / 6 = 66.67%**
- API errors: **0**
- Repair attempts: **2**
- Slug normalizations: **1**
- Average latency: **8.144 s**
- Total tokens: **953,866**

## Three-run comparison

| Variant | Overall | Trigger | Negative | System router | Tokens |
|---|---:|---:|---:|---:|---:|
| Router v3 baseline | 68.7% | 60.0% | 84.0% | 50.0% | 439,755 |
| Catalog-enhanced | **77.86%** | **73.33%** | **88.0%** | 50.0% | 595,359 |
| true v4, all profiles in one prompt | 76.34% | 69.33% | 88.0% | **66.67%** | 953,866 |

## Interpretation

The full `when / avoid / contrast` profile table improved orchestration for some cases but did not improve overall atomic routing. Relative to the catalog-enhanced run, 10 previously failing cases were recovered while 12 previously passing cases regressed.

The main engineering signal is prompt competition: injecting all 25 detailed profiles at once increased token use substantially while reducing positive recall. This suggests that profile detail should be used selectively rather than globally.

Notable gains versus the catalog-enhanced run included `zhudongxing-linghuoxing-jihuaxing`, `shiliuzijue`, and `chengqianbihou-zhibing-jiuren`. Notable regressions included `tan-gangqin`, plus individual trigger losses in `diaocha-yanjiu`, `shishiqiushi-sigao`, `chijiuzhan-san-jieduan`, `fangxia-baofu-kaidong-jiqi`, and `maodun-fenxi`.

## Decision

- Retrieval / evidence layer: unchanged and stable.
- Full-profile single-prompt Router: **do not freeze**.
- The 156-case suite remains a **development/regression set** and should not be used as final held-out evidence.
- Do not add case-specific prompt rules based on this run.
- Next structural experiment should be a **two-stage router**: a compact first pass for route/coarse candidate selection, followed by a second pass that exposes only the relevant subset of detailed routing profiles.
- Final acceptance should use a fresh held-out suite after the routing architecture is frozen.

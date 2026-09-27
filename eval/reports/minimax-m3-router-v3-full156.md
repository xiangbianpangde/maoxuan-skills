# MiniMax M3 Router v3 — Full 156-case Benchmark

- Date: 2026-09-27
- GitHub Actions run: `36304488317`
- Commit: `7eb37e0b69ea9abf6cce7fd72aef4be18a7d6bfb`
- Model: `minimax-m3`
- Base URL: `https://api.minimaxi.com/v1`
- Workers: 4
- Suite: 75 should-trigger + 50 should-not-trigger + 25 edge + 6 system-router = 156

## Executive summary

- Scored: **131**
- Passed: **90 / 131 = 68.7%**
- Atomic exact target: **87 / 125 = 69.6%**
- Should-trigger recall: **45 / 75 = 60.0%**
- Should-not-trigger specificity: **42 / 50 = 84.0%**
- System-router exact contract: **3 / 6 = 50.0%**
- Edge cases: 25 recorded, not auto-scored; originating target included in **15 / 25**
- API errors: **0**
- Repair attempts: **2**
- Slug normalizations: **2**
- Average latency: **7.038 s**
- Total tokens: **439,755**

> Status: evidence/retrieval integration is stable, but Router v3 should not be frozen as final routing logic. The 156-case suite is now a development/regression set because its failures have been inspected.

## Per-skill atomic results

| Skill | Trigger | Negative | Balanced |
|---|---:|---:|---:|
| `chengqianbihou-zhibing-jiuren` | 1/3 | 0/2 | 16.7% |
| `chijiuzhan-san-jieduan` | 1/3 | 1/2 | 41.7% |
| `xingxingzhihuo-genjudi` | 1/3 | 1/2 | 41.7% |
| `cong-zhanzheng-xuexi-zhanzheng` | 0/3 | 2/2 | 50.0% |
| `shiliuzijue` | 0/3 | 2/2 | 50.0% |
| `tan-gangqin` | 0/3 | 2/2 | 50.0% |
| `jianmiezhan-jizhong-bingli` | 2/3 | 1/2 | 58.3% |
| `lianglei-maodun` | 2/3 | 1/2 | 58.3% |
| `neiyin-juedinglun` | 1/3 | 2/2 | 66.7% |
| `shijian-renshilun` | 1/3 | 2/2 | 66.7% |
| `zhanlue-zhanshu-bianzheng` | 1/3 | 2/2 | 66.7% |
| `zhudongxing-linghuoxing-jihuaxing` | 1/3 | 2/2 | 66.7% |
| `buduicheng-zhanlue` | 3/3 | 1/2 | 75.0% |
| `zuzhi-jiupian-zhenduan` | 3/3 | 1/2 | 75.0% |
| `bianzheng-pingheng` | 2/3 | 2/2 | 83.3% |
| `diaocha-yanjiu` | 2/3 | 2/2 | 83.3% |
| `qunzhong-luxian` | 2/3 | 2/2 | 83.3% |
| `tongyi-zhanxian-duli` | 2/3 | 2/2 | 83.3% |
| `zhanlue-miaoshi-zhanshu-zhongshi` | 2/3 | 2/2 | 83.3% |
| `fangxia-baofu-kaidong-jiqi` | 3/3 | 2/2 | 100.0% |
| `maodun-fenxi` | 3/3 | 2/2 | 100.0% |
| `maodun-techuxing` | 3/3 | 2/2 | 100.0% |
| `shishiqiushi-sigao` | 3/3 | 2/2 | 100.0% |
| `yiban-gebie-zhidao` | 3/3 | 2/2 | 100.0% |
| `youxiao-goutong-wenti-jiuej` | 3/3 | 2/2 | 100.0% |

## Main confusion pattern

Among the **30 missed should-trigger cases**, `maodun-fenxi` appeared in **21** predictions. This is a catch-all attractor effect: a generic “find the main problem” skill is displacing specialized mechanisms.

Most common skills in missed-positive predictions:

- `maodun-fenxi`: 21
- `maodun-techuxing`: 10
- `neiyin-juedinglun`: 9
- `bianzheng-pingheng`: 7
- `zuzhi-jiupian-zhenduan`: 6
- `buduicheng-zhanlue`: 6
- `fangxia-baofu-kaidong-jiqi`: 6

## Boundary failures

Eight should-not-trigger cases selected their target Skill. The main pattern is missing applicability boundaries:

- disadvantage-oriented strategy Skills triggered even when the organization was already dominant;
- concentration-of-resources triggered despite abundant resources;
- conflict/correction Skills triggered for simple performance issues or severe misconduct where formal process is more appropriate;
- systemic organization diagnosis triggered on vague low-evidence collaboration problems.

## System-router audit

- `r01`: PASS — source lookup for 《实践论》 location.
- `r02`: FAIL only on framework contract. Model chose `feedback-from-people` instead of expected `practice-knowledge-cycle`, while still including required `shishiqiushi-sigao`; semantically plausible.
- `r03`: FAIL — relevant atomic analysis selected, but request was not promoted to expected `complex-problem-solving` composite.
- `r04`: PASS — investigation-oriented method application.
- `r05`: PASS — neutral source lookup for historical context.
- `r06`: FAIL — relevant strategy atomic set selected, but request was not promoted to expected `strategy-analysis` composite.

This indicates that exact orchestration and capability coverage should be reported separately.

## Edge-case audit

- 25 edge cases remain qualitative by design.
- Originating target included in **15 / 25**.
- The other 10 frequently selected plausible neighboring Skills, so target-hit should not be treated as edge accuracy.
- One edge case used high-confidence slug normalization (`diaoccha-yanjiu` → `diaocha-yanjiu`).

## Engineering conclusion

1. **Retrieval/Evidence layer: GO.** This run exposed no API or corpus-layer failures.
2. **Router v3 final freeze: NO-GO.** Positive recall of 60% and exact system composition of 50% are not sufficient for a freeze candidate.
3. **Do not patch the 156 prompts case-by-case.** It is now the development/regression suite.
4. Router v4 should use explicit `when / avoid / contrast` profiles for all 25 Skills and enforce a specificity rule: specialized mechanisms outrank generic catch-all Skills.
5. Final acceptance must use a fresh held-out suite that was not used for routing tuning.

# Router Benchmark Policy

## Dataset roles

- `eval/atomic-routing-benchmark.generated.jsonl` + `router/routing-tests.json` currently form the 156-case **development/regression suite**.
- Run `36304488317` on MiniMax M3 / Router v3 was fully inspected. Therefore this suite is no longer an untouched final test set.
- Future Router changes may be checked against this suite for regression, but final acceptance must use a new held-out suite that was not used to tune routing rules.

## Metrics

Report these dimensions separately:

1. **Atomic trigger recall** — target Skill present on `should_trigger`.
2. **Atomic non-trigger specificity** — target Skill absent on `should_not_trigger`.
3. **System orchestration exactness** — route / framework / composite contract matches.
4. **Capability coverage** — required atomic capabilities are present even if orchestration differs.
5. **Edge audit** — qualitative review only unless an explicit edge rubric is added.
6. **Schema reliability** — API errors, repair count, slug normalization count.

Do not collapse all six dimensions into a single quality claim.

## Anti-overfitting rule

Do not add a routing rule that merely memorizes one benchmark sentence or its surface keywords. Routing changes should be justified by a Skill-level invariant such as applicability condition, exclusion condition, contrast with a neighboring Skill, specificity rule, or route/composite escalation rule.

## Current freeze rule

Router v3 is not final-freeze quality. Before a freeze candidate:

- build/activate 25 explicit routing profiles;
- rerun the 156-case regression suite;
- create a fresh held-out suite;
- run the held-out suite once before inspecting its failures;
- only then decide whether to freeze routing and proceed to Task Gain evaluation.

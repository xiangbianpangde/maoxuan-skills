# Runtime Skills v2

This directory contains compact runtime delivery cards for the 25 Atomic Skills.

The original upstream `SKILL.md` files remain the audit/source representation. They are **not** the default runtime prompt representation after Task Gain v1 showed that large raw Skill documents can crowd out task-specific engineering detail.

Each Runtime Card contains only:

- `objective`
- `trigger`
- 3–5 executable `steps`
- `checks`
- `avoid`

Rules:

1. Keep the frozen `catalog-single` Router.
2. Inject only the Atomic cards selected by the Router, maximum 4.
3. For `source_lookup`, use Retrieval/Evidence directly; do not inject methodology cards.
4. Composite context is compact and used only when the frozen Router selects a genuine composite task.
5. Runtime Cards are modern abstractions. They are not original historical text and must never be cited as such.
6. Current political persuasion/elections/voter mobilization, violence, coercion, and evasion are outside runtime transfer.
7. `eval/task_gain_v1` remains unchanged as the observed baseline; v2 uses a new frozen task suite.

Validation:

```bash
python3 scripts/validate_runtime_cards.py
python3 eval/run_task_gain_v2.py --dry-run
```

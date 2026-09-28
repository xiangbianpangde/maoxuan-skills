from __future__ import annotations
import copy, importlib, json, time

base = importlib.import_module(__package__ + ".runtime")

# Re-export the frozen v4 surface used by benchmark and validation code.
VARIANTS = base.VARIANTS
git_blob_sha = base.git_blob_sha
load_suite = base.load_suite
load_cards = base.load_cards
label_map = base.label_map
judge_system = base.judge_system
validate_judge = base.validate_judge
judge_one = base.judge_one
rb = base.rb
hb = base.hb
v3 = base.v3
legacy = base.legacy

_REQUIRED = {"objective", "primary_bottleneck", "actions", "decision_gates", "stop_or_rollback"}
_ENVELOPES = ("plan", "task_plan", "execution_plan", "result", "output", "data", "response")
_ALIASES = {
    "objective": ("goal", "goal_statement", "task_objective"),
    "primary_bottleneck": ("bottleneck", "main_bottleneck", "key_bottleneck", "primary_constraint"),
    "facts": ("known_facts", "observations"),
    "unknowns": ("uncertainties", "open_questions"),
    "actions": ("steps", "action_items", "next_actions"),
    "decision_gates": ("gates", "decision_points", "decision_criteria", "go_no_go"),
    "stop_or_rollback": ("stop_conditions", "rollback_conditions", "abort_conditions", "rollback"),
    "dependencies": ("prerequisites",),
    "assumptions": ("assumption_list",),
    "answer_focus": ("focus", "focus_points", "answer_priorities"),
}
_ACTION_ALIASES = {
    "action": ("step", "task", "action_item"),
    "actor": ("owner", "responsible", "assignee"),
    "evidence_or_metric": ("metric", "evidence", "signal", "success_metric"),
    "decision_rule": ("rule", "criterion", "decision_criterion"),
}


def _looks_like_plan(obj: object) -> bool:
    if not isinstance(obj, dict):
        return False
    keys = set(obj)
    if keys & _REQUIRED:
        return True
    aliases = {a for xs in _ALIASES.values() for a in xs}
    return bool(keys & aliases)


def _structural_normalize(plan: dict):
    """Normalize harmless envelopes and field aliases without inventing task semantics."""
    if not isinstance(plan, dict):
        return plan, []
    p = copy.deepcopy(plan)
    changes = []

    if not (set(p) & _REQUIRED):
        unwrapped = None
        unwrap_name = None
        for key in _ENVELOPES:
            value = p.get(key)
            if _looks_like_plan(value):
                unwrapped = value
                unwrap_name = key
                break
        if unwrapped is None:
            dict_values = [(k, v) for k, v in p.items() if isinstance(v, dict) and _looks_like_plan(v)]
            if len(dict_values) == 1:
                unwrap_name, unwrapped = dict_values[0]
        if unwrapped is not None:
            p = copy.deepcopy(unwrapped)
            changes.append(f"envelope:{unwrap_name}->plan")

    for canonical, aliases in _ALIASES.items():
        if canonical in p:
            continue
        for alias in aliases:
            if alias in p:
                p[canonical] = p.pop(alias)
                changes.append(f"alias:{alias}->{canonical}")
                break

    actions = p.get("actions")
    if isinstance(actions, list):
        normalized_actions = []
        for idx, item in enumerate(actions):
            if not isinstance(item, dict):
                normalized_actions.append(item)
                continue
            a = copy.deepcopy(item)
            for canonical, aliases in _ACTION_ALIASES.items():
                if canonical in a:
                    continue
                for alias in aliases:
                    if alias in a:
                        a[canonical] = a.pop(alias)
                        changes.append(f"actions[{idx}].alias:{alias}->{canonical}")
                        break
            normalized_actions.append(a)
        p["actions"] = normalized_actions

    return p, changes


def normalize_plan(plan: dict, contract: dict, policy: dict):
    p, structural_changes = _structural_normalize(plan)
    p, base_changes = base.normalize_plan(p, contract, policy)
    return p, structural_changes + base_changes


def parse_normalize_validate(text: str, contract: dict, policy: dict):
    visible, stripped = v3.sanitize_visible(text)
    try:
        raw = rb.parse_json_object(visible)
    except Exception as e:
        return None, [f"parse: {type(e).__name__}: {e}"], [], stripped
    plan, changes = normalize_plan(raw, contract, policy)
    errs = v3.validate_plan(plan, contract)
    return plan, errs, changes, stripped


def call_planner(case: dict, route: dict, cards: dict, contract: dict, policy: dict, args, with_methods: bool):
    selected = v3.selected_cards(route, cards, contract) if with_methods else []
    method_context = "\n\n".join(v3.render_card(c) for c in selected)
    user_obj = {
        "task": case["prompt"],
        "reference_requirements": case["reference_requirements"],
        "hardness_features": case.get("hardness_features", []),
    }
    user = json.dumps(user_obj, ensure_ascii=False)
    if method_context:
        user += "\n\nINTERNAL METHOD CARDS:\n" + method_context
    sysmsg = v3.planner_system(with_methods, contract)
    payloads = []
    repaired = False
    all_changes = []
    stripped_total = 0
    t = time.perf_counter()
    try:
        text, payload = rb.post_chat(
            args.base_url, args.api_key, args.model, sysmsg, user,
            args.timeout, not args.no_response_format,
        )
        payloads.append(payload)
        plan, errs, changes, stripped = parse_normalize_validate(text, contract, policy)
        all_changes.extend(changes)
        stripped_total += stripped

        if errs:
            repaired = True
            repair_payload = {
                "original_task": user_obj,
                "normalized_previous_output": plan,
                "validation_errors": errs,
                "required_top_level_keys": [
                    "objective", "facts", "unknowns", "primary_bottleneck", "actions",
                    "decision_gates", "stop_or_rollback", "dependencies", "assumptions", "answer_focus",
                ],
                "repair_instruction": (
                    "Return one complete corrected planner JSON object only. Preserve usable semantic content from the previous output, "
                    "restore every required field from the original task, and follow the planner contract exactly."
                ),
            }
            repair_user = user + "\n\n[STRICT JSON REPAIR]\n" + json.dumps(repair_payload, ensure_ascii=False)
            text, payload = rb.post_chat(
                args.base_url, args.api_key, args.model, sysmsg, repair_user,
                args.timeout, not args.no_response_format,
            )
            payloads.append(payload)
            plan, errs, changes, stripped = parse_normalize_validate(text, contract, policy)
            all_changes.extend(changes)
            stripped_total += stripped

        if errs:
            raise ValueError("; ".join(errs))
        return {
            "plan": plan,
            "selected_slugs": [c["slug"] for c in selected],
            "usage": rb.usage_total(payloads),
            "latency_s": round(time.perf_counter() - t, 3),
            "repair_attempted": repaired,
            "normalizations": all_changes,
            "reasoning_stripped_chars": stripped_total,
            "planner_context_chars": len(sysmsg) + len(user),
            "error": None,
        }
    except Exception as e:
        return {
            "plan": None,
            "selected_slugs": [c["slug"] for c in selected],
            "usage": rb.usage_total(payloads),
            "latency_s": round(time.perf_counter() - t, 3),
            "repair_attempted": repaired,
            "normalizations": all_changes,
            "reasoning_stripped_chars": stripped_total,
            "planner_context_chars": len(sysmsg) + len(user),
            "error": f"{type(e).__name__}: {e}",
        }


def answer_one(case: dict, variant: str, route: dict, schema: dict, cards: dict, contract: dict, policy: dict, args):
    if variant == "vanilla":
        ans = v3.direct_answer(case, "vanilla", route, schema, cards, args)
        ans["fallback_used"] = False
        return ans

    planner = call_planner(
        case, route, cards, contract, policy, args,
        with_methods=(variant == "method-planner"),
    )
    if planner["error"] or not planner["plan"]:
        final = v3.direct_answer(case, "vanilla", route, schema, cards, args)
        final["planner"] = planner
        final["fallback_used"] = True
        final["fallback_reason"] = planner["error"]
        final["latency_s"] = round(final["latency_s"] + planner["latency_s"], 3)
        final["reasoning_stripped_chars"] += planner["reasoning_stripped_chars"]
        return final

    final = v3.call_executor(case, planner["plan"], contract, args)
    final["planner"] = planner
    final["fallback_used"] = False
    final["latency_s"] = round(final["latency_s"] + planner["latency_s"], 3)
    final["reasoning_stripped_chars"] += planner["reasoning_stripped_chars"]
    return final

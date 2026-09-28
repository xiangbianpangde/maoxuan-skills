from __future__ import annotations
import hashlib, json, random, re, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVAL_DIR = ROOT / "eval"
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

import run_router_benchmark as rb
import run_heldout_benchmark as hb
from task_gain import runtime as legacy
from task_gain_v2 import runtime as v2

VARIANTS = ["vanilla", "compact-direct", "generic-planner", "method-planner"]
REASONING_PATTERNS = [
    re.compile(r"<think>.*?</think>", re.I | re.S),
    re.compile(r"<analysis>.*?</analysis>", re.I | re.S),
    re.compile(r"<reasoning>.*?</reasoning>", re.I | re.S),
]

def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

def load_suite():
    d = ROOT / "eval/task_gain_v3"
    freeze = json.loads((d / "TASK_GAIN_V3_FREEZE.json").read_text(encoding="utf-8"))
    rp = d / "rubric-v3.json"
    pp = ROOT / "skills/runtime/PLANNER_CONTRACT.json"
    cp = ROOT / "skills/runtime/RUNTIME_CARDS.json"
    checks = [
        (rp, freeze["rubric_git_blob"]),
        (pp, freeze["planner_contract_git_blob"]),
        (cp, freeze["runtime_cards_git_blob"]),
    ]
    for p, expected in checks:
        got = git_blob_sha(p)
        if got != expected:
            raise ValueError(f"{p} git-blob mismatch: {got} != {expected}")
    tasks = []
    for rel, expected in sorted(freeze["task_files"].items()):
        p = ROOT / rel
        got = git_blob_sha(p)
        if got != expected:
            raise ValueError(f"{p} git-blob mismatch: {got} != {expected}")
        tasks.extend(json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip())
    if len(tasks) != freeze["cases_total"]:
        raise ValueError("task count mismatch")
    if len({x["id"] for x in tasks}) != len(tasks):
        raise ValueError("duplicate task id")
    return (
        tasks,
        json.loads(rp.read_text(encoding="utf-8")),
        freeze,
        json.loads(pp.read_text(encoding="utf-8")),
    )

def load_cards():
    doc = json.loads((ROOT / "skills/runtime/RUNTIME_CARDS.json").read_text(encoding="utf-8"))
    return {x["slug"]: x for x in doc["cards"]}

def sanitize_visible(text: str) -> tuple[str, int]:
    raw = text or ""
    out = raw
    for pat in REASONING_PATTERNS:
        out = pat.sub("", out)
    low = out.lower()
    for tag in ("</think>", "</analysis>", "</reasoning>"):
        idx = low.rfind(tag)
        if idx >= 0:
            out = out[idx + len(tag):]
            low = out.lower()
    out = out.strip()
    return out, max(0, len(raw) - len(out))

def base_system() -> str:
    return """Answer the Chinese task directly and task-natively (normally <=1100 Chinese characters).
Do not expose hidden chain-of-thought; show only conclusions, observable structure, steps, checks, measurements, decision gates and stop/rollback conditions.
Do not role-play as a political or historical figure. Do not use current political persuasion, elections, voter mobilization, violence, coercion or evasion as application domains.
Preserve all user constraints. Do not invent facts or numeric thresholds. When a threshold is not derivable, specify how to calibrate it from baseline, error budget, pilot data or an explicit comparison rule.
For technical tasks, preserve domain variables, failure modes, dependencies, rollback paths and measurable acceptance evidence.
For personal-safety cases, prioritize safety, evidence preservation and appropriate formal escalation over generic private mediation."""

def render_card(card: dict) -> str:
    return "\n".join([
        f"[INTERNAL METHOD {card['runtime_name']}]",
        f"Objective: {card['objective']}",
        "Use when: " + "；".join(card["trigger"]),
        "Steps:",
        *[f"{i+1}. {s}" for i, s in enumerate(card["steps"])],
        "Checks: " + "；".join(card["checks"]),
        "Avoid: " + "；".join(card["avoid"]),
    ])

def selected_cards(route: dict, cards: dict, contract: dict) -> list[dict]:
    cap = int(contract.get("max_method_cards", 2))
    out = []
    for slug in (route.get("atomic_skills") or []):
        card = cards.get(slug)
        if card:
            out.append(card)
        if len(out) >= cap:
            break
    return out

def planner_system(with_methods: bool, contract: dict) -> str:
    schema = json.dumps(contract["planner_output_schema"], ensure_ascii=False)
    mode = (
        "You may use the supplied compact method cards as internal planning aids. Do not copy card names, historical terminology, or methodology provenance into the plan."
        if with_methods else
        "No project method cards are supplied. Build the best task-native plan from the task itself."
    )
    return f"""You are a hidden planning compiler. Return ONE JSON object only; no markdown and no chain-of-thought.
{mode}
The plan is not user-visible. Convert the task into a concrete execution/decision scaffold.
Preserve facts and conflicting evidence. Separate unknowns from facts.
Materialize actions into domain-native steps with actors, observable evidence/metrics and decision rules.
Use task-provided numbers when available. Never invent placeholder thresholds such as X/Y; when a number is unknown, specify a calibration procedure or comparative rule.
Include rollback/stop criteria when the task has material risk.
For safety-sensitive organizational cases, use proportionate formal escalation and evidence preservation.
Required JSON shape:
{schema}
Keep facts <= {contract['constraints']['facts_max']}, unknowns <= {contract['constraints']['unknowns_max']}, actions {contract['constraints']['actions_min']}-{contract['constraints']['actions_max']}, decision_gates {contract['constraints']['decision_gates_min']}-{contract['constraints']['decision_gates_max']}, stop_or_rollback {contract['constraints']['stop_or_rollback_min']}-{contract['constraints']['stop_or_rollback_max']}."""

def validate_plan(p: dict, contract: dict) -> list[str]:
    errs = []
    if not isinstance(p, dict):
        return ["not object"]
    str_fields = ["objective", "primary_bottleneck"]
    list_fields = ["facts", "unknowns", "actions", "decision_gates", "stop_or_rollback", "dependencies", "assumptions", "answer_focus"]
    for k in str_fields:
        if not isinstance(p.get(k), str) or not p.get(k, "").strip():
            errs.append(f"{k}: non-empty string required")
    for k in list_fields:
        if not isinstance(p.get(k), list):
            errs.append(f"{k}: list required")
    if errs:
        return errs
    c = contract["constraints"]
    if len(p["facts"]) > c["facts_max"]: errs.append("facts too long")
    if len(p["unknowns"]) > c["unknowns_max"]: errs.append("unknowns too long")
    if not (c["actions_min"] <= len(p["actions"]) <= c["actions_max"]): errs.append("actions count")
    if not (c["decision_gates_min"] <= len(p["decision_gates"]) <= c["decision_gates_max"]): errs.append("decision_gates count")
    if not (c["stop_or_rollback_min"] <= len(p["stop_or_rollback"]) <= c["stop_or_rollback_max"]): errs.append("stop_or_rollback count")
    if len(p["answer_focus"]) > c["answer_focus_max"]: errs.append("answer_focus too long")
    for i, a in enumerate(p["actions"]):
        if not isinstance(a, dict):
            errs.append(f"actions[{i}] not object"); continue
        for k in ("action", "actor", "evidence_or_metric", "decision_rule"):
            if not isinstance(a.get(k), str) or not a.get(k, "").strip():
                errs.append(f"actions[{i}].{k}")
    for k in ("facts", "unknowns", "decision_gates", "stop_or_rollback", "dependencies", "assumptions", "answer_focus"):
        if isinstance(p.get(k), list) and any(not isinstance(x, str) for x in p[k]):
            errs.append(f"{k}: strings only")
    return errs

def call_planner(case: dict, route: dict, cards: dict, contract: dict, args, with_methods: bool):
    selected = selected_cards(route, cards, contract) if with_methods else []
    method_context = "\n\n".join(render_card(c) for c in selected)
    user_obj = {"task": case["prompt"], "reference_requirements": case["reference_requirements"], "hardness_features": case.get("hardness_features", [])}
    user = json.dumps(user_obj, ensure_ascii=False)
    if method_context:
        user += "\n\nINTERNAL METHOD CARDS:\n" + method_context
    sysmsg = planner_system(with_methods, contract)
    payloads = []
    repaired = False
    t = time.perf_counter()
    try:
        text, p = rb.post_chat(args.base_url, args.api_key, args.model, sysmsg, user, args.timeout, not args.no_response_format)
        payloads.append(p)
        visible, stripped = sanitize_visible(text)
        plan = rb.parse_json_object(visible)
        errs = validate_plan(plan, contract)
        if errs:
            repaired = True
            repair_user = user + "\n\nPrevious planner JSON was invalid: " + json.dumps(errs, ensure_ascii=False) + "\nReturn complete corrected JSON only."
            text, p = rb.post_chat(args.base_url, args.api_key, args.model, sysmsg, repair_user, args.timeout, not args.no_response_format)
            payloads.append(p)
            visible2, stripped2 = sanitize_visible(text)
            stripped += stripped2
            plan = rb.parse_json_object(visible2)
            errs = validate_plan(plan, contract)
        if errs:
            raise ValueError("; ".join(errs))
        return {"plan": plan, "selected_slugs": [c["slug"] for c in selected], "usage": rb.usage_total(payloads), "latency_s": round(time.perf_counter() - t, 3), "repair_attempted": repaired, "reasoning_stripped_chars": stripped, "planner_context_chars": len(sysmsg) + len(user), "error": None}
    except Exception as e:
        return {"plan": None, "selected_slugs": [c["slug"] for c in selected], "usage": rb.usage_total(payloads), "latency_s": round(time.perf_counter() - t, 3), "repair_attempted": repaired, "reasoning_stripped_chars": 0, "planner_context_chars": len(sysmsg) + len(user), "error": f"{type(e).__name__}: {e}"}

def executor_system(contract: dict) -> str:
    rules = "\n".join("- " + x for x in contract["executor_rules"])
    return base_system() + "\n\nYou receive a hidden task-native execution plan, not authoritative facts. Use it as a scaffold and answer the original task directly.\n" + rules

def call_executor(case: dict, plan: dict, contract: dict, args):
    sysmsg = executor_system(contract)
    user = case["prompt"] + "\n\n[INTERNAL TASK-NATIVE PLAN]\n" + json.dumps(plan, ensure_ascii=False)
    t = time.perf_counter()
    try:
        text, p = rb.post_chat(args.base_url, args.api_key, args.model, sysmsg, user, args.timeout, False)
        visible, stripped = sanitize_visible(text)
        return {"text": visible, "usage": p.get("usage"), "latency_s": round(time.perf_counter() - t, 3), "system_chars": len(sysmsg), "executor_input_chars": len(user), "reasoning_stripped_chars": stripped, "error": None}
    except Exception as e:
        return {"text": "", "usage": None, "latency_s": round(time.perf_counter() - t, 3), "system_chars": len(sysmsg), "executor_input_chars": len(user), "reasoning_stripped_chars": 0, "error": f"{type(e).__name__}: {e}"}

def direct_answer(case: dict, variant: str, route: dict, schema: dict, cards: dict, args):
    base = base_system()
    if variant == "vanilla":
        sysmsg = base + "\nNo project-specific methodology context is available."
    elif variant == "compact-direct":
        compact = v2.compact_context(route, cards)
        sysmsg = base + "\nUse the supplied compact method card(s) only as internal execution guidance. Do not name the cards. Preserve task-native technical detail."
        if compact:
            sysmsg += "\n\n" + compact
        else:
            sysmsg += "\nNo compact method card was selected."
    else:
        raise ValueError(variant)
    t = time.perf_counter()
    try:
        text, p = rb.post_chat(args.base_url, args.api_key, args.model, sysmsg, case["prompt"], args.timeout, False)
        visible, stripped = sanitize_visible(text)
        return {"text": visible, "usage": p.get("usage"), "latency_s": round(time.perf_counter() - t, 3), "system_chars": len(sysmsg), "executor_input_chars": len(case["prompt"]), "reasoning_stripped_chars": stripped, "planner": None, "error": None}
    except Exception as e:
        return {"text": "", "usage": None, "latency_s": round(time.perf_counter() - t, 3), "system_chars": len(sysmsg), "executor_input_chars": len(case["prompt"]), "reasoning_stripped_chars": 0, "planner": None, "error": f"{type(e).__name__}: {e}"}

def answer_one(case: dict, variant: str, route: dict, schema: dict, cards: dict, contract: dict, args):
    if variant in {"vanilla", "compact-direct"}:
        return direct_answer(case, variant, route, schema, cards, args)
    with_methods = variant == "method-planner"
    planner = call_planner(case, route, cards, contract, args, with_methods=with_methods)
    if planner["error"] or not planner["plan"]:
        return {"text": "", "usage": None, "latency_s": planner["latency_s"], "system_chars": 0, "executor_input_chars": 0, "reasoning_stripped_chars": planner["reasoning_stripped_chars"], "planner": planner, "error": "planner_failed: " + str(planner["error"])}
    final = call_executor(case, planner["plan"], contract, args)
    final["planner"] = planner
    final["latency_s"] = round(final["latency_s"] + planner["latency_s"], 3)
    final["reasoning_stripped_chars"] += planner["reasoning_stripped_chars"]
    return final

def label_map(task_id: str) -> dict:
    vs = list(VARIANTS)
    random.Random(int(hashlib.sha256(("v3:" + task_id).encode()).hexdigest()[:16], 16)).shuffle(vs)
    return dict(zip("ABCD", vs))

def judge_system(rubric: dict) -> str:
    dims = "\n".join(f"- {k}: {v}" for k, v in rubric["dimensions"].items())
    anc = "\n".join(f"- {k}: {v}" for k, v in rubric["anchors"].items())
    row = '{"factual_correctness":0,"method_fit":0,"analysis_structure":0,"actionability":0,"evidence_fidelity":0,"boundary_compliance":0,"overall_utility":0}'
    policy = "\n".join("- " + x for x in rubric.get("judge_policy", []))
    return f"""You are a blinded evaluator. Judge only the visible final answer; never request or reward hidden chain-of-thought.
Do not infer which answer used planning or project methods. Do not reward methodology names, historical language, verbosity, or extra structure by itself.
Score task-native decision quality, correctness, constraint handling, executable detail, evidence discipline, and calibrated uncertainty.
Judge policy:
{policy}
Dimensions:
{dims}
Integer score anchors 0-4:
{anc}
Return JSON only:
{{"scores":{{"A":{row},"B":{row},"C":{row},"D":{row}}},"best_labels":["A"],"notes":{{"A":"","B":"","C":"","D":""}}}}"""

def validate_judge(parsed: dict, rubric: dict):
    out = {}
    errs = []
    dims = set(rubric["dimensions"])
    for lab in "ABCD":
        row = (parsed.get("scores") or {}).get(lab)
        if not isinstance(row, dict):
            errs.append(f"missing {lab}")
            continue
        clean = {}
        for d in dims:
            v = row.get(d)
            if not isinstance(v, (int, float)) or not 0 <= v <= 4:
                errs.append(f"invalid {lab}.{d}")
            else:
                clean[d] = float(v)
        out[lab] = clean
    return out, errs

def judge_one(case: dict, answers: dict, rubric: dict, args):
    mapping = label_map(case["id"])
    anon = {lab: answers[v]["text"] for lab, v in mapping.items()}
    prompt = json.dumps({"task": case["prompt"], "reference_requirements": case["reference_requirements"], "hardness_features": case["hardness_features"], "dimension_weights": case["weights"], "answers": anon}, ensure_ascii=False)
    sysmsg = judge_system(rubric)
    payloads = []
    t = time.perf_counter()
    model = args.judge_model or args.model
    repaired = False
    try:
        text, p = rb.post_chat(args.base_url, args.api_key, model, sysmsg, prompt, args.timeout, not args.no_response_format)
        payloads.append(p)
        visible, _ = sanitize_visible(text)
        parsed = rb.parse_json_object(visible)
        scores, errs = validate_judge(parsed, rubric)
        if errs:
            repaired = True
            rp = prompt + "\nPrevious judge JSON invalid: " + json.dumps(errs, ensure_ascii=False) + ". Return complete corrected JSON only."
            text, p = rb.post_chat(args.base_url, args.api_key, model, sysmsg, rp, args.timeout, not args.no_response_format)
            payloads.append(p)
            visible, _ = sanitize_visible(text)
            parsed = rb.parse_json_object(visible)
            scores, errs = validate_judge(parsed, rubric)
        if errs:
            raise ValueError("; ".join(errs))
        return {"label_map": mapping, "scores": scores, "best_labels": parsed.get("best_labels") or [], "notes": parsed.get("notes") or {}, "judge_model": model, "usage": rb.usage_total(payloads), "repair_attempted": repaired, "latency_s": round(time.perf_counter() - t, 3), "error": None}
    except Exception as e:
        return {"label_map": mapping, "scores": {}, "best_labels": [], "notes": {}, "judge_model": model, "usage": rb.usage_total(payloads), "repair_attempted": repaired, "latency_s": round(time.perf_counter() - t, 3), "error": f"{type(e).__name__}: {e}"}

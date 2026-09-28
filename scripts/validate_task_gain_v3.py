#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASK_DIR = ROOT / "eval/task_gain_v3/tasks"
RUBRIC = ROOT / "eval/task_gain_v3/rubric-v3.json"
CONTRACT = ROOT / "skills/runtime/PLANNER_CONTRACT.json"
CARDS = ROOT / "skills/runtime/RUNTIME_CARDS.json"
V2_TASKS = ROOT / "eval/task_gain_v2/tasks-v2.jsonl"

EXPECTED_CATS = {
    "research-decision": 9,
    "engineering-project": 9,
    "organization": 9,
    "learning-strategy": 9,
}


def main():
    tasks=[]
    for p in sorted(TASK_DIR.glob("*.jsonl")):
        tasks.extend(json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip())
    rubric=json.loads(RUBRIC.read_text(encoding="utf-8"))
    contract=json.loads(CONTRACT.read_text(encoding="utf-8"))
    cards=json.loads(CARDS.read_text(encoding="utf-8"))
    old={json.loads(x)["id"] for x in V2_TASKS.read_text(encoding="utf-8").splitlines() if x.strip()}

    assert len(tasks)==36, len(tasks)
    ids=[t["id"] for t in tasks]
    assert len(set(ids))==len(ids)
    assert not (set(ids)&old), "v3 task IDs overlap v2"
    counts={k:0 for k in EXPECTED_CATS}
    for t in tasks:
        assert t["category"] in EXPECTED_CATS, t["category"]
        counts[t["category"]]+=1
        assert len(t.get("prompt",""))>=120, t["id"]
        assert len(t.get("reference_requirements",""))>=30, t["id"]
        assert len(t.get("hardness_features") or [])>=5, t["id"]
        assert len(set(t["hardness_features"]))==len(t["hardness_features"]), t["id"]
        assert abs(sum(float(x) for x in t["weights"].values())-1.0)<1e-9, t["id"]
        assert set(t["weights"])==set(rubric["dimensions"]), t["id"]
    assert counts==EXPECTED_CATS, counts

    assert contract["max_method_cards"]==2
    c=contract["constraints"]
    assert 3<=c["actions_min"]<=c["actions_max"]<=7
    assert c["decision_gates_min"]>=1
    assert c["stop_or_rollback_min"]>=1

    slugs=[x["slug"] for x in cards["cards"]]
    assert len(slugs)==25 and len(set(slugs))==25

    assert rubric["primary"]["overall_success_rule"]
    cps=rubric["primary"]["co_primary"]
    assert len(cps)==2
    assert "method-planner_vs_vanilla" in cps[0]["comparison"]
    assert "method-planner_vs_generic-planner" in cps[1]["comparison"]

    print(json.dumps({
        "ok":True,
        "tasks":len(tasks),
        "categories":counts,
        "unique_hardness_features":len({x for t in tasks for x in t["hardness_features"]}),
        "max_method_cards":contract["max_method_cards"],
        "runtime_cards":len(slugs),
    },ensure_ascii=False))


if __name__=="__main__":
    main()

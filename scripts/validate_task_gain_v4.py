#!/usr/bin/env python3
from __future__ import annotations
import json, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT/"eval") not in sys.path:sys.path.insert(0,str(ROOT/"eval"))
from task_gain_v4 import runtime as v4

ALLOWED_TAGS={"conflicting_evidence","resource_constraint","uncertainty","multi_objective","rollback","feedback_loop","measurement_noise","distribution_shift","dependency","phase_change","safety_or_compliance","time_pressure"}

def main():
    tasks,rubric,freeze,contract,policy=v4.load_suite(); assert len(tasks)==32; assert len({t["id"] for t in tasks})==32
    counts={}
    for t in tasks:
        counts[t["category"]]=counts.get(t["category"],0)+1; assert len(t["prompt"])>=90,t["id"]; assert len(t["reference_requirements"])>=25,t["id"]
        tags=t["hardness_features"]; assert 4<=len(tags)<=6,(t["id"],tags); assert set(tags)<=ALLOWED_TAGS,(t["id"],set(tags)-ALLOWED_TAGS); assert len(set(tags))==len(tags)
        assert abs(sum(float(x) for x in t["weights"].values())-1.0)<1e-9; assert set(t["weights"])==set(rubric["dimensions"])
    assert counts=={"research-decision":8,"engineering-project":8,"organization":8,"learning-strategy":8},counts
    old=[]
    for p in (ROOT/"eval/task_gain_v3/tasks").glob("*.jsonl"):old.extend(json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip())
    assert not ({t["id"] for t in tasks}&{t["id"] for t in old})
    assert policy["heldout_policy"]["fresh_cases"]==32; assert policy["heldout_policy"]["variants"]==v4.VARIANTS; assert policy["fail_open"]["enabled"] is True; assert policy["fail_open"]["fallback"]=="vanilla"; assert contract["max_method_cards"]==2

    sample={"objective":"o","facts":["f"]*10,"unknowns":[],"primary_bottleneck":"b","actions":[{"action":"a1","actor":"x","evidence_or_metric":"m","decision_rule":"r"},{"action":"a2","actor":"x","evidence_or_metric":"m","decision_rule":"r"},{"action":"a3","actor":"x","evidence_or_metric":"m","decision_rule":"r"}],"decision_gates":["g"],"stop_or_rollback":["s"],"dependencies":[],"assumptions":[],"answer_focus":"focus"}
    norm,changes=v4.normalize_plan(sample,contract,policy); assert norm["answer_focus"]==["focus"]; assert len(norm["facts"])==contract["constraints"]["facts_max"]; assert "answer_focus:string->list" in changes; assert not v4.v3.validate_plan(norm,contract)

    wrapped={"result":{"goal":"o","known_facts":"f","open_questions":"u","bottleneck":"b","steps":[{"step":"a1","owner":"x","metric":"m1","rule":"r1"},{"step":"a2","owner":"x","metric":"m2","rule":"r2"},{"step":"a3","owner":"x","metric":"m3","rule":"r3"}],"gates":"g","rollback_conditions":"s","focus":"focus"}}
    norm2,changes2=v4.normalize_plan(wrapped,contract,policy)
    assert not v4.v3.validate_plan(norm2,contract),(norm2,v4.v3.validate_plan(norm2,contract))
    assert "envelope:result->plan" in changes2
    assert "alias:goal->objective" in changes2
    assert "alias:steps->actions" in changes2
    assert "actions[0].alias:step->action" in changes2

    p=rubric["primary"]; assert p["planning_hypothesis"]["comparison"]=="generic-planner_vs_vanilla"; assert p["method_increment_hypothesis"]["comparison"]=="method-planner_vs_generic-planner"
    print(json.dumps({"ok":True,"tasks":len(tasks),"categories":counts,"allowed_tags":len(ALLOWED_TAGS),"fail_open":True,"runtime_cards_git_blob":freeze["runtime_cards_git_blob"],"structural_normalization":True},ensure_ascii=False))

if __name__=="__main__":main()

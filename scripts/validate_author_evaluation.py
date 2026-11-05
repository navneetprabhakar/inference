"""Validate authored v2 development/confirmation without decoding confirmation."""
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/author-review-v3"
DEV, CONFIRM = DATA / "development-cases.jsonl", DATA / "confirmation-cases.jsonl"
OUT = ROOT / "reports/author-review-v1/evaluation-preparation.json"

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path): return [json.loads(x) for x in path.read_text().splitlines() if x]
def words(case): return set(re.findall(r"[a-z0-9]+", " ".join(m["content"].casefold() for m in case["messages"] if m["role"] == "user")))
def validate(rows):
    errors=[]
    for row in rows:
        if row.get("authorship") != "assistant_authored_not_independent_benchmark" or row.get("kind") not in {"prose","tool"} or not row.get("id") or not isinstance(row.get("messages"),list): errors.append([row.get("id"),"shape/authorship"]); continue
        if row["kind"] == "prose" and not row.get("rubric"): errors.append([row["id"],"missing prose rubric"])
        if row["kind"] == "tool":
            if "calls" not in row or not row.get("expected_answer"): errors.append([row["id"],"missing executable tool specification"])
            for call in row.get("calls",[]):
                if set(call) != {"name","arguments"}: errors.append([row["id"],"tool call shape"])
    return errors
def main():
    dev, confirm = load(DEV), load(CONFIRM); errors = validate(dev) + validate(confirm)
    overlap_ids=set(x["id"] for x in dev)&set(x["id"] for x in confirm); lexical=[]
    for d in dev:
        for c in confirm:
            a,b=words(d),words(c); score=len(a&b)/max(1,len(a|b))
            if score >= .72: lexical.append({"development":d["id"],"confirmation":c["id"],"word_jaccard":score})
    families=set(x["family"] for x in dev); confirmation_families=set(x["family"] for x in confirm)
    report={"kind":"versioned_assistant_authored_evaluation_preparation_not_independent_benchmark","development":{"path":str(DEV.relative_to(ROOT)),"sha256":sha(DEV),"cases":len(dev),"families":dict(Counter(x["family"] for x in dev)),"decoder_selection_allowed":True},"confirmation":{"path":str(CONFIRM.relative_to(ROOT)),"sha256":sha(CONFIRM),"cases":len(confirm),"families":dict(Counter(x["family"] for x in confirm)),"frozen":True,"decoder_selection_allowed":False},"legacy_12_case_confirmation":{"path":"data/author-review-v1/confirmation-cases.jsonl","untouched":True,"not_read_by_this_validator":True},"disjoint_ids":not overlap_ids,"overlapping_ids":sorted(overlap_ids),"high_lexical_overlap_pairs":lexical,"validation_errors":errors,"rubrics":{"prose":"case-level grounding, meaning, instruction, continuity, ambiguity, or abstention checks plus reviewer judgement; substring checks are diagnostic evidence only, not semantic correctness.","tools":"model-driven turns until final answer or bounded turn limit; strict ordered expected call name and exact argument object; fixtures execute only for exact permitted calls; final answer scored separately."},"known_limitations":["Both suites are assistant-authored evaluation artifacts, not independently authored benchmarks.","Automated prose checks cannot establish naturalness, factual correctness, or robust instruction following; review actual outputs.","No confirmation case may be used for decoder selection."]}
    report["gates_passed"] = len(dev)>=120 and len(confirm)>=120 and not errors and not overlap_ids and not lexical and families==confirmation_families
    OUT.write_text(json.dumps(report,indent=2)+"\n"); print(json.dumps(report,indent=2))
if __name__ == "__main__": main()

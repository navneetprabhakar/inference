"""Build a bounded, provenance-preserving curriculum for the eight-hour goal.

It reuses only prior GPT-reviewed multi-turn keeps and adds distinct executable
local fixture trajectories.  It intentionally does not use the failed v1
templates, the partial candidate, or sealed evaluation text.
"""
import hashlib, json, random
from collections import Counter
from pathlib import Path
import numpy as np
from tokenizers import Tokenizer
from sft_common import ROOT, call_text, encode_episode, execute, result_answer, system

OUT = ROOT / "data/eight-hour-improvement-v3-reviewed"
SRC = ROOT / "data/author-review-v1/reviewed-candidate.jsonl"
EVAL = ROOT / "data/eight-hour-improvement-v1/evaluation-v3-corrected-r2"
SEED = 20261102

def digest(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def norm(s): return ' '.join(''.join(c.lower() if c.isalnum() else ' ' for c in s).split())

def main():
    if OUT.exists() and any(OUT.iterdir()): raise RuntimeError("refusing to overwrite frozen curriculum")
    source=[json.loads(x) for x in SRC.read_text().splitlines() if x]
    rows=[]
    for r in source:
        if r["source"].get("assistant_review_status") != "keep": continue
        rows.append({"id":"reviewed-"+r["id"],"family":"reviewed_multiturn_dialogue","messages":r["messages"],"provenance":{"kind":"prior_gpt_reviewed_keep","source":str(SRC.relative_to(ROOT)),"source_id":r["id"],"reviewer":"gpt-5.6-terra","independent_human_review":False}})
    reviewed=len(rows)
    # 250 distinct exact tool episodes; arguments and fixture results are
    # computed locally and stored rather than invented by a teacher.
    cities=["Pune","Kochi","Jaipur","Bengaluru","Delhi","Chennai","Surat","Indore","Mysuru","Nagpur"]
    topics=["budget review","design sync","travel plan","book club","dentist reminder","team lunch","project handoff","garden list","release notes","invoice followup"]
    for i in range(250):
        kind=i%5
        if kind==0:
            op=["add","subtract","multiply","divide"][(i//5)%4]; a=13+(i*17)%137; b=2+(i*9)%29
            if op=="divide": a=b*(2+i%11)
            call={"name":"calculate","arguments":{"op":op,"a":a,"b":b}}; q=f"Use the calculator for {a} {op} {b}, then report the exact result."
        elif kind==1:
            f,t=[("m","cm"),("cm","m"),("km","m"),("m","km")][(i//5)%4]; v=1+(i*19)%997
            call={"name":"convert","arguments":{"value":v,"from_unit":f,"to_unit":t}}; q=f"Use conversion to change {v} {f} into {t}, then state the converted measurement."
        elif kind==2:
            city=cities[(i//5)%len(cities)]; call={"name":"get_weather","arguments":{"city":city}}; q=f"Check the local test weather fixture for {city} and report its returned conditions."
        elif kind==3:
            ident=f"SKU-{100+(i*37)%900}"; call={"name":"lookup_item","arguments":{"item_id":ident}}; q=f"Look up {ident} with the local item fixture and report its price and stock."
        else:
            topic=topics[(i//5)%len(topics)]; call={"name":"search_notes","arguments":{"query":topic}}; q=f"Search the local notes fixture for {topic} and report the returned note."
        result=execute(call)
        rows.append({"id":f"local-fixture-{i:03d}","family":"deterministic_local_tool_trajectory","messages":[{"role":"system","content":system()},{"role":"user","content":q},{"role":"assistant","content":call_text(call)},{"role":"tool","content":json.dumps(result,separators=(",",":"))},{"role":"assistant","content":result_answer(call,result)}],"provenance":{"kind":"programmatic_exact_local_fixture","generator":"prepare_eight_hour_reviewed_curriculum.py","fixture_result":result}})
    # Exact opening-string guard against both frozen splits.  This is a
    # conservative leakage check, not a claim of semantic independence.
    eval_openings={norm(json.loads(x)["turns"][0]["user"]) for p in [EVAL/"development.jsonl",EVAL/"confirmation.jsonl"] for x in p.read_text().splitlines() if x}
    leaked=[r["id"] for r in rows if norm(next(m["content"] for m in r["messages"] if m["role"]=="user")) in eval_openings]
    if leaked: raise RuntimeError("evaluation opening overlap: "+",".join(leaked[:5]))
    tok=Tokenizer.from_file(str(ROOT/"data/sft-v3/tokenizer.json")); kept=[]; ids=[]; masks=[]; lengths=[]
    for r in rows:
        e=encode_episode(tok,r["messages"])
        if e is None: continue
        a,b,n=e; kept.append(r); ids.append(a); masks.append(b); lengths.append(n)
    OUT.mkdir(parents=True)
    (OUT/"records.jsonl").write_text(''.join(json.dumps(r,ensure_ascii=False,separators=(",",":"))+"\n" for r in kept))
    np.savez_compressed(OUT/"episodes.npz",ids=np.stack(ids),mask=np.stack(masks),length=np.array(lengths,np.int32))
    order=list(range(len(kept))); random.Random(SEED).shuffle(order)
    (OUT/"order.json").write_text(json.dumps({"seed":SEED,"epochs":1,"order":order})+"\n")
    targets=Counter(); families=Counter()
    for r,m in zip(kept,masks): families[r["family"]]+=1; targets[r["family"]]+=int(m.sum())
    manifest={"kind":"eight_hour_reviewed_distinct_curriculum","records":len(kept),"reviewed_multiturn_records":reviewed,"distinct_programmatic_tool_records":250,"families":dict(families),"supervised_tokens_by_family":dict(targets),"evaluation_opening_overlap":0,"seed":SEED,"tokenizer_sha256":digest(ROOT/"data/sft-v3/tokenizer.json"),"records_sha256":digest(OUT/"records.jsonl"),"episodes_sha256":digest(OUT/"episodes.npz"),"order_sha256":digest(OUT/"order.json"),"provenance":"Reviewed keeps were prior current-auth GPT CLI-reviewed dialogues. Tool trajectories are deterministic local fixtures, separately labelled. No confirmation content was used in selection."}
    (OUT/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(json.dumps(manifest,indent=2))
if __name__ == "__main__": main()

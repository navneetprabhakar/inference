"""Compare the running preview code on a separately pinned directional-operation regression."""
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import torch
from assistant_preview import Chat
from serve_chat import CPUGuard,ROOT,load_student,resolve_weights
from tokenizer import load

DIR=ROOT/"reports/explicit-command-order-v2"
PIN="5bdbbe2f9a7cfe70b284b9b96414bf6bb5fb3f7c0e17f9e5cbb63f23bf1df90c"


def run(stage):
    if stage not in ("before","after","after-final","release-check","frozen"):raise ValueError("expected before or after")
    raw=(DIR/"cases.json").read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PIN:raise ValueError("regression suite changed")
    path=DIR/(stage+".json")
    if path.exists():raise ValueError("stage already recorded")
    torch.set_num_threads(1)
    weights,sha=resolve_weights(None,None,ROOT/"reports/working-chat/conversation-preview.json")
    model=load_student(weights,sha,"cpu")
    tokenizer=load()
    rows=[]
    for case in json.loads(raw)["cases"]:
        chat=Chat(model,tokenizer,CPUGuard())
        if case["prior"] is not None:
            call={"name":"calculate","arguments":{"op":"add","a":3,"b":11}}
            fixture={"error":"synthetic outage"} if case["prior"]=="error" else {"result":case["prior"]}
            chat.session.start_turn(permit_calls=True,fixture_for=call,fixture=fixture)
            chat.session.propose(json.dumps(call),assistant_call_boundary=True)
        result=chat.turn(case["user"],permit_calls=case["permit"])
        answer=result["answer"] or ""
        trace=result["trace"]
        norm=answer.strip().casefold()
        goal=case["outcome"]
        ok=not trace
        if goal=="subtract":
            args={"op":"subtract","a":case["a"],"b":case["b"]}
            try:
                ok=(len(trace)==1 and trace[0].get("name")=="calculate" and trace[0].get("arguments")==args
                    and trace[0]["ok"] and math.isclose(float(answer),trace[0]["data"]["result"]))
            except (ValueError,TypeError):
                ok=False
        elif goal=="denied":ok=ok and any(w in norm for w in ("permit","disabled","prohibit","not allowed","off for this turn"))
        elif goal=="missing_prior":ok=ok and any(w in norm for w in ("no successful","no verified","no numeric result"))
        elif goal=="clarify":ok=ok and any(w in norm for w in ("specify","clarify","starting amount","which amount","operands"))
        elif goal=="expression":ok=ok and re.fullmatch(r'44\s*(?:-|−|minus)\s*17[.]?',norm) is not None
        elif goal=="unavailable":ok=ok and any(w in norm for w in ("unavailable","no live","only","cannot","can't"))
        elif goal!="no_call":raise ValueError(goal)
        ok=bool(ok and (goal=="no_call" or not result["failure"]))
        rows.append(dict(id=case["id"],outcome=goal,passed=ok,answer=result["answer"],trace=trace,frames=result["frames"],
                         frame_origins=result["frame_origins"],failure=result["failure"]))
    summary=dict(stage=stage,suite_sha256=PIN,source_sha256=hashlib.sha256((ROOT/"explicit_command_chat.py").read_bytes()).hexdigest(),checkpoint_sha256=sha,device="cpu",
                 passed=sum(r["passed"] for r in rows),total=len(rows),rows=rows)
    path.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(stage,summary["passed"],"/",summary["total"],flush=True)
    print([r["id"] for r in rows if not r["passed"]])


def compound_smoke():
    from assistant_preview import Chat
    torch.set_num_threads(1)
    weights,sha=resolve_weights(None,None,ROOT/"reports/working-chat/conversation-preview.json")
    m=load_student(weights,sha,"cpu")
    tok=load()
    call={"name":"calculate","arguments":{"op":"add","a":29,"b":8}}
    rows=[]
    for value in (41,-10):
        for reverse in (False,True):
            c=Chat(m,tok,CPUGuard())
            second="subtract the observed sum from seven" if reverse else "subtract seven from the observed sum"
            q="First add 29 and 8. Next "+second+"."
            r=c.turn(q,True,call,{"result":value})
            a,b=(7,value) if reverse else (value,7)
            ok=(len(r["trace"])==2 and r["trace"][0]["data"]["result"]==value
                and r["trace"][1].get("arguments")=={"op":"subtract","a":a,"b":b}
                and r["trace"][1].get("ok") and r["answer"]==str(a-b))
            rows.append(dict(user=q,fixture=value,passed=ok,answer=r["answer"],trace=r["trace"],origins=r["frame_origins"]))
    for q in ("First add 29 and 8. Next calculate the difference between the earlier amount and seven.",
              "Please deduct 13 centimetres from a wooden strip of 7 metres."):
        r=Chat(m,tok,CPUGuard()).turn(q)
        rows.append(dict(user=q,passed=not r["trace"] and "specify" in (r["answer"] or "").lower(),
                         trace=r["trace"],answer=r["answer"]))
    r=Chat(m,tok,CPUGuard()).turn("First add 29 and 8. Next subtract seven from the observed sum.",True,call,{"error":"test outage"})
    rows.append(dict(user="same two-step request with first-call outage",trace=r["trace"],answer=r["answer"],
                     passed=len(r["trace"])==1 and not r["trace"][0]["ok"] and "test outage" in (r["answer"] or "")))
    out=dict(scope="Separate compound integration checks, not a before/after quality estimate",checkpoint_sha256=sha,
             passed=sum(bool(x["passed"]) for x in rows),total=len(rows),rows=rows)
    out["source_sha256"]=hashlib.sha256((ROOT/"explicit_command_chat.py").read_bytes()).hexdigest()
    target=DIR/f"compound-{out['source_sha256'][:12]}.json"
    with target.open("x") as stream:json.dump(out,stream,indent=2,ensure_ascii=False)
    print("compound",out["passed"],"/",out["total"])
    assert out["passed"]==out["total"]


if __name__=="__main__":
    if sys.argv[1]=="compound":compound_smoke()
    else:run(sys.argv[1])

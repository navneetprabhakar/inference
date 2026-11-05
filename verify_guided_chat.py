"""Exercise the explicit guided workflow with the pinned local student and real broker."""
from pathlib import Path
import json

import torch

from checkpoint import checksum
from guided_chat import Chat
from serve_chat import CPUGuard, PREVIEW_PIN, resolve_weights, load_student
from slot_dialogue_head import model_size
from tokenizer import load

HOST = "host/guided-typed-serialization"
LEARNED = "learned-dialogue-act/guided-typed-serialization"


def check():
    torch.set_num_threads(1)
    weights,pin=resolve_weights(None,None,PREVIEW_PIN)
    model=load_student(weights,pin,"cpu")
    tok=load()
    checks=[]
    def session():return Chat(model,tok,CPUGuard())
    def idle(c,msg,permit=True):
        out=c.turn(msg,permit_calls=permit)
        assert not out["failure"] and not out["trace"],(msg,out)
        return out
    def observed(c,text,expected,value,origin=HOST,fixture=None):
        kwargs={"fixture_for":expected,"fixture":fixture} if fixture is not None else {}
        out=c.turn(text,permit_calls=True,**kwargs)
        assert out["failure"] is None and len(out["trace"])==1,(text,out)
        event=out["trace"][0]
        assert event["name"]==expected["name"] and event["ok"]
        assert event["data"]["result"]==value and out["answer"]==str(value),(text,out)
        body=json.loads(out["frames"][0])
        assert body=={"call":expected},(text,body)
        assert out["frame_origins"]==[origin,"host/observed-number"],out["frame_origins"]
        assert c._chat.guide is None
        return out

    c=session()
    assert "Choose" in idle(c,"/calculate",False)["answer"]
    assert "3" in idle(c,"divide by 3",False)["answer"]
    proposal={"name":"calculate","arguments":{"op":"divide","a":12,"b":3}}
    observed(c,"12",proposal,109,fixture={"result":109})
    checks.append("disabled opener and partial, enabled completion executes immediately; fixture 109 rather than arithmetic 4")

    c=session()
    idle(c,"/convert",False);idle(c,"to minutes",False);idle(c,"from hours",False)
    ready=idle(c,"2",False)
    assert "go ahead" in ready["answer"] and c._chat.guide.suspended
    idle(c,"go ahead",False)
    p={"name":"convert","arguments":{"value":2,"from":"h","to":"min"}}
    observed(c,"go ahead",p,118,fixture={"result":118})
    checks.append("disabled complete request retains known fields; disabled go-ahead cannot run; explicit enabled go-ahead uses observed 118")

    c=session();idle(c,"/calculate",False);idle(c,"multiply 3 and 4",False)
    assert not c._chat.guide.request.missing
    r=idle(c,"9")
    assert "cleared" in r["answer"] and not c._chat.guide.request.values
    idle(c,"go ahead")
    assert not c.session.trace
    checks.append("unlabelled edit to a ready suspended request clears both operands before any resume")

    c=session()
    idle(c,"/convert");idle(c,"from metres")
    out=idle(c,"to seconds")
    assert "different things" in out["answer"] and "to" not in c._chat.guide.request.values
    idle(c,"3")
    observed(c,"centimetres",{"name":"convert","arguments":{"from":"m","to":"cm","value":3}},300)
    checks.append("incompatible unit never dispatched; corrected target unit executes once")

    c=session()
    idle(c,"/convert");idle(c,"to metres")
    observed(c,"0.25 km",{"name":"convert","arguments":{"value":0.25,"from":"km","to":"m"}},250)
    c=session()
    idle(c,"/convert");idle(c,"from hours");idle(c,"to minutes")
    observed(c,"1.5",{"name":"convert","arguments":{"value":1.5,"from":"h","to":"min"}},90)
    checks.append("source-only and target-only fragments preserve both unit directions")

    c=session();idle(c,"/convert");idle(c,"2 hours")
    idle(c,"The source is days")
    assert c._chat.guide.request.values=={"value":2,"from":"day"}
    observed(c,"The target is hours",{"name":"convert","arguments":{"value":2,"from":"day","to":"h"}},48)
    c=session();idle(c,"/convert");idle(c,"to minutes")
    observed(c,"from 2 hours",{"name":"convert","arguments":{"value":2,"from":"h","to":"min"}},120)
    checks.append("explicit source/destination language cannot populate the opposite slot, even with an intervening amount")

    c=session();idle(c,"/convert");idle(c,"3 hours")
    idle(c,"Not seconds.")
    assert not c._chat.guide.request.values
    idle(c,"go ahead")
    assert not c.session.trace
    checks.append("negated single field is neither supplied nor used for a stale call")

    c=session()
    idle(c,"/convert");idle(c,"2 kg")
    idle(c,"Actually use grams instead of kilograms")
    assert c._chat.guide.request.values=={"value":2,"from":"g"}
    observed(c,"to kilograms",{"name":"convert","arguments":{"value":2,"from":"g","to":"kg"}},0.002)
    checks.append("explicit unit replacement updates existing source rather than filling missing target")

    c=session()
    idle(c,"/calculate");idle(c,"add 7")
    idle(c,"Use 11 in place of 7")
    assert c._chat.guide.request.values=={"a":11}
    observed(c,"3",{"name":"calculate","arguments":{"op":"add","a":11,"b":3}},14)
    checks.append("explicit in-place revision overrides learned supply and preserves the missing operand")

    c=session()
    idle(c,"/calculate");idle(c,"divide by 4")
    r=idle(c,"Replace 77 with 12")
    assert "cleared" in r["answer"] and not c._chat.guide.request.values
    idle(c,"20")
    assert c._chat.guide.request.values=={"a":20}
    observed(c,"5",{"name":"calculate","arguments":{"op":"divide","a":20,"b":5}},4)
    checks.append("unresolved correction clears all obsolete values; no stale divisor execution")

    c=session()
    idle(c,"/calculate");idle(c,"subtract -5")
    observed(c,"starting number is -2",{"name":"calculate","arguments":{"op":"subtract","a":-2,"b":-5}},3)
    c=session();idle(c,"/calculate")
    observed(c,"divide -6 by -3",{"name":"calculate","arguments":{"op":"divide","a":-6,"b":-3}},2)
    checks.append("negative partial and complete arithmetic use signed operands in the correct order")

    c=session()
    idle(c,"/calculate");select=idle(c,"I need the product of two quantities.")
    assert select["frame_origins"]==["learned-dialogue-act/host-guided-prompt"]
    idle(c,"3")
    observed(c,"-2",{"name":"calculate","arguments":{"op":"multiply","a":3,"b":-2}},-6,origin=LEARNED)
    assert model_size()==36118
    checks.append("classifier-chosen multiplication and real typed frame visibly distinguished from explicit menu choice")

    c=session();idle(c,"/calculate");idle(c,"add 3")
    cancelled=idle(c,"Cancel")
    assert c._chat.guide is None and cancelled["selected_path"]=="host/guided-cancel"
    c=session();idle(c,"/calculate");idle(c,"add 3")
    cancelled=idle(c,"I take back the request.")
    assert c._chat.guide is None and cancelled["selected_path"]=="learned-dialogue-act/host-guided-cancel"
    checks.append("explicit and classifier-selected cancellations have distinct origins; neither dispatches")

    c=session();idle(c,"/calculate");idle(c,"add 3")
    name=idle(c,"My name is Arvo.")
    assert c._chat.guide is None and name["selected_path"]=="host/session-memory"
    c=session();idle(c,"/convert");idle(c,"from grams")
    c.turn("I want to discuss the themes in my poem.",permit_calls=False)
    assert c._chat.guide is None and not c.session.trace
    checks.append("name and unrelated subject switches clear pending state")

    c=session();near=idle(c,"/calculate add 2 and 3")
    assert c._chat.guide is None and "by itself" in near["answer"]
    c=session();ambient=c.turn("I need to change a measurement.",permit_calls=False)
    assert c._chat.guide is None and not any("guided" in tag for tag in ambient["frame_origins"])
    c=session();idle(c,"/convert");bad=idle(c,"12 furlongs to metres")
    assert c._chat.guide.request.values=={} and not bad["trace"]
    c=session();idle(c,"/calculate");idle(c,"add 7")
    idle(c,"suppose I had 14 instead")
    assert c._chat.guide is None
    checks.append("only standalone slash commands activate; unsupported units and hypotheticals cannot supply hidden operands")

    c=session();idle(c,"/calculate");idle(c,"add")
    for bad in ("3^2","4.2.7","4,7","3 or 9","1/2"):
        idle(c,bad)
        assert c._chat.guide is not None and not c._chat.guide.request.values
    checks.append("malformed numeric tokens and alternative operands cannot be silently reinterpreted")

    c=session();idle(c,"/calculate");idle(c,"add 9")
    idle(c,"Don't run the calculator yet.")
    idle(c,"4")
    assert c._chat.guide.suspended and not c.session.trace
    observed(c,"go ahead",{"name":"calculate","arguments":{"op":"add","a":9,"b":4}},13)
    checks.append("explicit prohibition latches an enabled go-ahead even when later supplying the final value")

    c=session();idle(c,"/calculate");idle(c,"divide by 0")
    out=c.turn("14")
    assert len(out["trace"])==1 and not out["trace"][0]["ok"] and out["trace"][0]["error"]=="division by zero"
    assert "division by zero" in out["answer"] and out["frame_origins"]==[HOST,"host/observed-error"]
    checks.append("real adapter error propagates with its typed proposal and host error origin")
    return dict(state="passed",student_sha256=pin,classifier_parameters=model_size(),checks=checks,
                source_sha256={f:checksum(Path(f)) for f in ("guided_chat.py","verify_guided_chat.py")})


if __name__=="__main__":
    print(json.dumps(check(),indent=2))

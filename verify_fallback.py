"""Fresh diagnostics for the independently scored fallback. No access to scoring sets."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path

import torch

from checkpoint import checksum
from fallback_chat import Chat
from fallback_head import RECEIPT, ROOT, load_head
from gpt2 import GPT2
from serve_chat import CPUGuard
from tokenizer import load


def calc(op,a,b):
    return {"name":"calculate","arguments":{"op":op,"a":a,"b":b}}


def convert(value, source, target):
    return {"name":"convert","arguments":{"value":value,"from":source,"to":target}}


def head_screen():
    head=load_head()
    actual_trace=[dict(name="calculate",ok=True,data={"result":32},arguments={"op":"add","a":20,"b":12})]
    # Fixed new prompts. Score the predicted intent AND both ordered operands/units.
    cases=[
        ("Could you subtract thirteen from thirty-eight for me?", [], "subtract",calc("subtract",38,13)),
        ("I own 4 rows with 11 sockets each. Use the calculator to find the total.", [], "multiply",calc("multiply",4,11)),
        ("If 63 washers are split equally between seven tins, how many per tin?", [], "divide",calc("divide",63,7)),
        ("Please convert 2.75 litres to millilitres.", [], "convert",convert(2.75,"l","ml")),
        ("In millimetres, how long is eight centimetres?", [], "convert",convert(8,"cm","mm")),
        ("We need an invitation addressed to the choir.", [], "text",None),
        ("Give a brief definition of a measuring tape.", [], "text",None),
        ("Can you multiply by 4?", [], "multiply",None),
        ("Add 9 to that amount.", actual_trace, "add",calc("add",32,9)),
        ("What number was returned earlier?", actual_trace, "recall_number",None),
    ]
    rows=[]
    for user,trace,action,proposal in cases:
        d=head.decide(user,trace)
        rows.append(dict(user=user, context_trace=trace, expected_action=action, expected_proposal=proposal,
                         decision=asdict(d), correct=d.action==action and d.proposal==proposal))
    return dict(correct=sum(row["correct"] for row in rows), total=len(rows), rows=rows)


def runtime_tests(file, sha):
    if checksum(file)!=sha:
        raise ValueError("GPT-2 checkpoint checksum mismatch")
    checkpoint=torch.load(file,map_location="cpu",mmap=True,weights_only=True)
    with torch.device("meta"):
        model=GPT2()
    model.load_state_dict(checkpoint.get("model",checkpoint),strict=True,assign=True)
    del checkpoint
    model.eval()
    tok=load()
    fixture_call=calc("add",11,28)
    runs=[
        [("Please add 11 and 28 with the calculator.", True,fixture_call,{"result":53}),
         ("Repeat that number.",True,None,None),
         ("Now add 6 to that result.",True,None,None)],
        [("Please convert 0.25 kilograms to grams.",True,None,None)],
        [("Write a short wish for someone starting a pottery class.",True,None,None)],
        [("Without using tools, add 17 and 14.",True,None,None)],
        [("Please divide 35 by 5.",False,None,None)],
    ]
    reports=[]
    for conversation in runs:
        runtime=Chat(model,tok,CPUGuard())
        for user,permit,proposal,fixture in conversation:
            runtime.turn(user,permit,proposal,fixture)
        reports.append(runtime.history)
    assert not reports[3][0]["trace"] and not reports[4][0]["trace"]
    assert reports[0][0]["trace"][0]["source"]=="synthetic recorded fixture"
    assert reports[0][0]["trace"][0]["data"]["result"]==53
    assert reports[0][1]["trace"]==[] and "53" in reports[0][1]["copy_prompt"]
    assert reports[0][2]["trace"][0]["arguments"]=={"op":"add","a":53,"b":6}
    return dict(gpt2_checkpoint=str(file),sha256=sha,conversations=reports)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights",type=Path)
    parser.add_argument("--sha256")
    parser.add_argument("--out",type=Path,default=ROOT/"runs/working-head-01/self-tests.json")
    args=parser.parse_args()
    if bool(args.weights)!=bool(args.sha256):
        parser.error("--weights and --sha256 must be given together")
    torch.set_num_threads(1)
    result=dict(head_sha256=json.loads(RECEIPT.read_text())["sha256"], head=head_screen())
    if args.weights:
        result["runtime"]=runtime_tests(args.weights,args.sha256)
    args.out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print(f"Exact routing and slots: {result['head']['correct']}/{result['head']['total']}")
    if "runtime" in result:
        for history in result["runtime"]["conversations"]:
            print([(r["decision"]["action"],r["answer"],r["failure"]) for r in history])


if __name__=="__main__":
    main()

"""CPU test of the frozen development harness through actual Chat.turn and fixtures."""
import json
from collections import deque
from types import SimpleNamespace

import torch
from torch import nn

from evaluate_working import records, run_case, score_turn, summary
from local_chat import Chat
from tokenizer import EOT, load

# Explicit controls for the frozen rubrics. These strings are evaluator-only.
PROSE={
    "p01":["Neri.","Bela."],"p02":["The florist.","The tannery."],
    "p03":["Cracked.","No."],"p04":["It was found at Belmoor.","No."],
    "p05":["Arden, Zale","Arden, Tern, Zale"],
    "p06":["Where should we meet?","The boathouse."],
    "p07":["The archivist opened the vault.","The archivists opened the vault."],
    "p08":["Tavi.","Tavi."],"p09":["No.","Yes."],"p10":["Linen.","No."],
    "n01":["A","B"],"n02":["No.","No."],"n03":["The source and target units.","The target unit."],
    "n04":["No.","No."],
}


class FramedControl(nn.Module):
    def __init__(self,tokenizer,bodies):
        super().__init__()
        self.anchor=nn.Parameter(torch.zeros(1))
        self.ids=deque()
        for body in bodies:
            raw=json.dumps(body,ensure_ascii=False,separators=(",",":"))
            self.ids.extend(tokenizer.encode(raw).ids+[EOT])

    def forward(self,unused):
        scores=torch.zeros(1,1,EOT+1)
        scores[0,0,self.ids.popleft()]=1
        return scores


def test():
    torch.set_num_threads(1)
    cases=records()
    tok=load()
    guard=SimpleNamespace(check=lambda:None)
    def txt(s):return {"text":s}
    def add(x,y):return {"call":{"name":"calculate","arguments":{"op":"add","a":x,"b":y}}}
    scripted={
        "t01":[{"call":cases[10]["turns"][0]["calls"][0]},txt("168"),add(168,19),txt("187")],
        "t02":[{"call":cases[11]["turns"][0]["calls"][0]},txt("58"),txt("58")],
        "t03":[{"call":cases[12]["turns"][0]["calls"][0]},txt("61"),txt("61")],
        "t04":[{"call":cases[13]["turns"][0]["calls"][0]},txt("32"),txt("kilograms")],
        "t05":[{"call":cases[14]["turns"][0]["calls"][0]},txt("The calculator timed out."),txt("No.")],
        "t06":[{"call":cases[15]["turns"][0]["calls"][0]},add(105,11),txt("116"),txt("105")],
    }
    results=[]
    for case in cases:
        bodies=scripted[case["id"]] if case["id"] in scripted else [txt(a) for a in PROSE[case["id"]]]
        result=run_case(case,Chat(FramedControl(tok,bodies),tok,guard))
        assert result["passed"],result
        results.append(result)
    control=summary(results)
    assert control["conversations"]=={"passed":20,"total":20}
    assert control["turns"]=={"passed":40,"total":40}
    assert control["first_call_per_required_turn"]["total"]==7
    assert control["faithful_over_all_expected_readbacks"]["total"]==10
    # Wrong first call succeeds and returns 6. Its readback can be faithful and
    # its recall can pass independently even though the original task failed.
    wrong=[add(2,4),txt("6"),txt("6")]
    bad=run_case(cases[11],Chat(FramedControl(tok,wrong),tok,guard))
    assert not bad["passed"] and bad["turns"][0]["score"]["faithful_to_actual_result"]
    assert bad["turns"][1]["score"]["passed"]
    # Error-path follow-up also uses what actually happened.
    alt=run_case(cases[14],Chat(FramedControl(tok,[add(2,4),txt("6"),txt("Yes.")]),tok,guard))
    assert not alt["passed"] and alt["turns"][1]["score"]["passed"]
    # An attempted prohibited adapter fails the no-call requirement even if the final letter is right.
    no=run_case(cases[16],Chat(FramedControl(tok,[add(2,4),txt("A"),txt("B")]),tok,guard))
    assert not no["passed"] and no["turns"][1]["score"]["passed"]
    # The result 58 is only one number. An unrelated sentence or a contradiction should not pass.
    ref=results[11]["turns"][0]
    for answer in ("I cannot confirm that 58.", "It was 58 or 61.", "Our parrot is 58.","58 was not the result."):
        out=dict(ref["response"],answer=answer)
        score=score_turn("t02",0,cases[11]["turns"][0],out,[])
        assert not score["passed"] and not score["faithful_to_actual_result"],answer
    for turn in results[15]["turns"]:
        assert turn["score"]["passed"]
    print(json.dumps(dict(scope="CPU scripted controls; no trained student was run",ideal=control,
                          negatives=["faithful wrong call","prior successful alternative to fixture error",
                                     "prohibited call","unrelated number","contradictory number"]),indent=2))


if __name__=="__main__":
    test()

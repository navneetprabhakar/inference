"""Run the separately frozen B holdout once for a preselected follow-on checkpoint."""
import argparse
import json
from pathlib import Path

import torch

from checkpoint import checksum
from evaluate_working import CpuGuard, run_case, summary
from gpt2 import GPT2
from local_chat import Chat
from pretrain import atomic_status
from tokenizer import load

DIRECTORY=Path(__file__).parent/"reports/working-validation-b"
B_SHA="e0ba8dceb8dcdd21263d990a2c6010c8ddd6a46ec4e06d36ee8313196841b4da"
SCORER_SHA="bb096b57bdc8ee47c0e4e6d3ca9ba167c45dc799b2e8f89d663e2214e245cd4c"


def records():
    if checksum(DIRECTORY/"cases.jsonl")!=B_SHA or checksum(Path(__file__).with_name("evaluate_working.py"))!=SCORER_SHA:
        raise ValueError("validation B cases or frozen rubric scorer changed")
    rows=[json.loads(l) for l in (DIRECTORY/"cases.jsonl").open()]
    assert len(rows)==20 and len({r["id"] for r in rows})==20 and all(len(r["turns"])==2 for r in rows)
    return rows


def evaluate_b(model,tokenizer,guard,path,identity):
    cases=records()
    model.eval()
    dest=Path(path)
    dest.mkdir(parents=True,exist_ok=False)
    meta=dict(role="independent validation B; single preselected follow-on checkpoint",identity=identity,
              cases_sha256=B_SHA,content_scorer_sha256=SCORER_SHA,chat_sha256=checksum(Path(__file__).with_name("local_chat.py")),
              decoder="normal Chat.turn raw greedy; no output repair or retries")
    atomic_status(dest/"meta.json",meta)
    results=[]
    finished=False
    try:
        with (dest/"transcripts.jsonl").open("x") as log:
            for case in cases:
                guard.check()
                result=run_case(case,Chat(model,tokenizer,guard))
                results.append(result)
                log.write(json.dumps(result,ensure_ascii=False)+"\n")
                log.flush()
        report=summary(results)
        atomic_status(dest/"scores.json",report)
        finished=True
        return report
    finally:
        atomic_status(dest/"status.json",dict(state="complete" if finished else "incomplete",
                                              completed=len(results),expected=len(cases)))


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("weights",type=Path)
    p.add_argument("sha")
    p.add_argument("run",type=Path)
    p.add_argument("--minutes",type=int,default=45)
    args=p.parse_args()
    if checksum(args.weights)!=args.sha or args.minutes<=0:raise SystemExit("invalid checkpoint pin or deadline")
    torch.set_num_threads(1)
    state=torch.load(args.weights,map_location="cpu",weights_only=True,mmap=True)
    model=GPT2()
    model.load_state_dict(state["model"] if "model" in state else state)
    del state
    print(json.dumps(evaluate_b(model,load(),CpuGuard(args.run,args.minutes*60),args.run,
                                dict(checkpoint_sha256=args.sha,device="cpu")),indent=2))

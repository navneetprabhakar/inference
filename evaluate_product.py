"""Score an explicitly identified product runtime with the existing frozen A or B rubrics."""
import argparse
import json
from pathlib import Path
import torch

import evaluate_working
import evaluate_validation_b
from checkpoint import checksum
from fallback_chat import Chat
from gpt2 import GPT2
from pretrain import atomic_status
from tokenizer import load


def evaluate(weights,sha,path,holdout="A",chat_cls=Chat):
    if checksum(weights)!=sha:raise ValueError("model checksum mismatch")
    torch.set_num_threads(1)
    state=torch.load(weights,weights_only=True,map_location="cpu",mmap=True)
    model=GPT2().eval()
    model.load_state_dict(state.get("model",state))
    del state
    tokenizer=load()
    cases=evaluate_working.records() if holdout=="A" else evaluate_validation_b.records()
    guard=evaluate_working.CpuGuard(path,45*60)
    path.mkdir(exist_ok=False)
    source=Path("reports/working-chat/head-v2.json" if chat_cls.__module__=="followon_product_chat" else "reports/working-chat/head.json")
    reader=None
    if chat_cls.__module__ in ("product_chat","followon_product_chat"):
        from product_chat import reader_identity
        reader=reader_identity()
    atomic_status(path/"meta.json",dict(weights_sha256=sha,head_pin=json.loads(source.read_text()),reader=reader,holdout=holdout,
                                       runtime=f"{chat_cls.__module__}.{chat_cls.__name__}",device="cpu"))
    results=[]
    try:
        with (path/"transcripts.jsonl").open("x") as f:
            for case in cases:
                guard.check()
                record=evaluate_working.run_case(case,chat_cls(model,tokenizer,guard))
                results.append(record)
                f.write(json.dumps(record,ensure_ascii=False)+"\n")
                f.flush()
        summary=evaluate_working.summary(results)
        atomic_status(path/"scores.json",summary)
        return summary
    finally:
        atomic_status(path/"status.json",dict(completed=len(results),total=len(cases)))


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("weights",type=Path)
    p.add_argument("sha256")
    p.add_argument("run",type=Path)
    p.add_argument("--holdout",choices=["A","B"],default="A")
    p.add_argument("--mode",choices=["structured","product","product-v2"],default="structured")
    args=p.parse_args()
    runtime=Chat
    if args.mode=="product":
        from product_chat import Chat as runtime
    elif args.mode=="product-v2":
        from followon_product_chat import Chat as runtime
    print(json.dumps(evaluate(args.weights,args.sha256,args.run,args.holdout,runtime),indent=2))

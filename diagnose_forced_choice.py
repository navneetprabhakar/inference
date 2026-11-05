"""Fixed, offline comparison of raw GPT-2 replies and explicit candidate scoring."""
from functools import lru_cache
import json
from pathlib import Path
import random
import time

import torch
from torch.nn import functional as F

from checkpoint import checksum
from gpt2 import GPT2
from local_chat import Chat, encode_frame
from tokenizer import load

ROOT=Path(__file__).resolve().parent
REPORT=ROOT/"reports/forced-choice-02"
RUN=ROOT/"runs/forced-choice-02"
PROTOCOL_SHA="28363d30dce84e7b411b83593e2a31172440b802297e8c6a5b263e919fc48f43"


class Deadline:
    def __init__(self):self.start=time.monotonic()

    def check(self):
        if time.monotonic()-self.start>=30*60:
            raise TimeoutError("CPU diagnosis time limit")


def prefix_for(tok,history_ids,user):
    head,body=encode_frame(tok,"user",user)
    return history_ids+head+body+tok.encode("Assistant:").ids


@torch.inference_mode()
def completion_logp(model,tok,prefix,label):
    _,answer=encode_frame(tok,"assistant",{"text":label})
    tokens=prefix+answer
    if len(tokens)>1024:raise ValueError("candidate exceeds context")
    x=torch.tensor([tokens[:-1]],dtype=torch.long)
    mask=torch.zeros_like(x,dtype=torch.bool)
    mask[:,len(prefix)-1:]=True
    logits=model(x,prediction_mask=mask)
    targets=torch.tensor(answer,dtype=torch.long)
    pieces=-F.cross_entropy(logits,targets,reduction="none")
    return float(pieces.sum()),pieces.tolist()


def run():
    torch.set_num_threads(1)
    if checksum(REPORT/"protocol.json")!=PROTOCOL_SHA:raise ValueError("protocol pin mismatch")
    spec=json.loads((REPORT/"protocol.json").read_text())
    weights=ROOT/"runs/working-chat-02/weights.pt"
    if checksum(weights)!=spec["weights_sha256"]:raise ValueError("student pin mismatch")
    RUN.mkdir(exist_ok=False)
    guard=Deadline()
    model=GPT2().cpu().eval()
    model.load_state_dict(torch.load(weights,weights_only=True,map_location="cpu",mmap=True))
    tok=load()

    @lru_cache(maxsize=64)
    def neutral(instruction,label):
        return completion_logp(model,tok,prefix_for(tok,[],instruction),label)[0]

    candidates=spec["cases"].copy()
    random.Random(9023).shuffle(candidates)
    with (RUN/"transcripts.jsonl").open("x") as writer:
        for pair in candidates:
            for i,member in enumerate(pair["members"]):
                guard.check()
                chat=Chat(model,tok,guard)
                prior=None
                if member["prior"] is not None:
                    prior=chat.turn(member["prior"],permit_calls=False)
                prefix=prefix_for(tok,chat.ids.copy(),member["user"])
                raw=chat.turn(member["user"],permit_calls=False)
                scores={}
                for label in pair["options"]:
                    direct,token_scores=completion_logp(model,tok,prefix,label)
                    base=neutral(pair["instruction"],label)
                    scores[label]=dict(direct=direct,neutral=base,corrected=direct-base,
                                       answer_token_logprobs=token_scores)
                naive=max(pair["options"],key=lambda opt:scores[opt]["direct"])
                selected=max(pair["options"],key=lambda opt:scores[opt]["corrected"])
                result=dict(pair=pair["id"],member=i,mode=pair["mode"],prior=prior,prompt=member["user"],
                            expected=member["expected"],options=pair["options"],raw=raw,scores=scores,
                            direct_choice=naive,calibrated_choice=selected,prefix_ids=prefix)
                writer.write(json.dumps(result,ensure_ascii=False)+"\n")
                writer.flush()
    print(json.dumps(dict(cases=len(candidates),outputs=2*len(candidates),seconds=time.monotonic()-guard.start)))


if __name__=="__main__":
    run()

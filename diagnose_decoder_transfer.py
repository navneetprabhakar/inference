"""Run the preregistered working-chat-02 paired diagnosis. CPU inference only."""
from collections import Counter
from pathlib import Path
import json
import random
import time

import torch

from checkpoint import checksum
from gpt2 import GPT2
from local_chat import Chat
from tokenizer import load

ROOT=Path(__file__).resolve().parent
REPORT=ROOT/"reports/decoder-transfer-02"
RUN=ROOT/"runs/decoder-transfer-02"
SPEC_SHA="e441d05266d6652f1d07c41155c3028b4544cffb7fa7025e66074b8ef47fe43e"


class Deadline:
    def __init__(self):
        self.start=time.monotonic()

    def check(self):
        if time.monotonic()-self.start>=30*60:raise TimeoutError("CPU diagnosis time limit")


def run():
    torch.set_num_threads(1)
    assert checksum(REPORT/"protocol.json")==SPEC_SHA
    spec=json.loads((REPORT/"protocol.json").read_text())
    file=ROOT/"runs/working-chat-02/weights.pt"
    if checksum(file)!=spec["weights_sha256"]:raise ValueError("Candidate pin mismatch")
    RUN.mkdir(exist_ok=False)
    tok=load()
    model=GPT2().cpu().eval()
    model.load_state_dict(torch.load(file,map_location="cpu",weights_only=True,mmap=True))
    guard=Deadline()
    sessions=[(case,arm) for case in spec["cases"] for arm in ("exact","paraphrase")]
    random.Random(5753).shuffle(sessions)
    with (RUN/"transcripts.jsonl").open("x") as f:
        for case,arm in sessions:
            chat=Chat(model,tok,guard)
            turns=[]
            for user,rubric in zip(case[arm],case["rubrics"]):
                guard.check()
                result=chat.turn(user,permit_calls=False)
                turns.append(dict(user=user,rubric=rubric,answer=result["answer"],frames=result["frames"],
                                  failure=result["failure"],trace=result["trace"]))
            f.write(json.dumps(dict(case=case["id"],arm=arm,turns=turns),ensure_ascii=False)+"\n")
            f.flush()
    print(json.dumps(dict(sessions=len(sessions),turns=2*len(sessions),seconds=time.monotonic()-guard.start)))


if __name__=="__main__":
    run()

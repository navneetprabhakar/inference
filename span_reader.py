"""A small optional extractive reader. It selects a literal span or defers to GPT-2."""
import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import random
import re
import time
import zlib

import torch
from torch import nn
from torch.nn import functional as F

from chat_teaching import examples, natural_examples
from checkpoint import checksum
from pretrain import atomic_status

WORDS = re.compile(r"[^\W_]+(?:['’][^\W_]+)*|[^\w\s]", re.UNICODE)
BINS = 4096
LIMIT = 176
MAX_SPAN = 12
RUN = Path("runs/working-reader-01")


@dataclass
class Encoded:
    words: list
    features: list
    offsets: list
    contexts: list
    target: tuple


def encode(history, target=None):
    # Position zero represents abstention; every other candidate is copied verbatim.
    contexts=[m["text"] for m in history]
    query_words={w.group().casefold() for w in WORDS.finditer(contexts[-1])}
    ids=[1]
    features=[[0.]*6]
    offsets=[(-1,0,0)]
    for index,message in enumerate(history):
        text=message["text"]
        for match in WORDS.finditer(text):
            token=match.group()
            ids.append(2+zlib.crc32(token.casefold().encode())%(BINS-2))
            features.append([float(index==len(history)-1),float(message["role"]=="user"),
                             float(token[:1].isupper()),float(token.isdigit()),
                             float(token.casefold() in query_words),min(1,(len(history)-index-1)/4)])
            offsets.append((index,match.start(),match.end()))
    if len(ids)>LIMIT:
        return None
    label=(0,0)
    if target:
        value=target.strip().rstrip(".!?").strip().casefold()
        # Short exact spans only. Preserve case-sensitive rewrites for the decoder.
        if value and len(value.split())<=MAX_SPAN and target.upper()!=target:
            for end in range(len(ids)-1,0,-1):
                m,_,right=offsets[end]
                for start in range(end,max(0,end-MAX_SPAN),-1):
                    group,left,_=offsets[start]
                    if group!=m:break
                    if contexts[m][left:right].casefold()==value:
                        label=(start,end)
                        break
                if label!=(0,0):break
    return Encoded(ids,features,offsets,contexts,label)


def batch(rows):
    width=max(len(r.words) for r in rows)
    words=torch.zeros((len(rows),width),dtype=torch.long)
    features=torch.zeros((len(rows),width,6))
    for i,r in enumerate(rows):
        words[i,:len(r.words)]=torch.tensor(r.words)
        features[i,:len(r.words)]=torch.tensor(r.features)
    return words,features


class Reader(nn.Module):
    def __init__(self):
        super().__init__()
        self.words=nn.Embedding(BINS,48,padding_idx=0)
        self.encoder=nn.GRU(54,40,batch_first=True,bidirectional=True)
        self.head=nn.Sequential(nn.Linear(240,64),nn.Tanh(),nn.Linear(64,2))

    def forward(self,words,features):
        content=torch.cat([self.words(words),features],dim=-1)
        # Packed sequences make padding invisible to both GRU directions.
        lengths=(words!=0).sum(dim=1)
        packed=nn.utils.rnn.pack_padded_sequence(content,lengths.cpu(),batch_first=True,enforce_sorted=False)
        out,_=self.encoder(packed)
        hidden,_=nn.utils.rnn.pad_packed_sequence(out,batch_first=True,total_length=words.shape[1])
        qmask=features[:,:,0:1]
        query=(hidden*qmask).sum(1,keepdim=True)/qmask.sum(1,keepdim=True).clamp_min(1.)
        joint=torch.cat([hidden,query.expand_as(hidden),hidden*query],-1)
        return self.head(joint).masked_fill((words==0).unsqueeze(-1),-1e4)


def choice(row,logits,threshold=.85):
    probs=logits[:len(row.words)].softmax(dim=0)
    confidence,index=probs.max(dim=0)
    start,end=map(int,index)
    if min(confidence).item()<threshold or start==0 or end<start or end-start>=MAX_SPAN:
        return None
    a,left,_=row.offsets[start]
    b,_,right=row.offsets[end]
    return row.contexts[a][left:right] if a==b else None


@torch.inference_mode()
def read(model,history,threshold=.85):
    row=encode(history)
    if row is None:return None
    return choice(row,model(*batch([row]))[0],threshold)


def data():
    denied=set(json.loads(Path("reports/working-chat/excluded-histories.json").read_text()))
    pools=[[],[]]
    for h in examples(1459)+natural_examples(1459):
        digest=hashlib.sha256(json.dumps(h,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        if digest in denied:continue
        group=int(digest[:8],16)%10==0
        for i in range(1,len(h),2):
            r=encode(h[:i],h[i]["text"])
            if r is not None:pools[group].append(r)
    return pools


def train():
    torch.set_num_threads(1)
    torch.manual_seed(765)
    rng=random.Random(765)
    start=time.monotonic()
    RUN.mkdir(exist_ok=False)
    rows,hold=data()
    pos=[r for r in rows if r.target!=(0,0)]
    neg=[r for r in rows if r.target==(0,0)]
    model=Reader()
    opt=torch.optim.AdamW(model.parameters(),lr=.003)
    for step in range(1,901):
        if time.monotonic()-start>=720:raise TimeoutError("CPU training cap")
        group=rng.choices(pos,k=16)+rng.choices(neg,k=16)
        words,features=batch(group)
        # Unknown lexical items must still be copyable by context and token shape.
        words=words.masked_fill((torch.rand(words.shape)<.12)&(words>=2),2)
        target=torch.tensor([r.target for r in group])
        logits=model(words,features)
        loss=F.cross_entropy(logits.transpose(1,2).reshape(-1,logits.shape[1]),target.flatten())
        opt.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(),1.,error_if_nonfinite=True)
        opt.step()
    model.eval()
    counts=Counter()
    with torch.inference_mode():
        for i in range(0,len(hold),32):
            group=hold[i:i+32]
            logits=model(*batch(group))
            for r,l in zip(group,logits):
                value=choice(r,l)
                a,b=r.target
                correct=None if not a else r.contexts[r.offsets[a][0]][r.offsets[a][1]:r.offsets[b][2]]
                counts['rows']+=1
                counts['positive_rows']+=int(a!=0)
                counts['attempts']+=int(value is not None)
                counts['correct_attempts']+=int(value is not None and value.casefold()==(correct or '').casefold())
    dest=RUN/'weights.pt'
    torch.save(model.state_dict(),dest)
    summary=dict(state='trained',train_positive=len(pos),train_negative=len(neg),internal_validation=counts,
                 elapsed_seconds=time.monotonic()-start,parameters=sum(p.numel() for p in model.parameters()),
                 weights_sha256=checksum(dest),threshold=.85,limitations='In-family synthetic holdout. No release or conversation accuracy inferred.')
    atomic_status(RUN/'result.json',summary)
    print(json.dumps(summary))


if __name__=='__main__':
    train()

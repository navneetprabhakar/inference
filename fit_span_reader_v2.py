"""Single endpoint CPU reader experiment with independent held-out wording forms."""
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import random
import re
import time

import torch
from torch import nn
from torch.nn import functional as F

from chat_teaching import examples, natural_examples
from checkpoint import checksum
from compositional_teaching import SEED, FORMS, STARTS, MIDS, ENDS, records
from pretrain import atomic_status
from span_reader import Reader, WORDS, MAX_SPAN, batch, choice, encode

DIR = Path("reports/reader-v2")
RUN = Path("runs/working-reader-02")
NUM = re.compile(r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)")
NONCES = {a+b+c for a in STARTS for b in MIDS for c in ENDS}
LOWER_OR_UPPER = re.compile(r"\b(?:upper\s?case|lower\s?case|capital letters|small letters)\b", re.I)


def row_for(history, target=None, force_defer=False):
    row = encode(history, None if force_defer else target)
    if row is None or force_defer or not target:
        return row
    value = target.strip().removesuffix(".")
    if NUM.fullmatch(value):
        # V1's target.upper() == target excluded all purely numeric targets.
        for end in range(len(row.words)-1, 0, -1):
            m, _, right = row.offsets[end]
            for start in range(end, max(0,end-MAX_SPAN), -1):
                other,left,_ = row.offsets[start]
                if m != other:
                    break
                if row.contexts[m][left:right] == value:
                    row.target = (start,end)
                    return row
    elif row.target!=(0,0) and LOWER_OR_UPPER.search(history[-1]["text"]):
        a,b=row.target
        m,left,_=row.offsets[a]
        _,_,right=row.offsets[b]
        if row.contexts[m][left:right]!=value:
            row.target=(0,0)
    return row


class ExpandedReader(Reader):
    """Add one self-attention block over the contextual token states."""
    def __init__(self):
        super().__init__()
        self.context_attention=nn.MultiheadAttention(80,4,batch_first=True)
        self.norm=nn.LayerNorm(80)

    def forward(self, words, features):
        lengths=(words!=0).sum(1)
        content=torch.cat([self.words(words),features],-1)
        packed=nn.utils.rnn.pack_padded_sequence(content,lengths.cpu(),batch_first=True,enforce_sorted=False)
        states,_=self.encoder(packed)
        states,_=nn.utils.rnn.pad_packed_sequence(states,batch_first=True,total_length=words.shape[1])
        cross,_=self.context_attention(states,states,states,key_padding_mask=words==0,need_weights=False)
        hidden=self.norm(states+cross)
        mask=features[:,:,0:1]
        question=(hidden*mask).sum(1,keepdim=True)/mask.sum(1,keepdim=True).clamp_min(1)
        features=torch.cat([hidden,question.expand_as(hidden),hidden*question],-1)
        return self.head(features).masked_fill((words==0).unsqueeze(-1),-1e4)


def digest(history):
    return sha256(json.dumps(history,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def ids(history):
    return {m.group() for msg in history for m in WORDS.finditer(msg["text"])} & NONCES


def build(spec):
    denied=set()
    for filename in ("reports/working-chat/excluded-histories.json","reports/working-chat/followon-excluded-histories.json",
                     "reports/working-validation-b/additional-excluded-histories.json"):
        denied.update(json.loads(Path(filename).read_text()))
    reserved={}
    heldout_ids=set()
    heldout_keys=set()
    training_records=[]
    comp=list(records(spec["data_seed"]))
    for family,forms in FORMS.items():
        rng=random.Random(f"reader-v2:{spec['seed']}:{family}")
        reserved[family]=sorted(rng.sample(range(len(forms)),spec["forms_reserved_per_family"]))
        for form in reserved[family]:
            candidates=[r for r in comp if r["family"]==family and r["form"]==form and r["variant"]==0]
            keys=rng.sample([r["pair"] for r in candidates],spec["pairs_per_reserved_form"])
            for pair in keys:
                heldout_keys.add((family,form,pair))
    validation=[]
    for r in comp:
        family=r["family"];h=r["history"];key=(family,r["form"],r["pair"])
        if key in heldout_keys:
            heldout_ids.update(ids(h))
            validation.append((family,h))
        elif r["form"] not in reserved[family]:
            training_records.append((family,h))
    training_records.extend(("initial",h) for h in examples(SEED)+natural_examples(SEED))
    rows=[]
    seen=set()
    skipped=Counter()
    for family,h in training_records:
        pin=digest(h)
        if pin in seen or pin in denied or ids(h)&heldout_ids:
            skipped[family]+=1
            continue
        seen.add(pin)
        for j in range(1,len(h),2):
            r=row_for(h[:j],h[j]["text"])
            if r:rows.append(r)
    validation_rows=[]
    for family,h in validation:
        assert digest(h) not in denied
        for j in range(1,len(h),2):
            row=row_for(h[:j],h[j]["text"])
            assert row is not None
            validation_rows.append((family,row))
    probes=[]
    for line in (DIR/"paraphrases.jsonl").read_text().splitlines():
        ex=json.loads(line)
        row=row_for(ex["history"],ex["target"],ex.get("defer",False))
        assert row is not None
        probes.append(("fresh paraphrase",row))
    split=dict(reserved_forms=reserved,heldout_nonce_count=len(heldout_ids),heldout_nonce_sha256=sha256(json.dumps(sorted(heldout_ids)).encode()).hexdigest(),
               heldout_nonce_intersections_train=0,heldout_histories=len(validation),train_histories=len(seen),
               excluded_training_histories=skipped,paraphrase_sha256=checksum(DIR/"paraphrases.jsonl"))
    return rows,validation_rows,probes,split


@torch.inference_mode()
def assess(model, rows, threshold):
    total=Counter()
    family=defaultdict(Counter)
    errors=[]
    for i in range(0,len(rows),32):
        group=rows[i:i+32]
        rb=[v for _,v in group]
        logits=model(*batch(rb))
        for (key,r),l in zip(group,logits):
            p=choice(r,l,threshold)
            a,b=r.target
            gold=(r.contexts[r.offsets[a][0]][r.offsets[a][1]:r.offsets[b][2]] if a else None)
            correct=p is not None and gold is not None and p.casefold()==gold.casefold()
            for counter in (total,family[key]):
                counter["rows"]+=1
                counter["positives"]+=int(bool(a))
                counter["attempts"]+=int(p is not None)
                counter["correct"]+=int(correct)
                counter["negative_false_extractions"]+=int(not a and p is not None)
            if not correct and p is not None and len(errors)<20:
                errors.append(dict(family=key,text=r.contexts,gold=gold,predicted=p))
    return dict(counts=total,precision=total["correct"]/max(1,total["attempts"]),
                correct_positive_coverage=total["correct"]/max(1,total["positives"]),
                family=family,representative_errors=errors)


def train():
    torch.set_num_threads(1)
    start=time.monotonic()
    RUN.mkdir(exist_ok=False)
    spec=json.loads((DIR/"protocol.json").read_text())
    torch.manual_seed(spec["seed"])
    rng=random.Random(spec["seed"])
    rows,hold,probe,split=build(spec)
    positive=[r for r in rows if r.target!=(0,0)]
    negative=[r for r in rows if r.target==(0,0)]
    # Exact fit and test configuration are fixed before initializing weights.
    atomic_status(RUN/"config.json",dict(protocol=spec,split=split,train_positive=len(positive),train_negative=len(negative),
                                        code_sha256=checksum(Path(__file__)),protocol_sha256=checksum(DIR/"protocol.json")))
    model=ExpandedReader()
    opt=torch.optim.AdamW(model.parameters(),lr=spec["learning_rate"])
    for step in range(1,spec["train_steps"]+1):
        if time.monotonic()-start>=spec["wall_seconds_cap"]-20:
            atomic_status(RUN/"result.json",dict(state="stopped",reason="CPU time cap",step=step-1))
            return
        group=rng.choices(positive,k=spec["batch_size"]//2)+rng.choices(negative,k=spec["batch_size"]//2)
        words,features=batch(group)
        drop=(torch.rand(words.shape)<.16)&(words>=2)
        words=words.masked_fill(drop,2)
        gold=torch.tensor([r.target for r in group])
        logits=model(words,features)
        loss=F.cross_entropy(logits.transpose(1,2).reshape(-1,logits.shape[1]),gold.flatten())
        opt.zero_grad(set_to_none=True)
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(),1.,error_if_nonfinite=True)
        opt.step()
        if step%150==0:
            atomic_status(RUN/"status.json",dict(step=step,elapsed=time.monotonic()-start,loss=float(loss.detach())))
    model.eval()
    threshold=spec["threshold"]
    internal=assess(model,hold,threshold)
    para=assess(model,probe,threshold)
    passed=(internal["precision"]>=spec["internal_precision_min"] and internal["correct_positive_coverage"]>=spec["internal_correct_positive_coverage_min"]
            and para["precision"]>=spec["paraphrase_precision_min"] and para["correct_positive_coverage"]>=spec["paraphrase_correct_positive_coverage_min"])
    elapsed=time.monotonic()-start
    if elapsed>spec["wall_seconds_cap"]:passed=False
    dest=RUN/"weights.pt"
    torch.save(model.state_dict(),dest)
    result=dict(state="accepted" if passed else "experimental",parameters=sum(p.numel() for p in model.parameters()),
                weights_sha256=checksum(dest),elapsed_seconds=elapsed,train_steps=spec["train_steps"],threshold=threshold,
                internal=internal,paraphrases=para,split=split,protocol_sha256=checksum(DIR/"protocol.json"),
                limitation="Form-held-out synthetic check with disjoint generated identifiers, plus 30 separately authored probes; no release or user-traffic quality implication.")
    atomic_status(RUN/"result.json",result)
    atomic_status(DIR/"result.json",result)
    if passed:
        atomic_status(DIR/"accepted-pin.json",dict(sha256=result["weights_sha256"],threshold=threshold,
                    result_sha256=checksum(DIR/"result.json"),parameters=result["parameters"],protocol_sha256=result["protocol_sha256"]))
    print(json.dumps(dict(state=result["state"],internal=internal["counts"],paraphrases=para["counts"],seconds=elapsed)))


if __name__=="__main__":
    train()

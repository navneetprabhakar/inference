"""Versioned CPU dialogue-act heads; kept separate from the first experiment."""
from collections import Counter,defaultdict
from functools import lru_cache
import json
from pathlib import Path
import re
import time

import torch
from torch import nn
from torch.nn import functional as F

from checkpoint import checksum
from fallback_head import parse
from pretrain import atomic_status
from slot_dialogue_head import CLASSES, LEX, features as open_features, training_rows as prior_cleared

REPORT=Path(__file__).resolve().parent/"reports/slot-dialogue/v2"
RUN=Path(__file__).resolve().parent/"runs/slot-dialogue-head-02"
TOPIC_WORDS=set("number numbers unit units calculator conversion converter operation tool calculate calculation measurement measurements quantity quantities value figures figure amount amounts operand operands reading readings target source input output sum product quotient difference request task slot".split())
SLOTS={"@","#"}


def feature_groups(mode,text):
    if mode=="open":
        full,words=open_features(text)
        return full,{},words
    seq,_=parse(text,None)
    words=[w for w in seq if w not in SLOTS and w not in TOPIC_WORDS]
    role={"rolebias":.18}
    for i,w in enumerate(words):
        role["rw:"+w]=1.0
        if i:role["rb:"+words[i-1]+"|"+w]=1.0
        if i>=2:role["rg:"+words[i-2]+"|"+w]=.45
        if i<2:role[f"rs{i}:"+w]=.40
        if len(w)>2:
            pad="^"+w+"$"
            for n in (3,4):
                for j in range(len(pad)-n+1):role["rc:"+pad[j:j+n]]=.23
    shape={"contextbias":.15}
    schema=["slot" if w in SLOTS else ("field" if w in TOPIC_WORDS else "word") for w in seq]
    shape["shape:"+" ".join(schema[:13])]=.6
    for i,w in enumerate(seq):
        if w in SLOTS:
            shape["slot:"+w]=.65
            if i:shape["pre:"+seq[i-1]+":"+w]=1.
            if i+1<len(seq):shape["post:"+w+":"+seq[i+1]]=.6
        if w in TOPIC_WORDS:
            shape["topic:"+w]=.30
    for i,w in enumerate(seq[:-1]):
        if "word" not in schema[i:i+2]:
            shape["typed:"+w+"|"+seq[i+1]]=.6
    return role,shape,seq


def encode(mode,texts,vocab):
    width=len(vocab)
    a=torch.zeros((len(texts),width))
    b=torch.zeros_like(a)
    known=[]
    for i,text in enumerate(texts):
        role,shape,words=feature_groups(mode,text)
        for matrix,feats in ((a,role),(b,shape)):
            for k,v in feats.items():
                if k in vocab:matrix[i,vocab[k]]=v
        if mode=="open":
            n=sum("w:"+w in vocab for w in words)
        else:
            n=sum(w in SLOTS or "rw:"+w in vocab or "topic:"+w in vocab for w in words)
        known.append(n/max(1,len(words)))
    role=F.normalize(a,dim=1)
    if mode=="open":return role,known
    return F.normalize(role+.60*F.normalize(b,dim=1),dim=1),known


def fit(mode,rows,spec):
    keys=set()
    forms=defaultdict(Counter)
    for r in rows:
        role,shape,_=feature_groups(mode,r['user'])
        keys.update(role);keys.update(shape)
        forms[r['label']][r['form']]+=1
    vocab={k:i for i,k in enumerate(sorted(keys))}
    x,_=encode(mode,[r['user'] for r in rows],vocab)
    labels=CLASSES[mode]
    y=torch.tensor([labels.index(r['label']) for r in rows])
    row_weights=torch.tensor([1/(len(forms[r['label']])*forms[r['label']][r['form']]) for r in rows])
    row_weights/=row_weights.sum()
    linear=nn.Linear(len(vocab),len(labels))
    opt=torch.optim.Adam(linear.parameters(),lr=spec['learning_rate'])
    for _ in range(spec['iterations']):
        loss=(F.cross_entropy(linear(x),y,reduction='none')*row_weights).sum()
        loss+=spec['l2']*linear.weight.square().sum()/len(labels)
        opt.zero_grad(set_to_none=True);loss.backward();opt.step()
    return dict(vocab=vocab,weight=linear.weight.detach(),bias=linear.bias.detach())


def decisions(mode,texts,head,spec):
    x,known=encode(mode,texts,head['vocab'])
    probs=torch.softmax(x@head['weight'].T+head['bias'],dim=1)
    num,idx=probs.topk(2,dim=1)
    out=[]
    for i in range(len(texts)):
        conf=float(num[i,0]);margin=conf-float(num[i,1])
        label=CLASSES[mode][int(idx[i,0])]
        pred=label if conf>=spec['confidence_min'] and margin>=spec['margin_min'] and known[i]>=spec['known_word_fraction_min'] else None
        out.append(dict(prediction=pred,label=label,confidence=conf,margin=margin,known_fraction=known[i]))
    return out


def metrics(rows,preds,spec):
    forms=Counter((r['label'],r['form']) for r in rows); total=Counter(); macro=Counter();by=defaultdict(Counter);errors=[]
    for r,d in zip(rows,preds):
        p=d['prediction'];accept=p is not None; good=r['label']==p
        for ct,m in ((total,1),(macro,1/forms[r['label'],r['form']]),(by[r['label']],1)):
            ct['rows']+=m;ct['accepted']+=m*accept;ct['correct']+=m*good
        if accept and not good and len(errors)<20:errors.append(dict(user=r['user'],expected=r['label'],predicted=p,confidence=d['confidence']))
    def rate(c):
        return dict(c,precision=c['correct']/max(1,c['accepted']),coverage=c['accepted']/max(1,c['rows']))
    row,form=rate(total),rate(macro)
    return dict(passed=all(z['precision']>=spec['semantic_precision_min'] and z['coverage']>=spec['coverage_min'] for z in (row,form)),rows=row,forms=form,per_label={k:rate(v) for k,v in by.items()},accepted_errors=errors)


def get_data():
    _,original,_=prior_cleared()
    previous=[dict(r,form="original-"+str(r["form"])) for r in original if r['split']=='train']
    spec=json.loads((REPORT/'protocol.json').read_text());pin=spec['custody_sha256']
    source=REPORT/'custody-input.jsonl'
    if checksum(source)!=pin:raise ValueError("v2 source pin mismatch")
    protected=json.loads((REPORT/'protected-custody.json').read_text())
    other=json.loads((REPORT/'other-suite-exclusions.json').read_text())
    if protected['source_sha256']!=pin or other['input_sha256']!=pin:raise ValueError("v2 protected screen pin mismatch")
    excluded=set(protected['excluded_indices'])|set(other['indices'])
    new=[r for l in source.open() if (r:=json.loads(l))['index'] not in excluded]
    # V1 train set appears in V2 with its original semantics. New held-out forms stay
    # disjoint by form and question text from every training row, including V1.
    seen={(r['mode'],r['user'].casefold()) for r in previous}
    unique=[]
    for r in new:
        key=(r['mode'],r['user'].casefold())
        if key in seen:continue
        seen.add(key);unique.append(r)
    return spec,previous+unique,excluded


def train():
    torch.set_num_threads(1)
    spec,rows,excluded=get_data()
    torch.manual_seed(spec['seed'])
    start=time.monotonic()
    RUN.mkdir(exist_ok=False);results={};heads={};counts={}
    for mode in CLASSES:
        train_rows=[r for r in rows if r['mode']==mode and r['split']=='train']
        challenge=[r for r in rows if r['mode']==mode and r['split']=='challenge']
        assert not {r['form'] for r in train_rows}&{r['form'] for r in challenge}
        heads[mode]=fit(mode,train_rows,spec)
        preds=decisions(mode,[r['user'] for r in challenge],heads[mode],spec)
        results[mode]=metrics(challenge,preds,spec)
        counts[mode]=dict(train=len(train_rows),challenge=len(challenge),challenge_forms=len({r['form'] for r in challenge}))
    coeff=sum(head['weight'].numel()+head['bias'].numel() for head in heads.values())
    elapsed=time.monotonic()-start
    passed=all(z['passed'] for z in results.values()) and coeff<=spec['max_coefficients'] and elapsed<=spec['cpu_seconds_cap']
    dest=RUN/'weights.pt'
    torch.save(dict(heads=heads,parameters=coeff,protocol=spec),dest)
    result=dict(state='accepted' if passed else 'experimental',parameters=coeff,weights_sha256=checksum(dest),counts=counts,
        protocol_sha256=checksum(REPORT/'protocol.json'),code_sha256=checksum(Path(__file__)),cpu_seconds=elapsed,decision=results,
        excluded_v2_indices=sorted(excluded),scope='Single second fit; all V1 held-out forms excluded; eight genuinely distinct V2 forms per act. Noncoverage is deferral; actual tool execution remains host authorized.')
    atomic_status(REPORT/'fit-result.json',result)
    if passed:
        atomic_status(REPORT/'accepted-pin.json',dict(weights_sha256=result['weights_sha256'],parameters=coeff,
            evaluation_sha256=checksum(REPORT/'fit-result.json'),protocol_sha256=result['protocol_sha256']))
    print(json.dumps(dict(state=result['state'],parameters=coeff,counts=counts,metrics={k:(v['rows'],v['forms']) for k,v in results.items()})))


@lru_cache(maxsize=1)
def verified():
    pin_file=REPORT/'accepted-pin.json'
    if not pin_file.exists():raise RuntimeError("No approved slot-dialogue v2 fit")
    pin=json.loads(pin_file.read_text())
    if checksum(RUN/'weights.pt')!=pin['weights_sha256'] or checksum(REPORT/'protocol.json')!=pin['protocol_sha256'] or checksum(REPORT/'fit-result.json')!=pin['evaluation_sha256']:
        raise ValueError("Slot-dialogue v2 pin mismatch")
    result=json.loads((REPORT/'fit-result.json').read_text())
    if result['state']!='accepted' or not all(v['passed'] for v in result['decision'].values()):raise ValueError("Slot-dialogue v2 not accepted")
    state=torch.load(RUN/'weights.pt',weights_only=True,map_location='cpu')
    count=sum(h['weight'].numel()+h['bias'].numel() for h in state['heads'].values())
    if count!=pin['parameters'] or state['parameters']!=count:raise ValueError("Slot-dialogue v2 count mismatch")
    return state


def model_size():
    return verified()['parameters']


@torch.inference_mode()
def classify(text,pending=False):
    if not isinstance(text,str) or not 0<len(text.strip())<=256:return None
    state=verified(); mode='pending' if pending else 'open'
    d=decisions(mode,[text],state['heads'][mode],state['protocol'])[0]
    return d['prediction'] if d['prediction']!='none' else None


if __name__=='__main__':
    train()

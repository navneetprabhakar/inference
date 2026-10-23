"""Bounded benchmark input stream and durable aggregate work meter."""
import hashlib
import json
import math
import random
import sqlite3
import time
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parent
PROJECT=ROOT.parents[1]
REFERENCE=PROJECT/'restart/mac15m-feasibility-v1'
CHECKPOINT=PROJECT/'restart/foundation-stage2-v1/stage2-checkpoint.pt'
UPSTREAM=REFERENCE/'upstream'
TARGETS=131072
GIB=1024**3

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,value):
    p=Path(p);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(p)
def append(p,value):
    with Path(p).open('a') as f:f.write(json.dumps(value)+'\n');f.flush()
def rate(step):
    if step<1000:return .0005*step/1000
    return .00025*(1+math.cos(math.pi*(step-1000)/99000))

class Meter:
    def __init__(self):
        self.db=sqlite3.connect(ROOT/'work.sqlite',timeout=10)
        self.db.execute('CREATE TABLE IF NOT EXISTS work(id INTEGER PRIMARY KEY,phase TEXT,positions INTEGER,epoch REAL)')
    def reserve(self,n,phase):
        self.db.execute('BEGIN IMMEDIATE')
        used=self.db.execute('SELECT COALESCE(SUM(positions),0) FROM work').fetchone()[0]
        if used+n>160000000 or used+n+153846537>320000000:
            self.db.rollback();raise RuntimeError('AGGREGATE_POSITION_CAP')
        self.db.execute('INSERT INTO work(phase,positions,epoch) VALUES(?,?,?)',(phase,int(n),time.time()));self.db.commit()
    def total(self):return self.db.execute('SELECT COALESCE(SUM(positions),0) FROM work').fetchone()[0]

class Stream:
    """Exact upstream seed42/shard/block order; skip without model execution."""
    def __init__(self,split='train',skip_sequences=0):
        files=sorted((UPSTREAM/'data/TinyStories_all_data').glob('*.bin'))
        self.files=files[1:] if split=='train' else files[:1]
        self.rng=random.Random(42);self.shard=-1;self.cursor=0;self.indices=[];self.tokens=None
        self.rng.shuffle(self.files);self.consumed=0
        while skip_sequences:
            if self.cursor==len(self.indices):self._advance()
            n=min(skip_sequences,len(self.indices)-self.cursor)
            self.cursor+=n;skip_sequences-=n;self.consumed+=n
    def _advance(self):
        self.shard+=1
        if self.shard==len(self.files):self.rng.shuffle(self.files);self.shard=0
        self.tokens=np.memmap(self.files[self.shard],dtype=np.uint16,mode='r')
        self.indices=list(range(len(self.tokens)//256-1));self.rng.shuffle(self.indices);self.cursor=0
    def batch(self,n):
        out=np.empty((n,257),np.int32)
        for k in range(n):
            if self.cursor==len(self.indices):self._advance()
            first=self.indices[self.cursor]*256;out[k]=self.tokens[first:first+257]
            self.cursor+=1;self.consumed+=1
        return out

def mapping():
    pairs=[('tok_embeddings.weight','model.embed_tokens.weight')]
    for i in range(6):
        a=f'layers.{i}.';b=f'model.layers.{i}.'
        for old,new in [('attention.wq','self_attn.q_proj'),('attention.wk','self_attn.k_proj'),
                        ('attention.wv','self_attn.v_proj'),('attention.wo','self_attn.o_proj'),
                        ('feed_forward.w1','mlp.gate_proj'),('feed_forward.w2','mlp.down_proj'),
                        ('feed_forward.w3','mlp.up_proj'),('attention_norm','input_layernorm'),('ffn_norm','post_attention_layernorm')]:
            pairs.append((a+old+'.weight',b+new+'.weight'))
    pairs.append(('norm.weight','model.norm.weight'))
    return dict(pairs)

def origin():
    import torch
    expected=json.loads((ROOT/'contract.json').read_text())['reference']['checkpoint_sha256']
    if sha(CHECKPOINT)!=expected:raise RuntimeError('Origin checkpoint changed')
    return torch.load(CHECKPOINT,map_location='cpu',weights_only=False)

def moments(state):
    names=[k for k in state['model'] if k!='output.weight']
    out={}
    for group in state['optimizer']['param_groups']:
        selected=[k for k in names if (state['model'][k].ndim>=2)==(group['weight_decay']>0)]
        if len(selected)!=len(group['params']):raise RuntimeError('Optimizer key order mismatch')
        for key,index in zip(selected,group['params']):
            item=state['optimizer']['state'][index]
            if int(item['step'])!=state['optimizer_step']:raise RuntimeError('Origin optimizer step mismatch')
            out[mapping()[key]]={'m':item['exp_avg'].numpy(),'v':item['exp_avg_sq'].numpy()}
    if len(out)!=56:raise RuntimeError('Missing optimizer state')
    return out

def window(rows,first,last):
    return sum(r['targets']*max(0,min(last,r['end'])-max(first,r['start']))/(r['end']-r['start']) for r in rows)/(last-first)

"""Document-local shifted segments with one predecessor token, no target repeats."""
from dataclasses import dataclass
import numpy as np
from slm.common.tokenizer import STRUCTURAL

@dataclass(frozen=True)
class Segment:
    document:str
    first:int
    last:int
    inputs:tuple
    targets:tuple


def segments(document,content,context=512):
    if not isinstance(document,str) or not document or type(context) is not int or context<1:raise ValueError('Invalid segment identity/context')
    content=tuple(content)
    if any(type(i) is not int or i<len(STRUCTURAL) for i in content):raise ValueError('Content contains structural/invalid IDs')
    stream=(STRUCTURAL['bos'],)+content+(STRUCTURAL['eos'],)
    for start in range(0,len(stream)-1,context):
        end=min(start+context,len(stream)-1)
        yield Segment(document,start,end,stream[start:end],stream[start+1:end+1])


def collate(items,context=512):
    items=list(items)
    if not items or any(len(s.inputs)>context or len(s.inputs)!=len(s.targets) or s.last-s.first!=len(s.inputs) or not s.inputs for s in items):raise ValueError('Invalid batch')
    width=max(len(s.inputs) for s in items)
    x=np.full((len(items),width),STRUCTURAL['pad'],dtype=np.int32)
    y=x.copy();mask=np.zeros(x.shape,dtype=np.float32)
    for i,s in enumerate(items):
        n=len(s.inputs);x[i,:n]=s.inputs;y[i,:n]=s.targets;mask[i,:n]=1
    return x,y,mask,[(s.document,s.first,s.last) for s in items]

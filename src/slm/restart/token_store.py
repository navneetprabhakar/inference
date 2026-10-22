"""Immutable, hash-verified train-only token reader. No model dependencies."""
import hashlib,json
from pathlib import Path
import numpy as np
from slm.common.tokenizer import STRUCTURAL
from .segments import Segment,collate


def _read(root,relative):
    rel=Path(relative)
    if rel.is_absolute() or '..' in rel.parts:raise ValueError('Unsafe data path')
    p=root/rel
    if p.resolve(strict=True)!=p.absolute() or not p.is_file():raise ValueError('Redirected data path')
    return p.read_bytes()


class TrainingTokens:
    def __init__(self,path,*,manifest_sha256,vocab_size=8192):
        root=Path(path).absolute()
        raw=_read(root,'manifest.json')
        if hashlib.sha256(raw).hexdigest()!=manifest_sha256:raise ValueError('Unbound data manifest')
        m=json.loads(raw)
        if m['split']!='train' or type(vocab_size) is not int or vocab_size<=len(STRUCTURAL):
            raise ValueError('Train-only token store required')
        if not {'tokens.u16','index.jsonl'}<=set(m['files']):raise ValueError('Missing data inventory')
        files={}
        for name,digest in m['files'].items():
            value=_read(root,name)
            if hashlib.sha256(value).hexdigest()!=digest:raise ValueError('Data file changed: '+name)
            if name in ('tokens.u16','index.jsonl'):files[name]=value
        # Own immutable bytes: later external file edits cannot alter an active reader.
        self._tokens=np.frombuffer(files['tokens.u16'],dtype='<u2')
        if len(self._tokens)!=m['targets']:raise ValueError('Token count mismatch')
        self._index={};families=set();offset=0
        for line in files['index.jsonl'].decode().splitlines():
            row=json.loads(line);doc=row['audit_id'];n=row['targets']
            if (not isinstance(doc,str) or not doc or doc in self._index
                    or not isinstance(row['family_id'],str) or not row['family_id']
                    or row['family_id'] in families or row['split']!='train' or row['partial'] is not False
                    or type(n) is not int or n<1 or row['full_document_targets']!=n
                    or type(row['offset']) is not int or row['offset']!=offset):
                raise ValueError('Invalid training index')
            values=self._tokens[offset:offset+n]
            if (len(values)!=n or values[-1]!=STRUCTURAL['eos']
                    or np.any(values[:-1]<len(STRUCTURAL)) or np.any(values>=vocab_size)):
                raise ValueError('Invalid content IDs or EOS')
            self._index[doc]=row;families.add(row['family_id']);offset+=n
        if offset!=len(self._tokens) or len(self._index)!=m['documents'] or len(families)!=m['families']:
            raise ValueError('Incomplete index coverage')
        self.manifest_sha256=manifest_sha256
        self.targets=offset
        self.documents=len(self._index)

    def segment(self,document,first,last):
        if (document not in self._index or type(first) is not int or type(last) is not int
                or not 0<=first<last<=self._index[document]['targets'] or last-first>512):
            raise ValueError('Invalid scheduled span')
        base=self._index[document]['offset']
        targets=tuple(map(int,self._tokens[base+first:base+last]))
        predecessor=STRUCTURAL['bos'] if first==0 else int(self._tokens[base+first-1])
        return Segment(document,first,last,(predecessor,)+targets[:-1],targets)

    def microbatch(self,spans):
        spans=list(spans)
        if not 1<=len(spans)<=4:raise ValueError('Invalid microbatch size')
        rows=[self.segment(*s) for s in spans]
        x,y,mask,identities=collate(rows)
        return x,y,mask,mask.astype(bool),identities

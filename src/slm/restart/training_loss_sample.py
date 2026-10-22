"""Fixed training-only diagnostic subset, selected before any candidate output.

Whole documents in SHA256 order until at least 200k targets. No model updates;
evaluation positions are charged to runtime, not optimizer exposure counts.
"""
import hashlib
import json
from .token_store import TrainingTokens


def specification(store):
    rows=sorted(store._index.values(),key=lambda r:hashlib.sha256(('m1-train-loss-v1:'+r['family_id']+':'+r['audit_id']).encode()).hexdigest())
    selected=[];targets=0
    for row in rows:
        selected.append(row['audit_id']);targets+=row['targets']
        if targets>=200000:break
    if targets<200000:raise ValueError('Insufficient training-loss diagnostic supply')
    return {'schema':1,'purpose':'fixed-training-loss-diagnostic','source_manifest_sha256':store.manifest_sha256,
            'selection':'sha256(m1-train-loss-v1:family:id), whole documents until >=200000 targets',
            'documents':selected,'targets':targets,'scored_utf8_bytes':sum(store._index[d]['scored_utf8_bytes'] for d in selected)}


class TrainingLossSample:
    def __init__(self,root,*,source_manifest_sha256,spec_raw,spec_sha256,vocab_size=8192):
        if hashlib.sha256(spec_raw).hexdigest()!=spec_sha256:raise ValueError('Changed training-loss specification')
        self.source=TrainingTokens(root,manifest_sha256=source_manifest_sha256,vocab_size=vocab_size)
        spec=json.loads(spec_raw)
        if spec!=specification(self.source):raise ValueError('Changed deterministic training-loss selection')
        self.rows=tuple(self.source._index[d] for d in spec['documents'])
        self.targets=spec['targets'];self.scored_bytes=spec['scored_utf8_bytes'];self.vocab_size=vocab_size
        self.manifest_sha256=spec_sha256

    def segments(self):
        for row in self.rows:
            for first in range(0,row['targets'],512):
                yield self.source.segment(row['audit_id'],first,min(first+512,row['targets']))

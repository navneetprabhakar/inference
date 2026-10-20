"""Pinned local-only conversation research reader; original admission readers unchanged."""
# Creator: Navneet Prabhakar
import json
from pathlib import Path
import numpy as np
from slm.data.stream_hash import sha
from slm.data.schema import digest
from slm.data.tokenized import ShardBatches
SOURCES={'smol-contraints','smol-summarize-20k','smollm-rewrite-30k'}

def read_release(root,policy_hash):
    root=Path(root);policy=json.loads((root/'admission.json').read_text())
    if sha(root/'admission.json')!=policy_hash:raise ValueError('Pinned conversation admission differs')
    if policy.get('kind')!='private-local-conversation-research-v1' or policy.get('authorized_by')!='Navneet Prabhakar' or policy.get('training_approved') is not True or policy.get('human_attestation') is not False or policy.get('content_category')!='unreviewed' or policy.get('cloud_allowed') is not False or set(policy.get('allowed_constituents',[]))!=SOURCES:
        raise ValueError('Explicit isolated private local SFT scope required')
    if policy['max_physical_passes']!=2 or policy['maximum_new_sft_positions']>20000000:raise ValueError('Conversation research exposure cap differs')
    for p,h in policy['input_bindings'].items():
        if sha(p)!=h:raise ValueError('Conversation admission input differs: '+p)
    rows=[json.loads(x) for x in (root/'train.jsonl').open()]
    if sha(root/'train.jsonl')!=policy['train_sha256'] or len(rows)!=policy['train_rows'] or len({r['split_group'] for r in rows})!=len(rows):raise ValueError('Exact complete train membership differs')
    for r in rows:
        if r['source'] not in SOURCES or r['official_split']!='train' or r['content_category']!='unreviewed':raise ValueError('Unadmitted source/split/category')
    return rows,policy

class ConversationBatches:
    def __init__(self,root,tokenizer,expected_plan_hash):
        self.root=Path(root);self.plan=json.loads((self.root/'schedule.json').read_text())
        if sha(self.root/'schedule.json')!=expected_plan_hash:raise ValueError('Frozen finite schedule differs')
        rows,policy=read_release(self.root,self.plan['admission_sha256'])
        self.base=ShardBatches(self.root/'tokens',tokenizer,self.plan['token_manifest_sha256'])
        self.schedule=np.array(self.plan['schedule'],dtype=np.int64)
        if self.schedule.shape!=(2,len(rows)) or any(sorted(s.tolist())!=list(range(len(rows))) for s in self.schedule):raise ValueError('Exactly two complete finite passes required')
        self.schedule=self.schedule.flatten();self.prefix=[(0,0)]
        for i in self.schedule:
            a=self.base.counts(int(i));b=self.base.counts(int(i)+1);p=self.prefix[-1];self.prefix.append((p[0]+b[0]-a[0],p[1]+b[1]-a[1]))
        if self.prefix[-1]!=(self.plan['physical_positions'],self.plan['supervised_positions']) or self.prefix[-1][0]>policy['maximum_new_sft_positions']:raise ValueError('Physical schedule budget differs')
        self.fingerprint=expected_plan_hash;self.vocab_size=self.base.vocab_size;self.max_length=self.base.max_length;self.tokenizer_hash=self.base.tokenizer_hash;self.items=self
    def __len__(self):return len(self.schedule)
    def __getitem__(self,index):
        if type(index) is not int or not 0<=index<len(self):raise IndexError(index)
        return self.base[int(self.schedule[index])]
    def counts(self,cursor):
        if type(cursor) is not int or not 0<=cursor<=len(self):raise ValueError('Finite schedule cursor required')
        return self.prefix[cursor]
    def close(self):self.base.close()
    def __enter__(self):return self
    def __exit__(self,*args):self.close()

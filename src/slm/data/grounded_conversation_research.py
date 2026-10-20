"""Isolated finite local human-QA/replay batches; original readers remain unchanged."""
# Creator: Navneet Prabhakar
import collections,json
from pathlib import Path
from slm.data.schema import digest
from slm.data.stream_hash import sha
from slm.data.tokenized import ShardBatches

def read_release(root,expected_hash):
    root=Path(root);p=json.loads((root/'admission.json').read_text())
    if sha(root/'admission.json')!=expected_hash:raise ValueError('Grounded admission differs')
    if (p.get('kind')!='private-local-grounded-conversation-v1' or p.get('authorized_by')!='Navneet Prabhakar' or p.get('training_approved') is not True or p.get('human_attestation') is not False or p.get('content_category')!='unreviewed' or p.get('cloud_allowed') is not False or p.get('max_physical_passes')!=2):raise ValueError('Explicit isolated local research scope required')
    for name,h in p['inputs'].items():
        if sha(name)!=h:raise ValueError('Grounded admission input changed: '+name)
    rows=[json.loads(l) for l in (root/'train.jsonl').open()]
    if sha(root/'train.jsonl')!=p['train_sha256'] or len(rows)!=p['train_rows'] or len({r['paragraph_component'] for r in rows})!=len(rows):raise ValueError('Complete unique paragraph dialogues required')
    heldouts={r['split_group'] for name in ('development','reserved') for l in Path(p['preparation_root'],name+'-references.jsonl').open() for r in [json.loads(l)]}
    blocked={r['split_group'] for l in Path(p['preparation_root'],'direct-judgments.jsonl').open() for r in [json.loads(l)] if r['judgment']!='consider'}
    for r in rows:
        if r['official_split']!='train' or r['source']!='SQuAD-1.1' or r['content_category']!='unreviewed' or r['split_group'] in heldouts|blocked or [m['role'] for m in r['messages']]!=['user','assistant']*3:raise ValueError('Unadmitted source/heldout/negative dialogue')
        for t,q in enumerate(r['original_questions']):
            a=q['answers'][0]
            if r['context'][a['answer_start']:a['answer_start']+len(a['text'])]!=a['text'] or r['messages'][2*t+1]['content']!=a['text']:raise ValueError('Original human answer differs')
    replay=[json.loads(l) for l in (root/'replay.jsonl').open()]
    original={r['split_group']:r for l in Path(p['untouched_retention_source']).open() for r in [json.loads(l)]}
    if sha(root/'replay.jsonl')!=p['replay_sha256'] or len(replay)!=p['replay_rows'] or len({r['split_group'] for r in replay})!=len(replay):raise ValueError('Finite untouched replay membership differs')
    if any(original.get(r['split_group'])!=r for r in replay):raise ValueError('Replay must be intact previously untouched family')
    return rows,replay,p

class GroundedBatches:
    def __init__(self,root,tokenizer,expected_hash):
        root=Path(root);self.plan=json.loads((root/'schedule.json').read_text())
        if sha(root/'schedule.json')!=expected_hash:raise ValueError('Finite grounded schedule changed')
        rows,replay,policy=read_release(root,self.plan['admission_sha256'])
        self.bases=[ShardBatches(root/name,tokenizer,self.plan['token_manifests'][name]) for name in ('qa-tokens','replay-tokens')]
        self.schedule=self.plan['schedule']
        if not self.schedule or any(type(s) is not list or len(s)!=2 or any(type(i) is not int for i in s) or s[0] not in (0,1) or not 0<=s[1]<len(self.bases[s[0]]) for s in self.schedule):raise ValueError('Explicit finite batch address required')
        counts=collections.Counter(tuple(s) for s in self.schedule)
        if counts!=collections.Counter({(source,i):2 for source,b in enumerate(self.bases) for i in range(len(b))}):raise ValueError('Exactly two finite passes, no variants or implicit wrap')
        self.prefix=[(0,0)]
        for source,i in self.schedule:
            a=self.bases[source].counts(i);b=self.bases[source].counts(i+1);p=self.prefix[-1];self.prefix.append((p[0]+b[0]-a[0],p[1]+b[1]-a[1]))
        if self.prefix[-1]!=(self.plan['physical_positions'],self.plan['supervised_positions']) or self.prefix[-1][0]>policy['maximum_remaining_sft_positions']:raise ValueError('Exact physical exposure differs')
        self.fingerprint=expected_hash;self.vocab_size=self.bases[0].vocab_size;self.tokenizer_hash=self.bases[0].tokenizer_hash;self.max_length=max(b.max_length for b in self.bases);self.items=self
        if any(b.vocab_size!=self.vocab_size or b.tokenizer_hash!=self.tokenizer_hash for b in self.bases):raise ValueError('Components require identical tokenizer')
    def __len__(self):return len(self.schedule)
    def __getitem__(self,i):
        if type(i) is not int or not 0<=i<len(self):raise IndexError(i)
        source,index=self.schedule[i];return self.bases[source][index]
    def counts(self,cursor):
        if type(cursor) is not int or not 0<=cursor<=len(self):raise ValueError('Finite cursor required')
        return self.prefix[cursor]
    def close(self):
        for b in self.bases:b.close()
    def __enter__(self):return self
    def __exit__(self,*args):self.close()

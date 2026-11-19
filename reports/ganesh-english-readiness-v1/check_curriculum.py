"""Verify the proposed split and produce the exposed, teacher-free rollout prompts."""
import collections
import json
import sys
from pathlib import Path
from prepare_curriculum import ROOT, REPORT, OUT, SOURCE, digest

sys.path[:0]=[str(ROOT/'reports/ganesh-english-sourcing-v1/scale-1000'),str(ROOT)]
import verify_selection as v
import check_selection_overlap as overlap

def read(path):
    return list(map(json.loads,path.read_text().splitlines()))

receipt=json.loads((REPORT/'curriculum.json').read_text())
assert receipt['parent_sha256']==digest(SOURCE)
original={r['id']:r for r in read(SOURCE)}
ledger=json.loads((REPORT/'split-ledger.json').read_text())
assert receipt['ledger_sha256']==digest(REPORT/'split-ledger.json')
assert len(ledger)==len(original)==len({r['id'] for r in ledger})
prior=[]
for name in overlap.EXPOSED:
    prior.extend((r.get('group'),overlap.fingerprint(r)) for r in read(ROOT/name) if 'messages' in r)
tok=v.RustBPETokenizer.from_directory(str(ROOT/'runs/ownbase-v2-data/tokenizer'))
audit={}
for split in ('train','development'):
    path=OUT/(split+'.jsonl')
    assert digest(path)==receipt[split]['sha256']
    data=read(path);mass=collections.Counter();targets=set();prompts=[];references=[]
    assert {r['source_id'] for r in data}=={r['id'] for r in ledger if r['split']==split}
    bounds=v.native(data)
    for row in data:
        source=original[row['source_id']]
        assert source['messages']==row['messages'] and source['group']==row['group']
        enc=v.encode_conversation(tok,row['messages'],policies=row['policies'],context=2048)
        assert sum(enc['mask'])==row['target_positions']
        mass[row['family']]+=sum(enc['mask'])
        targets.update(v.norm(m['content']) for m in row['messages'][1::2])
        text,grams=overlap.fingerprint(row)
        for group,(other,othergrams) in prior:
            assert text!=other and len(grams&othergrams)/max(1,len(grams|othergrams))<.35,(group,row['group'])
        prior.append((row['group'],(text,grams)))
        if split=='development':
            prompts.append(dict(id=row['group'],family=row['family'],turns=[dict(user=m['content'],policy=policy) for m,policy in zip(row['messages'][::2],row['policies'])]))
            references.append(dict(id=row['group'],source_id=row['source_id'],assistant_targets=[m['content'] for m in row['messages'][1::2]],recall_probe=source.get('recall_probe')))
    audit[split]=dict(native=bounds,unique_normalized_assistant_texts=len(targets),family_target_mass=mass)
    if prompts:
        for name,records in [('development-prompts',prompts),('reviewer-references',references)]:
            (OUT/(name+'.json')).write_text(json.dumps(records,ensure_ascii=False)+'\n')
audit['training_admitted']=False
audit['scoring']='Use generated conversation histories. Score every planned assistant turn for correctness, grounded facts, latest constraints, requested form and permitted action. Record reasons and first failure. Blocked turns count as failures. Complete session requires all turns to pass. References are assessor-only. This exposed split changes both source and topic; results do not isolate either effect.'
(REPORT/'curriculum-checks.json').write_text(json.dumps(audit,indent=2)+'\n')
print('Passed split membership, source equality, both native policies, exact targets and exposed lexical overlap.')

"""Recheck IDs, votes, split families, exact input overlap, retained text and loader determinism."""
from collections import Counter
from hashlib import sha256
import json
from build import DEST,HERE,official,norm,digest
from snli_semantic import training_pairs,validation_pairs

def main():
    expected={};families={};images={};phrases={};counts=Counter()
    for split,f in [('train','train.jsonl'),('validation','internal-validation.jsonl')]:
        families[split]=set();images[split]=set();phrases[split]=set()
        for l in (DEST/f).open():
            r=json.loads(l);assert r['split']==split and r['official_split']=='train'
            assert not r['pair_id'].startswith('vg_') and not r['caption_id'].startswith('vg_')
            assert r['pair_id'] not in expected
            assert r['pair_sha256']==digest(norm(r['premise'])+'\0'+norm(r['hypothesis']))
            expected[r['pair_id']]=(r['premise'],r['hypothesis'],r['label'],r['caption_id'],r['recorded_votes'],r['official_row'])
            families[split].add(r['group']);images[split].add(r['image_id']);phrases[split].update((norm(r['premise']),norm(r['hypothesis'])))
            counts[(split,r['annotation_tier'])]+=1
    assert families['train'].isdisjoint(families['validation'])
    assert images['train'].isdisjoint(images['validation'])
    assert phrases['train'].isdisjoint(phrases['validation'])
    m=sha256();found=set()
    for i,r in enumerate(official(m)):
        if r['pairID'] not in expected:continue
        assert expected[r['pairID']]==(r['sentence1'].strip(),r['sentence2'].strip(),r['gold_label'],r['captionID'],r['annotator_labels'],i)
        found.add(r['pairID'])
    assert len(found)==len(expected) and m.hexdigest()==json.loads((HERE/'screen.json').read_text())['raw']['train_jsonl_sha256']
    x=training_pairs(1459,limit=32);assert x==training_pairs(1459,limit=32)
    assert all(r['split']=='train' and r['annotation_tier']=='multi-unanimous' for r in x)
    y=validation_pairs(1459,limit=32);assert all(r['split']=='validation' for r in y)
    v=dict(original_verified_pairs=len(expected),exact_input_sentence_overlap=0,group_overlap=0,image_overlap=0,
           train_member_sha256=m.hexdigest(),split_annotator_counts={'/'.join(k):v for k,v in counts.items()},
           train_seed1459_first32_sha256=digest(json.dumps(x,sort_keys=True,ensure_ascii=False)))
    (HERE/'verification.json').write_text(json.dumps(v,indent=2)+'\n');print(v)
if __name__=='__main__':main()

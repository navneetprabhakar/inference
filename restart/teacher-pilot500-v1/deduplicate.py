"""Remove a manually confirmed shared planning template, preserving split labels."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
from slm.common.tokenizer import BPE

ROOT=Path(__file__).resolve().parent.parent/'teacher-pilot500-v2'

def main():
    rows=[json.loads(l) for l in (ROOT/'curated.jsonl').read_text().splitlines()]
    planning=[r for r in rows if r['category']=='planning']
    assert len(planning)==50
    # Whole-review confirmed identical numerical problem and answer schedule;
    # topic noun and surface phrasing vary. Do not promote any heldout to train.
    canonical=min(r['id'] for r in planning if r['split']=='train')
    removed=[r for r in planning if r['id']!=canonical]
    kept=[r for r in rows if r['category']!='planning' or r['id']==canonical]
    assert all(r['split'] in ('train','development','test') for r in kept)
    counts=defaultdict(Counter);bpe=BPE.load(ROOT.parent/'execution-v1/tokenizer-8192')
    shingles=[]
    for r in kept:
        x,y,mask=bpe.serialize(r['messages'])
        recount=dict(content_tokens=sum(len(bpe.encode(m['content'])) for m in r['messages']),
            serialized_predicted_positions=len(y),assistant_supervised_targets=sum(mask),
            utf8_bytes=sum(len(m['content'].encode()) for m in r['messages']))
        assert recount==r['counts']
        for split in ('all',r['split']):counts[split].update(recount);counts[split].update(documents=1)
        text=' '.join(m['content'] for m in r['messages']);words=re.findall(r'\w+',text.lower())
        shingles.append(set(zip(*(words[k:] for k in range(5)))))
    for i,a in enumerate(shingles):
        for b in shingles[i+1:]:
            overlap=len(a&b)
            assert overlap/(len(a)+len(b)-overlap)<.8
    (ROOT/'salvaged.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in kept))
    receipt=dict(status='QUALITY_CURATED_AND_PLANNING_TEMPLATE_DEDUPLICATED_CANDIDATES',
        generated=500,quality_holds=77,planning_template_removals=len(removed),canonical_planning_id=canonical,
        planning_ids_removed=[r['id'] for r in removed],kept_candidates=len(kept),
        counts={k:dict(v) for k,v in counts.items()},exact_duplicates=0,word5gram_jaccard80_pairs_remaining=0,
        original_splits_preserved=True,heldout_promotions_to_train=0,
        broad_conversation_training_readiness='NOT_PASSED',
        original_frozen_corpus_admissions=0,
        caveat='All remaining examples still use a narrow event/task curriculum. Reused task designs and repeated short assistant answers remain; zero detected 80% word-shingle pairs is not a proof of independent evaluation or zero leakage.')
    (ROOT/'usable-counts.json').write_text(json.dumps(receipt,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
    print(json.dumps({k:v for k,v in receipt.items() if k!='planning_ids_removed'},ensure_ascii=False))

if __name__=='__main__':main()

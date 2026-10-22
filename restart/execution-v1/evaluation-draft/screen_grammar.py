"""Exact/near lexical screening of draft grammar; not complete ancestry proof."""
import collections,csv,hashlib,json,sqlite3,math
from pathlib import Path
from slm.restart.edu_filter import normalized
O=Path(__file__).resolve().parent;R=O.parents[2]

def main():
    patterns=[];inverted=collections.defaultdict(set);files={};seen=set();entities={};families={}
    for split in ['development','final']:
        p=O/(split+'-grammar-v2-candidates.jsonl');files[p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
        rows=[json.loads(x) for x in p.read_text().splitlines()]
        assert len(rows)==200
        assert collections.Counter(r['subtype'] for r in rows)==dict.fromkeys(['agreement','tense','pronoun','determiner'],50)
        entities[split]={r['entity'] for r in rows};families[split]={r['template_family'] for r in rows}
        for subtype in ['agreement','tense','pronoun','determiner']:
            assert collections.Counter(r['correct_index'] for r in rows if r['subtype']==subtype)=={0:25,1:25}
        for row in rows:
            assert row['length_match'] and len(set(row['continuation_token_lengths']))==1
            for choice,text in enumerate(row['alternatives']):
                norm=normalized(text);assert norm not in seen,(row['id'],'duplicate');seen.add(norm)
                words=norm.split();grams={tuple(words[i:i+5]) for i in range(len(words)-4)}
                assert grams
                idx=len(patterns);patterns.append((row['id'],choice,norm,grams))
                for gram in grams:inverted[gram].add(idx)
    assert not entities['development']&entities['final']
    assert not families['development']&families['final']
    manifest=R/'restart/fineweb-salvage-reviewed-v1/accepted-manifest.csv'
    with manifest.open() as f:train={int(r['audit_id']):r['family_id'] for r in csv.DictReader(f) if r['split']=='train'}
    db=sqlite3.connect(f'file:{R}/restart/corpus-audit-v1/audit.sqlite?mode=ro',uri=True)
    counts=collections.Counter();hits=[]
    def scan(doc_id,origin,text,family):
        words=text.split();gramset={tuple(words[i:i+5]) for i in range(len(words)-4)}
        candidates=collections.Counter()
        for gram in gramset:
            for idx in inverted.get(gram,()):candidates[idx]+=1
        for idx,shared in candidates.items():
            item,choice,norm,grams=patterns[idx]
            exact=(' '+norm+' ') in (' '+text+' ')
            near=shared/len(grams)>=.8
            if exact or near:hits.append(dict(item=item,choice=choice,document=doc_id,origin=origin,family=family,exact_containment=exact,shared_fivegram_fraction=shared/len(grams)))
        counts[origin]+=1
    for doc_id,norm in db.execute('SELECT id,normalized FROM docs'):
        if doc_id in train:scan(doc_id,'training',norm,train[doc_id])
    for doc_id,norm,origin in db.execute('SELECT id,normalized,origin FROM protections'):
        scan(doc_id,'existing_protection',norm,origin)
    result={'status':'LEXICAL_SCREEN_PASS' if not hits else 'OVERLAP_REVIEW_REQUIRED','input_sha256':files,'train_manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest(),'screened_documents':dict(counts),'grammar_items':400,'distinct_alternative_texts':len(patterns),'hits':hits,'threshold':'Full normalized sentence containment OR >=80% of alternative distinct word-fivegrams in a document.','limitations':['Short grammar frames can overlap innocently; hits require review.','This is not proof of all semantic/ancestral non-overlap.','Only 20 template families per split; do not describe 200 instances as 200 independent templates.','Draft artifacts remain unfrozen until all evaluation suites and final leakage checks are complete.']}
    (O/'grammar-v2-screen.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='hits'}|{'hit_count':len(hits)},indent=2))
if __name__=='__main__':main()

"""Verify authored narrative artifacts and screen corpus/protected text overlap."""
import collections,csv,hashlib,json,sqlite3
from pathlib import Path
from slm.common.tokenizer import BPE
from slm.restart.edu_filter import normalized
O=Path(__file__).resolve().parent;R=O.parents[2];D=O/'authored-narratives-v2'
def main():
    receipt=json.loads((D/'receipt.json').read_text());tok=BPE.load(O.parent/'tokenizer-8192')
    assert hashlib.sha256((O.parent/'tokenizer-8192/manifest.json').read_bytes()).hexdigest()==receipt['tokenizer_manifest_sha256']
    patterns=[];index=collections.defaultdict(set);names={};frames={};texts=set();ids=set()
    for split in ['development','final']:
        p=D/(split+'-narrative.jsonl');assert hashlib.sha256(p.read_bytes()).hexdigest()==receipt['files_sha256'][p.name]
        rows=[json.loads(x) for x in p.read_text().splitlines()];assert len(rows)==100
        names[split]={r['entity'] for r in rows};frames[split]={r['template_family'] for r in rows}
        assert len(names[split])==5 and len(frames[split])==20
        assert set(collections.Counter(r['template_family'] for r in rows).values())=={5}
        for row in rows:
            assert row['id'] not in ids;ids.add(row['id'])
            text=row['prefix'];assert 30<=len(text.split())<=60
            assert tok.encode(text)==row['prefix_token_ids'] and tok.decode(row['prefix_token_ids'])==text
            assert row['entity'] in text and len(row['premise_facts'])==3
            assert row['origin']=='assistant_authored_evaluation_only'
            assert (row['temperature'],row['top_p'],row['minimum_words'],row['maximum_words'],row['early_eos_failure_below_words'])==(.7,.9,80,120,40)
            assert row['generation_seed']==int.from_bytes(hashlib.sha256(row['id'].encode()).digest()[:4],'big')
            norm=normalized(text);assert norm not in texts;texts.add(norm)
            words=norm.split();grams={tuple(words[i:i+5]) for i in range(len(words)-4)}
            ix=len(patterns);patterns.append((row['id'],split,norm,grams))
            for gram in grams:index[gram].add(ix)
    assert not names['development']&names['final'] and not frames['development']&frames['final']
    manifest=R/'restart/fineweb-salvage-reviewed-v1/accepted-manifest.csv'
    train={int(r['audit_id']) for r in csv.DictReader(manifest.open()) if r['split']=='train'}
    db=sqlite3.connect(f'file:{R}/restart/corpus-audit-v1/audit.sqlite?mode=ro',uri=True)
    counts=collections.Counter();hits=[]
    def scan(key,origin,text,exclude_split=None):
        words=text.split();grams={tuple(words[i:i+5]) for i in range(len(words)-4)};candidates=collections.Counter()
        for gram in grams:
            for ix in index.get(gram,()):candidates[ix]+=1
        for ix,shared in candidates.items():
            item,split,norm,ref=patterns[ix]
            if split==exclude_split:continue
            exact=(' '+norm+' ') in (' '+text+' ')
            if exact or shared/len(ref)>=.8:hits.append(dict(item=item,document=key,origin=origin,exact=exact,fivegram_fraction=shared/len(ref)))
        counts[origin]+=1
    for key,norm in db.execute('SELECT id,normalized FROM docs'):
        if key in train:scan(key,'training',norm)
    for key,norm in db.execute('SELECT id,normalized FROM protections'):scan(key,'existing_protection',norm)
    for item,split,norm,_ in patterns:scan(item,'opposite_evaluation_split',norm,split)
    result=dict(status='LEXICAL_SCREEN_PASS' if not hits else 'OVERLAP_REVIEW_REQUIRED',input_sha256=receipt['files_sha256'],train_manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),screened_documents=dict(counts),items=200,template_families_per_split=20,hits=hits,threshold='Full normalized prefix containment OR >=80% distinct word-fivegram containment; opposite split checked in both directions.',limitations=['Lexical screen is not exhaustive semantic ancestry proof.','All same-frame variants remain in their own split.','Final custody and combined-suite provenance binding remain pending.'])
    (D/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()

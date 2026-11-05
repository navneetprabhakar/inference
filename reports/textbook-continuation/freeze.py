"""Build attributed little-endian token streams from reviewed, source-grouped candidates."""
from collections import Counter,defaultdict
from pathlib import Path
import json,random,re,sys
import numpy as np
from local import DEST,ROOT,HERE,h,Dedupe,file_hash,norm,STORY_REV,WIKI_REV,SALT
from tokenizer import load
FINAL=ROOT/'data/balanced-continuation-v1'
WIKI_BAD=re.compile(r'\b(?:politic\w*|government|election\w*|democrat\w*|republican\w*|partisan|president|currently|current (?:head|leader|chair|president)|israel\w*|palestin\w*|refugee\w*|blood|medical|tissue sample|patient\w*|treatment|medication|genocide|slave\w*|enslav\w*|religio\w*|christian\w*|church|racis\w*|racial|military|prison|war\w*|soldier\w*|millionaire|wealthiest|the largest in the world|number.one|world.s largest|reportedly|alleg\w*)\b|\b(?:named|called|titled|are|were|about|had|for|as|at|to|on|a|and|is|in|of|was|the|by|from)\s*[.,;]|\b(?:is|to|in|at|about|of|by|was|from|for|a)\s{2,}\w|\(\s*\)|\s{2,}\.',re.I)
STORY_BAD=re.compile(r'\b(?:stupid|idiot|gun\w*|knife|hurt herself|hurt himself|disappear forever|dead|drown\w*|burn\w*|shot|dangerous medicine|poison\w*|kidnap\w*|blood)\b',re.I)
def candidate(r):
    if r['source']=='wiki':return not WIKI_BAD.search(r['text']+' '+r['title'])
    if r['source']=='stories':return not STORY_BAD.search(r['text'])
    if re.search(r'\b(?:weapon\w*|suicid\w*|chemotherapy|diagnos\w*|plutonium|cancer\w*|malaria|heart attack|patient\w*|prescription|blood pressure|cholesterol|medical treatment|reagan|partisan|vice president from|immunotherapy|clinical advice|immunodeficien\w*|mental illness|at the time of this writing|currently|today.s inflation)\b',r['text'],re.I):return False
    if re.search(r'\b(?:I felt|I heard|I was born|I remember|I stretched|my mother|my father|my novel)\b',r['text']):return False
    return True
def main():
    from argparse import ArgumentParser
    p=ArgumentParser();p.add_argument('--output',type=Path,default=FINAL);args=p.parse_args()
    out=args.output
    if out.exists():raise ValueError('existing output')
    stage=out.with_name(out.name+'.partial');stage.mkdir(parents=True)
    allrows=[]
    for name in ['local.jsonl','textbooks.jsonl']:
        with (DEST/name).open() as f:allrows.extend(r for line in f if candidate(r:=json.loads(line)))
    # Candidate priority is stable. Novel textbooks are preferred to duplicates from any other source.
    rng=random.Random(182701)
    rng.shuffle(allrows)
    allrows.sort(key=lambda r:(r['split']=='train',r['source']!='textbook'))
    d=Dedupe();tok=load();totals=Counter();dropped=Counter();selected=[]
    review=json.loads((HERE/'admission.json').read_text())
    held=set(review['held_document_ids'])
    for r in allrows:
        if r.get('book') in review['held_books'] or r['document_id'] in held:continue
        source=r['source']
        if source=='stories' and totals[(source,r['split'])]>=(2600000 if r['split']=='train' else 150000):
            continue
        if not d.add(r['text']):
            dropped[source]+=1;continue
        totals[(source,r['split'])]+=r['tokens']
        selected.append(r)
    shards={}
    rng.shuffle(selected)
    with (stage/'documents.jsonl').open('w') as docs:
        for source in ['wiki','stories','textbook']:
            for split in ['train','validation']:
                key=source+'-'+split
                file=stage/(key+'.u16');offset=0;n=0
                with file.open('wb') as f:
                    for r in selected:
                        if r['source']!=source or r['split']!=split:continue
                        text=r.pop('text')
                        ids=tok.encode(text).ids+[50256]
                        assert len(ids)==r['tokens'] and 50256 not in ids[:-1]
                        f.write(np.asarray(ids,dtype='<u2').tobytes())
                        docs.write(json.dumps(dict(r,offset=offset),ensure_ascii=False)+'\n')
                        offset+=len(ids);n+=1
                shards[key]=dict(docs=n,tokens=offset,sha256=file_hash(file))
    info=dict(shards=shards,documents_sha256=file_hash(stage/'documents.jsonl'),split_salt=SALT,
              prior_scope='All named GPT-2 feasibility/v1/v2/v3 input indexes excluded by story row interval and article-family. Independent data ancestry; seen by other historical models unknown.',
              source_revision=dict(TinyStories=STORY_REV,Wikipedia=WIKI_REV,OpenStax='See title-specific index.'),
              dedup_exclusions=dropped,textbook_titles_sha256=file_hash(HERE/'titles.json'),
              review_policy_sha256=file_hash(HERE/'admission.json'),
              source_candidates_sha256={p:file_hash(DEST/p) for p in ['textbooks.jsonl','local.jsonl']},
              local_use='Local noncommercial research. Preserve separate source licenses and publisher attribution. No redistribution or derivative licensing conclusion.')
    (stage/'manifest.json').write_text(json.dumps(info,indent=2)+'\n');stage.rename(out)
    print(json.dumps(shards,indent=2))
if __name__=='__main__':main()

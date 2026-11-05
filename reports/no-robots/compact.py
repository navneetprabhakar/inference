"""Narrow subcohorts to short self-contained and visibly attributable task text."""
import re,json,sys
from pathlib import Path
from hashlib import sha256
HERE=Path(__file__).resolve().parent
DEST=HERE.parents[1]/'data/no-robots'
EXCLUDE=re.compile(r"\b(?:article|lyrics|songwriter|song|newspaper|journalist|press release|social media post|tweet|novel|book excerpt|product description|brand name|advertis\w*|fan ?fiction|trademark|born|died|politic\w*|quarterback|invasion|presidential|celebrity|economy|liquidity|forex|financial|fundrais\w*|forecast|recipe|vitamin|exercise program|diet\w*|nutrition\w*|calorie|gluten|deficien\w*|drinking|voting|religio\w*|healing|actor|director|film|release date|album|Harry Potter|Disney|Pokemon|Mickey|Marvel|Shrek|Elvis|Batman|YouTuber|TikTok|instagram|twitter|street|romantic|love letter|stripper|income|life story|franchis\w*|war|battle|attack|horror|dead|drown\w*|treat\w* illness|HIV|glucose|presidency|trump|medical|health|anatomy|blood|mature audience|burn|antibiotic\w*|newborn|Airbnb|according to|said that|lives in|facebook|daily mail|new york times|respectively in|restaurant\w*|travel destination|rental|R-rated|investor\w*|birthdate|my address|lastname|physical therapist|bleach)\b|\[\s*\d+\s*\]|[£€$]\s*\d|[“\"][^”\"]{65,}[”\"]",re.I)
def eligible(r):
    c=r['category'];q,a=[m['text'] for m in r['history'][:2]]
    t=q+' '+a
    if EXCLUDE.search(t) or len(q.split())>95 or len(a.split())>90:return False
    if re.search(r'\b(?:19\d\d|20[012]\d)\b',t):return False
    if c in ('Extract','Closed QA','Summarize','Rewrite','Classify'):
        if re.search(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b',q) and len(q.split())>45:return False
        if c in ('Closed QA','Extract','Summarize') and len(q.split())>69:return False
    if c in ('Open QA','Brainstorm'):
        if re.search(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b|\b\d{3,}\b',t) or re.search(r'\b(?:most popular|closest|famous|historical|best places|best places|brand|celebrat\w*|history of|who wrote|who is|currency|sports|can I eat|health|dog food|what do .+ eat)\b',t,re.I):return False
    if c=='Generation':
        # Prefer testable format constraints and practical naming/writing beyond the modal poetry.
        if re.search(r'\b(?:poem|poetry|verse|haiku|rhym\w*|stanza|limerick|lyrics|ballad|sonnet|acrostic)\b',q,re.I):return False
    return True
def compact():
    return [r for s in (DEST/'candidates.jsonl').open() if eligible(r:=json.loads(s))]
if __name__=='__main__':
    rs=compact()
    from collections import Counter
    print(Counter(r['category'] for r in rs))
    for k in sorted(set(r['category'] for r in rs)):
        selected=sorted((r for r in rs if r['category']==k),key=lambda r:sha256(('nr-compact-a'+r['prompt_id']).encode()).digest())[:8]
        Path('/tmp/astra_nr2_'+k.replace(' ','-')+'.txt').write_text('\n'.join(r['prompt_id'][:10]+' '+ ' | '.join(m['text'].replace('\n',' ') for m in r['history']) for r in selected)+'\n')

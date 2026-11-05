"""Search the full train split for simple practical tasks, independently of broad creative tags."""
from collections import Counter
from hashlib import sha256
import json,re
import pyarrow.parquet as pq
from compact import EXCLUDE
from prepare import DEST,SHA,checked,norm,terms,SENSITIVE,OUTSIDE,RISK,FABRICATED,TRADEMARK,many_quotes,chat_row,load,digest,REVISION
NUM={'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10}
BLOCK=re.compile(r'\b(?:boyfriend|girlfriend|my parents|spouse|spider.man|doct\w*|adverse|illness|surger\w*|medic\w*|allerg\w*|fat loss|diet|clinical|senior citizen|Reddit|post by|social media|Instagram|travel|restaurants?|brands?|fantasy XIV|Pitt|Spider-Man|game of thrones|film\w*|movies?|series|musician|athlete|celebr\w*|youtub\w*|meme|headline|bbc|fashion designer|financial|econom\w*|unsafe|anesthesia|current|prescri\w*|polic\w*|senator|sensitive|religion|genocide|wound|disaster|nationality|native american|skincare|workout|climbing|vaccine|eating disorders?|boy scouts|immigrant|drown|terror\w*|editorial|crypto|brand\w*|race\w*|gender|gendered|male or female|female or male|deities|diet\w*|pregnan\w*|assassin\w*|ghost|sex\w*|Trump|economic|attacker|death|gore|knife|blades?|allergy|copyright|tv show|novels?|on netflix|redacted)\b',re.I)
LIST_NUM=re.compile(r'\b(two|three|four|five|six|seven|eight|nine|ten|[2-9]|10)\b',re.I)
GEN=re.compile(r'\b(?:ideas?|ways|examples?|names?|tips|activities|reasons|suggestions?|steps|questions?|prompts|themes?|items?|tools?|words?|things|topics?|titles?)\b',re.I)
def group(cat,q,a):
    if not 3<=len(q.split())<=84 or not 1<=len(a.split())<=95:return
    t=q+' '+a
    if any(p.search(t) for p in [EXCLUDE,BLOCK,SENSITIVE,RISK,OUTSIDE,TRADEMARK]) or many_quotes(q) or FABRICATED.search(a):return
    if re.search(r'\b(?:19\d\d|20[012]\d)\b|\[\d+\]|(?:\b[A-Z][a-z]+ ){3}[A-Z][a-z]+',t):return
    if cat in ('Brainstorm','Generation') and GEN.search(q) and LIST_NUM.search(q):
        n=LIST_NUM.search(q)[1].lower();n=int(n) if n.isdigit() else NUM[n]
        lines=re.findall(r'^\s*(?:[-*•]|\d{1,2}[.):])\s*\S',a,re.M)
        if len(lines)==n and not re.search(r'\b(?:poem|stanza|story|haiku|rhyme|film|countries|scientific names|critically endangered|deceive|made.up facts|names of famous|source|trivia|I have heard)\b',q,re.I):
            return 'counted-list'
    if cat in ('Classify','Extract','Closed QA','Rewrite','Summarize') and len(q.split())>=8 and terms(q)&terms(a):
        if len(q.split())>55 and re.search(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b',q):return
        if re.search(r'\b(?:classify|sort|categorize|alphabetical|nouns?|singular|plural|positive|negative|sentiment|parts of speech|past tense|active voice|passive voice|literal|bullet.point|comma.separated|extract|how many|reword|rephrase|clarify|paraphrase|rewrite|reorder|correct the grammar)\b',q,re.I):
            if cat in ('Extract','Closed QA','Summarize','Classify') and len(terms(a)-terms(q))>max(2,len(terms(a))//2):return
            if re.search(r'\b(?:poem|poetry|fiction|news|review on|magazine|said|novel|named|labels? this person|patent|standards?)\b',q,re.I):return
            return 'structured-transform'
    if cat=='Open QA' and re.search(r'\b(?:mathematics|triangle|rectangle|square root|photosynthesis|water cycle|chemical symbol|evaporation|planets?|area of|fraction|decimals?|multiplication|gravity|kilomet\w*|metre|vocabulary|dictionary|noun|verb|literary|synonym|homophone|mean and median)\b',q,re.I):return 'elementary-explanation'

def main():
    tok=load();rows=[]
    for i,r in enumerate(pq.read_table(checked(DEST/'train.parquet',SHA),use_threads=False).to_pylist()):
        if [m['role'] for m in r['messages']]!=['user','assistant']:continue
        q,a=[m['content'].strip() for m in r['messages']]
        if q!=r['prompt'].strip():continue
        groupname=group(r['category'],q,a)
        if not groupname:continue
        h=[dict(role='user',text=q),dict(role='assistant',text=a)]
        ids,labels=chat_row(tok,h)
        if len(ids)>512:continue
        rows.append(dict(official_split='train',source='HuggingFaceH4/no_robots',revision=REVISION,row=i,prompt_id=r['prompt_id'],category=r['category'],history=h,inputs=len(ids),assistant_targets=sum(z!=-100 for z in labels),history_sha256=digest(json.dumps(h,ensure_ascii=False,sort_keys=True)),stratum=groupname))
    (DEST/'practical.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
    print(Counter(r['stratum'] for r in rows))
    for k in set(r['stratum'] for r in rows):
        sel=sorted((r for r in rows if r['stratum']==k),key=lambda r:digest('nr-practical-a'+r['prompt_id']))[:8]
        (DEST/(k+'-audit.txt')).write_text('\n'.join(r['prompt_id'][:10]+' '+' | '.join(m['text'].replace('\n',' ') for m in r['history']) for r in sel))
if __name__=='__main__':main()

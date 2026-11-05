"""Screen the pinned official human training split, then freeze sample-admitted strata."""
from collections import defaultdict,Counter
from hashlib import sha256
from pathlib import Path
import json,re,sys
import pyarrow.parquet as pq
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT))
from acquire import SHA,REVISION
from broad_teaching import checked
from scaled_teaching import RISK,FABRICATED,LOCAL_OR_HEALTH,VOLATILE
from fit_working import chat_row
from tokenizer import load

DEST=ROOT/'data/no-robots'
SENSITIVE=re.compile(r"\b(?:address|zip ?code|phone|e-?mail|social secur\w*|redact\w*|full name|personal information|pii|credit card|bank account|account number|passcode|passport|street|boulevard|avenue|lawsuit|legal|attorney|copyright|third.party|lyrics|novel excerpt|adapted from|quoted from|published by|reprinted|article from|new york times|guardian|bbc|cnn|poet|screenplay|characters? from|in the style of|like the style of|court|war|nazi|slav\w*|abortion|marijuana|religi\w*|bible|church|police|murder|shoot\w*|stabb\w*|weapon\w*|drunk|alcohol|smoking|pregna\w*|sick|sex\w*|intimacy|relationship advice|depress\w*|mental|racis\w*|allerg\w*|doctor|anxiety|patient\w*|kill\w*|democrat\w*|republican\w*|politic\w*|senator|president|husband|wife|daughter|family name|my son|my mother|my father|autism|dyslex\w*|dietary|supplement|invest\w*|tax|disabled|crime|cigarett\w*|minor child|terror\w*|discriminat\w*|bully\w*|passport|abuse|obese|weight loss|body weight|medicat\w*|street address|SSN|birthday is|personal identity)\b|@|https?://|www\.|\d{5,}|\b\d{3}[-. )]+\d{3}[-. ]+\d{4}\b|[<>]|\x00|\ufffd",re.I)
OUTSIDE=re.compile(r"\b(?:as an AI|I was born|I grew up|my experience|as a .+ I|when I was|I have visited|in my childhood|I have seen|I visited|in my opinion|I personally|I remember|right now the|currently|I booked|I have sent|I am working|I can search)\b",re.I)
TRADEMARK=re.compile(r'\b(?:spider.man|harry potter|marvel|disney|superhero|batman|star wars|hobbit|tolkien|batman|pokemon|Taylor Swift|Beatles|shakespeare|sherlock|copyright|haiku by|song by|excerpt from|newspaper|sports score|news article|Wikipedia|wikiHow|author writes)\b',re.I)
TOPIC=re.compile(r'\b(?:list|ideas?|creative|names?|activities|ideas?|suggest|invent|examples?|exercise|imagine|plan|brainstorm|create|write|give|outline|generate|compose|make|draft)\b',re.I)
CREATIVE=re.compile(r'\b(?:fiction\w*|character|slogan|riddle|poem|story|pun|haiku|names?|caption|acrostic|title|imaginary|fantasy|wordplay|brainstorm|logo|joke|tagline|limerick|ideas?|writing prompt|short scene)\b',re.I)
EDU=re.compile(r'^(?:how (?:do|does|can|would|did)|why|what (?:is|are|does)|can you (?:explain|describe)|explain|what.s the difference|what is the difference)',re.I)
TOOLS=re.compile(r'\b(?:send|book|reserve|order|shipping|pay|due today|execute|log in|make a reservation|go online|as your|you are a|act as|roleplay|impersonate|pretend (?:you|to) )\b',re.I)
STOPS=set('a an and are as at be by can did do does for from has have how i if in into is it its more not of on one or our out please should so than that the their them there these they this those to was were what which who will with would you your some here below above following output give answer list passage text rewrite using return provide based please according only words write many'.split())

def norm(t):return ' '.join(re.findall(r'\w+',t.casefold()))
def digest(t):return sha256(t.encode()).hexdigest()
def terms(t):return {w.rstrip('s') for w in norm(t).split() if len(w)>=3 and w not in STOPS}
def grams(history):
    ws=norm(' '.join(m['text'] for m in history if 'text' in m)).split()
    return {tuple(ws[i:i+5]) for i in range(len(ws)-4)}
def many_quotes(text):
    return bool(re.search(r'["“][^"”]{140,}["”]|^> |\b(?:chapter|verse) \d+[:.]',text,re.I|re.M))
def admissible(msgs,cat):
    for m in msgs:
        text=m['text']
        if not text or RISK.search(text) or SENSITIVE.search(text) or TRADEMARK.search(text) or many_quotes(text):return False
        if m['role']=='assistant' and (OUTSIDE.search(text) or FABRICATED.search(text) or len(text.split())>115):return False
    for q,a in zip(msgs[::2],msgs[1::2]):
        q,a=q['text'],a['text']
        if not 3<=len(q.split())<=280 or not 1<=len(a.split())<=115:return False
        if cat in ('Rewrite','Closed QA','Summarize','Extract','Classify'):
            if len(q.split())<12 or not terms(a)&terms(q):return False
            nums=set(re.findall(r'(?<!\w)\d+(?:\.\d+)?',a))
            if nums-set(re.findall(r'(?<!\w)\d+(?:\.\d+)?',q))-set(map(str,range(1,11))):return False
            if cat in ('Closed QA','Extract','Summarize') and len(terms(a)&terms(q))<.42*len(terms(a)):return False
            if cat=='Rewrite' and len(terms(a)&terms(q))<.25*len(terms(a)):return False
        elif cat=='Open QA':
            if not EDU.search(q) or len(q.split())>35 or VOLATILE.search(q+' '+a) or LOCAL_OR_HEALTH.search(q+' '+a) or TOOLS.search(q):return False
        elif cat in ('Generation','Brainstorm'):
            if not TOPIC.search(q) or not CREATIVE.search(q) or len(q.split())>75 or TOOLS.search(q) or VOLATILE.search(q+' '+a):return False
        elif cat=='Chat':
            if len(msgs)<4 or TOOLS.search(q) or LOCAL_OR_HEALTH.search(q+' '+a) or VOLATILE.search(q+' '+a):return False
        else:return False
    return True

def candidates():
    raw=pq.read_table(checked(DEST/'train.parquet',SHA),use_threads=False).to_pylist()
    if len(raw)!=9500:raise ValueError('Unexpected train size')
    tok=load();all_ids=Counter(r['prompt_id'] for r in raw)
    prior=[]
    for name in ['broad_teaching','scaled_teaching','quac_teaching','squad_teaching','taskmaster_teaching','chat_teaching','compositional_teaching']:
        prior.extend(__import__(name).examples(0))
    seen_prompt={norm(h[0]['text']) for h in prior}
    seen=[];posting=defaultdict(list)
    def remember(g):
        i=len(seen);seen.append(g)
        for k in g:posting[k].append(i)
    for h in prior:remember(grams(h))
    rows=[];rejected=Counter()
    for i,r in enumerate(raw):
        cid=r['prompt_id'];cat=r['category'];history=[{'role':m['role'],'text':m['content'].strip()} for m in r['messages']]
        if all_ids[cid]!=1 or not 2<=len(history)<=6 or [m['role'] for m in history]!=['user','assistant']*(len(history)//2):
            rejected['duplicate_id_or_invalid_role_sequence']+=1;continue
        if r['prompt'].strip()!=history[0]['text'] or not admissible(history,cat):
            rejected['quality_privacy_boundaries']+=1;continue
        inputs,labels=chat_row(tok,history)
        if len(inputs)>512:rejected['codec_length']+=1;continue
        q=norm(history[0]['text']);g=grams(history)
        if q in seen_prompt or any(n>=.75*max(len(g),len(seen[j])) for j,n in Counter(j for k in g for j in posting[k]).items()):
            rejected['duplicate_prompt_or_history']+=1;continue
        remember(g);seen_prompt.add(q)
        rows.append(dict(official_split='train',source='HuggingFaceH4/no_robots',revision=REVISION,
                   row=i,prompt_id=cid,category=cat,history=history,inputs=len(inputs),assistant_targets=sum(z!=-100 for z in labels),
                   history_sha256=digest(json.dumps(history,ensure_ascii=False,sort_keys=True))))
    (DEST/'candidates.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
    print(len(rows),Counter(r['category'] for r in rows),rejected)
def sample(rows,salt,n):
    grouped=defaultdict(list)
    for r in rows:grouped[r['category']].append(r)
    return {k:sorted(v,key=lambda r:digest(salt+r['prompt_id']))[:n] for k,v in sorted(grouped.items())}
if __name__=='__main__':
    if sys.argv[1]=='build':candidates()
    else:
        rows=[json.loads(line) for line in (DEST/'candidates.jsonl').open()]
        draws=sample(rows,sys.argv[2],int(sys.argv[3]))
        for k,v in draws.items():
            for r in v:print(k,r['prompt_id'][:10],' | '.join(m['text'].replace('\n',' ') for m in r['history']))

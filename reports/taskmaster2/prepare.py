"""Freeze source-separated SFT and pretraining-only Taskmaster-2 excerpts."""
from collections import Counter,defaultdict
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
from random import Random

REPORT=Path(__file__).resolve().parent
ROOT=REPORT.parents[1]
sys.path.insert(0,str(ROOT))
from tokenizer import load
from fit_working import chat_row
from scaled_teaching import RISK
from taskmaster_teaching import DEST

def digest(s):return sha256(s.encode()).hexdigest()
def norm(s):return " ".join(re.findall(r"[a-z0-9]+",s.casefold()))

PRIVATE=re.compile(r"\b(?:my name|your name|full name|postal|zip code|address|phone|e-mail|email|credit card|debit card|card number|my number|numbers? to reach|my home|where (?:do you live|are you located)|your (?:current )?location|where I live|allerg\w*|gluten|vegan for health|diabet\w*|ambulance|accessible|disab\w*|wheelchair|wife|husband|pregnan\w*|birth\w*|identification|verification|confirmation number)\b|\b\d{5,}\b|\b\d{1,5} (?:[A-Z][\w.]+ ){1,3}(?:Street|Avenue|Boulevard|Road|Lane|Drive)\b|@|\[|\]|www\.|https?:",re.I)
ACTION=re.compile(r"\b(?:reserv\w*|book(?:s|ed|ing)?|purchas\w*|buy|checkout|check out|order(?:s|ed|ing)?|payment|pay for|confirm\w*|cancel\w*|call (?:you|me|them)|text (?:you|me)|send|email|dispatch\w*|delivery|play(?:ing)? (?:it|this|that|the song)|ticket(?:s)?|\w+@\w+)\b",re.I)
CLAIM=re.compile(r"\b(?:i(?:'ve| have)? (?:found|see|searched|checked|looked|offer|have|recommend|suggest)|we (?:found|have|offer)|(?:let me|i will|i'll|i can) (?:look|check|search|find|pull|get|play|bring)|there (?:is|are)|available|availability|in stock|rated|cheapest|costs|charged|priced|stars?|dollars|\$|opens at|closes at|per night|comes with|includes|i personally|i love|i like|i prefer|i enjoy|we recommend)\b",re.I)
MORE=re.compile(r"\b(?:prefe\w*|looking for|interested in|would (?:you|that)|which|what|when|where|how many|how much|kind of|types? of|do you|are you|did you|is there|any specific|particular|tell me|looking (?:to|at)|want to|in mind|or)\b",re.I)
START=re.compile(r"\b(?:i(?:'d| would| am| was|'m)? (?:like|want|need|look|search|plan|hope|prefer)|looking for|help me|can you|could you|find me|tell me|what|which|where|when|how|is there|are there|recommend|show me|suggest|want to|interested in|we(?:'re| are) looking)\b",re.I)
SMALL=re.compile(r"^(?:(?:yes|yeah|sure|no|okay|ok|right|hello|hi|great|alright|all right|got it|thank you|thanks|i see|of course|absolutely|certainly|perfect|sounds good|no problem|i understand|i can help (?:you )?with that)[!., ]*)+$",re.I)
# Only question sentences and short nonfactual acknowledgements can be assistant context.
def question(text):
    if CLAIM.search(text) or ACTION.search(text) or not text.rstrip().endswith('?'):return False
    parts=[part.strip() for part in re.split(r'(?<=[.!?])\s+',text) if part.strip()]
    return bool(parts and MORE.search(parts[-1]) and len(parts[-1].split())>=4 and
                all(part.endswith('?') or SMALL.fullmatch(part) for part in parts))

REASK=re.compile(r"what else|anything else|again|repeating|repeat that|say that again|how can I help|can you tell me more|did you want to know|what would you like to know",re.I)
HOME=re.compile(r"\b(?:i (?:live|reside) in|i(?: am|.m) (?:currently |right now )?(?:in|near|at) (?:the |[a-z]+)|i (?:am|live) (?:close|nearby)|where are you (?:right now|now|currently)|what city are you in|where are you at|my (?:daughter|son|girlfriend|boyfriend|parents?|nephew|niece)|your (?:daughter|son|girlfriend|boyfriend)|i(?:'m| am) (?:currently )?(?:located|living) in|at my house|my (?:first|last) name|pick me up at|postcode|under the name|spell (?:your|my) name)\b",re.I)
FACETS=[
    (r"genre|type of (?:movie|film)|kind of (?:movie|film)",r"comedy|comedies|funny|animated|animation|action|thriller|romantic|horror|drama|science fiction"),
    (r"type of (?:food|cuisine)|kind of (?:food|cuisine)|what cuisine",r"italian|chinese|mexican|japanese|thai|korean|indian|pizza|barbecue|seafood"),
    (r"price range|budget|how much.*spend",r"\$|dollars?|budget of"),
    (r"how many (?:days|nights)",r"\b(?:\d+|two|three|four|five|six|seven) (?:days?|nights?)\b"),
    (r"what dates|what days|what are those dates",r"january|february|march|april|may \d|june|july|august|september|october|november|december|tomorrow|next monday"),
]
NEWNAME=re.compile(r"\b[A-Z][a-z]+(?: [A-Z][a-z]+)+\b")
def aligned(text,context):
    if REASK.search(text):return False
    for q,a in FACETS:
        if re.search(q,text,re.I) and re.search(a,context,re.I):return False
    if any(norm(name) not in norm(context) for name in NEWNAME.findall(text)):return False
    return True
def safe(text):
    return (2<=len(text)<=540 and not RISK.search(text) and not PRIVATE.search(text) and not HOME.search(text) and
            not ACTION.search(text) and not any(t in text for t in ['<','>','�']))

def merged(d):
    out=[]
    for i,t in enumerate(d['utterances']):
        if t['index']!=i or t['speaker'] not in ('USER','ASSISTANT'):return []
        speaker=t['speaker'].lower()
        text=t['text'].strip()
        if out and out[-1][0]==speaker:out[-1][1].append(text)
        else:out.append([speaker,[text],i])
    return [(speaker,' '.join(text),i) for speaker,text,i in out]

def candidate(d):
    turns=merged(d)
    # Start at a source's first natural request only; never splice unsupported middle turns.
    out=[]
    for role,text,i in turns:
        if not out and role=='assistant':continue
        if not out and (not START.search(text) or len(text.split())<4):return None
        if not safe(text):break
        if role=='assistant' and not (question(text) or SMALL.fullmatch(text)):break
        out.append(dict(role=role,text=text))
        if len(out)>=8:break
    if len(out)<2:return None
    # Assistant-only training excludes bare acknowledgement targets.
    count=0
    for j in range(1,len(out),2):
        if not question(out[j]['text']) or not aligned(out[j]['text'], " ".join(m["text"] for m in out[:j] if m["role"]=="user")):break
        count=j+1
    if count:return 'sft',out[:count]
    if len(out)>=3 and any(START.search(m['text']) for m in out[2:] if m['role']=='user'):
        return 'pretrain-only',out
    return None

PREFERENCE=re.compile(r"\b(?:i(?:'d| would) (?:rather|prefer|like)|i prefer|i(?:'m| am) (?:looking|interested)|i (?:like|enjoy|want)|we(?:'d| would) (?:like|prefer)|my preference|looking for|no preference|i don't (?:want|like|mind)|i would rather|i'd rather|either .+ or|important to me|i was hoping)\b",re.I)
def preference_excerpt(d):
    turns=merged(d)
    choices=[]
    for i,(role,text,_) in enumerate(turns):
        if role!='user' or not safe(text) or not PREFERENCE.search(text) or len(text.split())<9:continue
        if re.search(r"\b(?:sent|ordered|searched|found it|my account|my details|password|surgery|illness|addiction|diabetic|injury|address)\b",text,re.I):continue
        h=[dict(role='user',text=text)]
        if i and turns[i-1][0]=='assistant':
            a=turns[i-1][1]
            if safe(a) and question(a) and not REASK.search(a) and not NEWNAME.search(a):
                h.insert(0,dict(role='assistant',text=a))
        choices.append(h)
    if choices:return ('pretrain-only',max(choices,key=lambda h:(len(h),len(h[-1]['text']))))
    return None

def group(key):
    return re.sub(r'(?<=\d)[a-z]+$','',key.casefold())
def get_splits(raw):
    bydomain=defaultdict(set)
    for domain,ds in raw.items():bydomain[domain].update(group(d['instruction_id']) for d in ds)
    train={}
    for domain,gr in bydomain.items():
        keys=sorted(gr,key=lambda k:digest('tm2-whole-goal-v1:'+k))
        n=max(1,round(.1*len(keys)))
        for i,k in enumerate(keys):train[(domain,k)]='internal-dev' if i<n else 'train'
    return train

def shingles(h):
    words=norm(' '.join(m['text'] for m in h)).split()
    return {tuple(words[i:i+5]) for i in range(len(words)-4)}

def main():
    # Verify against the pinned Git objects locally, with no network operation.
    from hashlib import sha1
    files=json.loads((REPORT/'files.json').read_text())
    raw={}
    for f in files:
        path=Path(f['path'])
        body=(DEST/path.name).read_bytes()
        assert len(body)==f['size'] and sha1(b'blob '+str(len(body)).encode()+b'\0'+body).hexdigest()==f['sha']
        raw[path.stem]=json.loads(body)
    tok=load()
    parts=get_splits(raw)
    rows=[]
    all_ids=Counter(d["conversation_id"] for ds in raw.values() for d in ds)
    ids=set()
    for domain,ds in raw.items():
        for d in ds:
            cid=d['conversation_id']
            if all_ids[cid]!=1:continue
            ids.add(cid)
            hit=candidate(d)
            if not hit or hit[0]!="sft" or domain in {"food-ordering","sports"}: hit=preference_excerpt(d)
            if hit and hit[0]=="pretrain-only" and domain=="music":continue
            if cid in { "dlg-104812d4-b522-4ad9-b1c3-9e43e096dac8","dlg-574a6bb3-e2e7-4ccd-a823-e6f32cdfe4dc","dlg-bbcfd6b3-0715-492b-8e64-2a91dddd982d" }:continue
            if hit is None:continue
            typ,h=hit
            key=group(d['instruction_id'])
            row=dict(usage=typ,domain=domain,split=parts[(domain,key)],instruction_id=d['instruction_id'],
                     goal_group=domain+'/'+key,conversation_id=cid,history=h,
                     history_sha256=digest(json.dumps(h,sort_keys=True,ensure_ascii=False)))
            if typ=='sft':
                inputs,labels=chat_row(tok,h)
                if len(inputs)>512:continue
                row.update(input_tokens=len(inputs),assistant_targets=sum(x!=-100 for x in labels))
            rows.append(row)
    # Holdouts prefer ownership of approximate duplicates.
    rows.sort(key=lambda r:(r['split']=='train',r['history_sha256']))
    from broad_teaching import examples as broad
    from scaled_teaching import examples as scaled
    from quac_teaching import examples as quac
    prior=broad(0)+scaled(0)+quac(0)
    seen=[]
    posting=defaultdict(list)
    def add(s):
        i=len(seen);seen.append(s)
        for g in s:posting[g].append(i)
    from chat_teaching import examples as chat
    from compositional_teaching import examples as composition
    from tool_teaching import examples as tools_basic
    from tool_teaching_varied import examples as tools_varied
    prior+=chat(0)+composition(0)+tools_basic(0)+tools_varied(7)
    prior_open={norm(m["text"]) for h in prior for m in h[:1] if m.get("role")=="user" and "text" in m}
    hold_open=set()
    for h in prior:add(shingles([m for m in h if "text" in m]))
    dropped=Counter()
    admitted=[]
    for r in rows:
        user=next(m["text"] for m in r["history"] if m["role"]=="user")
        opening=norm(user)
        if opening in prior_open or (r["split"]=="train" and opening in hold_open):
            dropped["shared_opening"]+=1;continue
        if r["split"]=="internal-dev":hold_open.add(opening)
        s=shingles(r['history'])
        neighbors=Counter(i for g in s for i in posting[g])
        if any(n>=.75*max(len(s),len(seen[i])) for i,n in neighbors.items()):
            dropped['near_duplicate']+=1;continue
        add(s)
        admitted.append(r)
    policy=json.loads((REPORT/"admission.json").read_text())
    retained=[r for r in admitted if r["domain"] in policy["admit"][r["usage"]] and r["conversation_id"] not in policy["hold_ids"]]
    dropped["sample_audit_hold"]=len(admitted)-len(retained)
    admitted=retained
    filesout={}
    for typ in ['sft','pretrain-only']:
        for split in ['train','internal-dev']:
            subset=[r for r in admitted if r['usage']==typ and r['split']==split]
            f=DEST/(typ+'-'+split+'.jsonl')
            f.write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in subset))
            unique={norm(m['text']):m['text'] for r in subset for m in r['history']}
            filesout[f.name]=dict(rows=len(subset),goals=len({r['goal_group'] for r in subset}),domains=Counter(r['domain'] for r in subset),
                 multi_turn=sum(len(r['history'])>=4 for r in subset),input_tokens=sum(r.get('input_tokens',0) for r in subset),
                 assistant_targets=sum(r.get('assistant_targets',0) for r in subset),assistant_text_tokens=sum(len(tok.encode(m['text']).ids) for r in subset for m in r['history'] if m['role']=='assistant'),raw_text_tokens=sum(len(tok.encode(m['text']).ids) for r in subset for m in r['history']),unique_utterance_token_positions=sum(len(tok.encode(t).ids) for t in unique.values()),
                 sha256=sha256(f.read_bytes()).hexdigest())
    (REPORT/'receipt.json').write_text(json.dumps(dict(files=filesout,raw_dialogues=sum(all_ids.values()),duplicate_id_rows=sum(n for n in all_ids.values() if n>1),source_domains={k:len(v) for k,v in raw.items()},rejected_before_near_duplicates=len(ids)-len(rows),exclusions=dropped),indent=2)+'\n')
    print(json.dumps(filesout))
if __name__=='__main__':main()

"""Prepare human SNLI labels from just the official training JSONL."""
from collections import Counter
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
import json,re,sys,unicodedata
from zipfile import ZipFile
from acquire import DEST,HERE,SHA
ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT))
from tokenizer import load

TRAIN='snli_1.0/snli_1.0_train.jsonl'
LABELS={'entailment','neutral','contradiction'}
SALT='snli-image-connected-premise-v1'
def norm(t):return ' '.join(re.findall(r"[a-z0-9]+(?:'[a-z]+)?",unicodedata.normalize('NFKC',t).casefold().replace('’',"'")))
def digest(t):return sha256(t.encode()).hexdigest()
class Families:
    def __init__(self):self.parent={}
    def root(self,x):
        self.parent.setdefault(x,x);g=x
        while self.parent[g]!=g:g=self.parent[g]
        while self.parent[x]!=x:
            nxt=self.parent[x];self.parent[x]=g;x=nxt
        return g
    def join(self,a,b):
        a,b=self.root(a),self.root(b)
        if a!=b:self.parent[max(a,b)]=min(a,b)

SENSITIVE=re.compile(r"\b(?:african|asian|hispanic|latino|mexican|irish|german|chinese|indian|jew\w*|religio\w*|church|mosque|temple|muslim|christian|hindu|racial|race of|racis\w*|ethni\w*|nationality|immigra\w*|homeless\w*|poor person|poor man|poor woman|poverty|wealthy|unemploy\w*|prison\w*|crim\w*|police\w*|cop|officer|arrest\w*|convic\w*|detain\w*|handcuff\w*|suspect|steal\w*|thief|terror\w*|shoot\w*|shot|gun\w*|rifle\w*|weapon\w*|knife|bomb\w*|war|military|soldier\w*|army|combat|fight\w*|assault\w*|beat up|viol\w*|kill\w*|murder\w*|blood\w*|bleed\w*|dead|dying|died|death|injur\w*|hurt\w*|suicid\w*|hospital\w*|doctor\w*|patient\w*|sick\w*|medical\w*|therap\w*|disab\w*|wheelchair\w*|autis\w*|blind|deaf|depress\w*|mental\w*|diseas\w*|drug\w*|alcohol\w*|beer\w*|drunk\w*|smok\w*|cigaret\w*|naked|nude|sex\w*|gay|lesbian|transgender|pregnan\w*|breast\w*|underwear|bikini\w*|porn\w*|abuse\w*|fat|obese|overweight|ugly|stupid|idiot\w*|retard\w*|prostitut\w*|protest\w*|politic\w*|democrat\w*|republican\w*|president|slave\w*|foreigner|tourist\w* from|skin tone|suntan|drown\w*|homosex\w*|addict\w*|caucasian|afro|oriental|islam\w*|indigenous|african.american|european|veteran|holocaust|refugee\w*|discriminat\w*|tortur\w*|hijab|nun|priest|pray\w*|firearm\w*)\b|\b(?:white|black|brown|colored|dark|light)[- ](?:skin\w*|man|woman|boy|girl|people|person|male|female|teenager|child|kid|lad\w*|gentleman)\b|\b(?:man|woman|person) of colou?r\b|https?://|@|\d{4,}|[<>\ufffd]",re.I)
NOISY=re.compile(r'["“”]|[{}\[\]|]|\b(?:caption|in this photo|this picture|in the photograph|maybe|probably|possibly|appears? to|seems? to|I think|someone thinks|might be|can.t tell)\b',re.I)
def clean(t):
    return (4<=len(t.split())<=42 and 12<=len(t)<=280 and not SENSITIVE.search(t) and not NOISY.search(t)
            and not t.endswith('?') and bool(re.search(r'[A-Za-z]',t)))
def image_of(row):
    p=row['pairID'];c=row['captionID']
    if p.startswith('vg_') or c.startswith('vg_'):return None
    m=re.fullmatch(r'(\d+)\.jpg#\d+',c)
    return m[1] if m and p.startswith(c) else None
def official(member_hash):
    with (DEST/'official-train.jsonl').open('rb') as stream:
        for line in stream:
            member_hash.update(line);yield json.loads(line)
def levels(ann,gold):
    # Author created the pair for a label. Empty or singleton label lists
    # have no demonstrated independent-agreement evidence.
    if not ann:return 'author-only'
    if len(ann)==1:return 'single-recorded' if ann[0]==gold else None
    return 'multi-unanimous' if len(ann)>=3 and all(x==gold for x in ann) else None
def main():
    recovery=json.loads((HERE/'source-recovery.json').read_text())
    assert recovery['independently_verified_original_pairs']==550152
    tok=load()
    family=Families();owners={};raw_unique={};raw_prem=set();rawhyp=set();cnt=Counter();lens=Counter()
    votes=Counter();seen_pairs={};conflicts=set();image_ids=set();caption_ids=set();best_votes={}
    @lru_cache(maxsize=16000)
    def tokens(s):return len(tok.encode(s).ids)
    with (DEST/'preliminary.jsonl').open('w') as temp:
        member_hash=sha256()
        for number,r in enumerate(official(member_hash)):
            prem=r['sentence1'].strip();hyp=r['sentence2'].strip();gold=r['gold_label'];ann=r['annotator_labels']
            np,nh=norm(prem),norm(hyp);cnt['raw']+=1
            for s,ns in [(prem,np),(hyp,nh)]:
                if ns not in raw_unique:raw_unique[ns]=tokens(s)
            lens['raw_repeated_input_positions']+=tokens(prem)+tokens(hyp);raw_prem.add(np);rawhyp.add(nh)
            votes[(len(ann),gold)]+=1
            im=image_of(r)
            if not im:
                if r['pairID'].startswith('vg_') or r['captionID'].startswith('vg_'):cnt['visual_genome']+=1
                else:cnt['unrecognized_id']+=1
                continue
            image_ids.add(im);caption_ids.add(r['captionID'])
            family.join(im,owners.setdefault(np,im))
            key=digest(np+'\0'+nh)
            if key in seen_pairs and seen_pairs[key]!=gold:conflicts.add(key)
            seen_pairs[key]=gold
            tier=levels(ann,gold)
            if gold not in LABELS or tier is None:
                cnt['unresolved_or_not_unanimous']+=1;continue
            if np==nh or not clean(prem) or not clean(hyp):
                cnt['text_filter']+=1;continue
            best_votes[key]=max(best_votes.get(key,0),len(ann))
            temp.write(json.dumps(dict(premise=prem,hypothesis=hyp,label=gold,annotation_tier=tier,
                recorded_votes=ann,annotation_count=len(ann),image_id=im,caption_id=r['captionID'],
                pair_id=r['pairID'],official_row=number,pair_sha256=key),ensure_ascii=False)+'\n')
    assert member_hash.hexdigest()==recovery['member_sha256']
    raw_stats=dict(train_jsonl_sha256=member_hash.hexdigest(),rows=cnt['raw'],unique_premises=len(raw_prem),unique_hypotheses=len(rawhyp),
                   unique_input_texts=len(raw_unique),unique_input_token_positions=sum(raw_unique.values()),
                   unique_premise_token_positions=sum(raw_unique[x] for x in raw_prem),**lens,
                   source_annotation_counts={'%s/%s'%k:v for k,v in votes.items()})
    # Choose validation on entire transitive image/premise components before quality/sample selection.
    family_split={i:('validation' if int(digest(SALT+family.root(i))[:12],16)%20==0 else 'train') for i in image_ids}
    seen=set(); eligible=Counter();sizes=Counter()
    paths={s:(DEST/(s+'-candidate.jsonl')).open('w') for s in ['train','validation']}
    with (DEST/'preliminary.jsonl').open() as f:
        for line in f:
            r=json.loads(line);key=r['pair_sha256']
            if key in conflicts:cnt['conflicting_pair_labels']+=1;continue
            if key in seen or r['annotation_count']!=best_votes[key]:cnt['duplicate_pair']+=1;continue
            seen.add(key);split=family_split[r['image_id']]
            r['group']=family.root(r['image_id']);r['split']=split;r['official_split']='train'
            paths[split].write(json.dumps(r,ensure_ascii=False)+'\n')
            eligible[(split,r['annotation_tier'],r['label'])]+=1
    for f in paths.values():f.close()
    result=dict(raw=raw_stats,screen_counts=dict(cnt),qualified_before_audit={'/'.join(k):v for k,v in eligible.items()},
       source_images=len(image_ids),source_captions=len(caption_ids),connected_premise_image_families=len(set(family.root(i) for i in image_ids)),conflicting_unique_pairs=len(conflicts))
    (HERE/'screen.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()

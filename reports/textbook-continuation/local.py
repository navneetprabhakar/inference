"""Extract new-position narrative and encyclopedic candidates without reading protected cases."""
from collections import Counter,defaultdict
from hashlib import sha256
from pathlib import Path
import json,re,sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'reports/corpus-readiness')]
from build import RAW,STORY,M2,STORY_REV,WIKI_REV,jsonrows,norm,family,file_hash,RIGHTS,CONTACT,RESIDUE,signature
from refine import BIOGRAPHY,PERSONAL,GAP
from tokenizer import load
import pyarrow.parquet as pq
DEST=ROOT/'data/text-continuation-work'
SALT='astra-balanced-prose-v1'
def h(s):return sha256(s.encode()).hexdigest()
def split(source,group):
    return 'validation' if int(h(SALT+source+group)[:12],16)%20==0 else 'train'
EXTRA=re.compile(r'\b(?:abuse|robber|homicid\w*|murder\w*|suicid\w*|kill\w*|stabb\w*|shot dead|molest\w*|sexual\w*|rape\w*|convict\w*|criminal\w*|suffered|violen\w*|casualties|pregnan\w*|addict\w*|religio\w*|alcohol\w*|cannabis|drug abuse|psychiatr\w*|medical advice|antibiotic|medication|symptom\w*|bomb\w*|massacre\w*|nazi\w*|racis\w*|girl friend|terroris\w*|atrocit\w*|propaganda|suicide|adult film|porn\w*|serial killer|extremis\w*|surname|deceased|wounded|corruption|sexual|alleg\w*|divorc\w*|demographi\w*)\b',re.I)
BADSTART=re.compile(r'^(?:this|these|that|they|therefore|however|moreover|he|she|it|according to|its|in contrast|another|for example|for instance|as a result|meanwhile)\b',re.I)
def clean(p):
    w=p.split()
    return (50<=len(w)<=220 and '\n' not in p and p[-1:] in '.!?' and p[:1].isupper() and
        len(re.findall(r'[.!?](?:\s|$)',p))>=2 and not BADSTART.search(p) and not any(r.search(p) for r in [EXTRA,PERSONAL,BIOGRAPHY,GAP,RESIDUE,CONTACT]) and
        not re.search(r'["“”]|\b(?:is|was|are|were|length|of|to|at|by)\s+[.,;]|[;,:]\s*\)|\b(?:see also|according to legend|citation|references)\b',p,re.I) and
        len(re.findall(r'\b(?:the|to|for|and|on|is|was|of|in)\b',p,re.I))>=5)
class Dedupe:
    def __init__(self):self.inv=defaultdict(list);self.exact=set();self.count=0
    def add(self,t,force=False):
        k=h(norm(t))
        if k in self.exact:return False
        sig=sorted(signature(t))[:16]
        if not force and any(n>=4 for n in Counter(i for z in sig for i in self.inv[z]).values()):return False
        for z in sig:self.inv[z].append(self.count)
        self.count+=1;self.exact.add(k)
        return True

def main():
    DEST.mkdir(exist_ok=True)
    pilot=json.loads((ROOT/'data/feasibility-v1/manifest.json').read_text())
    assert file_hash(RAW)==RAW.stem
    for name in ['data00.json','data01.json']:assert file_hash(STORY/name)==pilot['raw_sha256'][name]
    groups=set()
    for ver in ['feasibility-v1','extended-trial-v1','extended-trial-v2','extended-trial-v3']:
        for r in jsonrows(ROOT/'data'/ver/'documents.jsonl'):
            if r['source']=='wiki':groups.add(family(r.get('title',r['group'].split('/wiki/')[-1])))
    for r in jsonrows(ROOT.parent/'inference-history-20261021/data/grounded-qa-groups-v2/eligible.jsonl'):
        groups.add(family(r['article']))
    for r in jsonrows(ROOT/'data/quac-train-v1/train.jsonl'):groups.add(family(r['title']))
    prior_ids=set()
    for f in [M2/'wikipedia-discovery-sample.jsonl',M2/'wikipedia-prose-v1/uniform-sample.jsonl',M2/'wikipedia-prose-v1/token-weighted-sample.jsonl']:
        prior_ids.update(str(r.get('source_id',r.get('id',''))) for r in jsonrows(f))
    tok=load()
    rows=[];d=Dedupe();counts=Counter()
    def emit(src,g,i,t,**meta):
        if not d.add(t):return
        n=len(tok.encode(t).ids)+1
        rows.append(dict(source=src,group=g,document_id=i,split=split(src,g),text=t,tokens=n,normalized_sha256=h(norm(t)),**meta))
        counts[src]+=n
    for batch in pq.ParquetFile(RAW).iter_batches(batch_size=200,use_threads=False):
        for r in batch.to_pylist():
            g=family(r['title'])
            if (g in groups or r['id'] in prior_ids or ':' in r['title'] or re.search(r'^\d|^List of|^Index of|^Outline of',r['title']) or
                RIGHTS.search(r['text']) or CONTACT.search(r['text'])):continue
            ps=r['text'].split('\n\n')
            if not ps or PERSONAL.search(ps[0]) or BIOGRAPHY.search(ps[0]) or EXTRA.search(ps[0]):continue
            for j,p in enumerate(ps[:12]):
                if not clean(p.strip()):continue
                emit('wiki',g,'wiki:'+r['id']+':'+str(j),p.strip(),title=r['title'],canonical_url=r['url'],raw_sha256=h(r['text']),paragraph=j,license='Wikimedia historical CC BY-SA terms; attribution via URL',revision=WIKI_REV)
        if counts['wiki']>=4300000:break
    story_held=set(h(norm(x['story'])) for x in json.loads((STORY/'data00.json').read_bytes()))
    raw=json.loads((STORY/'data01.json').read_bytes())
    for r in raw[:22500]:
        story=r['story'];story_held.add(h(norm(story)));d.add(story,True)
    for i,r in enumerate(raw[22500:],22500):
        t=r['story'];g=h(norm(t))
        if g in story_held or not 65<=len(t.split())<=350 or EXTRA.search(t) or CONTACT.search(t) or RESIDUE.search(t):continue
        emit('stories',g,'data01.json:'+str(i),t,raw_sha256=h(t),revision=STORY_REV,license='CDLA-Sharing-1.0',source_row=i)
        if counts['stories']>=3150000:break
    with (DEST/'local.jsonl').open('w') as f:
        for r in rows:f.write(json.dumps(r,ensure_ascii=False)+'\n')
    print(dict(counts))
if __name__=='__main__':main()

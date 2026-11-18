"""Bounded lexical audit against explicitly exposed sets; no sealed release read."""
import collections,hashlib,json,re,unicodedata
from pathlib import Path
R=Path('reports/ganesh-english-sourcing-v1');P=Path('runs/ganesh-english-sourcing-v1/reviewed-candidates.jsonl')
new=[json.loads(l) for l in P.read_text().splitlines()]
paths=['reports/english-first-v1/fit-train.jsonl','reports/english-first-v1/development-reference.jsonl','reports/ganesh-conversation-pilot-v1/train.jsonl','reports/ganesh-conversation-pilot-v1/development.jsonl','reports/ganesh-english-curriculum-v2/train.jsonl']
def norm(s):return ' '.join(unicodedata.normalize('NFKC',s).casefold().split())
def text(r):return ' '.join(norm(m.get('content',json.dumps(m,sort_keys=True))) for m in r['messages'] if m['role'] in ('user','assistant'))
def shingles(s):
 words=re.findall(r'\w+',s);return {tuple(words[i:i+5]) for i in range(len(words)-4)}
old=[];bound={}
for p in paths:
 p=Path(p)
 if not p.exists():continue
 bound[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
 for l in p.read_text().splitlines():
  r=json.loads(l)
  if 'messages' in r:old.append((str(p),r))
exact=[];near=[]
for i,a in enumerate(new):
 ta=text(a);sa=shingles(ta)
 for path,b in old+[(str(P),r) for r in new[:i]]:
  tb=text(b);sb=shingles(tb)
  if ta==tb:exact.append({'candidate':a['id'],'other':b.get('id'),'path':path})
  sim=len(sa&sb)/max(1,len(sa|sb))
  if sim>=.35:near.append({'candidate':a['id'],'other':b.get('id'),'path':path,'fivegram_jaccard':sim})
targets=collections.Counter()
for r in new:targets[r['family']]+=r['encoding'][0]['assistant_targets']
result={'status':'limited_lexical_check','compared_rows':len(old),'bound_files':bound,'exact_conversation_matches':exact,'near_matches_threshold_0_35':near,'family_target_positions':dict(targets),'limitations':['Fivegram similarity cannot establish semantic/template independence','Only explicit exposed files inspected; historical corpora not exhaustively compared','Sealed release not opened','No admission authorised']}
(R/'overlap-check.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

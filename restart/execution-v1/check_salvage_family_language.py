"""Conservative connected-family and language gates for individual M2 salvage."""
import collections,hashlib,json,pathlib,sqlite3,subprocess
from urllib.parse import urlsplit,unquote
from slm.data.detector_projection import fasttext_line
O=pathlib.Path(__file__).resolve().parent;R=O.parents[1];A=R/'restart/corpus-audit-v1';I=O/'m2-intake/individual-salvage-v1';D=I/'family-language-v1'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def canonical(f):
 if f.startswith('HuggingFaceFW/fineweb-edu:'):return 'source-id:'+f.split(':',1)[1]
 if f.startswith('roneneldan/TinyStories:'):return 'story:'+f.split(':',1)[1]
 if f.startswith('host:'):
  host=f[5:];parts=host.split('.');return 'domain-suffix:'+('.'.join(parts[-2:]) if not all(p.isdigit() for p in parts) else host)
 return f

def main():
 if D.exists():raise FileExistsError('Immutable gate evidence exists')
 items=[json.loads(x) for x in (I/'candidates.jsonl').read_text().splitlines()]
 assert sha(I/'candidates.jsonl')==json.loads((I/'receipt.json').read_text())['candidates_sha256']
 db=sqlite3.connect((A/'audit.sqlite').as_uri()+'?mode=ro',uri=True)
 n=db.execute('SELECT max(id) FROM docs').fetchone()[0];parent=list(range(n+len(items)+1));anchors={};held=[];candidate_keys=[]
 def root(i):
  while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
  return i
 def union(a,b):
  a,b=root(a),root(b)
  if a!=b:parent[b]=a
 def attach(i,keys):
  for f in keys:
   key=canonical(f)
   if key in ('source-id:','host:','domain-suffix:','url:'):continue
   if key in anchors:union(i,anchors[key])
   else:anchors[key]=i
 for ident,families,isheld in db.execute('SELECT id,families,held FROM docs'):
  attach(ident,json.loads(families))
  if isheld:held.append(ident)
 for line in (A/'near-pairs.tsv').open():
  a,b,*_=line.rstrip().split('\t');union(int(a),int(b))
 for line in (A/'containment-hits.tsv').open():held.append(int(line.split('\t',1)[0]))
 for i,item in enumerate(items):
  u=urlsplit(item['url']);keys=['url:'+item['url'],'host:'+(u.hostname or '').lower()]
  if item['source_id']:keys.append('source-id:'+item['source_id'])
  if item['source']=='wikipedia':keys.append('article:'+unquote(u.path.removeprefix('/wiki/')).replace(' ','_'))
  candidate_keys.append(keys);attach(n+i+1,keys)
 blocked={root(i) for i in held};reasons={};groups=collections.defaultdict(list)
 for i in range(len(items)):
  groups[root(n+i+1)].append(i);reasons[i]=['protected_connected_family'] if root(n+i+1) in blocked else []
 # Reuse the pinned detector binaries; this is classifier inference, not training.
 pinned={path:digest for path,digest in db.execute('SELECT path,sha256 FROM files')};db.close()
 detector=R.parent/'inference-history-20261021/data/language-detector-v4'
 for p in [detector/'fasttext',detector/'lid.176.ftz']:assert sha(p)==pinned[str(p)]
 D.mkdir();windows=[];mapping=[]
 for i,item in enumerate(items):
  t=item['text'];chunks=[t]+[t[j:j+1024] for j in range(0,len(t),1024) if sum(c.isalpha() for c in t[j:j+1024])>=40]
  for j,chunk in enumerate(chunks):windows.append(fasttext_line(chunk));mapping.append({'candidate':i,'window':j})
 (D/'language-input.txt').write_text('\n'.join(windows)+'\n')
 result=subprocess.run([str(detector/'fasttext'),'predict-prob',str(detector/'lid.176.ftz'),str(D/'language-input.txt'),'1'],check=True,capture_output=True,text=True,timeout=60)
 (D/'language-predictions.txt').write_text(result.stdout)
 predictions=result.stdout.splitlines();assert len(predictions)==len(mapping)
 scores=collections.defaultdict(list)
 for record,line in zip(mapping,predictions):
  label,p=line.split();p=float(p);scores[record['candidate']].append(p if label=='__label__en' else 0.)
 rows=[]
 for i,item in enumerate(items):
  if min(scores[i])<.8:reasons[i].append('whole_document_or_window_language')
  rows.append({'candidate':i,'source':item['source'],'row_index':item['row_index'],'tokens':item['tokens'],'family_keys':candidate_keys[i],
   'candidate_family_members':groups[root(n+i+1)],'language_windows':len(scores[i]),'minimum_english_probability':min(scores[i]),'exclusions':reasons[i]})
 passed=[r for r in rows if not r['exclusions']]
 report={'status':'FAMILY_LANGUAGE_GATES_CHECKED_NOT_ADMITTED','documents':len(items),'language_windows':len(mapping),
  'pass_documents':len(passed),'pass_content_tokens':sum(r['tokens'] for r in passed),
  'excluded_by_reason':dict(collections.Counter(reason for r in rows for reason in r['exclusions'])),
  'records':rows,'policy':'Original conservative final-two-label host families plus source ID, exact URL and Wikipedia article title; existing duplicate components and all known held/protected IDs propagate exclusion.',
  'training_admitted':False,'remaining':['rights/provenance exceptions','factual-risk disposition','split assignment'],
  'inputs_sha256':{str(p.relative_to(R)):sha(p) for p in [I/'candidates.jsonl',A/'near-pairs.tsv',A/'containment-hits.tsv']},
  'detector_sha256':{p.name:sha(p) for p in [detector/'fasttext',detector/'lid.176.ftz']}}
 (D/'result.json').write_text(json.dumps(report,indent=2)+'\n');(D/'language-map.json').write_text(json.dumps(mapping)+'\n')
 print(json.dumps({k:v for k,v in report.items() if k not in ['records','inputs_sha256','detector_sha256']},indent=2))
if __name__=='__main__':main()

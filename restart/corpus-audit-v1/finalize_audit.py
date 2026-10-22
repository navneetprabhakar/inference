"""Reconcile full audit outputs. Emits reference manifests only; training stays disabled."""
import json,sqlite3,struct,hashlib,csv,re,functools
from pathlib import Path
from collections import Counter,defaultdict
O=Path(__file__).resolve().parent;c=sqlite3.connect(O/'audit.sqlite');N=c.execute('select count(*) from docs').fetchone()[0]
class DSU:
 def __init__(self,n):self.p=list(range(n+1))
 def root(self,i):
  while self.p[i]!=i:self.p[i]=self.p[self.p[i]];i=self.p[i]
  return i
 def union(self,a,b):
  a=self.root(a);b=self.root(b)
  if a!=b:self.p[max(a,b)]=min(a,b)
near=DSU(N);fam=DSU(N);rows=[None]*(N+1);raw=defaultdict(Counter)
for i,s,t,h,r,fs,sh,ref in c.execute('select id,source,tokens,held,reasons,families,sha,reference from docs'):
 rows[i]={'source':s,'tokens':t,'held':bool(h),'reasons':json.loads(r),'families':json.loads(fs),'sha':sh,'reference':ref}
 raw[s]['raw_documents']+=1;raw[s]['raw_content_tokens']+=t;raw[s]['official_or_historical_heldout']+=h
# Check every language prediction aligns with its document map and counts.
failed=Counter();window_total=Counter();minscore={}
with (O/'language-map.bin').open('rb') as ids,(O/'language-predictions-fixed.txt').open() as predictions:
 count=0
 for line in predictions:
  b=ids.read(4);assert len(b)==4;doc,=struct.unpack('<I',b);label,prob=line.split();prob=float(prob);count+=1
  window_total[rows[doc]['source']]+=1;minscore[doc]=min(minscore.get(doc,1),prob if label=='__label__en' else 0)
  if label!='__label__en' or prob<.8:failed[doc]+=1
 assert not ids.read(1)
assert count==json.loads((O/'build-summary.json').read_text())['language_windows']
for i in failed:rows[i]['reasons'].append('full_document_or_window_language')
# Independently verify all proposed Jaccard links against complete STRING shingles.
@functools.lru_cache(maxsize=256)
def shingles(i):
 t=c.execute('select normalized from docs where id=?',(i,)).fetchone()[0].split()
 return {' '.join(t[j:j+5]) for j in range(len(t)-4)}
edge_counts=Counter();hash_false_positives=0
with (O/'near-pairs.tsv').open() as f:
 for line in f:
  a,b,score,kind=line.rstrip('\n').split('\t');a=int(a);b=int(b)
  if kind=='exact':assert rows[a]['sha']==rows[b]['sha']
  else:
   sa,sb=shingles(a),shingles(b)
   if not(5*len(sa&sb)>=4*len(sa|sb)):
    hash_false_positives+=1;continue
  near.union(a,b);fam.union(a,b);edge_counts[kind]+=1
print('verified exact/near edges',dict(edge_counts),flush=True)
# Preserve known source/document identities; broad host suffix groups prevent subdomain leakage.
def canonical(f):
 if f.startswith('HuggingFaceFW/fineweb-edu:'):return 'source-id:'+f.split('HuggingFaceFW/fineweb-edu:',1)[1]
 if f.startswith('roneneldan/TinyStories:'):return 'story:'+f.split('roneneldan/TinyStories:',1)[1]
 if f.startswith('host:'):
  host=f[5:];parts=host.split('.')
  return 'domain-suffix:'+('.'.join(parts[-2:]) if not all(p.isdigit() for p in parts) else host)
 return f
anchors={}
for i,r in enumerate(rows[1:],1):
 for value in r['families']:
  key=canonical(value)
  if key in ['source-id:','host:','domain-suffix:','url:']:continue
  if key in anchors:fam.union(i,anchors[key])
  else:anchors[key]=i
# Apply documented quality refinement to every original candidate, not merely spot-checked rows.
for i,text in c.execute("select id,text from docs where source in ('TinyStories','FineWeb','Cosmopedia')"):
 ls=[x for x in text.splitlines() if x.strip()];pipes=sum('|' in x for x in ls)
 if re.search(r'</s>|<\|(?:endoftext|im_start|im_end)\|>',text):rows[i]['reasons'].append('model_control_marker_in_source')
 if pipes>=4 and pipes/max(1,len(ls))>.2:rows[i]['reasons'].append('table_caption_heavy')
 if re.search(r"consider buying|buy now|add to cart|coupon code|free shipping|you won.t be disappointed",text,re.I):rows[i]['reasons'].append('promotional_call_to_action')
manual_roots={near.root(x['audit_id']) for x in json.loads((O/'quality-addendum.json').read_text())['manual_exclusions']}
for i in range(1,N+1):
 if near.root(i) in manual_roots:rows[i]['reasons'].append('direct_content_review_exclusion')
# All protected substring/span hits are excluded, even when the content is otherwise high quality.
containment={};protected_short={r[0] for r in c.execute('select normalized from protections')}
with (O/'containment-hits.tsv').open() as f:
 for line in f:
  doc,protected,span=line.rstrip('\n').split('\t',2);doc=int(doc)
  text=c.execute('select normalized from docs where id=?',(doc,)).fetchone()[0]
  assert ' '+span+' ' in ' '+text+' '
  containment[doc]={'protected_id':int(protected),'span_sha256':hashlib.sha256(span.encode()).hexdigest(),'words':len(span.split())}
for i,t in c.execute('select id,normalized from docs'):
 if t in protected_short:containment.setdefault(i,{'protected_id':'exact-evaluation-text','words':len(t.split())})
blocked_roots={fam.root(i) for i,r in enumerate(rows[1:],1) if r['held'] or i in containment}
# Exclusive waterfall plus overlapping reason counts. Quality is independent of ancestry.
reasons=defaultdict(Counter);stages=defaultdict(Counter);eligible=[]
for i,r in enumerate(rows[1:],1):
 s=r['source']
 if s not in ['TinyStories','FineWeb','Cosmopedia']:continue
 for reason in r['reasons']:reasons[s][reason]+=1
 def mark(stage):stages[s][stage+'_documents']+=1;stages[s][stage+'_tokens']+=r['tokens']
 if r['held']:mark('official_heldout');continue
 if 'unresolved_seed_document_ancestry' in r['reasons']:mark('ancestry_quarantine');continue
 if r['reasons']:mark('quality_rejected');continue
 mark('quality_pass')
 if fam.root(i) in blocked_roots:mark('evaluation_family_excluded');continue
 mark('quality_and_protection_pass');eligible.append(i)
# Keep one deterministic best-quality representative per connected near-duplicate component.
groups=defaultdict(list)
for i in eligible:groups[near.root(i)].append(i)
accepted=[];duplicates=[]
for ids in groups.values():
 ids.sort(key=lambda i:(-minscore.get(i,0),rows[i]['sha'],rows[i]['reference']))
 accepted.append(ids[0]);duplicates.extend(ids[1:])
for i in duplicates:
 s=rows[i]['source'];stages[s]['duplicate_removed_documents']+=1;stages[s]['duplicate_removed_tokens']+=rows[i]['tokens']
# Freeze family IDs from all known members, not selected rows alone.
family_min={}
for i,r in enumerate(rows[1:],1):
 root=fam.root(i);key=r['source']+':'+r['sha'];family_min[root]=min(key,family_min.get(root,key))
def identity(i):return hashlib.sha256(('english-restart-20261021-family-v1|'+family_min[fam.root(i)]).encode()).hexdigest()
def split(i):
 x=int(identity(i)[:16],16)/2**64
 return 'train' if x<.90 else ('development' if x<.95 else 'test')
by_split=defaultdict(Counter);by_family=defaultdict(set);accepted.sort();mapping={}
with (O/'accepted-manifest.csv').open('w') as f:
 w=csv.writer(f);w.writerow(['audit_id','source','split','family_id','normalized_sha256','original_text_sha256','content_tokens','original_reference'])
 for i in accepted:
  r=rows[i];s=r['source'];sp=split(i);fid=identity(i);text=c.execute('select text from docs where id=?',(i,)).fetchone()[0]
  w.writerow([i,s,sp,fid,r['sha'],hashlib.sha256(text.encode()).hexdigest(),r['tokens'],r['reference']]);mapping[i]=(sp,fid)
  stages[s]['usable_documents']+=1;stages[s]['usable_content_tokens']+=r['tokens'];by_split[sp]['documents']+=1;by_split[sp]['content_tokens']+=r['tokens'];by_split[sp]['content_plus_one_eos_per_doc']+=r['tokens']+1;by_family[sp].add(fid)
 for sp in by_split:by_split[sp]['families']=len(by_family[sp])
assert all(not (by_family[a]&by_family[b]) for a in by_family for b in by_family if a!=b)
assert len({rows[i]['sha'] for i in accepted})==len(accepted)
assert len({near.root(i) for i in accepted})==len(accepted)
assert not any(fam.root(i) in blocked_roots for i in accepted)
# Every candidate reconciles to exactly one final disposition.
with (O/'dispositions.jsonl').open('w') as f:
 dupset=set(duplicates)
 for i,r in enumerate(rows[1:],1):
  if r['source'] not in ['TinyStories','FineWeb','Cosmopedia']:continue
  if i in mapping:state=mapping[i][0]
  elif r['held']:state='official_heldout'
  elif 'unresolved_seed_document_ancestry' in r['reasons']:state='ancestry_quarantine'
  elif r['reasons']:state='quality_rejected'
  elif fam.root(i) in blocked_roots:state='evaluation_family_excluded'
  elif i in dupset:state='duplicate_removed'
  else:raise AssertionError(i)
  f.write(json.dumps({'id':i,'source':r['source'],'disposition':state,'tokens':r['tokens'],'reasons':r['reasons'],'family_id':identity(i),'containment_evidence':containment.get(i),'reference':r['reference']})+'\n')
for s,v in stages.items():
 exclusive=['official_heldout','ancestry_quarantine','quality_rejected','evaluation_family_excluded','duplicate_removed']
 assert sum(v[k+'_documents'] for k in exclusive)+v['usable_documents']==raw[s]['raw_documents'],(s,v)
 assert sum(v[k+'_tokens'] for k in exclusive)+v['usable_content_tokens']==raw[s]['raw_content_tokens'],(s,v)
result={'status':'complete_under_frozen_operational_policy','training_approved':False,'model_size_approved':False,'raw':raw,'waterfall':stages,'overlapping_quality_reasons':reasons,'splits':by_split,'language_windows':dict(window_total),'exact_near_edges':dict(edge_counts),'rejected_hash_false_positive_edges':hash_false_positives,'contained_protected_text_documents':len(containment),'usable_documents':len(accepted),'usable_content_tokens':sum(rows[i]['tokens'] for i in accepted),'validation':{'zero_known_cross_split_family_overlap':True,'zero_normalized_exact_duplicates':True,'one_representative_per_verified_near_component':True,'zero_known_protected_family_members':True,'all_candidate_documents_and_tokens_reconciled':True},'limits':['Operational screening is not factual-truth or human semantic-quality certification.','Near join is complete at Jaccard .8 over 64-bit full-document shingle hashes; every positive edge verified with exact string shingles. Hash-collision false-negative risk is extremely small but not formally zero.','Containment checks full evaluation strings >=12 words and all fixed 32-word protected blocks at stride16; any shared contiguous 47-word span contains a checked block. Short strings only exclude whole-document equality.','Semantic paraphrases and unknown upstream ancestry cannot be exhaustively certified. Cosmopedia entirely quarantined because underlying source-document identity is unresolved.','Host grouping uses last two DNS labels conservatively; public suffixes such as co.uk can overgroup, never split a known host family.','Numbers use existing 16k BPE; a future newly fitted tokenizer changes exact token counts.']}
(O/'results.json').write_text(json.dumps(result,indent=2)+'\n');c.execute('PRAGMA wal_checkpoint(TRUNCATE)');c.close();print(json.dumps(result,indent=2),flush=True)

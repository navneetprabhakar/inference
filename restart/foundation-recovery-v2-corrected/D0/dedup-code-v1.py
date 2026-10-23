"""CPU normalized/near deduplication and conservative family capacity bounds."""
import sys,re,json,sqlite3,hashlib,collections,time
import numpy as np
from common import *

class DSU:
 def __init__(self,n):self.p=list(range(n))
 def find(self,i):
  while self.p[i]!=i:self.p[i]=self.p[self.p[i]];i=self.p[i]
  return i
 def union(self,a,b):
  a,b=self.find(a),self.find(b)
  if a!=b:self.p[max(a,b)]=min(a,b)

def words(text):return re.findall(r'[a-z0-9]+',text.lower())
def shingles(text):
 w=words(text);return {int.from_bytes(hashlib.blake2b(' '.join(w[i:i+5]).encode(),digest_size=8).digest(),'little') for i in range(max(0,len(w)-4))}
def sketch(values):
 if not values:return np.zeros(64,np.uint64)
 x=np.array(list(values),np.uint64)[:,None]+np.arange(1,65,dtype=np.uint64)[None,:]*np.uint64(0x9e3779b97f4a7c15)
 x=(x^(x>>30))*np.uint64(0xbf58476d1ce4e5b9);x=(x^(x>>27))*np.uint64(0x94d049bb133111eb);x=x^(x>>31)
 return x.min(axis=0)
def jaccard(a,b):return len(a&b)/len(a|b) if a or b else 1.
def bookkey(meta):
 t=meta['title'].lower();t=re.sub(r'\b(?:\d+(?:st|nd|rd|th)?\s*(?:edition|ed\.?|e)|revised|updated)\b','',t);return ' '.join(words(t))

def main():
 check('D0');freeze_check('D0');db=sqlite3.connect(ROOT/'payloads/broad-candidate.sqlite');db.row_factory=sqlite3.Row;rows=[dict(x) for x in db.execute('select h,norm,family,domain,tokens,text,metadata,source_id,ordinal,line_sha from docs order by h')];n=len(rows);family=DSU(n);duplicate=DSU(n);norms={};roots={};titles={};exact=0
 source=sqlite3.connect('file:'+str(PROJECT/'restart/execution-v1/m2-intake/pressbooks-full-repaired-filter-impact-v1/candidate.sqlite')+'?mode=ro',uri=True)
 for i,r in enumerate(rows):
  if i%100==0:check('D0')
  # Complete exact row/line provenance, not a sampled locator check.
  x=source.execute('select hex(text_SHA256),hex(line_SHA256) from occurrences where source_id=? and ordinal=?',(r['source_id'],r['ordinal'])).fetchone();assert x and x[0].lower()==r['h'] and x[1].lower()==r['line_sha']
  if r['norm'] in norms:duplicate.union(i,norms[r['norm']]);family.union(i,norms[r['norm']]);exact+=1
  else:norms[r['norm']]=i
  m=json.loads(r['metadata']);title=bookkey(m)
  for key,index in [(r['family'],roots),(title,titles)]:
   if key in index:family.union(i,index[key])
   else:index[key]=i
 # Protected evaluation material is consumed only inside this CPU audit process.
 # No sealed plaintext or model scores leave it; emit only exclusion hashes/counts.
 cases=read(ROOT/'cases.json');sealed=read(ROOT/'private-eval/sealed.json');legacy=read(OLD/'packet.json');protected=[]
 for bank in [cases['calibration'],cases['development'],sealed['stories'],legacy['stories']]:protected += [' '.join(words(c['prefix'])) for c in bank]
 for bank in [cases['grammar'],cases['facts'],sealed['facts'],legacy['grammar'],legacy['grounded']]:
  for c in bank:protected += [' '.join(words(c['prefix']+o)) for o in c['options']]
 protected=sorted(set(p for p in protected if p));matcher=re.compile(r'(?<!\w)(?:'+'|'.join(re.escape(p) for p in protected)+r')(?!\w)');blocked=[]
 for i,r in enumerate(rows):
  if i%100==0:check('D0')
  if matcher.search(' '.join(words(r['text']))):blocked.append(i)
 blocked_families={family.find(i) for i in blocked}
 sh=[];sk=[];index=collections.defaultdict(list);pairs=set();near=0
 for i,r in enumerate(rows):
  if i%100==0:
   check('D0');save(ROOT/'D0/dedup-progress.json',dict(documents=i,total=n,near_edges=near,epoch=time.time()))
  a=shingles(r['text']);s=sketch(a);candidates=set()
  for band in range(16):candidates.update(index[(band,s[4*band:4*band+4].tobytes())])
  for j in candidates:
   # Record candidate links for later exact cross-split audit.
   sim=jaccard(a,sh[j]);pairs.add((j,i,sim))
   if sim>=.8:duplicate.union(i,j);family.union(i,j);near+=1
  sh.append(a);sk.append(s)
  for band in range(16):index[(band,s[4*band:4*band+4].tobytes())].append(i)
 # Propagate protected matches across every connected alias/duplicate family.
 blocked_families={family.find(i) for i in blocked}
 keep=[];seen=set()
 for i,r in enumerate(rows):
  if duplicate.find(i) in seen:continue
  seen.add(duplicate.find(i))
  if family.find(i) in blocked_families:continue
  keep.append(i)
 db.execute('CREATE TABLE IF NOT EXISTS clean(h TEXT PRIMARY KEY,family_component TEXT,domain TEXT,tokens INTEGER)')
 for i in keep:db.execute('insert into clean values(?,?,?,?)',(rows[i]['h'],rows[family.find(i)]['h'],rows[i]['domain'],rows[i]['tokens']))
 db.commit();totals=collections.Counter();families=collections.defaultdict(set)
 for i in keep:totals[rows[i]['domain']]+=rows[i]['tokens'];families[rows[i]['domain']].add(family.find(i))
 alltotal=sum(totals.values());none=totals['everyday']+totals['procedural'];edu=totals['educational'];upper=min(alltotal-2000000,2*max(0,none-4*131072),int(max(0,totals['everyday']-2*131072)/.15),int(max(0,totals['procedural']-2*131072)/.15))
 result=dict(status='DEDUPLICATED_CANDIDATE_COUNTS_NOT_ADMISSION',input_documents=n,exact_normalized_duplicate_records=exact,near_duplicate_edges_at_Jaccard_point8=near,near_candidate_pairs=len(pairs),surviving_documents=len(keep),native_content_tokens=dict(totals),total_native_content_tokens=alltotal,BOS_boundary_positions=len(keep),source_family_components=len({family.find(i) for i in keep}),families_per_domain={k:len(v) for k,v in families.items()},protected_match_records=len(blocked),protected_families_removed=len(blocked_families),sealed_access='CPU leakage-screen process only; no primary/model plaintext exposure or acceptance scoring; protected strings not emitted',rights_quality_sample_not_cleared=True,minimum_required_native_content_total=12000000,optimistic_training_content_upper_bound_under_domain_and_heldout_loss_caps=upper,necessary_supply_floors_possible=alltotal>=12000000 and upper>=10000000,retrieval_limits='64 pseudorandom MinHash values,16bands of4; exact normalized dedup and retrieved5-word Jaccard checked. LSH is probabilistic, not an exhaustive all-pairs semantic duplicate guarantee.',student_positions=0,training_updates=0,teacher_calls=0,epoch=time.time())
 save(ROOT/'D0/dedup.json',result);np.save(ROOT/'payloads/sketches.npy',np.array(sk));save(ROOT/'payloads/clean-index.json',dict(kept_indices=keep,hashes=[r['h'] for r in rows],families=[family.find(i) for i in range(n)]));print(json.dumps(result))
if __name__=='__main__':main()

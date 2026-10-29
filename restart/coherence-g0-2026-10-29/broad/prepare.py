"""Prospective broad-prose admission candidate, CPU only; never updates old D0."""
import sqlite3,json,hashlib,collections,re
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[2];SRC=ROOT/'restart/foundation-recovery-v2-corrected/payloads/broad-candidate.sqlite'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(n,x):(P/n).write_text(json.dumps(x,indent=2)+'\n')
def main():
 assert not (P/'candidate-freeze.json').exists()
 old=ROOT/'restart/foundation-recovery-v2-corrected/D0/fresh-sample.json';excluded={r['h'] for r in json.loads(old.read_text())['draws']}
 policy=dict(source=str(SRC.relative_to(ROOT)),source_sha256=sha(SRC),allowed_grants=['CC-BY-4.0','CC-BY-SA-4.0','CC0-1.0'],split='whole old near-duplicate family_component, hash modulo10:0development,1reserve,2..9train',prior_sample_hashes_excluded=sorted(excluded),sample='34everyday33procedural33educational training documents by frozen seeded hash, without replacement',severe_corruption_allowed=0,major_defects_allowed=5,revision_batches_allowed=1,status='CANDIDATE_NOT_ADMITTED',no_new_legal_certification=True)
 write('policy.json',policy);db=sqlite3.connect(f'file:{SRC}?mode=ro',uri=True);rows=[];holds=collections.Counter()
 for h,f,d,n,text,meta,lic in db.execute('SELECT c.h,c.family_component,c.domain,c.tokens,d.text,d.metadata,d.license FROM clean c JOIN docs d ON c.h=d.h ORDER BY c.h'):
  m=json.loads(meta)
  if h in excluded:holds['prior_semantic_sample']+=1;continue
  if lic not in policy['allowed_grants'] or not all(m.get(k) for k in ['url','book_url','author','title']):holds['provenance_incomplete']+=1;continue
  bucket=int(hashlib.sha256(('coherence-g0-family-v1:'+f).encode()).hexdigest(),16)%10;split='development' if bucket==0 else 'reserve' if bucket==1 else 'train'
  rows.append(dict(h=h,family=f,domain=d,tokens=n,split=split,license=lic,url=m['url'],book_url=m['book_url'],author=m['author'],title=m['title']))
 counts={s:{d:sum(r['tokens'] for r in rows if r['split']==s and r['domain']==d) for d in ['everyday','procedural','educational']} for s in ['train','development','reserve']}
 sample=[]
 for d,n in [('everyday',34),('procedural',33),('educational',33)]:
  rs=sorted([r for r in rows if r['split']=='train' and r['domain']==d],key=lambda r:hashlib.sha256(('291029-g0-broad:'+r['h']).encode()).digest())[:n];assert len(rs)==n
  for r in rs:
   text=db.execute('SELECT text FROM docs WHERE h=?',(r['h'],)).fetchone()[0];assert hashlib.sha256(text.encode()).hexdigest()==r['h'];sample.append({**r,'text':text})
 db.close();write('private/candidate-manifest.json',rows);write('private/semantic-sample.json',sample)
 supply=sum(counts['train'].values())>=4000000 and all(n>=1000000 for n in counts['train'].values());write('inventory.json',dict(status='AWAITING_SEMANTIC_REVIEW' if supply else 'SUPPLY_FAIL',documents=len(rows),token_counts=counts,holds=dict(holds),supply_pass=supply,sample_documents=len(sample),sample_chars=sum(len(r['text']) for r in sample),admitted_tokens=0))
 write('candidate-freeze.json',dict(files={str(f.relative_to(ROOT)):sha(f) for f in [P/'prepare.py',P/'policy.json',P/'private/candidate-manifest.json',P/'private/semantic-sample.json',P/'inventory.json']}));print(json.dumps(json.loads((P/'inventory.json').read_text()),indent=2))
if __name__=='__main__':main()

"""Final independent source-identity exclusion and corpus consistency checks."""
import hashlib,json,re,sqlite3
from pathlib import Path
from urllib.parse import urlsplit
import numpy as np
import pyarrow.parquet as pq
from prepare_pilot import normalized,digest
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'data/continuation-v1'
def identity(url):
 u=urlsplit(url);return u.netloc.lower().removeprefix('www.')+u.path.rstrip('/')
def main():
 m=json.loads((DATA/'manifest.json').read_text());c=sqlite3.connect(DATA/'documents.sqlite')
 old=ROOT.parent/'inference-archive-20261029/restart/execution-v1/m2-intake/raw/b393f51fefab26cd6f4c8f65707c1924f6666c4961a0ebebe04bb57f7ec832de.parquet'
 old_urls=set(pq.read_table(old,columns=['url'])['url'].to_pylist());old_urls={identity(x) for x in old_urls}
 blocked=[]
 for h,meta in c.execute('SELECT hash,metadata FROM docs'):
  if identity(json.loads(meta).get('url','')) in old_urls:blocked.append(h)
 # Exclude same-URL revisions even when their text is not an exact/near match.
 c.executemany('DELETE FROM docs WHERE hash=?',[(h,) for h in blocked]);c.commit()
 # Reject table/list-heavy extracts that passed the broad language screen.
 table_heavy=[]
 for h,text in c.execute('SELECT hash,text FROM docs'):
  lines=[x.strip() for x in text.splitlines() if x.strip()]
  short_fraction=sum(len(x) for x in lines if len(x.split())<=3)/max(1,sum(map(len,lines)))
  if short_fraction>.4 or text.count('|')/len(text)>.01:table_heavy.append(h)
 c.executemany('DELETE FROM docs WHERE hash=?',[(h,) for h in table_heavy]);c.commit()
 prior=sqlite3.connect(f'file:{ROOT / "data/pilot-v1/documents.sqlite"}?mode=ro',uri=True);old_hashes={r[0] for r in prior.execute('SELECT hash FROM docs')};prior.close()
 e=json.loads((ROOT/'reports/evaluation-v1/evaluation-set.json').read_text());old_hashes.update(h for v in e['provenance'].values() for h in v.get('normalized_document_sha256',[]))
 groups={};exact=set();paras=set();new_para_duplicates=0
 for h,split,group,text in c.execute('SELECT hash,split,group_id,text FROM docs'):
  assert h==digest(normalized(text));assert h not in old_hashes and h not in exact;exact.add(h)
  assert group not in groups or groups[group]==split;groups[group]=split
  for p in re.split(r'\n+',text):
   if len(p.strip())>=80:
    ph=digest(normalized(p));new_para_duplicates+=ph in paras;paras.add(ph)
 assert new_para_duplicates==0,new_para_duplicates
 # Re-encode retained documents with the unchanged tokenizer; this ensures bins
 # agree with the verified SQLite records after URL exclusions.
 from tokenizers import Tokenizer
 tok=Tokenizer.from_file(str(DATA/'tokenizer.json'))
 for source in ['fineweb','wikipedia','pressbooks']:
  for split in ['train','validation']:
   path=DATA/f'{source}-{split}.bin';count=0
   with path.open('wb') as f:
    cur=c.execute('SELECT text,tokens FROM docs WHERE source=? AND split=? ORDER BY rowid',(source,split))
    while rows:=cur.fetchmany(128):
     for enc,(_,expected) in zip(tok.encode_batch([r[0] for r in rows]),rows):
      ids=enc.ids+[1];assert len(ids)==expected;np.asarray(ids,dtype=np.uint16).tofile(f);count+=len(ids)
   m['sources'][f'{source}-{split}'].update(tokens=count,sha256=hashlib.sha256(path.read_bytes()).hexdigest());m['source_token_counts'][source][split]=count
 total=0;ranges={}
 with (DATA/'train.bin').open('wb') as f:
  for source in ['fineweb','wikipedia','pressbooks']:
   a=np.memmap(DATA/f'{source}-train.bin',dtype=np.uint16,mode='r');n=len(a)//512*512;a[:n].tofile(f);ranges[source]=[total,total+n];total+=n
  np.asarray([1],dtype=np.uint16).tofile(f)
 assert total>=205_000_000,total
 prior_checks=m.get('final_verification',{})
 result={'same_url_documents_removed':len(blocked)+prior_checks.get('same_url_documents_removed',0),'table_heavy_documents_removed':len(table_heavy)+prior_checks.get('table_heavy_documents_removed',0),'verified_retained_documents':len(exact),'verified_distinct_long_paragraphs':len(paras),'exact_overlap_with_prior_documents_or_prior_evaluation':0,'new_long_paragraph_duplicates':0,'cross_split_group_overlap':0,'train_tokens':total,'limits':'Approximate near-duplicate screening is inherited from preparation. Semantic paraphrases and unrepresented legacy passage overlap may remain.'}
 m.update(train_tokens=total,source_ranges=ranges,train_sha256=hashlib.sha256((DATA/'train.bin').read_bytes()).hexdigest(),final_verification=result)
 (DATA/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');(ROOT/'reports/continuation-v1/data-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
if __name__=='__main__':main()

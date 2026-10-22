"""Independent full manifest/text/token verification; no model imports."""
import csv,sqlite3,json,hashlib
from pathlib import Path
from collections import Counter,defaultdict
from tokenizers import Tokenizer
O=Path(__file__).resolve().parent;H=O.parents[1].parent/'inference-history-20261021';T=H/'data/iteration-two-foundation-tokenizers-v1/vocab-16384/core.json'
tok=Tokenizer.from_file(str(T));manifest={int(r['audit_id']):r for r in csv.DictReader((O/'accepted-manifest.csv').open())};c=sqlite3.connect(f'file:{O}/audit.sqlite?mode=ro',uri=True)
assert len(manifest)==sum(1 for _ in csv.DictReader((O/'accepted-manifest.csv').open()))
counts=defaultdict(Counter);families=defaultdict(set);seen=set();batch=[];checked=0
expected=json.loads((O/'results.json').read_text())
def flush():
 global checked,batch
 if not batch:return
 for (i,t),enc in zip(batch,tok.encode_batch([t for _,t in batch])):
  r=manifest[i];assert len(enc.ids)==int(r['content_tokens']);assert hashlib.sha256(t.encode()).hexdigest()==r['original_text_sha256'];assert tok.decode(enc.ids)==t
  sp=r['split'];counts[sp]['documents']+=1;counts[sp]['content_tokens']+=len(enc.ids);families[r['family_id']].add(sp);assert r['normalized_sha256'] not in seen;seen.add(r['normalized_sha256']);checked+=1
 batch=[]
for i,t in c.execute('select id,text from docs order by id'):
 if i in manifest:batch.append((i,t))
 if len(batch)>=256:flush()
flush();assert checked==len(manifest)
for sp,v in counts.items():
 assert dict(v)=={k:expected['splits'][sp][k] for k in ['documents','content_tokens']}
assert all(len(v)==1 for v in families.values())
result={'full_manifest_records_retokenized':checked,'exact_content_tokens':sum(v['content_tokens'] for v in counts.values()),'per_split':counts,'all_original_text_hashes_match':True,'all_token_counts_match':True,'all_roundtrips_match':True,'no_exact_duplicates':True,'no_family_split_overlap':True,'tokenizer_sha256':hashlib.sha256(T.read_bytes()).hexdigest(),'training_or_model_imports':False}
(O/'independent-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

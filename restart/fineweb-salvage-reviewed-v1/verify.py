import csv,json,sqlite3,hashlib,pathlib,collections
from tokenizers import Tokenizer
p=pathlib.Path(__file__).resolve().parent
base=p.parent/'corpus-audit-v1'
tp=p.parents[2]/'inference-history-20261021/data/iteration-two-foundation-tokenizers-v1/vocab-16384/core.json'
tok=Tokenizer.from_file(str(tp));rows={int(x['audit_id']):x for x in csv.DictReader((p/'accepted-manifest.csv').open())}
old={int(x['audit_id']):x for x in csv.DictReader((base/'accepted-manifest.csv').open())}
assert all(old[i]==x for i,x in rows.items())
c=sqlite3.connect(f'file:{base}/audit.sqlite?mode=ro',uri=True)
counts=collections.defaultdict(collections.Counter);seen=set();families=collections.defaultdict(set);batch=[];checked=0
r=json.loads((p/'results.json').read_text())
def flush():
 global batch,checked
 for (i,t),enc in zip(batch,tok.encode_batch([t for _,t in batch])):
  x=rows[i];assert len(enc.ids)==int(x['content_tokens']);assert tok.decode(enc.ids)==t
  assert hashlib.sha256(t.encode()).hexdigest()==x['original_text_sha256']
  assert x['normalized_sha256'] not in seen;seen.add(x['normalized_sha256']);families[x['family_id']].add(x['split'])
  counts[x['split']]['documents']+=1;counts[x['split']]['content_tokens']+=len(enc.ids);checked+=1
 batch=[]
for i,t in c.execute('select id,text from docs order by id'):
 if i in rows:batch.append((i,t))
 if len(batch)>=256:flush()
flush();assert checked==len(rows);assert all(len(x)==1 for x in families.values())
for s,v in counts.items():assert all(v[k]==r['splits'][s][k] for k in v)
review=[]
for name in ['semantic-review-v1','fineweb-salvage-v1','fineweb-salvage-reviewed-v1']:
 review.extend(json.loads(x) for x in (p.parent/name/'judgments.jsonl').read_text().splitlines())
passes={int(x['audit_id']) for x in review if x['label']=='pass'}
assert all(i in passes and x['split']=='train' for i,x in rows.items() if x['source']=='FineWeb')
failedfamilies={old[int(x['audit_id'])]['family_id'] for x in review if x['label'] in ['fail','major']}
assert not {x['family_id'] for x in rows.values()} & failedfamilies
assert all(old[int(x['audit_id'])]['split']=='train' for x in review)
assert not {int(x['audit_id']) for x in review if x['label'] in ['fail','major']}&rows.keys()
result={'retokenized_documents':checked,'exact_content_tokens':sum(x['content_tokens'] for x in counts.values()),'per_split':counts,'hashes_and_roundtrips_match':True,'unchanged_subset_of_pinned_mechanical_manifest':True,'no_exact_duplicates':True,'no_family_split_overlap':True,'failed_review_records_excluded':True,'development_and_test_texts_not_semantically_reviewed':True,'existing_near_duplicate_and_protected_overlap_exclusions_preserved_by_subset':True,'all_recovered_fineweb_individually_reviewed_pass':True,'no_failed_family_retained':True,'model_initialized_or_training_run':False,'tokenizer_sha256':hashlib.sha256(tp.read_bytes()).hexdigest()}
(p/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

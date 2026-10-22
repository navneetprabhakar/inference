import csv,json,hashlib,pathlib,collections,math
p=pathlib.Path(__file__).resolve().parent
old=p.parent/'corpus-audit-v1/accepted-manifest.csv'
assert hashlib.sha256(old.read_bytes()).hexdigest()=='0f368e5a98a74f2f40e2f986e48b3021935b4995bc323546ac466c283f90c51e'
rows=list(csv.DictReader(old.open()));byid={x['audit_id']:x for x in rows}
js=[json.loads(x) for x in (p/'judgments.jsonl').read_text().splitlines()]
assert len({x['audit_id'] for x in js})==len(js)
sample=json.loads((p/'sample.json').read_text());sm={x['audit_id']:x for x in sample}
for x in js:assert x['audit_id'] in sm and sm[x['audit_id']]['split']=='train'
summary={}
for source in ['TinyStories','FineWeb']:
 j=[x for x in js if x['source']==source];c=collections.Counter(x['label'] for x in j)
 assert sorted(x['review_index'] for x in j)==list(range(1,len(j)+1))
 fails=c['fail']+c['major'];major=c['major']
 passed=len(j)==200 and fails<=10 and major<=4
 rejected=fails>10 or major>4
 assert passed or rejected
 summary[source]={'selected':200,'fully_read':len(j),'unread':200-len(j),'labels':dict(c),'usable_reviewed':len(j)-fails,'source_gate':'pass_at_boundary' if passed else 'reject','reviewed_content_tokens':sum(int(byid[x['audit_id']]['content_tokens']) for x in j),'major_failure_minimum_in_full_200':major/200}
failed_families={byid[x['audit_id']]['family_id'] for x in js if x['label'] in ['fail','major']}
accepted=[];excluded=[];counts=collections.defaultdict(collections.Counter)
for x in rows:
 reason='source_semantic_gate_failed' if summary[x['source']]['source_gate']=='reject' else 'review_failed_family' if x['family_id'] in failed_families else None
 if reason:excluded.append(dict(x,exclusion=reason));counts[reason]['documents']+=1;counts[reason]['content_tokens']+=int(x['content_tokens'])
 else:accepted.append(x)
def write(name,rs):
 with (p/name).open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
write('accepted-manifest.csv',accepted);write('excluded-manifest.csv',excluded)
splits=collections.defaultdict(collections.Counter)
for x in accepted:
 c=splits[x['split']];c['documents']+=1;c['content_tokens']+=int(x['content_tokens']);c['tokens_with_one_eos_per_document']+=int(x['content_tokens'])+1
assert len(accepted)+len(excluded)==len(rows)
assert sum(int(x['content_tokens']) for x in accepted+excluded)==51604297
# Wilson interval: descriptive only; no population-quality certification.
n=200;k=190;z=1.959963984540054;a=(k/n+z*z/(2*n))/(1+z*z/n);b=z*math.sqrt(k/n*(1-k/n)/n+z*z/(4*n*n))/(1+z*z/n)
r={'status':'semantic_admission_review_complete_with_fineweb_rejected','training_approved':False,'model_size_approved':False,'review':summary,'admitted_sources':['TinyStories'],'total_documents':len(accepted),'total_content_tokens':sum(int(x['content_tokens']) for x in accepted),'splits':splits,'exclusions_from_mechanical_pool':counts,'tiny_sample_usable_95pct_wilson_interval':[a-b,a+b],'semantically_certified_population_counts':None,'interpretation':'Exact counts of records admitted under sample-based policy, not a claim each remaining record has been semantically reviewed. FineWeb all quarantined as source; Cosmopedia remains ancestry-quarantined.','tokenizer_sha256':'0044125dd66d4414a4f7dabf9cdfe356dfdcbd7b91a09393fa28fe6bfac30a64','tokenizer_total_vocabulary':16384,'original_manifest_sha256':hashlib.sha256(old.read_bytes()).hexdigest(),'accepted_manifest_sha256':hashlib.sha256((p/'accepted-manifest.csv').read_bytes()).hexdigest()}
(p/'results.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))

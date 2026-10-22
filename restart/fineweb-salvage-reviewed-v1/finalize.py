import csv,json,pathlib,hashlib,collections
P=pathlib.Path(__file__).resolve().parent;R=P.parent
base=R/'corpus-audit-v1/accepted-manifest.csv';tinybase=R/'semantic-review-v1/accepted-manifest.csv'
assert hashlib.sha256(base.read_bytes()).hexdigest()=='0f368e5a98a74f2f40e2f986e48b3021935b4995bc323546ac466c283f90c51e'
assert hashlib.sha256(tinybase.read_bytes()).hexdigest()=='71444df43882202845088c1845f7980b227b39755bc289c92c28727f56c22445'
old=list(csv.DictReader(base.open()));byid={r['audit_id']:r for r in old};tiny=list(csv.DictReader(tinybase.open()));assert all(r['source']=='TinyStories' for r in tiny)
reviews=[];summary={}
for name in ['semantic-review-v1','fineweb-salvage-v1','fineweb-salvage-reviewed-v1']:
 j=[json.loads(x) for x in (R/name/'judgments.jsonl').read_text().splitlines()];j=[x for x in j if x.get('source','FineWeb')=='FineWeb']
 sample=json.load(open(R/name/'sample.json'));sample=[x for x in sample if x['source']=='FineWeb'];sm={x['audit_id']:x for x in sample}
 assert len({x['audit_id'] for x in j})==len(j)
 assert all(x['audit_id'] in sm and sm[x['audit_id']]['split']=='train' for x in j)
 if name=='fineweb-salvage-reviewed-v1':assert len(j)==len(sample)==59
 c=collections.Counter(x['label'] for x in j)
 summary[name]={'selected':len(sample),'read_in_full':len(j),'unread':len(sample)-len(j),'labels':dict(c),'read_content_tokens':sum(int(byid[x['audit_id']]['content_tokens']) for x in j)}
 for x in j:reviews.append(dict(x,review_directory=name))
assert len({x['audit_id'] for x in reviews})==len(reviews)
failedfamilies={byid[x['audit_id']]['family_id'] for x in reviews if x['label'] in ['fail','major']}
passids={x['audit_id'] for x in reviews if x['label']=='pass'}
recovered=[r for r in old if r['source']=='FineWeb' and r['audit_id'] in passids and r['family_id'] not in failedfamilies]
assert all(r['split']=='train' for r in recovered)
accepted=sorted(tiny+recovered,key=lambda r:int(r['audit_id']));acceptedids={r['audit_id'] for r in accepted}
reviewmap={x['audit_id']:x for x in reviews}
excluded=[]
for r in old:
 if r['audit_id'] in acceptedids:continue
 reason='prior_tinystories_semantic_failure' if r['source']=='TinyStories' else 'review_failed_family' if r['family_id'] in failedfamilies else 'review_minor_not_admitted' if r['audit_id'] in reviewmap else 'not_individually_semantically_admitted'
 excluded.append(dict(r,exclusion=reason))
for name,rows in [('accepted-manifest.csv',accepted),('recovered-fineweb-manifest.csv',recovered),('excluded-manifest.csv',excluded)]:
 with (P/name).open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
splits=collections.defaultdict(collections.Counter);sources=collections.defaultdict(collections.Counter)
for r in accepted:
 for c in [splits[r['split']],sources[r['source']]]:
  c['documents']+=1;c['content_tokens']+=int(r['content_tokens']);c['tokens_with_one_eos_per_document']+=int(r['content_tokens'])+1
fine=[r for r in old if r['source']=='FineWeb'];ft=sum(int(r['content_tokens']) for r in recovered)
result={'status':'limited_individually_reviewed_fineweb_salvage_complete_broad_filter_rejected','training_approved':False,'model_size_approved':False,'review':summary,'fresh_sample_gate':'failed: 14 failures in first 55 of fixed 200; even all unread passing would leave 7% failures. No source-wide admission.','recovered_fineweb_documents':len(recovered),'recovered_fineweb_content_tokens':ft,'pass_records_removed_for_failed_family':sorted(passids-{r['audit_id'] for r in recovered}),'remaining_fineweb_quarantine_documents':len(fine)-len(recovered),'remaining_fineweb_quarantine_content_tokens':sum(int(r['content_tokens']) for r in fine)-ft,'total_documents':len(accepted),'total_content_tokens':sum(int(r['content_tokens']) for r in accepted),'splits':splits,'sources':sources,'tokenizer_total_vocabulary':16384,'tokenizer_sha256':'0044125dd66d4414a4f7dabf9cdfe356dfdcbd7b91a09393fa28fe6bfac30a64','note':'Every recovered FineWeb document was directly read in full and passed without noted material issue; not independent factual certification. No unreviewed FineWeb document admitted. TinyStories admission remains sample-based. No FineWeb heldout evaluation set admitted.'}
assert result['total_content_tokens']==16975190+ft
assert len(accepted)+len(excluded)==117620
(P/'results.json').write_text(json.dumps(result,indent=2)+'\n')
(R/'fineweb-salvage-v1/validation-result.json').write_text(json.dumps(dict(summary['fineweb-salvage-v1'],gate='failed',source_admission=False,filters_changed_after_sample=False),indent=2)+'\n')
print(json.dumps(result,indent=2))

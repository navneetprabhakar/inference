import hashlib,importlib.util,json,pathlib,collections
R=pathlib.Path(__file__).resolve().parent;ROOT=R.parents[3];O=ROOT/'runs/ganesh-english-sourcing-v1/scale-1000/worker-a'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def digest(v):return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
def ref(p):return {'path':str(p.relative_to(ROOT)),'sha256':sha(p)}
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
rows=[json.loads(l) for l in (R/'accepted.jsonl').read_text().splitlines()]
original_bindings=[{'group':r['group'],'messages_sha256':digest(r['messages'])} for r in rows]
hist=collections.defaultdict(list);inventory=[]
for raw in sorted(O.glob('*.raw.json'),key=lambda p:(p.stat().st_mtime_ns,p.name)):
 data=json.loads(raw.read_text())
 if 'conversations' not in data:continue
 inventory.append(ref(raw))
 label=raw.name.removesuffix('.raw.json');request=O/(label+'.request.json');events=O/(label+'.events.jsonl')
 assert request.exists() and events.exists()
 requested=json.loads(request.read_text());assert requested['raw_sha256']==sha(raw)
 assert requested['command'][requested['command'].index('--model')+1]=='gpt-6.1-terra'
 for c in data['conversations']:
  messages=[{'role':role,'content':t[role]} for t in c['turns'] for role in ['user','assistant']]
  hist[c['group']].append({'revision':len(hist[c['group']]),'messages_sha256':digest(messages),'raw_artifact':str(raw.relative_to(ROOT)),'raw_sha256':sha(raw),'request_receipt':ref(request),'events_receipt':ref(events)})
entries=[]
for r in rows:
 versions=hist[r['group']];count=len(versions)-1;assert 0<=count<=2
 matching=[v for v in versions if v['raw_artifact']==r['generation']['raw_artifact'] and v['raw_sha256']==r['generation']['raw_sha256'] and v['messages_sha256']==digest(r['messages'])];assert len(matching)==1
 entries.append({'group':r['group'],'messages_sha256':digest(r['messages']),'total_generation_revisions':count,'selected_revision':matching[0]['revision'],'versions':versions})
history={'schema':'worker-generation-revision-history-v1','scope':'Every retained raw generation artifact containing conversations in this worker; initial generation plus at most two revisions per scenario.','generator_interface':'codex exec','requested_model':'gpt-6.1-terra','generation_artifact_inventory':inventory,'entries':entries}
write(R/'generation-revision-history.json',history);history_immutable=R/('generation-revision-history-'+sha(R/'generation-revision-history.json')[:16]+'.json');history_immutable.write_bytes((R/'generation-revision-history.json').read_bytes())
full_review=R/'final-content-review-e50edbd7a805333c.json';full_map={x['group']:x for x in json.loads(full_review.read_text())};memory=[]
for r in rows:
 raw=ROOT/r['generation']['raw_artifact'];assert sha(raw)==r['generation']['raw_sha256'];c=next(c for c in json.loads(raw.read_text())['conversations'] if c['group']==r['group']);original=c['recall_probe'];assert original==r['recall_probe']
 h=digest(r['messages']);assert full_map[r['group']]['messages_sha256']==h and full_map[r['group']]['decision']=='pass'
 matching_reviews=[]
 for receipt in r['review_receipts']:
  path=ROOT/receipt['path'];assert sha(path)==receipt['sha256'];rr=next(x for x in json.loads(path.read_text())['reviews'] if x['group']==r['group']);assert rr['content_sha256']==h and rr['decision']=='accept';matching_reviews.append(rr)
 credit=original is not None
 if credit:
  assert any(x['memory_annotation_valid'] is True for x in matching_reviews)
  assert set(original)=={'support_turn','probe_turn','focus'} and original['probe_turn']-original['support_turn']-1>=2
  reason='Selected raw annotation is unchanged. Exact-message cold review explicitly validates the memory annotation, and full manual inspection covers every assistant turn. Focus: '+original['focus']
 else:reason='Selected raw generation has no recall annotation. No delayed-memory credit is claimed; the no-annotation cold-review flag is not treated as evidence of a probe.'
 memory.append({'group':r['group'],'messages_sha256':h,'credit':credit,'recall_probe':original if credit else None,'original_generated_annotation':original,'reason':reason,'source_receipts':[{'path':r['generation']['raw_artifact'],'sha256':r['generation']['raw_sha256']},*r['review_receipts'],ref(full_review)]})
write(R/'final-memory-evidence.json',{'schema':'selected-memory-evidence-v1','entries':memory});memory_immutable=R/('final-memory-evidence-'+sha(R/'final-memory-evidence.json')[:16]+'.json');memory_immutable.write_bytes((R/'final-memory-evidence.json').read_bytes())
for r,h,m in zip(rows,entries,memory):
 assert r['group']==h['group']==m['group']
 r['total_generation_revisions']=h['total_generation_revisions'];r['generation_history_receipt']=ref(history_immutable);r['memory_probe_credit']=m['credit'];r['recall_probe']=m['recall_probe'];r['memory_evidence_receipt']=ref(memory_immutable)
assert original_bindings==[{'group':r['group'],'messages_sha256':digest(r['messages'])} for r in rows]
spec=importlib.util.spec_from_file_location('memory_integrity',R.parent/'selection_memory_integrity.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
for r in rows:module.verify_memory(r,ROOT)
(R/'accepted.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
report={'status':'pass','rows':len(rows),'dialogue_bindings_unchanged':True,'memory_integrity_module':ref(R.parent/'selection_memory_integrity.py'),'credited_probes':sum(r['memory_probe_credit'] for r in rows),'uncredited_null_probes':sum(not r['memory_probe_credit'] and r['recall_probe'] is None for r in rows),'max_total_generation_revisions':max(r['total_generation_revisions'] for r in rows),'generation_history_receipt':ref(history_immutable),'memory_evidence_receipt':ref(memory_immutable),'full_content_review':ref(full_review),'accepted':ref(R/'accepted.jsonl')}
write(R/'metadata-gate-receipt.json',report);print(json.dumps(report,indent=2))

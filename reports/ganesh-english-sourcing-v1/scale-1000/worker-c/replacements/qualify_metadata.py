import hashlib,importlib.util,json,collections,shutil
from pathlib import Path
ROOT=Path('/Users/navneetprabhakar/Documents/git/image/inference');R=ROOT/'reports/ganesh-english-sourcing-v1/scale-1000/worker-c/replacements';O=ROOT/'runs/ganesh-english-sourcing-v1/scale-1000/worker-c/replacements';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();digest=lambda v:hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
s=importlib.util.spec_from_file_location('memory',R.parents[1]/'selection_memory_integrity.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def ref(p):return {'path':str(p.relative_to(ROOT)),'sha256':sha(p)}
def pinned(name,data):
 p=R/name;assert not p.exists();p.write_text(json.dumps(data,indent=2)+'\n');h=sha(p);q=R/(p.stem+'-'+h[:16]+p.suffix);shutil.copyfile(p,q);return ref(q)
selected=R/'final-selected.jsonl';old_bytes=selected.read_bytes();rows=list(map(json.loads,old_bytes.splitlines()));assert len(rows)==40;original_messages={r['group']:digest(r['messages']) for r in rows};versions=collections.defaultdict(list);inventory=[]
for raw in sorted(O.glob('*.raw.json'),key=lambda p:p.stat().st_mtime_ns):
 data=json.loads(raw.read_text())
 if not isinstance(data,dict) or 'conversations' not in data:continue
 inventory.append(ref(raw));request=raw.with_name(raw.name.replace('.raw.json','.request.json'));events=raw.with_name(raw.name.replace('.raw.json','.events.jsonl'));assert request.exists() and events.exists()
 for c in data['conversations']:
  messages=[{'role':role,'content':t[role]} for t in c['turns'] for role in ('user','assistant')]
  versions[c['group']].append({'revision':len(versions[c['group']]),'messages_sha256':digest(messages),'raw_artifact':str(raw.relative_to(ROOT)),'raw_sha256':sha(raw),'request_receipt':ref(request),'events_receipt':ref(events)})
history=[];memory_entries=[]
for r in rows:
 g=r['group'];vs=versions[g];assert 1<=len(vs)<=3;matches=[v for v in vs if v['raw_artifact']==r['generation']['raw_artifact']];assert len(matches)==1;v=matches[0];assert v['messages_sha256']==r['content_sha256'];assert v['revision']==len(vs)-1
 history.append({'group':g,'messages_sha256':r['content_sha256'],'total_generation_revisions':len(vs)-1,'selected_revision':v['revision'],'versions':vs})
 raw=ROOT/r['generation']['raw_artifact'];c=next(c for c in json.loads(raw.read_text())['conversations'] if c['group']==g);assert c['recall_probe'] is None
 memory_entries.append({'group':g,'messages_sha256':r['content_sha256'],'credit':False,'recall_probe':None,'original_generated_annotation':None,'reason':'Selected raw conversation is nonmemory and has no recall annotation. No delayed-memory credit; a nonmemory review validity flag is not evidence of retrieval.','source_receipts':[ref(raw),r['review_receipts'][-1],r['final_content_review']]})
history_ref=pinned('generation-revision-history.json',{'schema':'worker-generation-revision-history-v1','scope':'Every retained raw generation containing conversations; all actual calls counted, including unchanged text if regenerated.','generator_interface':'codex exec','requested_model':'gpt-6.1-terra','generation_artifact_inventory':inventory,'entries':history})
memory_ref=pinned('final-memory-evidence.json',{'schema':'selected-memory-evidence-v1','entries':memory_entries})
by={e['group']:e for e in history}
for r in rows:
 r['memory_probe_credit']=False;r['recall_probe']=None;r['memory_evidence_receipt']=memory_ref;r['total_generation_revisions']=by[r['group']]['total_generation_revisions'];r['selected_generation_revision']=by[r['group']]['selected_revision'];r['generation_history_receipt']=history_ref
 m.verify_memory(r,ROOT);assert digest(r['messages'])==original_messages[r['group']]
backup=R/'final-selected-metadata-v1.jsonl';assert not backup.exists();backup.write_bytes(old_bytes)
selected.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows));receipt=R/'FINAL-RECEIPT.json';backup_receipt=R/'FINAL-RECEIPT-metadata-v1.json';assert not backup_receipt.exists();shutil.copyfile(receipt,backup_receipt);d=json.loads(receipt.read_text());d.update(source_payload_sha256=sha(selected),prior_metadata_payload_sha256=hashlib.sha256(old_bytes).hexdigest(),memory_integrity_verified=40,explicit_memory_credit_false=40,max_total_generation_revisions=max(r['total_generation_revisions'] for r in rows),generation_history_receipt=history_ref,memory_evidence_receipt=memory_ref,all40_messages_unchanged=True,remaining='Parent final global validation/assembly; cross-plan supplement completed separately.');receipt.write_text(json.dumps(d,indent=2)+'\n');print(json.dumps(d,indent=2))

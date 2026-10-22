from pathlib import Path
import sys,json,hashlib,sqlite3,collections,types,os
B=Path(__file__).resolve().parent;P=B/'wikibooks-rendered-heading-triage-executor-preparation-v1';D=B/'m2-intake/wikibooks-current-candidate-heading-metadata-v1';O=B/'wikibooks-heading-terminal-independent-verification-v1'
sys.path.insert(0,str(P));import triage
h=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=triage.verify(types.SimpleNamespace(code_pins_sha256='2e364f5e521b12b5aee2938ea5a531b1d002f2d404cceb4f60a3e93646851411',profile_sha256='cf70272ff26c43e0043fe8cf499e82f474e79e17cb7848498bc3521e10da8fe9'))
r=json.loads((D/'result.json').read_text());s=json.loads((D/'supervisor.json').read_text());own=json.loads((D/'ownership.json').read_text());assert r['status']=='COMPLETE_METADATA_FEATURE_INVENTORY_NOT_FILTER_OR_ADMISSION' and s['status']=='COMPLETE' and s['child_reaped'] and s['returncode']==0
for k in ['worker_PID','supervisor_PID']:
 try:os.kill(own[k],0)
 except ProcessLookupError:pass
 else:raise AssertionError('PID_present')
assert h(D/'features.metadata')==r['feature_file_SHA256'];db=triage.connect(p['screening']);db.row_factory=sqlite3.Row
by={x['source_ordinal']:dict(x) for x in db.execute('select source_ordinal,page_id,revision_id,family,text_sha256,content_tokens,characters,utf8_bytes from docs where language_pass=1 and known_discovery_hold=0')};db.close();assert len(by)==18688
holds={x['source_ordinal'] for x in json.loads(Path(p['manual_overlay']).read_text())['known_hold_overlay']};assert len(holds)==8
candidates=set(by)-holds;anchors={x['source_ordinal']:x for x in p['anchors']};expected=candidates|set(anchors);assert len(candidates)==18680 and len(expected)==18685 and len(set(anchors)&candidates)==5
seen={};tot=collections.Counter();featurebytes=0
with (D/'features.metadata').open('rb') as f:
 for raw in f:
  assert len(raw)<=1024 and raw.endswith(b'\n');featurebytes+=len(raw);x=json.loads(raw);i=x['source_ordinal'];assert i not in seen and i in expected;seen[i]=x;row=by[i]
  assert (x['page_id'],x['revision_id'],x['family'],x['text_sha256'],x['M1_tokens_stored'])==(row['page_id'],row['revision_id'],row['family'],row['text_sha256'],row['content_tokens'])
  assert x['candidate']==(i in candidates) and x['development_anchor']==(i in anchors) and x['known_manual_hold']==(i in holds) and x['context_review_only'] is True
  feat=x['feature'];tot['block_metadata_rows']+=feat['blocks']
  assert feat['empty_leaf_subtrees']<=feat['empty_subtrees'] and feat['empty_subtrees']<=feat['blocks'] and feat['unknown_kinds']<=feat['blocks']
  assert len(feat['empty_examples'])+x['empty_examples_omitted']==feat['empty_subtrees'];assert len(feat['unknown_examples'])+x['unknown_examples_omitted']==feat['unknown_kinds']
  if i in candidates:
   tot['candidate_documents']+=1;tot['candidate_tokens_stored_unchanged']+=row['content_tokens'];tot['candidate_documents_with_empty_subtree']+=bool(feat['empty_subtrees']);tot['candidate_empty_subtrees']+=feat['empty_subtrees'];tot['candidate_empty_leaf_subtrees']+=feat['empty_leaf_subtrees'];tot['candidate_unknown_kind_documents']+=bool(feat['unknown_kinds'])
  else:tot['excluded_development_anchor_documents']+=1
  if i in anchors:assert feat['empty_subtrees']==anchors[i]['expected_empty_subtrees'] and feat['empty_leaf_subtrees']==anchors[i]['expected_empty_leaves']
assert set(seen)==expected and dict(tot)==r['stats'];ids=[[i,by[i]['page_id'],by[i]['revision_id'],by[i]['family'],by[i]['text_sha256'],by[i]['content_tokens']] for i in sorted(candidates)];assert hashlib.sha256(json.dumps(ids,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()==r['candidate_identity_SHA256']==p['candidate_identity_SHA256']
# Reconcile actual current canonical outer identities independently; never query rendered.data or blocks.
coverage=[];owners=set()
for entry in p['stores']:
 db=triage.connect(entry['path']);local=0
 for off in range(0,len(expected),500):
  selected=sorted(expected)[off:off+500]
  for i,page,rev,fam in db.execute('select source_ordinal,page_id,revision_id,family from rendered where source_ordinal in ('+','.join('?' for _ in selected)+')',selected):
   assert i not in owners and (page,rev,fam)==(by[i]['page_id'],by[i]['revision_id'],by[i]['family']);owners.add(i);local+=1
 db.close();coverage.append({'path':entry['path'],'selected_union_rows':local})
assert owners==expected and coverage==r['store_owner_coverage'];assert s['elapsed_seconds']<120 and s['peak_tree_RSS_bytes']<=1000000000 and sum(q.stat().st_size for q in D.rglob('*') if q.is_file())<=32000000
assert r['candidate_exclusions_performed']==r['new_admitted_documents']==r['new_admitted_tokens']==0
O.mkdir(exist_ok=False);out={'status':'PASS_TERMINAL_METADATA_OUTPUT_RECONCILIATION_NO_BODY_OR_FEATURE_RERUN','preparation_input_pins_verified':39,'feature_SHA256':h(D/'features.metadata'),'feature_bytes':featurebytes,'all_feature_records':len(seen),'independently_recomputed_stats':dict(tot),'all12canonical_store_outer_identity_coverage':coverage,'all10anchors_reconciled':True,'candidate_identity_SHA256':r['candidate_identity_SHA256'],'worker_and_supervisor_PIDs_absent':True,'supervisor_limits_verified':s,'original_source_pins_unchanged':True,'read_scope':'Stored feature lines, screening/frame metadata and outer canonical identity columns only; no rendered.data, block metadata rescan, bodytext, HTML or tokenizer. All39 binary input pins rehashed.','interpretation':'Empty subtrees and unknown kinds are development context flags, not semantic corruption, source exclusions or admission. Candidate18,680/19,904,934 tokens remains provisional.','source_body_text_reads':0,'network_globalledger_training_operations':0,'output_files':{q.name:h(q) for q in D.iterdir() if q.is_file()}}
(O/'verification.json').write_text(json.dumps(out,indent=2)+'\n');(O/'manifest.json').write_text(json.dumps({'verification.json':h(O/'verification.json'),'verifier_SHA256':h(__file__)},indent=2)+'\n');print(h(O/'verification.json'),h(O/'manifest.json'))

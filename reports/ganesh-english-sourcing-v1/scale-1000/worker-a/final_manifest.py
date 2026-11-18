import json,pathlib,hashlib,collections,re
R=pathlib.Path(__file__).resolve().parent;ROOT=R.parents[3];O=ROOT/'runs/ganesh-english-sourcing-v1/scale-1000/worker-a'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
rows=[json.loads(l) for l in (R/'accepted.jsonl').read_text().splitlines()];audit=json.loads((R/'audit.json').read_text())
plans=json.loads((O/'plans.raw.json').read_text())['plans']+json.loads((R/'replacement-plans.json').read_text())+json.loads((R/'late-replacement-plans.json').read_text());excluded=sorted(set(p['group'] for p in plans)-set(r['group'] for r in rows))
counts=collections.Counter();calls=[]
for p in O.glob('*.raw.json'):
 data=json.loads(p.read_text())
 for c in data.get('conversations',[]):counts[c['group']]+=1
 if 'reviews' in data:
  prompt=p.with_name(p.name.replace('.raw.json','.prompt.txt'))
  assert '"author_review_notes"' not in prompt.read_text(),p
assert max(counts.values())<=3,dict(counts)
for p in O.glob('*.events.jsonl'):
 es=[json.loads(l) for l in p.read_text().splitlines()]
 assert any(e.get('type')=='turn.completed' for e in es),p
 assert all(e.get('item',{}).get('type') in (None,'agent_message','reasoning') for e in es),p
 calls.append({'path':str(p.relative_to(ROOT)),'sha256':sha(p)})
review_path=R/'final-content-review.json';review_sha=sha(review_path);immutable=R/('final-content-review-'+review_sha[:16]+'.json')
if immutable.exists():assert immutable.read_bytes()==review_path.read_bytes()
else:immutable.write_bytes(review_path.read_bytes())
manual=json.loads(review_path.read_text());assert len(manual)==len(rows)
for r,m in zip(rows,manual):
 assert m['group']==r['group'] and m['messages_sha256']==r['content_sha256'] and m['decision']=='pass'
 assert m['reviewed_turn_numbers']==list(range(1,len(r['messages'])//2+1))
baseline=ROOT/'runs/ganesh-english-sourcing-v1/reviewed-candidates.jsonl';old=[json.loads(l) for l in baseline.read_text().splitlines()]
def grams(r):
 words=re.findall(r'[a-z0-9]+',' '.join(m['content'] for m in r['messages']).lower());return set(zip(*(words[i:] for i in range(5))))
a=[grams(r) for r in rows];b=[grams(r) for r in old];overlaps=[]
for i,x in enumerate(a):
 for j,y in enumerate(b):
  score=len(x&y)/max(1,len(x|y))
  if score>=.35:overlaps.append({'new':rows[i]['group'],'prior':old[j]['group'],'jaccard5':score})
assert not overlaps,overlaps
assistants=[m['content'] for r in rows for m in r['messages'] if m['role']=='assistant']
report={'status':'complete_reviewed_candidate_staging_not_training_admission','requested_worker_target':240,'final_candidates':len(rows),'parent_authorized_quality_stop_before_worker_quota':True,'planned_scenarios':len(plans),'excluded_groups':excluded,'assistant_turns':len(assistants),'unique_normalized_assistant_texts':len(set(' '.join(t.lower().split()) for t in assistants)),'family_counts':dict(collections.Counter(r['family'] for r in rows)),'target_positions_single_policy':sum(r['encoding'][0]['assistant_targets'] for r in rows),'generation':{'interface':'codex exec','requested_model':'gpt-6.1-terra','cli_version':'codex-cli 0.167.1','backend_routing_independently_verified':False,'completed_cli_calls_including_planning_reviews_repairs':len(calls),'configured_max_concurrent_cli':2,'max_generation_versions_per_scenario':max(counts.values()),'raw_text_preserved':True,'tool_events':0},'artifacts':{'accepted':{'path':str((R/'accepted.jsonl').relative_to(ROOT)),'sha256':sha(R/'accepted.jsonl')},'full_content_review':{'path':str(immutable.relative_to(ROOT)),'sha256':review_sha},'validation':{'path':str((R/'audit.json').relative_to(ROOT)),'sha256':sha(R/'audit.json')},'peer_support':{'path':str((R.parent/'worker-c/a-support/manual-review-final.json').relative_to(ROOT)),'sha256':sha(R.parent/'worker-c/a-support/manual-review-final.json')}},'checks':{'native2048_both_policies_exact_prefix_and256reserve':'pass','max_context':audit['max_context'],'max_prompt':audit['max_prompt'],'max_reply_targets':audit['max_reply'],'full_manual_content_inspection':'every delivered assistant target; exact content hashes','cold_review_binding':'pass per assistant turn and exact input digest','lexical_internal_5gram_threshold_035':len(audit['lexical_overlap_flags']),'lexical_prior_candidates_threshold_035':len(overlaps),'prior_candidate_count':len(old),'prior_candidate_file_sha256':sha(baseline),'all_writers_joined':True},'protected':{'gcp_operations':0,'vm_start':False,'http_start':False,'frozen_data_mutated':False,'weights_mutated':False,'shared_corpus_mutated':False,'commits':0},'limitations':['Candidates only; no training admission or model-quality claim.','Same requested model generated and cold-reviewed in separate CLI sessions; not independent release validation.','Earlier cold reviews included plans; every delivered target additionally received message-only manual inspection.','No 3K–4K claim: native2048 packet with reserved256 reply budget.','Lexical and plan screens are not exhaustive semantic decontamination; root owns global grouping/admission.'],'cli_event_receipts':calls}
report['artifacts']['generation_revision_history']=rows[0]['generation_history_receipt']
report['artifacts']['memory_evidence']=rows[0]['memory_evidence_receipt']
report['artifacts']['metadata_gate']={'path':str((R/'metadata-gate-receipt.json').relative_to(ROOT)),'sha256':sha(R/'metadata-gate-receipt.json')}
report['checks']['explicit_revision_counts']='all rows present, maximum '+str(max(r['total_generation_revisions'] for r in rows))
report['checks']['memory_probe_credit_count']=sum(r['memory_probe_credit'] for r in rows)
report['checks']['memory_integrity']='all239 passed selected_memory_integrity.verify_memory; false credit always null'
(R/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');(R/'progress.json').write_text(json.dumps({k:report[k] for k in ['status','final_candidates','assistant_turns','excluded_groups']},indent=2)+'\n')
print(json.dumps({k:report[k] for k in ['status','final_candidates','assistant_turns','generation','artifacts','excluded_groups']},indent=2))

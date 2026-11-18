import collections,hashlib,importlib.util,json,pathlib,re
P=pathlib.Path(__file__).with_name('pipeline.py');sp=importlib.util.spec_from_file_location('bpipe',P);b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)
import sys
sys.path.insert(0,str(b.R.parent))
from selection_memory_integrity import verify_memory
rows=[json.loads(l) for l in (b.R/'accepted.jsonl').read_text().splitlines()];manual=json.loads((b.R/'manual.json').read_text());assert len({x['group'] for x in rows})==len(rows)
seen=set();lengths=collections.Counter();delays=collections.Counter();targets=0;texts=set();maxcontext=maxprompt=maxreply=0;issues=[]
for x in rows:
 if 'memory_evidence_receipt' in x:verify_memory(x,b.ROOT)
 g=x['group'];gen=x['generation'];raw=b.ROOT/gen['raw_artifact'];assert b.sha(raw)==gen['raw_sha256'];assert gen['interface']=='codex exec' and gen['requested_model']=='gpt-6.1-terra' and gen['cli_version']=='0.167.1'
 c=next(c for c in json.loads(raw.read_text())['conversations'] if c['group']==g);assert b.messages(c)==x['messages'];h=b.digest(x['messages']);assert h not in seen;seen.add(h)
 name=raw.name.removesuffix('.raw.json');b.audit_cli(name,b.GEN);req=json.loads((b.R/(name+'.request.json')).read_text());assert req['requested_model']=='gpt-6.1-terra' and req['tool_events_absent'];assert req['command'][req['command'].index('--model')+1]=='gpt-6.1-terra'
 assert manual[g]['decision']=='pass' and manual[g]['messages_sha256']==h
 pr=x['plan_receipt'];pp=b.ROOT/pr['path'];assert b.sha(pp)==pr['sha256'];plan=next(p for p in json.loads(pp.read_text()) if p['group']==g);n=len(x['messages'])//2;lengths[n]+=1
 if plan['turns']!=n:
  v=x['plan_variance'];vr=b.ROOT/v['receipt']['path'];assert b.sha(vr)==v['receipt']['sha256'];vv=json.loads(vr.read_text());assert vv['group']==g and vv['messages_sha256']==h and vv['planned']==plan['turns'] and vv['actual']==n and vv['scenario_preserved'] and 4<=n<=8
 cold=False;full=False
 for receipt in x['review_receipts']:
  f=b.ROOT/receipt['path'];assert b.sha(f)==receipt['sha256'];doc=json.loads(f.read_text())
  if isinstance(doc,dict) and 'reviews' in doc:
   r=next(r for r in doc['reviews'] if r['group']==g);assert r['messages_sha256']==h and r['decision']=='pass';nums=sorted(t['turn'] for t in r['turn_reviews']);assert nums in [list(range(1,n+1)),list(range(2,2*n+1,2))];assert all(t['verdict']=='pass' for t in r['turn_reviews']);cold=True
   rn=f.name.removesuffix('.raw.json');request=b.R/(rn+'.request.json');assert request.exists();rq=json.loads(request.read_text());assert rq['requested_model']=='gpt-6.1-terra' and rq['tool_events_absent']
   for a in rq['artifacts']:assert b.sha(b.ROOT/a['path'])==a['sha256']
  elif isinstance(doc,list):
   r=next(r for r in doc if r['group']==g);assert r['messages_sha256']==h and r['decision']=='pass' and r['assistant_turns_reviewed']==n and r['reviewed_turn_numbers']==list(range(1,n+1));full=True
 assert cold and full
 errs,stats=b.structural(c);assert not errs,(g,errs);assert stats==x['native_checks'];assert stats[0]['target_positions']==stats[1]['target_positions'];targets+=stats[0]['target_positions']
 for st in stats:maxcontext=max(maxcontext,st['context']);maxprompt=max(maxprompt,st['max_prompt']);maxreply=max(maxreply,st['max_reply']);assert st['max_prompt']+256<=2048 and st['max_reply']<=256
 q=x['recall_probe'];support=q.get('last_support_turn',q.get('support_turn'));assert q.get('valid',True) and 1<=support<q['probe_turn']<=n;gap=q['probe_turn']-support-1;assert gap>=2;delays[gap]+=1
 for msg in x['messages']:
  if msg['role']=='assistant':texts.add(re.sub(r'\s+',' ',msg['content'].strip()).casefold())
entries=[]
for x in rows:
 g=x['group'];m=manual[g];n=len(x['messages'])//2;entries.append({'group':g,'messages_sha256':b.digest(x['messages']),'decision':'pass','assistant_turns_reviewed':n,'reviewed_turn_numbers':list(range(1,n+1)),'rationale':m['note'],'reviewer':m.get('reviewer','worker-b orchestrator full content inspection'),'independent_release_review':False})
for e,x in zip(entries,rows):
 for k in ('total_generation_revisions','generation_history_receipt','memory_evidence_receipt','index_normalization_receipt'):
  if k in x:e[k]=x[k]
full=b.R/'final-content-review.json';full.write_text(json.dumps({'entries':entries,'training_admitted':False,'independent_release_review':False},ensure_ascii=False,indent=2))
report={'accepted_conversations':len(rows),'assistant_turns':sum(len(x['messages'])//2 for x in rows),'unique_normalized_assistant_texts':len(texts),'assistant_target_positions':targets,'pair_count_distribution':dict(sorted(lengths.items())),'intervening_pair_distribution':dict(sorted(delays.items())),'max_context_tokens':maxcontext,'max_generation_prompt_tokens':maxprompt,'reply_reserve':256,'max_actual_reply_targets':maxreply,'native_context':2048,'both_tool_policy_modes_checked':True,'positive_tool_calls':0,'all_raw_text_exact':True,'all_cold_reviews_full_turn_coverage':True,'all_final_content_hash_bound':True,'accepted_sha256':b.sha(b.R/'accepted.jsonl'),'final_content_review':{'path':str(full.relative_to(b.ROOT)),'sha256':b.sha(full)},'model_requested':'gpt-6.1-terra','backend_routing_verified':False,'training_admitted':False,'independent_release_eligible':False,'cloud_operations':0,'frozen_or_weights_changed':False,'limitations':['Synthetic candidate-only corpus; no training or model improvement established.','Focused memory rules and contextual cues remain; not an isolated memory benchmark.','Fresh same-model CLI reviews plus orchestrator inspection are not independent release acceptance.','Tool-policy prefixes checked, but no positive tool workflows generated.','Cross-plan screening and exact-message dedup do not establish universal semantic decontamination.']}
for k in ('generation_history_receipt','memory_evidence_receipt','index_normalization_receipt'):
 if rows and k in rows[0]:report[k]=rows[0][k]
report['total_generation_revisions_max']=max(x.get('total_generation_revisions',0) for x in rows)
(b.R/'final-audit.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))

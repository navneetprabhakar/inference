"""Run only after main root pipeline stops. Preserve selected originals and receipts."""
import importlib.util,json,re
from pathlib import Path
P=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('worker',P/'run_worker.py');w=importlib.util.module_from_spec(sp);sp.loader.exec_module(w)
rows={r['group']:r for r in map(json.loads,(P/'accepted.jsonl').read_text().splitlines())}
plans={p['group']:p for p in json.loads((P/'scenario-plan.json').read_text())['plans']}
flags=json.loads((P/'parent-flags.json').read_text());pending=[];attempts={}
for group,flag in flags.items():
 if not flag['status'].startswith('pending'):continue
 row=rows[group];path=w.ROOT/row['generation']['raw_artifact'];c=next(c for c in json.loads(path.read_text())['conversations'] if c['group']==group)
 match=re.search(r'-g(\d)\.raw',str(path));assert match
 attempts[group]=int(match.group(1));assert attempts[group]<2
 pending.append({'conversation':c,'issue':flag['issue'],'plan':plans[group]})
accepted=[];history=[]
for wave in range(1,3):
 if not pending:break
 label=f'parent-repair-wave{wave}'
 assert not (w.O/(label+'.raw.json')).exists(),'Never overwrite earlier evidence'
 generated,raw=w.cli(label,w.RULES+'\nRepair ONLY these scenarios. Parent second reading found errors missed by prior review. Preserve group/family/planned turn count; correct every target. Return complete conversations with accurate annotations. Do not replace facts with unsupported alternatives.\n'+json.dumps(pending,ensure_ascii=False),w.GEN_SCHEMA)
 convs=generated['conversations'];assert {c['group'] for c in convs}=={d['conversation']['group'] for d in pending}
 reviews,rp=w.review(label+'-cold',convs,plans);next_pending=[]
 for c in convs:
  group=c['group'];attempts[group]+=1;errs,enc=w.validate(c,plans[group]);review=reviews[group]
  if review['decision']!='accept' or any(t['decision']!='pass' for t in review['turn_reviews']) or not review['memory_annotation_valid'] or not review['distinct_scenario']:errs.append(review)
  history.append({'group':group,'total_generation_revisions':attempts[group],'errors':errs,'raw':str(raw.relative_to(w.ROOT)),'review':str(rp.relative_to(w.ROOT))})
  if not errs:
   old=rows[group];r={**old,'messages':w.messages(c),'recall_probe':c['recall_probe'],'content_sha256':w.digest(w.messages(c)),'generation':{**old['generation'],'raw_artifact':str(raw.relative_to(w.ROOT)),'raw_sha256':w.sha(raw)},'review_receipts':[{'path':str(rp.relative_to(w.ROOT)),'sha256':w.sha(rp)}],'total_generation_revisions':attempts[group],**enc};accepted.append(r)
   flags[group]['status']='repaired_by_Terra;pending_parent_final_inspection'
  elif attempts[group]<2:next_pending.append({'conversation':c,'issue':errs,'plan':plans[group]})
  else:flags[group]['status']='rejected_after_two_revisions;exclude'
 pending=next_pending
 (P/'parent-repairs.accepted.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in accepted))
 w.write(P/'parent-repairs.history.json',history);w.write(P/'parent-flags.json',flags)
print('Repaired staged',len(accepted),'of',len(attempts))

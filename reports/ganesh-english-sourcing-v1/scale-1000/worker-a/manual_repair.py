import importlib.util,json,re,os
from pathlib import Path
spec=importlib.util.spec_from_file_location('worker',Path(__file__).with_name('run_worker.py'));w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
R,O,ROOT=w.R,w.O,w.ROOT
prefix=os.environ.get('REPAIR_PREFIX','manual-fix');suffix='' if prefix=='manual-fix' else '-'+prefix;only=set(filter(None,os.environ.get('REPAIR_GROUPS','').split(',')))
q=json.loads((R/'quarantine.json').read_text());permanent={'a_034','a_061','a_104','a_156','a_230'}
rows={x['group']:x for p in R.glob('b*.accepted.jsonl') for x in [json.loads(l) for l in p.read_text().splitlines()]}
plans={};remaining={};pending=[]
for group,reason in q.items():
 if group in permanent or group not in rows or (only and group not in only):continue
 row=rows[group]; raw=ROOT/row['generation']['raw_artifact'];c=next(c for c in json.loads(raw.read_text())['conversations'] if c['group']==group)
 plans[group]=next(p for p in json.loads((ROOT/row['plan_receipt']['path']).read_text()) if p['group']==group)
 remaining[group]=2-int(re.search(r'-g(\d+)\.raw',raw.name).group(1))
 if remaining[group]<=0:raise RuntimeError('No further revision permitted '+group)
 pending.append({'conversation':c,'defects':[reason],'plan':plans[group]})
accepted=[];rejected=[]
for attempt in range(1,3):
 if not pending:break
 data,raw=w.cli(f'{prefix}-{attempt}-generation',w.RULES+'\nRepair these full conversations based on a manual FULL content review. The earlier cold reviewer missed these defects. Fix specifically without inventing new facts, strengthening sentiment, changing other scope or losing constraints. Keep all other correct turns unchanged where possible. No plan-only fact may leak into assistant claims. Return complete conversations, exact group/family/turn count.\n'+json.dumps(pending,ensure_ascii=False),w.GEN_SCHEMA)
 convs=data['conversations'];assert {c['group'] for c in convs}=={d['conversation']['group'] for d in pending}
 reviews,paths=w.review(f'{prefix}-{attempt}-review',convs,plans);newpending=[]
 for c in convs:
  g=c['group'];remaining[g]-=1;errors,encoding=w.validate(c,plans[g]);rr=reviews[g]
  if rr['decision']!='accept' or not rr['memory_annotation_valid'] or not rr['distinct_scenario'] or any(t['decision']!='pass' for t in rr['turn_reviews']):errors.append(rr)
  if errors:
   d={'conversation':c,'defects':errors,'plan':plans[g]}
   if remaining[g]>0:newpending.append(d)
   else:rejected.append(d)
  else:
   row=dict(rows[g]);row.update(messages=w.messages(c),recall_probe=c['recall_probe'],content_sha256=w.digest(w.messages(c)),generation={'interface':'codex exec','requested_model':'gpt-6.1-terra','cli_version':'codex-cli 0.167.1','raw_artifact':str(raw.relative_to(ROOT)),'raw_sha256':w.sha(raw)},review_receipts=[{'path':str(paths[g].relative_to(ROOT)),'sha256':w.sha(paths[g])}],manual_repair_remaining=remaining[g],**encoding)
   accepted.append(row)
 pending=newpending
 w.write(R/f'{prefix}-{attempt}-remaining.json',remaining)
(R/('manual-repairs'+suffix+'.cold-accepted.jsonl')).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in accepted));w.write(R/('manual-repairs'+suffix+'.rejected.json'),rejected)
print('cold-passed repairs',len(accepted),'rejected',len(rejected),flush=True)

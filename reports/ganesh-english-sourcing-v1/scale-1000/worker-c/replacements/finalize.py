import hashlib,importlib.util,json,collections,shutil
from pathlib import Path
p=Path(__file__).with_name('run_worker.py');spec=importlib.util.spec_from_file_location('replacement_worker',p);w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
rows=[json.loads(l) for l in (w.R/'selected-input.jsonl').read_text().splitlines()];new15=json.loads((w.R/'c015-selected.json').read_text());rows=[new15 if r['group']==new15['group'] else r for r in rows];rows += list(map(json.loads,(w.R/'b05.accepted.jsonl').read_text().splitlines()));rows.sort(key=lambda r:r['group']);assert len(rows)==40
manual={r['group']:r for r in json.loads((w.R/'manual-content-review.json').read_text())};new2=json.loads((w.R/'c002-first-repair-manual.json').read_text());manual[new2['group']]=new2
notes={41:'Not quite versus not yet distinguishes suggested closeness from time/noncompletion without exact amount.',42:'Optional serial comma in unambiguous list, style consistency and requested punctuation preserve exact items.',43:'Positive blue-cover opinion does not entail comparative preference over unseen green; source-bound rewrite correct.',44:'Then as consequence in hall-ready exchange distinguished from temporal eating/leaving sequence; application stays linguistic.'}
textreviews={}
for f in sorted(w.O.glob('text-b*.raw.json'))+[w.O/'c020-text-rebind.raw.json']:
 for rr in json.loads(f.read_text())['reviews']:textreviews[rr['group']]=(rr,f)
finalmanual=[]
for r in rows:
 g=r['group'];n=len(r['messages'])//2;assert w.digest(r['messages'])==r['content_sha256']
 raw=w.ROOT/r['generation']['raw_artifact'];assert w.sha(raw)==r['generation']['raw_sha256'];c=next(x for x in json.loads(raw.read_text())['conversations'] if x['group']==g);assert w.messages(c)==r['messages']
 if g in textreviews and g!='c_replace_015':
  rr,rp=textreviews[g];assert rr['content_sha256']==r['content_sha256'] and rr['decision']=='accept';assert all(t['decision']=='pass' for t in rr['turn_reviews']);assert sorted(t['turn'] for t in rr['turn_reviews'])==list(range(1,n+1));r['review_receipts'].append({'path':str(rp.relative_to(w.ROOT)),'sha256':w.sha(rp),'messages_only':True})
 else:
  rp=w.ROOT/r['review_receipts'][-1]['path'];rr=next(x for x in json.loads(rp.read_text())['reviews'] if x['group']==g);assert rr['content_sha256']==r['content_sha256'] and rr['decision']=='accept';assert all(t['decision']=='pass' for t in rr['turn_reviews']);r['review_receipts'][-1]['messages_only']=True
 if g=='c_replace_015':reason='All eight final turns inspected; only last reply changed after first manual review. Final response now includes both original separate facts and requested scope note, preserving no unsupported cream-envelope overlap.'
 elif int(g.split('_')[-1])>=41:reason=notes[int(g.split('_')[-1])]
 else:
  m=manual[g];assert m['messages_sha256']==r['content_sha256'] and m['decision']=='pass';reason=m['rationale']
 finalmanual.append({'group':g,'messages_sha256':r['content_sha256'],'decision':'pass','assistant_turns_reviewed':n,'reviewed_turn_numbers':list(range(1,n+1)),'rationale':reason})
manualpath=w.R/'final-content-review.json';assert not manualpath.exists();w.write(manualpath,finalmanual);h=w.sha(manualpath);shutil.copyfile(manualpath,w.R/f'final-content-review-{h}.json')
for r in rows:r['final_content_review']={'path':str(manualpath.relative_to(w.ROOT)),'sha256':h}
p=w.R/'final-selected.jsonl';assert not p.exists();p.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
summary={'selected':len(rows),'assistant_turns':sum(len(r['messages'])//2 for r in rows),'family_counts':dict(collections.Counter(r['family'] for r in rows)),'excluded_after_two_repairs':['c_replace_031','c_replace_032','c_replace_034','c_replace_039'],'replacement_new_groups':['c_replace_041','c_replace_042','c_replace_043','c_replace_044'],'source_payload_sha256':w.sha(p),'manual_review_sha256':h,'native2048_both_policies':True,'max_prompt':max(r['max_generation_prompt'] for r in rows),'max_reply_targets':max(r['max_reply_targets'] for r in rows),'reply_reserve':256,'messages_only_cold_review_all40':True,'manual_full_content_review_all40':True,'generation_model_requested':'gpt-6.1-terra','training_admitted':False,'release_accepted':False,'remaining':'cross-plan supplement with A/B replacements; root global validation and assembly'};w.write(w.R/'FINAL-RECEIPT.json',summary);print(summary)

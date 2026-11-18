import importlib.util,json
from pathlib import Path
P=Path(__file__).resolve().parent;s=importlib.util.spec_from_file_location('w',P/'run_worker.py');w=importlib.util.module_from_spec(s);s.loader.exec_module(w)
raw=w.O/'parent-repair-wave1.raw.json';c=next(c for c in json.loads(raw.read_text())['conversations'] if c['group']=='r_because_so_relationship');ms=w.messages(c)
evidence=json.loads((P/'word-count-replay.json').read_text())
prompt='''Fresh full semantic review of this conversation. No tools. Review every assistant reply using only dialogue as evidence. A deterministic Python whitespace word-count check is supplied for the exact three compared sentences; use those measured counts, not an estimated count. Do not presume acceptance; inspect all other claims/instructions too. One1-based exchange-indexed turn_review per assistant target. No generator notes or hidden scenario. Null recall_probe is valid for nonmemory. Echo supplied exact group and content hash.\n'''+json.dumps({'group':c['group'],'family':c['family'],'content_sha256':w.digest(ms),'messages':ms,'recall_probe':c['recall_probe'],'deterministic_check':evidence},ensure_ascii=False)
assert not (w.O/'wordcount-independent-recheck.raw.json').exists()
out,rp=w.cli('wordcount-independent-recheck',prompt,w.REVIEW_SCHEMA);r=out['reviews'][0];assert len(out['reviews'])==1 and r['group']==c['group'] and r['content_sha256']==w.digest(ms)
assert r['decision']=='accept' and all(t['decision']=='pass' for t in r['turn_reviews']) and sorted(t['turn'] for t in r['turn_reviews'])==list(range(1,len(c['turns'])+1))
old=next(r for r in map(json.loads,(P/'accepted.jsonl').read_text().splitlines()) if r['group']==c['group']);plan=next(p for p in json.loads((P/'scenario-plan.json').read_text())['plans'] if p['group']==c['group']);errs,enc=w.validate(c,plan);assert not errs
row={**old,'messages':ms,'content_sha256':w.digest(ms),'generation':{**old['generation'],'raw_artifact':str(raw.relative_to(w.ROOT)),'raw_sha256':w.sha(raw)},'review_receipts':[{'path':str(rp.relative_to(w.ROOT)),'sha256':w.sha(rp)}],'total_generation_revisions':2,**enc}
with (P/'parent-repairs.accepted.jsonl').open('a') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
flags=json.loads((P/'parent-flags.json').read_text());flags[c['group']]['status']='repaired_by_Terra;fresh_review_recheck_pass;pending_parent_final_inspection';w.write(P/'parent-flags.json',flags)
w.write(P/'wordcount-review-adjudication.json',{'group':c['group'],'messages_sha256':w.digest(ms),'original_bad_review':'parent-repair-wave1-cold.raw.json','false_flag':'Reviewer claimed8words in because-first sentence; deterministic replay proves7.','corrected_text_unchanged_in_recheck':True,'review_receipt':str(rp.relative_to(w.ROOT)),'review_sha256':w.sha(rp),'no_additional_generation_revision':True})
print('Word count corrected text independently re-reviewed against deterministic counts; no extra generation.')

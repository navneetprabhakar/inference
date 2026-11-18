import concurrent.futures,importlib.util,json,pathlib,hashlib
p=pathlib.Path(__file__).with_name('pipeline.py');s=importlib.util.spec_from_file_location('bpipe',p);b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
plans=json.loads((b.R/'replacement-plans.json').read_text())['plans'];receipt=b.R.parent/'worker-c/replacement-crossplan-v1.review.json';assert receipt.exists()
(b.R/'replacement-plan-admission.json').write_text(json.dumps({'groups':[p['group'] for p in plans],'reviewer':'Worker-b orchestrator read all10plans and worker-c fresh Terra cross-plan check','cross_plan_receipt':{'path':str(receipt.relative_to(b.ROOT)),'sha256':b.sha(receipt)},'decision':'generate for review only','training_admitted':False,'note':'Ten distinct ordinary narratives; preserve user-supplied causes, source attribution and uncertainty. No invented music playback for broken-radio story. Replaces9duplicates plus exhausted b199 constraint ambiguity.'},indent=2))
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
 fs=[ex.submit(b.run_batch,20,plans[:5]),ex.submit(b.run_batch,21,plans[5:])]
 for f in concurrent.futures.as_completed(fs): print(f.result(),flush=True)

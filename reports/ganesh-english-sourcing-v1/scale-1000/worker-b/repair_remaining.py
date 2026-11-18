import importlib.util,json,pathlib,sys
p=pathlib.Path(__file__).with_name('pipeline.py');s=importlib.util.spec_from_file_location('bpipe',p);b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
mode=sys.argv[1];groups=['b_148','b_190','b_206','b_235'] if mode=='31' else ['b_231'];rows={}
for f in b.R.glob('batch-*.staged.jsonl'):
 for line in f.read_text().splitlines():
  x=json.loads(line);rows[x['group']]=x
reasons={'b_148':'No jobs supplied and final draft omits jobs without explicitly stating rule; this cannot establish memory. Explicitly retain earlier no-jobs rule in final answer, or supply fictional job facts early enough for true delayed omission.','b_190':'Remove turn3 invented scrambling and assumed frustration. User only supplies brief rain timing. Keep wooden handle versus rubber grip memory, no invented emotional or behavioural facts.','b_206':'Replace unsupported friend-who-owns-it with supported return-to-friend/lender. Borrowing from a friend does not establish they own the book.','b_235':'Cupboard answer is rehearsed at4 and5 immediately before6. Replace these detours with substantive coherent unrelated-to-key-target details; keep actual key attribution and uncertainty, >=2complete intervening pairs since last cupboard mention.','b_231':'First assistant assumes user expected breakfast before user establishes it. Remove expectation or explicitly establish breakfast in useropening, preserving bakery closure reason and Monday date.'}
plans=[]
for g in groups:
 row=rows[g];raw=b.ROOT/row['generation']['raw_artifact'];c=next(c for c in json.loads(raw.read_text())['conversations'] if c['group']==g)
 plans.append({'group':g,'scenario':'REPAIR EXISTING DIALOGUE. Keep sound content, correct listed defects; do not add unsupported facts. '+reasons[g]+' Exact earlier draft: '+json.dumps(c,ensure_ascii=False),'memory_focus':row['recall_probe']['focus'],'detours':'Preserve coherent conversation; avoid rehearsing focused fact within2complete pairs of probe.','turns':len(row['messages'])//2,'revision_accounting':'This follows '+('one prior revision; final revision only' if mode=='32' else 'the original draft; at most two cumulative revisions')})
b.run_batch(int(mode),plans,max_revisions=0 if mode=='32' else 1)

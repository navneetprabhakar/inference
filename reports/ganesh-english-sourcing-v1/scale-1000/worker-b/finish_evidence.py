import json,pathlib,hashlib,collections
R=pathlib.Path(__file__).resolve().parent;ROOT=R.parents[3];O=ROOT/'runs/ganesh-english-sourcing-v1/scale-1000/worker-b'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dig(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
def ref(p):return {'path':str(p.relative_to(ROOT)),'sha256':sha(p)}
rows=[json.loads(l) for l in (R/'accepted.jsonl').read_text().splitlines()]; manual=json.loads((R/'manual.json').read_text()); mh=R/('final-manual-annotations-'+sha(R/'manual.json')[:16]+'.json');mh.write_bytes((R/'manual.json').read_bytes())
raws=collections.defaultdict(list)
for p in sorted(O.glob('batch-*-g*.raw.json')):
 for c in json.loads(p.read_text()).get('conversations',[]):
  ms=[{'role':role,'content':t[role]} for t in c['turns'] for role in ('user','assistant')]
  rq=R/(p.name.removesuffix('.raw.json')+'.request.json');assert rq.exists(),rq
  raws[c['group']].append({'raw_artifact':ref(p),'messages_sha256':dig(ms),'request_receipt':ref(rq)})
mem=[];hist=[];norm=[]
for x in rows:
 g=x['group'];h=dig(x['messages']);q=x['recall_probe'];support=q.get('last_support_turn',q.get('support_turn'));cq={'support_turn':support,'probe_turn':q['probe_turn'],'focus':q['focus']}; assert cq['probe_turn']-support>=3
 raw=ROOT/x['generation']['raw_artifact'];c=next(c for c in json.loads(raw.read_text())['conversations'] if c['group']==g)
 sources=[z for z in x['review_receipts'] if 'orchestrator-review' not in z['path']]+[ref(mh)]
 mem.append({'group':g,'messages_sha256':h,'credit':True,'recall_probe':cq,'original_generated_annotation':c['recall_probe'],'reason':q.get('rationale',manual[g]['note']),'source_receipts':sources})
 history=raws[g];revisions=len(history)-1;assert revisions<=2
 for v in history:v['selected']=v['raw_artifact']['path']==x['generation']['raw_artifact'] and v['messages_sha256']==h
 assert sum(v['selected'] for v in history)==1
 hist.append({'group':g,'messages_sha256':h,'total_generation_revisions':revisions,'history':history,'counting_rule':'All original and repair generation calls containing this group, including superseded drafts; fresh review-only calls are not generation revisions.'})
 for rr in x['review_receipts']:
  d=json.loads((ROOT/rr['path']).read_text())
  if isinstance(d,dict) and 'reviews' in d:
   rv=next(v for v in d['reviews'] if v['group']==g);nums=[v['turn'] for v in rv['turn_reviews']];n=len(x['messages'])//2
   assert sorted(nums) in [list(range(1,n+1)),list(range(2,2*n+1,2))]
   norm.append({'group':g,'messages_sha256':h,'source_receipt':rr,'original_turn_indices':nums,'normalized_pair_indices':[v//2 for v in nums] if sorted(nums)==list(range(2,2*n+1,2)) else nums,'rule':'Only an exact complete flat assistant-message sequence 2,4,...,2n is divided by2; otherwise exact complete pair indices1..n are required.'})
 x['recall_probe']=cq;x['memory_probe_credit']=True;x['total_generation_revisions']=revisions
for name,entries in [('final-memory-evidence',mem),('final-generation-history',hist),('final-index-normalization',norm)]:
 p=R/(name+'.json');p.write_text(json.dumps({'entries':entries,'training_admitted':False},ensure_ascii=False,indent=2))
for x in rows:
 x['memory_evidence_receipt']=ref(R/'final-memory-evidence.json');x['generation_history_receipt']=ref(R/'final-generation-history.json');x['index_normalization_receipt']=ref(R/'final-index-normalization.json')
(R/'accepted.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in rows))
full=json.loads((R/'final-content-review.json').read_text())
for e in full['entries']:
 x=next(x for x in rows if x['group']==e['group']);e['total_generation_revisions']=x['total_generation_revisions'];e['generation_history_receipt']=x['generation_history_receipt'];e['memory_evidence_receipt']=x['memory_evidence_receipt'];e['index_normalization_receipt']=x['index_normalization_receipt']
(R/'final-content-review.json').write_text(json.dumps(full,ensure_ascii=False,indent=2))
for name in ('progress.json','final-audit.json'):
 p=R/name;d=json.loads(p.read_text());d.update({'accepted_sha256':sha(R/'accepted.jsonl'),'state':'complete_candidate_review','final_content_review':ref(R/'final-content-review.json'),'memory_evidence_receipt':ref(R/'final-memory-evidence.json'),'generation_history_receipt':ref(R/'final-generation-history.json'),'index_normalization_receipt':ref(R/'final-index-normalization.json'),'total_generation_revisions_max':max(x['total_generation_revisions'] for x in rows)});p.write_text(json.dumps(d,indent=2))
print('Final',len(rows),sha(R/'accepted.jsonl'))

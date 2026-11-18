import json,hashlib,collections,sys
from pathlib import Path
ROOT=Path('/Users/navneetprabhakar/Documents/git/image/inference');R=ROOT/'reports/ganesh-foundations-extension-v1/orchestration';O=ROOT/'runs/ganesh-foundations-extension-v1/orchestration'
sys.path.insert(0,str(ROOT/'reports/ganesh-english-sourcing-v1/scale-1000'))
from verify_selection import verify_new,verify_full_content
from selection_memory_integrity import verify_memory
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
digest=lambda v:hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
def ref(p):return {'path':str(p.relative_to(ROOT)),'sha256':sha(p)}
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
rows=[json.loads(l) for l in (R/'accepted.jsonl').read_text().splitlines()]; excluded={'orch_013':'Invents a publication approval condition despite explicit instruction.','orch_015':'Invents a mandatory rollback execution test as completion criterion.','orch_020':'Assumes tentative launch date blocks explicitly requested scheduling.','orch_022':'Describes two completed checks as partially checked.'}
rows=[r for r in rows if r['group'] not in excluded];rows.sort(key=lambda r:r['group'])
notes={'001':'Readiness remains pending test evidence tied to the candidate; status is explicitly a draft.','002':'Research brief separates evidence and recommendation from final judgment; no delegation claimed.','004':'File content is unavailable; no conclusion is invented and future reading is proposed.','005':'Bounded upload retries check recording first and stop after failures; no execution claimed.','006':'Interim report distinguishes provided figures from outstanding risk review and unknown scheduling.','007':'Recipient clarified and text drafted; no message sent is claimed.','008':'Revised timeline identifies conflict and asks which constraint can move; no calendar update claimed.','009':'Failed health check stops expansion, rollback follows reported trigger, recovery evidence remains separate.','010':'Supplied note supports concise action list and no external lookup is needed.','011':'Parallel work follows explicit revised sequence; approval remains a dependency.','012':'Approval is version-specific and user-reported; publication remains unexecuted.','014':'Failed search cannot establish approval; proposed checks are not presented as findings.','016':'Cancellation applies to proposed reminder; draft review status remains unknown.','017':'Deletion scope and path clarified; assistant reports no deletion and supplies instruction only.','018':'User-defined retry limit is counted and diagnostic steps are proposals, not results.','019':'Pilot observations are separated from causal inference; requested further evidence is identified.','021':'Supplied workshop note grounds planning; call conflict and unknown review end remain explicit, without claiming a call change.','023':'Priority changes to drafting; prior agenda state and unknown timings preserved.','024':'User-defined two-attempt stop is preserved, partial import status remains unknown and next checks are proposals.'}
entries=[]
for r in rows:
 n=len(r['messages'])//2; k=r['group'][-3:];assert k in notes
 entries.append({'group':r['group'],'messages_sha256':digest(r['messages']),'decision':'pass','assistant_turns_reviewed':n,'reviewed_turn_numbers':list(range(1,n+1)),'rationale':notes[k]})
review=R/'final-content-review.json';write(review,{'reviewer':'parent agent full dialogue reading; content-specific rationale','entries':entries,'excluded_by_manual_review':excluded});rr=ref(review)
versions=collections.defaultdict(list);inventory=[]
for p in sorted(O.glob('*.raw.json'),key=lambda x:x.stat().st_mtime_ns):
 data=json.loads(p.read_text())
 if 'conversations' not in data:continue
 inventory.append(ref(p))
 for c in data['conversations']:
  ms=[{'role':role,'content':t[role]} for t in c['turns'] for role in ('user','assistant')]
  versions[c['group']].append({'revision':len(versions[c['group']]),'messages_sha256':digest(ms),'raw_artifact':str(p.relative_to(ROOT)),'raw_sha256':sha(p),'request_receipt':ref(p.with_name(p.name.replace('.raw.json','.request.json'))),'events_receipt':ref(p.with_name(p.name.replace('.raw.json','.events.jsonl')))})
by={r['group']:r for r in rows};history=[]
for g,vs in sorted(versions.items()):
 r=by.get(g); selected=next((v['revision'] for v in vs if r and v['raw_artifact']==r['generation']['raw_artifact']),None)
 history.append({'group':g,'messages_sha256':digest(r['messages']) if r else vs[-1]['messages_sha256'],'total_generation_revisions':len(vs)-1,'selected_revision':selected,'versions':vs,'selected':bool(r)})
hp=R/'generation-revision-history.json';write(hp,{'entries':history,'generation_artifact_inventory':inventory,'scope':'All generated candidates, including excluded versions'});hr=ref(hp)
mem=[]
for r in rows:
 raw=ROOT/r['generation']['raw_artifact'];c=next(x for x in json.loads(raw.read_text())['conversations'] if x['group']==r['group']);assert c['recall_probe'] is None
 mem.append({'group':r['group'],'messages_sha256':digest(r['messages']),'credit':False,'recall_probe':None,'original_generated_annotation':None,'reason':'No memory credit claimed; generated annotation is null.','source_receipts':[ref(raw),r['review_receipts'][-1],rr]})
mp=R/'memory-evidence.json';write(mp,{'entries':mem});mr=ref(mp)
hby={e['group']:e for e in history}
for r in rows:
 h=hby[r['group']];r.update(full_content_review_receipt=rr,memory_probe_credit=False,recall_probe=None,memory_evidence_receipt=mr,total_generation_revisions=h['total_generation_revisions'],selected_generation_revision=h['selected_revision'],generation_history_receipt=hr)
 verify_new(r);verify_full_content(r);verify_memory(r,ROOT)
out=R/'selected.jsonl';out.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
write(R/'verification.json',{'candidates_planned':24,'selected':len(rows),'turns':sum(len(r['messages'])//2 for r in rows),'selected_sha256':sha(out),'verify_new':'pass','verify_full_content':'pass','selection_memory_integrity':'pass','memory_credited':0,'all_generated_groups':len(versions),'all_version_history':hr,'manual_exclusions':excluded,'candidate_only':True,'training_admitted':False,'positive_tool_calls':0,'independent_release_review':False,'backend_routing_independently_verified':False})
print((R/'verification.json').read_text())

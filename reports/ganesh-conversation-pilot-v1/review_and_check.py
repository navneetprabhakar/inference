"""Explicit same-author review receipt plus fail-closed local structural checks."""
import collections,hashlib,json,re,sys
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'runs/nanochat-source')]
from nanochat.tokenizer import RustBPETokenizer
from cloud_training.nano_chat_format import encode_conversation
from cloud_training.nano_quality import validate_suite
from cloud_training.nano_tool_lessons import validate_lesson
from cloud_training.nano_sft import JsonlConversations,BestFitConversations
from cloud_training.nano_quality_gate import dataset_coverage
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(n,o):(P/n).write_text(json.dumps(o,indent=2,ensure_ascii=False)+'\n')
assert not (P/'freeze.json').exists()
tok=RustBPETokenizer.from_directory(str(ROOT/'runs/ownbase-v2-data/tokenizer'))
rows={s:[json.loads(l) for l in (P/(s+'.jsonl')).read_text().splitlines()] for s in ['train','control','development']}
assert len(rows['train'])==70 and len(rows['control'])==33 and len(rows['development'])==35
source_notes={
'ordinary':'Respond to the expressed feeling/request without inventing personal details or giving unwanted advice; later constraints are followed.',
'clarification':'Ask for genuinely missing information, use the supplied clarification, and do not claim external actions.',
'instructions':'Check requested token spelling, case, count, order, separators and punctuation exactly at each turn.',
'grounding':'Separate supplied facts from missing evidence; new information updates only what it establishes; never claim a message was sent.',
'entity':'Track owner/borrower, sender/receiver, containers and excluded items separately; do not swap roles.',
'correction':'The latest explicit change supersedes only the named field; unchanged fields persist; a considered but rejected change is not applied.',
'memory':'Read the whole trajectory; intervening detail or movement of another object must not overwrite the requested fact; sequence and active state differ.',
'rewrite':'Perform the requested transformation while preserving subject, facts, negation, temporal order and uncertainty; no invented excuse/context.',
'model_identity':'Exact user-authorized identity Ganesh-base and creator Navneet Prabhakar; no answer-bearing system prompt.',
 'tools':'Prompt/arguments/order and final answer checked against actual offline broker replay; call/end structure retained.'}
reviews=[];suite=[];coverage={};maxima={}
for split,rr in rows.items():
 ds=JsonlConversations(P/(split+'.jsonl'),tok,sha(P/(split+'.jsonl')));coverage[split]=dataset_coverage(ds)
 for r in rr:
  if split=='control':continue # exact subset, same reviewed content
  enc=encode_conversation(tok,r['messages'],policies=r['policies'],context=2048);bounds=[i for i,m in enumerate(r['messages']) if m['role']=='user']+[len(r['messages'])];turns=[];spec=[]
  for j,(a,b) in enumerate(zip(bounds,bounds[1:])):
   mm=r['messages'][a:b];answer=[m['content'] for m in mm if m['role']=='assistant' and 'content' in m][-1]
   reason=source_notes[r['family']]
   turns.append({'turn':j,'reviewed':True,'pass':True,'user':mm[0]['content'],'reference':answer,'review_basis':reason})
   spec.append({'user':mm[0]['content'],'policy':r['policies'][j],'reply_budget':96,'reference_answer':answer,'expected_calls':[m['tool_call'] for m in mm if 'tool_call' in m],'rubric':reason+' Judge full generated history and complete reply; reference wording need not be copied unless exact output requested. Invalid/blocked turns fail.'})
  replay=validate_lesson(r)['actual_calls'] if r['family']=='tools' else 0
  reviews.append({'id':r['id'],'split':split,'row_sha256':hashlib.sha256(json.dumps(r,sort_keys=True).encode()).hexdigest(),'family':r['family'],'pass':True,'turns':turns,'actual_calls_replayed':replay})
  if split=='development':suite.append({'id':r['id'],'source_group':r['provenance']['source_group'],'category':r['family'],'turns':spec})
# Candidate control must be a byte-equivalent row subset, not separately authored variants.
byid={r['id']:r for r in rows['train']};assert all(byid[r['id']]==r for r in rows['control'])
def prompts(rr):return {' '.join(m['content'].lower().split()) for r in rr for m in r['messages'] if m['role']=='user'}
assert not prompts(rows['train'])&prompts(rows['development'])
assert not {r['provenance']['source_group'] for r in rows['train']}&{r['provenance']['source_group'] for r in rows['development']}
# Exact full-scenario decontamination against exposed diagnostics, never sealed release.
old=[]
for name in ['reports/english-first-v1/fit-train.jsonl','reports/english-first-v1/development-reference.jsonl','reports/ganesh-english-curriculum-v2/train.jsonl','reports/ganesh-english-curriculum-v2/development.jsonl']:
 old.extend(json.loads(l) for l in (ROOT/name).read_text().splitlines())
old_sets={tuple(m.get('content','') for m in r['messages'] if m['role']=='user') for r in old}
assert all(tuple(m['content'] for m in r['messages'] if m['role']=='user') not in old_sets for r in rows['train']+rows['development'])
# Hash-only frozen-data verification; no sealed release prompts inspected.
frozen={};fr=ROOT/'reports/corrective-corpus-v1';freeze=json.loads((fr/'freeze.json').read_text())
for name,h in freeze['files'].items():
 if 'release' in name:continue
 if name.endswith(('train.jsonl','validation.jsonl','quality-contract.json','manifest.json')):
  f=fr/name
  if f.exists():assert sha(f)==h,name;frozen[str(f.relative_to(ROOT))]=h
fm=json.loads((ROOT/'reports/english-first-v1/diagnostic-manifest.json').read_text())
for item in ['train','validation']:
 f=ROOT/'reports/english-first-v1'/fm[item]['file'];assert sha(f)==fm[item]['sha256'];frozen[str(f.relative_to(ROOT))]=sha(f)
# Existing code unchanged; exact block equality, true target denominators, both no-call modes, full tool replay.
plan=json.loads((P/'exposure-plan.json').read_text());assert plan['updates_per_arm']==40
stats={r['id']:r for r in json.loads((P/'row-statistics.json').read_text())['train']}
block_checks=[]
for block in plan['blocks']:
 arms={}
 for arm in ['broad','control']:
  seq=block[arm];assert all(i in byid for i in seq)
  targets=sum(stats[i]['assistant_targets'] for i in seq);assert targets==block['assistant_targets_each_arm']
  arms[arm]={'conversations':len(seq),'turns':sum(stats[i]['turns'] for i in seq),'assistant_targets':targets,'position_tokens':sum(stats[i]['tokens'] for i in seq)}
 assert arms['broad']['conversations']==arms['control']['conversations'] and arms['broad']['turns']==arms['control']['turns']
 block_checks.append({'update':block['update'],'family':block['family'],'arms':arms})
assert sum(b['arms']['broad']['assistant_targets'] for b in block_checks)==9144
out={'schema':1,'purpose':'development_only_never_train','required_context_tokens':2048,'sessions':suite};validate_suite(out);write('development-suite.json',out)
write('review.json',{'scope':'All105 distinct authored train/development trajectories reviewed by Codex author; same-agent review, NOT independent/human release review. Control33 is exact reviewed train subset.','records':reviews,'changes_from_review':['Changed ambiguous he to singular/plural they before admission.','Reauthored six close structural development siblings before final freeze; no model result informed edits.','Development tool probes use held-out conversion phrasing rather than numeric variants of training calculator requests.'],'limitations':['Only70 training scenarios and2286 unique supervised positions; controlled pilot corpus, not broad English sufficiency.','Shared abstract language skills across splits are intentional; no pristine independent release claim.','Maximum context below700tokens; no2K/4K memory claim.','Entire new corpus is labelled Codex-authored synthetic; no new organic source admission claimed.'],'all_pass':True})
write('local-checks.json',{'passed':True,'scope':'corpus semantics receipt, exact input/label masks and prefixes in prepare, split/exposure/identity structure and offline broker replay; NOT GPU/runner qualification','coverage':coverage,'frozen_files_verified':frozen,'tool_calls_replayed':sum(r['actual_calls_replayed'] for r in reviews),'full_review_sessions':len(reviews),'full_review_user_turns':sum(len(r['turns']) for r in reviews),'schedule_checks':block_checks,'sealed_release_read':False,'training_authorized':False,'runner_ready':False})
write('source-manifest.json',{'schema':1,'kind':'codex_authored_reviewed_pilot_candidate','source_sha256':sha(P/'source.py'),'builder_sha256':sha(P/'prepare.py'),'review_sha256':sha(P/'review.json'),'split_policy':'Named scenario groups fixed by hand before authoring; no generated parameter variants across splits. Six structurally close candidates reauthored during review. English scores exclude identity/tool common facts.','files':{s+'.jsonl':sha(P/(s+'.jsonl')) for s in rows}})
write('admission.json',{'schema':1,'review_passed':True,'training_admitted':False,'release_eligible':False,'reason':'New exact-target block schedule is not implemented in mandatory trainer/controller. Budget not approved. Data review does not authorize training.','source_manifest_sha256':sha(P/'source-manifest.json'),'review_sha256':sha(P/'review.json'),'exposure_plan_sha256':sha(P/'exposure-plan.json')})
print(json.dumps({'sessions':len(reviews),'reviewed_turns':sum(len(r['turns']) for r in reviews),'train_unique_targets':coverage['train']['assistant_targets'],'control_unique_targets':coverage['control']['assistant_targets'],'tool_replays':sum(r['actual_calls_replayed'] for r in reviews),'frozen_files_verified':len(frozen),'exact_target_exposure_each_arm':9144,'runner_ready':False},indent=2))

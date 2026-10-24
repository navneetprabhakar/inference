"""Package screened candidates after recorded primary inspection; no training or teacher calls."""
import hashlib,json
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parent;PROJECT=ROOT.parents[1]
def read(p):return json.loads(Path(p).read_text())
def save(p,x):Path(p).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 assert not (ROOT/'STOP.json').exists()
 original=read(ROOT/'report.json');assert original['status']=='GENERATED_REVIEWED_PENDING_PRIMARY'
 plan=read(ROOT/'plan.json');assert sha(ROOT/'run.py')==plan['source_sha256']
 assert sha(PROJECT/'restart/sol-conversation-data-v1/generate.py')==plan['inherited_curriculum_sha256']
 assert sha(ROOT/'private/assignments.json')==plan['assignments_sha256']
 notes=read(ROOT/'private/primary-notes.json');assert set(plan['primary_sample_ids'])<=set(notes),'Complete fixed sample first'
 assert all(r['decision'] in ['pass','hold'] and r['reason'] for r in notes.values())
 records=[json.loads(x) for x in (ROOT/'private/candidates.jsonl').read_text().splitlines()]
 assert len(records)==1000 and len({r['id'] for r in records})==1000
 assert set(notes)<=set(r['id'] for r in records)
 receipts=[read(p) for p in (ROOT/'private').glob('*/receipt.json')]
 terminals=[read(p) for p in (ROOT/'private').glob('*/terminal.json')]
 assert len(receipts)==len(terminals)==100
 assert all(p['requested_model']=='gpt-6-sol' and not p['tools_used'] for p in receipts)
 assert all(p['reaped'] and p['returncode']==0 for p in terminals)
 counts={};files={};holds=[]
 for r in records:
  r['primary_review']=notes.get(r['id'])
  if r['id'] in notes and notes[r['id']]['decision']=='hold':
   holds.append(r['id']);r['quality_clear_candidate']=False
  assert r['training_admitted'] is False
 with (ROOT/'private/final-candidates.jsonl').open('w') as out:
  for r in records:out.write(json.dumps(r,ensure_ascii=False)+'\n')
 for split in ['train','development','test']:
  clear=[r for r in records if r['split']==split and r['quality_clear_candidate']]
  c=Counter(documents=len(clear))
  for r in clear:c.update(r['counts'])
  fit=[r for r in clear if r['fits_current_context256']]
  c.update(context256_diagnostic_documents=len(fit),context256_content_tokens=sum(r['counts']['content_tokens'] for r in fit),context256_assistant_content_tokens=sum(r['counts']['assistant_content_tokens'] for r in fit))
  counts[split]=dict(c)
  path=ROOT/'private'/f'{split}-candidates.jsonl'
  with path.open('w') as out:
   for r in clear:out.write(json.dumps(r,ensure_ascii=False)+'\n')
  files[path.name]=dict(sha256=sha(path),documents=len(clear))
  if split=='train':
   path=ROOT/'private/train-context256-candidates.jsonl'
   with path.open('w') as out:
    for r in fit:out.write(json.dumps(r,ensure_ascii=False)+'\n')
   files[path.name]=dict(sha256=sha(path),documents=len(fit),diagnostic_only=True)
 splits={}
 for r in records:
  assert r['family'] not in splits or splits[r['family']]==r['split']
  splits[r['family']]=r['split']
 primary=dict(selection='Frozen 50-example stratified sample: two per family plus ten sampled additional records; not all 1000 directly inspected',fixed_sample_total=50,fixed_sample_pass=sum(notes[x]['decision']=='pass' for x in plan['primary_sample_ids']),total_direct_reviews=len(notes),holds=holds,reviews=notes,reviewer='Primary assistant directly read displayed full messages; no student inference',limitations='Same-model Sol review plus primary inspection does not establish independent factual certification.')
 primary['joint_sample_clear']=sum(r['quality_clear_candidate'] for r in records if r['id'] in plan['primary_sample_ids'])
 primary['joint_sample_excluded']=50-primary['joint_sample_clear']
 save(ROOT/'private/primary-review-full.json',primary)
 public_primary={**primary,'reviews':{k:{'decision':v['decision']} for k,v in notes.items()},'detailed_evidence':'private/primary-review-full.json','detailed_evidence_sha256':sha(ROOT/'private/primary-review-full.json')}
 save(ROOT/'primary-review.json',public_primary)
 save(ROOT/'artifact-manifest.json',dict(files=files,tokenizer_sha256=sha(PROJECT/'restart/mac15m-feasibility-v1/upstream/tokenizer.model'),requested_model='gpt-6-sol',resolved_model_exposed=False,student_updates=0))
 save(ROOT/'teacher-screening-report.json',original)
 report={**original,'status':'COMPLETE_QUALITY_SCREENED_CANDIDATES','quality_clear_after_primary':sum(r['quality_clear_candidate'] for r in records),'primary_holds':holds,'primary_direct_reviews':len(notes),'fixed_sample_pass':primary['fixed_sample_pass'],'fixed_sample_total':50,'joint_sample_clear':primary['joint_sample_clear'],'packaged_candidate_counts':counts,'training_admitted':0}
 save(ROOT/'report.json',report)
 lines=['# GPT-6 Sol — 1,000 additional conversations','',
 'Generated 1,000 new synthetic English conversations with requested CLI model `gpt-6-sol`, separate from the earlier 100. Provider-resolved model identity was not exposed. Four concurrent CLI workers; no student backend, training or weight changes.','',
 f"All 1,000 received separate-call Sol review. The primary assistant directly inspected {len(notes)} complete conversations, including the frozen 50-example sample ({primary['fixed_sample_pass']}/50 clear). Primary dispositions are in `primary-review.json`, with detailed evidence kept locally in `private/primary-review-full.json`; rejected examples were not rewritten or replaced. Same-teacher review is not independent verification. Joint screening retained {primary['joint_sample_clear']} of the 50 inspected examples; this is not a claim that every remaining candidate is error-free.",'',
 '| Split | Screened conversations | Native content tokens | Assistant content tokens | Fit diagnostic 256-token format |','|---|---:|---:|---:|---:|']
 for s,c in counts.items():lines.append(f"| {s} | {c['documents']} | {c['content_tokens']} | {c['assistant_content_tokens']} | {c['context256_diagnostic_documents']} |")
 lines += ['',
 'Native counts use the existing 32k SentencePiece tokenizer. Assistant content counts exclude role/end-turn markers and are not final masked target counts. Context fit uses plain role labels solely as a diagnostic; no truncation or splitting was applied.','',
 '## Local data','',
 'Quality-screened payloads: `private/train-candidates.jsonl`, `private/development-candidates.jsonl`, `private/test-candidates.jsonl`. `private/train-context256-candidates.jsonl` is the smaller diagnostic-context subset. JSONL records include messages, split/family, counts, model review and any primary review. All payloads, holdout text, prompts and raw CLI events remain local and ignored by Git. `artifact-manifest.json` supplies hashes.','',
 '## Diversity and overlap','',
 'Twenty conversational skills and thirty everyday scene labels. Scene lists are disjoint between train/development/test; whole skill families retain the same split as the prior 100. Variations include clarification, correction, retention, practical constraints and misunderstandings. Heldouts are synthetic and inspected; they are not sealed independent benchmarks.','',
 'Deduplication checks normalized exact text and exact whole-conversation 5-word-shingle Jaccard >=0.5 within this batch and against the earlier 100 and previously exposed training candidates. Matches exclude affected new records. See `dedup-report.json` for evidence and source hashes. This is not embedding-based semantic deduplication or a guarantee against all historical contamination. Historical sealed evaluation files were not accessed.','',
 'Tool examples cover honesty when tools are unavailable and interpretation of fictional user-supplied tool outputs. No actual internal/MCP call-and-result traces were generated.','',
 '## Status and bounds','',
 f"Generation/review completed in {original['elapsed_seconds']/60:.2f} minutes using 100 calls, no automatic retry or model fallback. Observed usage: {original['usage']['input_tokens']} input, {original['usage']['output_tokens']} output and {original['usage']['reasoning_output_tokens']} reasoning-output tokens. Teacher usage tokens differ from native student-data counts.",'',
 'Bounds: four concurrent calls, 100 requests, 60 aggregate minutes, 240 seconds/request, 3,000,000 observed input tokens and 750,000 aggregate output-plus-reasoning tokens. Observed token caps are post-completion checks, not provider-side generation limits.','',
 'Training stays paused. These are screened conversation candidates; actual supervised target counts require frozen chat serialization, assistant loss masks and end-turn boundaries. The failed foundation admission gate remains unresolved, and conversation generation does not demonstrate student capability.']
 (ROOT/'README.md').write_text('\n'.join(lines)+'\n')
 print(json.dumps(dict(complete=True,screened=report['quality_clear_after_primary'],counts=counts),indent=2))
if __name__=='__main__':main()

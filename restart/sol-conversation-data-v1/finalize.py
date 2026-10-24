"""Package quality-screened candidates; never train or access historical sealed cases."""
import hashlib,json,re
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parent
PROJECT=ROOT.parents[1]
def read(p):return json.loads(p.read_text())
def save(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def shingles(messages):
 words=re.findall(r'\w+',' '.join(m['content'] for m in messages).lower())
 return set(tuple(words[i:i+5]) for i in range(len(words)-4))
def main():
 assert not (ROOT/'STOP.json').exists()
 report=read(ROOT/'report.json');assert report['status']=='GENERATED_REVIEWED_PENDING_PRIMARY'
 records=[json.loads(s) for s in (ROOT/'private/candidates.jsonl').read_text().splitlines()]
 assert len(records)==100 and len({r['id'] for r in records})==100
 assert len(list((ROOT/'private').glob('*/receipt.json')))==20
 notes=[
 'Useful clarification followed by an invitation preserving optional seeds and beginners.',
 '45-minute and revised 30-minute schedules sum correctly; supplies and group retained.',
 'Lantern count/location correct; unknown supplier and batteries not invented.',
 'Both schedules preserve durations and ordering; 45 and 15 minutes spare are correct.',
 'Capacity and price comparison correctly changes recommendation for 26 guests.',
 'Rewrite retains time, free supplies and limited spaces without promising registration.',
 'Summary grounded; 60 minus 38 plus 14 equals 36.',
 'Metal versus wood explanation correctly distinguishes heat transfer from temperature.',
 'Story response preserves gutter cause and the sequence before Leo moves pots.',
 'Pencil calculations 18 minus 8 equals 10 and 18 minus 10 equals 8 are correct.',
 'Weather naming follows single-word and non-cold constraints after updates.',
 'Unknown fair closing time remains distinct from craft tent closing.',
 'Booking cost 12 exceeds 10; revised draft costs 6 and no action claimed.',
 'Export correctly reported as 9 successes and 3 failures, not complete success.',
 'Valid JSON preserves event/place and changes only Saturday to Sunday.',
 'Casual conversation stays on tomato plant observations without unsupported advice.',
 'Troubleshooting updates hypothesis based on power-strip versus wall comparison.',
 'Wrapping instructions adapt to missing tape using ribbon and folds.',
 'Seasons explanation uses axial tilt and opposite hemispheres correctly.',
 'Seating conflict identified; adding a seventh chair satisfies the updated constraints.'
 ]
 sample=[dict(id=f'sol-{i:02d}-0',pass_quality=True,critical_error=False,reason=n) for i,n in enumerate(notes)]
 rejects={
 'sol-05-3':'First assistant turn invents p.m.; subsequent correction does not remove the bad supervised turn.',
 'sol-10-4':'Final invitation retains a declarative sentence despite the questions-only constraint.',
 'sol-12-2':'Final answer invents incomplete status for checklist items whose status was not specified.',
 'sol-14-4':'Capitalization changes exact supplied task strings; conservatively exclude.',
 'sol-17-1':'Corner-bookmark instructions omit the fold needed to form the pocket.'}
 assert set(rejects)==set(report['teacher_rejections'])
 save(ROOT/'primary-review.json',dict(selection='Frozen before generation: first variant of each of 20 families; not a random pass-rate estimate',sample=sample,sample_pass=20,sample_total=20,additional_flagged_reviews=[dict(id=k,exclude=True,reason=v) for k,v in rejects.items()],reviewer='Primary assistant directly read complete conversations; no student inference',limits='Same-model teacher review plus primary sample inspection; not independent human certification.'))
 # Compare only previously exposed training candidates; never read historical dev/test or sealed fixtures.
 prior=PROJECT/'restart/teacher-pilot500-v3/train-candidates.jsonl'
 old=[json.loads(line) for line in prior.read_text().splitlines()]
 oldgrams=[(str(r.get('id',i)),shingles(r['messages'])) for i,r in enumerate(old)]
 overlaps=[]
 for r in records:
  a=shingles(r['messages'])
  for oid,b in oldgrams:
   j=len(a&b)/len(a|b) if a|b else 1
   if j>=.5:overlaps.append(dict(new_id=r['id'],prior_training_id=oid,jaccard=j))
 assert not overlaps,'Historical training overlap requires exclusion before packaging'
 save(ROOT/'prior-training-overlap.json',dict(prior_path=str(prior.relative_to(PROJECT)),prior_sha256=hashlib.sha256(prior.read_bytes()).hexdigest(),prior_records=len(old),new_records=len(records),metric='Exact exhaustive whole-conversation 5-word-shingle Jaccard >= 0.5',matches=overlaps,limits='Only this known exposed training file was checked. No historical sealed fixtures accessed. Semantic leakage below threshold remains possible.'))
 counts={};hashes={}
 for split in ['train','development','test']:
  clear=[r for r in records if r['split']==split and r['quality_clear_candidate']]
  c=Counter(documents=len(clear))
  for r in clear:c.update(r['counts'])
  fit=[r for r in clear if r['fits_current_context256']]
  c.update(context256_diagnostic_documents=len(fit),context256_content_tokens=sum(r['counts']['content_tokens'] for r in fit),context256_assistant_content_tokens=sum(r['counts']['assistant_content_tokens'] for r in fit))
  path=ROOT/'private'/f'{split}-candidates.jsonl'
  with path.open('w') as out:
   for r in clear:out.write(json.dumps(r,ensure_ascii=False)+'\n')
  hashes[path.name]=hashlib.sha256(path.read_bytes()).hexdigest();counts[split]=dict(c)
 save(ROOT/'artifact-manifest.json',dict(files=hashes,tokenizer_sha256=hashlib.sha256((PROJECT/'restart/mac15m-feasibility-v1/upstream/tokenizer.model').read_bytes()).hexdigest(),requested_model='gpt-6-sol',resolved_model_exposed=False,student_updates=0))
 report.update(status='COMPLETE_QUALITY_SCREENED_CANDIDATES',primary_reviewed=25,primary_fixed_sample_pass=20,primary_fixed_sample_total=20,quality_screened_documents=95,packaged_candidate_counts=counts,training_admitted=0,training_paused=True,admission_remaining=['Freeze chat serialization and assistant/end-turn loss masking before counting actual supervised targets.','Current foundation data gate remains failed; this batch does not override it.'],historical_training_overlap_matches=0,historical_training_records_checked=len(old))
 save(ROOT/'report.json',report)
 lines=['# GPT-6 Sol conversation data — bounded batch','',
 'Completed 100 new synthetic English conversations using the exact requested CLI model `gpt-6-sol`; the provider did not expose a resolved model identifier. No student backend was loaded and no training occurred.','',
 '## Quality and splits','',
 'All 100 conversations received a separate-call Sol review. The primary assistant directly reviewed the frozen 20-example sample (one per family) and all five rejected conversations. The 20-example sample passed; five other conversations remain excluded without rewriting. Same-teacher review is not independent truth verification.','',
 '| Split | Screened conversations | Native content tokens | Assistant content tokens | Fit 256-token diagnostic |','|---|---:|---:|---:|---:|']
 for s,c in counts.items():lines.append(f"| {s} | {c['documents']} | {c['content_tokens']} | {c['assistant_content_tokens']} | {c['context256_diagnostic_documents']} |")
 lines += ['',
 'Counts use the existing 32k SentencePiece tokenizer. Assistant content tokens exclude role/end-turn markers; these are not finalized supervised target counts. The 256-token fit check uses plain role labels as a diagnostic only. No truncation or context splitting was performed.','',
 '## Artifacts','',
 'Quality-screened JSONL files are in `private/train-candidates.jsonl`, `private/development-candidates.jsonl`, and `private/test-candidates.jsonl`. Private payloads, prompts, raw CLI events and held-out text stay out of Git. `artifact-manifest.json` records output hashes.','',
 f'Whole task families stay in one split. Development/test are newly created synthetic holdouts; they are not independent benchmarks and primary inspection does not make them sealed. No exact duplicates or cross-split whole-conversation 5-shingle Jaccard matches >=0.5 were found. Also checked the known prior {len(old)}-record training file; see `prior-training-overlap.json`. Historical sealed evaluations were not accessed. These checks do not certify global semantic non-overlap.','',
 'Coverage includes clarification, corrections, grounded answers, planning, comparison, rewriting, summaries, elementary explanations, reading comprehension, arithmetic, preferences, uncertainty, tool honesty, quoted tool-result interpretation, structured output, casual chat, troubleshooting, instructions, misconceptions and conflicting constraints. Tool-honesty examples assume tools unavailable; tool-result examples interpret user-supplied fictional results. This batch contains no actual internal/MCP tool-call training traces.','',
 '## Training status','',
 'Training remains paused. These are quality-screened candidates, not admitted foundation data. Freeze chat serialization, assistant loss masking and end-turn boundaries before training or reporting final supervised targets. The existing foundation data-admission failure remains unresolved. The roughly 5k assistant content tokens in the training split are a pipeline/SFT smoke-test resource, not sufficient evidence for conversational capability or a full training corpus.','',
 f"Generation plus review: {report['elapsed_seconds']/60:.2f} minutes, 20 teacher requests, no retries or model fallback. Observed teacher usage: {report['usage']['input_tokens']} input, {report['usage']['output_tokens']} output and {report['usage']['reasoning_output_tokens']} reasoning-output tokens. These are teacher billing/usage tokens, distinct from student data counts. Maximum observed output plus reasoning per request was 14,000, aggregate bound 200,000; aggregate wall bound 30 minutes. Observed caps are post-generation checks, not provider-side generation limits."]
 (ROOT/'README.md').write_text('\n'.join(lines)+'\n')
 print(json.dumps(dict(status=report['status'],counts=counts,primary_reviewed=25),indent=2))
if __name__=='__main__':main()

"""Summarize primary manual review of all 120 answers; no model calls or training."""
import json,re,hashlib
from pathlib import Path
R=Path(__file__).resolve().parent;V=R/'private';P=R.parents[1]
def read(p):return json.loads(p.read_text())
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4194304),b''):h.update(b)
 return h.hexdigest()
for path,digest in read(R/'freeze.json')['files'].items():assert sha(P/path)==digest
# Recorded after direct reading of every question, oracle and generated answer.
# One non-exact natural answer repeats its final noun but unambiguously gives the correct relation/place.
manual_nonexact_pass={('rejected','fresh-02-0',0)}
number_words={'seventeen':17,'twenty-three':23,'thirty-six':36,'forty-two':42}
summary={};judgments=[]
for model in ['retained','rejected']:
 rows=read(V/(model+'-responses.json'));assert len(rows)==60
 cases={r['id']:True for r in rows};strict_cases=cases.copy()
 for row in rows:
  key=(model,row['id'],row['turn']);exact=re.findall(r'\w+',row['response'].casefold())==re.findall(r'\w+',row['expected'].casefold())
  assert exact==row['exact_normalized']
  assert row['eos']==(row['stop_token']==2)
  correct=exact or key in manual_nonexact_pass
  if key in manual_nonexact_pass:reason='Correct complete location relation/place with the final noun repeated; factual pass, fluency defect, exact-string fail.'
  elif correct:reason='Complete correct fact; no contradictory or unsupported extra claim.'
  elif row['turn']==2 and row['family']=='color':reason='Uses the unrelated latest color instead of recalling the corrected target color.'
  elif row['family']=='owner':reason='Incomplete or unsupported owner identity; full supplied name not recovered.'
  elif row['family']=='time':reason='Does not reproduce the complete supplied time.'
  elif row['family']=='quantity':reason='Wrong or incomplete count, fragment or question instead of the given number.'
  else:reason='Wrong fact, unsupported statement, stale answer or fragment; natural wording alone would not fix factual correctness.'
  judgments.append(dict(model=model,id=row['id'],turn=row['turn'],factual_correct=correct,fluent_factual_correct=exact,reason=reason))
  row['factual_correct']=correct;row['fluent_factual_correct']=exact;cases[row['id']] &= correct;strict_cases[row['id']] &= exact
 metrics=dict(turns=60,factual_correct=sum(r['factual_correct'] for r in rows),fluent_factual_correct=sum(r['fluent_factual_correct'] for r in rows),eos=sum(r['eos'] for r in rows),fully_factual_conversations=sum(cases.values()),conversations=20,fully_factual_sibling_pairs=sum(all(cases[r['id']] for r in rows if r['group']==g) for g in {r['group'] for r in rows}),sibling_pairs=10,constrained_exact_answer_and_format=sum(r['exact_normalized'] for r in rows if r['style']=='constrained'),constrained_turns=30)
 metrics['by_family']={f:dict(turns=sum(r['family']==f for r in rows),factual_correct=sum(r['factual_correct'] for r in rows if r['family']==f)) for f in ['color','location','owner','time','quantity']}
 metrics['by_turn']={label:dict(turns=20,factual_correct=sum(r['factual_correct'] for r in rows if r['turn']==turn)) for turn,label in enumerate(['initial','explicit_correction','delayed_recall_with_distractor'])}
 metrics['by_style']={style:dict(turns=30,factual_correct=sum(r['factual_correct'] for r in rows if r['style']==style)) for style in ['natural','constrained']}
 summary[model]=metrics
save(V/'manual-judgments.json',judgments)
result=read(R/'result.json')
save(R/'review.json',dict(status='FRESH_CONVERSATION_GROUNDING_FAIL_BOTH_CHECKPOINTS',primary_directly_reviewed_answers=120,models=summary,manual_nonexact_factual_passes=1,nonexact_factual_pass_policy='One natural-style answer unambiguously gives the correct complete location but repeats its final noun. This is accepted for factual content and rejected for fluent/exact response quality. Report both totals. No partial names, missing location relations, wrong counts or extra unsupported claims accepted.',rubric_changed=False,judge='Primary agent, not independent blind external or teacher review.',private_case_judgments_sha256=sha(V/'manual-judgments.json'),frozen_inputs_unchanged=True,training_updates=0,checkpoint_promoted=False,inference_positions=result['inference_positions'],elapsed_seconds=result['elapsed_seconds'],conclusion='Narrow-template accuracy did not generalize to unfamiliar values, conversational phrasing and state recall. Failures are substantive factual grounding failures, not merely response formatting. This assessment does not establish a parameter-capacity limit or isolate which training intervention will fix it.',historical_terminal_stop_unchanged=True,automatic_continuation=False))
assert summary['retained']['factual_correct']==3 and summary['rejected']['factual_correct']==6
assert summary['retained']['fully_factual_conversations']==summary['rejected']['fully_factual_conversations']==0
print(json.dumps(read(R/'review.json'),indent=2))

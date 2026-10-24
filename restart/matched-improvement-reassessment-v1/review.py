"""Descriptive primary semantic review; no model acceptance threshold, training or inference."""
import json,re,hashlib
from pathlib import Path
R=Path(__file__).resolve().parent;V=R/'private'
def read(p):return json.loads(p.read_text())
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
# Recorded after directly reading all 456 generated answers and the frozen task grammar.
extra={('short_answer',f'sentence-{i}-known-{w}',0) for i in range(4) for w in ['familiar','novel']}
extra.update({('broader_candidate',f'copy-location-3-novel-{w}',0) for w in ['familiar','novel']})
extra.update({('broader_candidate',f'sentence-0-novel-{w}',0) for w in ['familiar','novel']})
extra.update({('broader_candidate',f'history-color-{i}-familiar',0) for i in range(4)})
extra.update({('broader_candidate',f'history-color-{i}-familiar',1) for i in [0,1]})
partial_location={('short_answer',f'copy-location-{i}-{level}-{w}',0) for i,level in [(0,'known'),(0,'novel'),(1,'known')] for w in ['familiar','novel']}
partial_owner={('broader_candidate',f'copy-owner-0-known-{w}',0) for w in ['familiar','novel']}
partial_owner.update({('broader_candidate','copy-owner-1-known-novel',0),('broader_candidate','copy-owner-2-known-novel',0)})
partial_owner.update({('broader_candidate',f'answerability-0-True-{w}',0) for w in ['familiar','novel']})
verdicts=[];rows_by_model={};summary={}
for model in ['foundation','short_answer','broader_candidate']:
 rows=read(V/(model+'-responses.json'));assert len(rows)==152
 for row in rows:
  exact=re.findall(r'\w+',row['response'].casefold())==re.findall(r'\w+',row['expected'].casefold());assert exact==row['exact_normalized']
  key=(model,row['id'],row['turn']);correct=exact or key in extra
  if exact:reason='Complete correct answer, satisfying the fixed reference output.'
  elif key in extra and row['section']=='sentence':reason='Correct color fact conveyed as a short value; complete-sentence instruction not satisfied.'
  elif key in extra and row['section']=='history':reason='Correct color fact conveyed in a sentence; color-only output instruction not satisfied.'
  elif key in extra:reason='Correct location relation and uniquely identified cabinet; adjective omitted, and one answer repeats the noun. Factual content accepted; exact full-phrase/fluency requirement not satisfied.'
  elif key in partial_location:reason='Correct location landmark only, with required spatial relation missing; partial, not a complete factual answer.'
  elif key in partial_owner:reason='A correct complete component of the supplied name only; requested full identity incomplete.'
  elif model=='foundation':reason='Narrative continuation, unsupported additions or irrelevant answer; no complete grounded task response.'
  elif row['family']=='clarification':reason='Not a relevant grammatical question for the requested missing field; keyword or question-mark presence alone is insufficient.'
  else:reason='Incorrect, unsupported, incomplete or stale fact; partial substring matching does not award full factual correctness.'
  row['factual_content_correct']=correct;row['partial_correct_component_only']=key in partial_location or key in partial_owner
  verdicts.append(dict(model=model,id=row['id'],turn=row['turn'],factual_content_correct=correct,strict_exact_correct=exact,partial_correct_component_only=row['partial_correct_component_only'],reason=reason))
 rows_by_model[model]=rows
 def counts(selected):return dict(answers=len(selected),factual_content_correct=sum(x['factual_content_correct'] for x in selected),strict_exact=sum(x['exact_normalized'] for x in selected),partial_component_only=sum(x['partial_correct_component_only'] for x in selected),eos=sum(x['eos'] for x in selected))
 metrics=dict(all_answers_descriptive_only=counts(rows),sections={section:counts([x for x in rows if x['section']==section]) for section in ['copy','sentence','clarification','answerability','history']})
 metrics['copy_by_family']={family:counts([x for x in rows if x['section']=='copy' and x['family']==family]) for family in ['color','location','owner','time']}
 metrics['copy_factorial']={level+'_'+wording:counts([x for x in rows if x['section']=='copy' and x['value_level']==level and x['wording']==wording]) for level in ['known','novel'] for wording in ['familiar','novel']}
 metrics['history_by_turn']={name:counts([x for x in rows if x['section']=='history' and x['turn']==turn]) for turn,name in enumerate(['initial','immediate_update','delayed_recall'])}
 history_ids={x['id'] for x in rows if x['section']=='history'}
 metrics['history_complete_conversations']=dict(conversations=len(history_ids),factual_content_correct=sum(all(x['factual_content_correct'] for x in rows if x['id']==i) for i in history_ids),strict_exact=sum(all(x['exact_normalized'] for x in rows if x['id']==i) for i in history_ids))
 metrics['history_by_wording']={w:counts([x for x in rows if x['section']=='history' and x['wording']==w]) for w in ['familiar','novel']}
 metrics['recall_by_wording']={w:counts([x for x in rows if x['section']=='history' and x['wording']==w and x['turn']==2]) for w in ['familiar','novel']}
 metrics['answerability_by_presence']={condition:counts([x for x in rows if x['section']=='answerability' and x['condition']==condition]) for condition in ['present','absent']}
 summary[model]=metrics
save(V/'manual-verdicts.json',verdicts)
paired={};before={(x['id'],x['turn']):x for x in rows_by_model['short_answer']}
for section in ['all','copy','sentence','clarification','answerability','history']:
 after=[x for x in rows_by_model['broader_candidate'] if section=='all' or x['section']==section]
 paired[section]=dict(items=len(after),factual_gains=sum(x['factual_content_correct'] and not before[(x['id'],x['turn'])]['factual_content_correct'] for x in after),factual_losses=sum(not x['factual_content_correct'] and before[(x['id'],x['turn'])]['factual_content_correct'] for x in after),exact_gains=sum(x['exact_normalized'] and not before[(x['id'],x['turn'])]['exact_normalized'] for x in after),exact_losses=sum(not x['exact_normalized'] and before[(x['id'],x['turn'])]['exact_normalized'] for x in after))
assert summary['short_answer']['all_answers_descriptive_only']['factual_content_correct']==33
assert summary['broader_candidate']['all_answers_descriptive_only']['factual_content_correct']==66
save(R/'review.json',dict(status='MATCHED_DESCRIPTIVE_REASSESSMENT_DECISION_DEFERRED',primary_manually_reviewed_answers=456,models=summary,paired_broader_vs_short_answer=paired,scoring='Factual content and strict requested output are separate. Correct color values can convey the full fact while missing sentence/word-only formatting. Unambiguous spatial relation and unique referent accepted despite omitted adjective; strict score does not accept it. Name component or landmark without relation counted only as partial. No unsupported added facts or invented attributes accepted.',judgment_sensitivity='Non-exact factual passes: short-answer 8, broader 10. Strict exact answers independently show 25 -> 56, so the observed improvement does not rely on these semantic judgments.',judge='Primary agent, not an independent blind or teacher judge.',private_verdicts_sha256=sha(V/'manual-verdicts.json'),decision_deferred=True,checkpoint_promoted=False,training_updates=0,prior_evidence_preserved=True,conclusion='The broader candidate shows measured gains over the short-answer child, especially full locations, sentence realization and absent-fact abstention, while color-word responses regress under novel phrasing. New value strings, full identities, exact times and robust multi-turn recall remain limited. Both the prior positive tests and the harder negative tests describe different scopes and remain valid. No overall model acceptance/rejection decision is made.'))
print(json.dumps(dict(whole={model:m['all_answers_descriptive_only'] for model,m in summary.items()},copy_factorial={model:m['copy_factorial'] for model,m in summary.items()},sections={model:m['sections'] for model,m in summary.items()},history={model:m['history_complete_conversations'] for model,m in summary.items()},paired=paired),indent=2))

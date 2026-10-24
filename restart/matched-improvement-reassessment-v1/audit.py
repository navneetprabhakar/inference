"""Read-only integrity and matched-item accounting; audit pass is not model acceptance."""
import json,re,hashlib,importlib.util
from pathlib import Path
from sentencepiece import SentencePieceProcessor
R=Path(__file__).resolve().parent;P=R.parents[1];V=R/'private'
def read(p):return json.loads(p.read_text())
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4194304),b''):h.update(b)
 return h.hexdigest()
for path,digest in read(R/'freeze.json')['files'].items():assert sha(P/path)==digest,path
spec=importlib.util.spec_from_file_location('matched_audit_serialization',P/'restart/sol-conversation-sft-diagnostic-v1/runner.py');s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s);sp=SentencePieceProcessor(model_file=str(s.TOK))
bank={c['id']:c for c in read(V/'bank.json')};review=read(R/'review.json');result=read(R/'result.json');judgments=read(V/'manual-verdicts.json')
assert sha(V/'manual-verdicts.json')==review['private_verdicts_sha256'];judgments={(j['model'],j['id'],j['turn']):j for j in judgments}
positions=0;max_input=0;checks={};keys={}
for model in ['foundation','short_answer','broader_candidate']:
 rows=read(V/(model+'-responses.json'));assert sha(V/(model+'-responses.json'))==result['models'][model]['raw_responses_sha256'];assert len(rows)==152
 contexts={};exact_count=0;fact_count=0;keys[model]={(x['id'],x['turn']) for x in rows}
 for row in rows:
  case=bank[row['id']];assert row['expected']==case['oracle'][row['turn']]
  exact=re.findall(r'\w+',row['response'].casefold())==re.findall(r'\w+',row['expected'].casefold());assert exact==row['exact_normalized']
  assert row['eos']==(row['stop_token']==2);j=judgments[(model,row['id'],row['turn'])];assert j['strict_exact_correct']==exact
  exact_count+=exact;fact_count+=j['factual_content_correct']
  context=contexts.setdefault(row['id'],[]);context.append(dict(role='user',content=row['user']));n=len(s.prompt(sp,context));k=len(row['generated_ids']);assert n+32<=256
  # Includes the final EOS/BOS logit evaluation; capped generations have exactly k=32 forwards.
  steps=k+1 if row['stop_token'] is not None else k
  positions+=steps*n+steps*(steps-1)//2;max_input=max(max_input,n+steps-1)
  context.append(dict(role='assistant',content=row['response']))
 assert exact_count==result['models'][model]['exact_answers']==review['models'][model]['all_answers_descriptive_only']['strict_exact']
 assert fact_count==review['models'][model]['all_answers_descriptive_only']['factual_content_correct'];assert result['models'][model]['new_training_updates']==0
 checks[model]=dict(exact=exact_count,semantic_content= fact_count,answers=152)
assert keys['foundation']==keys['short_answer']==keys['broader_candidate']
assert positions==result['inference_positions']==342432
pairs=review['paired_broader_vs_short_answer']['all']
old={(j['id'],j['turn']):j for j in judgments.values() if j['model']=='short_answer'}
new={(j['id'],j['turn']):j for j in judgments.values() if j['model']=='broader_candidate'}
assert sum(new[k]['strict_exact_correct'] and not old[k]['strict_exact_correct'] for k in old)==pairs['exact_gains']==43
assert sum(not new[k]['strict_exact_correct'] and old[k]['strict_exact_correct'] for k in old)==pairs['exact_losses']==12
assert sum(new[k]['factual_content_correct'] and not old[k]['factual_content_correct'] for k in old)==pairs['factual_gains']==39
assert sum(not new[k]['factual_content_correct'] and old[k]['factual_content_correct'] for k in old)==pairs['factual_losses']==6
assert 25+pairs['exact_gains']-pairs['exact_losses']==56
assert 33+pairs['factual_gains']-pairs['factual_losses']==66
assert not result['training_updates'] and not result['promotion'] and result['decision_deferred']
receipt=dict(status='EVIDENCE_INTEGRITY_PASS_NO_MODEL_VERDICT',models=checks,identical_matched_item_keys=True,all_frozen_inputs_unchanged=True,original_and_both_children_unchanged=True,historical_stop_unchanged=True,primary_manual_verdicts=456,private_verdict_hash_verified=True,inference_positions_recomputed=positions,actual_generated_history_accounting_verified=True,max_actual_input_tokens=max_input,training_updates=0,promotion=False,decision_deferred=True,artifact_bytes=sum(p.stat().st_size for p in R.rglob('*') if p.is_file()))
(R/'audit.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))

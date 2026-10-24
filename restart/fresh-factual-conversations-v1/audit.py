"""Independent read-only accounting and integrity checks for the conversation assessment."""
import importlib.util,json,hashlib
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
spec=importlib.util.spec_from_file_location('fresh_audit_serialization',P/'restart/sol-conversation-sft-diagnostic-v1/runner.py');s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
sp=SentencePieceProcessor(model_file=str(s.TOK));review=read(R/'review.json');result=read(R/'result.json');judgments=read(V/'manual-judgments.json');bank={c['id']:c for c in read(V/'bank.json')}
assert sha(V/'manual-judgments.json')==review['private_case_judgments_sha256'];judgments={(j['model'],j['id'],j['turn']):j for j in judgments}
positions=0;max_context=0;models={}
for model in ['retained','rejected']:
 rows=read(V/(model+'-responses.json'));contexts={};complete={i:True for i in bank};byfamily={f:0 for f in ['color','location','owner','time','quantity']}
 assert sha(V/(model+'-responses.json'))==result['models'][model]['raw_responses_sha256']
 for row in rows:
  case=bank[row['id']];assert row['expected']==case['oracle'][row['turn']]
  context=contexts.setdefault(row['id'],[]);context.append(dict(role='user',content=row['user']));n=len(s.prompt(sp,context));generated=len(row['generated_ids']);assert row['stop_token']==2 and generated<32
  positions+=(generated+1)*n+generated*(generated+1)//2;max_context=max(max_context,n+generated)
  assert n+32<=256
  context.append(dict(role='assistant',content=row['response']))
  correct=judgments[(model,row['id'],row['turn'])]['factual_correct'];complete[row['id']] &= correct;byfamily[row['family']]+=correct
 metrics=review['models'][model]
 assert sum(byfamily.values())==metrics['factual_correct'];assert sum(complete.values())==metrics['fully_factual_conversations']==0
 models[model]=dict(manual_factual_scores_verified=True,by_family=byfamily,raw_responses_hash_verified=True,training_updates=result['models'][model]['new_training_updates'])
assert positions==result['inference_positions']==29438 and result['training_updates']==0
assert review['models']['retained']['factual_correct']==3 and review['models']['rejected']['factual_correct']==6
assert max_context<=256 and result['elapsed_seconds']<900
receipt=dict(status='EVIDENCE_AUDIT_PASS_NOT_MODEL_ACCEPTANCE',models=models,all_frozen_hashes_verified=True,historical_training_stop_unchanged=True,actual_generated_history_position_accounting_verified=True,inference_positions_recomputed=positions,maximum_actual_model_input_tokens=max_context,no_context_truncation=True,all_120_answers_ended_with_eos=True,primary_manual_judgments=120,training_updates=0,promotion=False,private_judgments_sha256=sha(V/'manual-judgments.json'),original_and_both_checkpoints_unchanged=True,artifact_bytes=sum(p.stat().st_size for p in R.rglob('*') if p.is_file()))
if (R/'knowledge-result.json').exists():
 supplementary=read(R/'knowledge-result.json');kf=read(R/'knowledge-freeze.json');kr=read(R/'knowledge-review.json')
 assert sha(V/'knowledge-bank.json')==kf['bank_sha256'] and sha(R/'knowledge_check.py')==kf['script_sha256']
 assert sha(V/'knowledge-prepare.py')==kf['local_preparation_sha256']
 assert sha(V/'knowledge-manual-judgments.json')==kr['manual_judgments_sha256']
 extra=0
 for model in ['retained','rejected']:
  supplementary_rows=read(V/(model+'-knowledge-responses.json'));histories={}
  assert sha(V/(model+'-knowledge-responses.json'))==supplementary['models'][model]['raw_responses_sha256']
  assert supplementary['models'][model]['new_training_updates']==0
  for row in supplementary_rows:
   context=histories.setdefault(row['id'],[]);context.append(dict(role='user',content=row['user']));n=len(s.prompt(sp,context));k=len(row['generated_ids']);assert row['stop_token']==2 and n+32<=256
   extra+=(k+1)*n+k*(k+1)//2;context.append(dict(role='assistant',content=row['response']))
 assert extra==supplementary['additional_positions']==3616
 assert positions+extra==supplementary['aggregate_inference_positions']==33054
 assert kr['models']['retained']['correct']==1 and kr['models']['rejected']['correct']==0
 assert supplementary['aggregate_elapsed_seconds']<900 and supplementary['peak_rss_bytes']<12*1024**3
 receipt.update(supplement_frozen_files_and_raw_hashes_verified=True,supplement_judgment_hash_verified=True,supplement_position_accounting_verified=True,aggregate_positions_with_supplement=positions+extra,total_manually_reviewed_answers=150,supplement_new_training_updates=0)
(R/'audit.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))

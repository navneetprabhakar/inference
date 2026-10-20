"""Bind local SFT source, finite data, durable budgets and new heldout protocols."""
# Creator: Navneet Prabhakar
import json,sqlite3
from pathlib import Path
from dataclasses import asdict
from slm.common.training import Recipe
from slm.data.stream_hash import sha
from slm.data.conversation_research import ConversationBatches
from slm.data.prose_screen import RequestGuard,word_key
PLAN=Path('configs/local-conversation-run-v1.json');DATA=Path('data/local-conversation-sft-v2');TOK=Path('data/iteration-two-foundation-tokenizers-v1/vocab-16384');MODEL=Path('data/english-balanced-experiment-v2/mlx/checkpoint/model')
def main():
 if PLAN.exists():raise FileExistsError(PLAN)
 prep=json.loads((DATA/'preparation.json').read_text());schedule=json.loads((DATA/'schedule.json').read_text());priors=[]
 for path in ['data/english-recovery-experiment-v1/physical.sqlite','data/english-balanced-experiment-v2/physical.sqlite']:
  db=sqlite3.connect('file:'+str(Path(path).resolve())+'?mode=ro',uri=True);total=db.execute('SELECT coalesce(sum(positions),0) FROM charges').fetchone()[0];prelim=db.execute("SELECT coalesce(sum(positions),0) FROM charges WHERE phase IN ('common','mlx','cuda')").fetchone()[0];pending=db.execute("SELECT count(*) FROM charges WHERE status!='complete'").fetchone()[0];db.close()
  if pending:raise ValueError('Sealed completed raw recovery ledgers required')
  priors.append(dict(path=path,sha256=sha(path),positions=total,preliminary_positions=prelim))
 if sum(p['positions'] for p in priors)!=1506080:raise ValueError('No carried-summary double counting or prior reset')
 protected=[m['content'] for line in Path('data/conversation-acceptance-v1/source-references.jsonl').open() for m in json.loads(line)['messages'] if len(word_key(m['content']))>=16 and len(word_key(m['content']).split())>=4];guard=RequestGuard(protected)
 for line in (DATA/'train.jsonl').open():
  if guard.matches('\n'.join(m['content'] for m in json.loads(line)['messages'])):raise ValueError('New heldout full-text containment leak')
 with ConversationBatches(DATA,TOK,sha(DATA/'schedule.json')) as batches:
  if batches.counts(len(batches))[0]!=538226 or len(batches)!=2452:raise ValueError('Frozen finite work differs')
 previous=json.loads(Path('data/english-balanced-experiment-v2/mlx/checkpoint/state.json').read_text())['recipe'];recipe=Recipe(**{**previous,'lr':.0001,'warmup_tokens':32768})
 paths=[*DATA.rglob('*'),*MODEL.rglob('*'),*TOK.rglob('*'),*Path('src/slm').rglob('*.py'),Path('scripts/run-local-conversation-sft-v1.py'),Path(__file__),Path('data/conversation-acceptance-v1/manifest.json'),Path('data/conversation-acceptance-v1/development-100.json'),Path('data/conversation-acceptance-v1/reserved-100.json'),Path('data/conversation-acceptance-v1/source-references.jsonl'),Path('configs/current-model-100-conversations-v1.json'),Path('data/english-recovery-corpus-v1/development.jsonl'),Path('data/english-balanced-experiment-v2/mlx-nll.json'),Path('configs/conversation-recovery-target-v1.json'),Path('configs/main-learning-budget-authorization-v2.json'),Path('configs/english-owner-cloud-hold-v1.json')]
 p=dict(creator='Navneet Prabhakar',kind='local-conversation-run-v1',authorization='Owner requests continued local conversation training toward70–75%correctness, no GCP. New local SFT stage is explicitly separate from still-unexecuted CUDA/main language route.',data=str(DATA),schedule_sha256=sha(DATA/'schedule.json'),source_model=str(MODEL),source_model_sha256=sha(MODEL/'manifest.json'),tokenizer=str(TOK),optimizer_transition='Exact corrected90step FP32 weights, explicit fresh AdamW moments/counters; numerical runtime unchanged. Lower LR than prior prose phase; source and failed checkpoints preserved.',recipe=asdict(recipe),planned_new_physical_positions=538226,planned_new_supervised_positions=249390,maximum_new_optimizer_updates=307,max_physical_passes_per_family=2,sealed_raw_priors=priors,maximum_remaining_sft_positions=20000000,planned_cumulative_recovery_physical_positions=2044306,cloud_allowed=False,teacher_calls=0,maximum_wall_seconds=14400,maximum_generation_seconds_per_protocol=3600,retention_documents='data/english-recovery-corpus-v1/development.jsonl',retention_baseline='data/english-balanced-experiment-v2/mlx-nll.json',scheduled_check_updates=[154,307],maximum_source_retention_regression_nats=.1,generation_protocols={'development-100':'data/conversation-acceptance-v1/development-100.json','regression-100':'configs/current-model-100-conversations-v1.json'},reserved_final_protocol='data/conversation-acceptance-v1/reserved-100.json',reserved_final_execution_allowed=False,correctness_target=.75,assessment='Actual student history; all raw replies published/directly graded; no teacher repair. Development reuse is not fresh final testing. No acceptance solely from loss.',limitations='First answer-conditioning stage is predominantly single-turn constraints/summaries/rewrites. Failed broad multi-turn source withheld; it does not establish adequate broad conversation supply or promise75%.',inputs={str(p):sha(p) for p in paths if p.is_file()})
 PLAN.write_text(json.dumps(p,indent=2,sort_keys=True)+'\n');print('Frozen local SFT plan',sha(PLAN),'bindings',len(p['inputs']))
if __name__=='__main__':main()

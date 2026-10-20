"""Bind the new local grounded/replay run to all source, numeric and budget evidence."""
# Creator: Navneet Prabhakar
import json,sqlite3
from dataclasses import asdict
from pathlib import Path
from slm.common.training import Recipe
from slm.data.grounded_conversation_research import GroundedBatches
from slm.data.stream_hash import sha
PLAN=Path('configs/grounded-conversation-run-v1.json');DATA=Path('data/grounded-replay-sft-v1');QA=Path('data/grounded-conversations-v1');TOK=Path('data/iteration-two-foundation-tokenizers-v1/vocab-16384');MODEL=Path('data/english-balanced-experiment-v2/mlx/checkpoint/model')
def main():
 if PLAN.exists():raise FileExistsError(PLAN)
 prep=json.loads((DATA/'preparation.json').read_text());audit=json.loads((DATA/'independent-audit.json').read_text())
 if not audit['complete'] or not audit['passed'] or audit['all12288_original_question_answer_spans_reconstructed']!=12288:raise ValueError('Independent actual source/numeric/exposure audit required')
 for name,h in audit['input_bindings'].items():
  if sha(name)!=h:raise ValueError('Independent audited input changed')
 priors=[];previous_sft=0
 for path in ['data/english-recovery-experiment-v1/physical.sqlite','data/english-balanced-experiment-v2/physical.sqlite','data/local-conversation-run-v1/physical.sqlite']:
  db=sqlite3.connect('file:'+str(Path(path).resolve())+'?mode=ro',uri=True)
  total=db.execute('SELECT coalesce(sum(positions),0) FROM charges').fetchone()[0];prelim=db.execute("SELECT coalesce(sum(positions),0) FROM charges WHERE phase IN ('common','mlx','cuda')").fetchone()[0];previous_sft+=db.execute("SELECT coalesce(sum(positions),0) FROM charges WHERE phase='conversation_sft'").fetchone()[0];pending=db.execute("SELECT count(*) FROM charges WHERE status!='complete'").fetchone()[0];db.close()
  if pending:raise ValueError('All raw prior gradient charges must be complete')
  priors.append(dict(path=path,sha256=sha(path),positions=total,preliminary_positions=prelim))
 if sum(p['positions'] for p in priors)!=1776439 or previous_sft!=270359:raise ValueError('No lost/double-counted discarded positions')
 remaining=20000000-previous_sft
 with GroundedBatches(DATA,TOK,sha(DATA/'schedule.json')) as b:
  physical,supervised=b.counts(len(b));updates=(len(b)+15)//16
 if physical!=prep['two_pass_physical_positions'] or physical>remaining:raise ValueError('Finite remaining SFT budget differs')
 source_state=json.loads(Path('data/english-balanced-experiment-v2/mlx/checkpoint/state.json').read_text());recipe=Recipe(**{**source_state['recipe'],'lr':.00003,'warmup_tokens':65536,'accumulation_steps':16})
 paths=[*DATA.rglob('*'),*QA.rglob('*'),*MODEL.rglob('*'),*TOK.rglob('*'),*Path('src/slm').rglob('*.py'),Path(__file__),Path('scripts/run-grounded-conversation-v1.py'),Path('configs/main-learning-budget-authorization-v2.json'),Path('configs/conversation-recovery-target-v1.json'),Path('configs/english-owner-cloud-hold-v1.json'),Path('configs/current-model-100-conversations-v1.json'),Path('data/english-recovery-corpus-v1/development.jsonl'),Path('data/english-balanced-experiment-v2/mlx-nll.json'),Path('reports/prior-conversation-protection-audit-v1.json')]
 p=dict(creator='Navneet Prabhakar',kind='local-grounded-conversation-run-v1',authorization='Owner requires continued local conversation training toward70–75%correctness; no GCP. New separately bounded source/recipe, not replay of rejected run.',data=str(DATA),schedule_sha256=sha(DATA/'schedule.json'),source_model=str(MODEL),source_model_sha256=sha(MODEL/'manifest.json'),tokenizer=str(TOK),optimizer_transition='Exact corrected90step FP32 model; fresh AdamW moments/counters explicitly declared, no resume claim. Failed SFT remains discarded and charged. Original numerical runtime/loss/embedding preserved.',recipe=asdict(recipe),planned_new_physical_positions=physical,planned_new_supervised_positions=supervised,maximum_new_optimizer_updates=updates,sealed_raw_priors=priors,maximum_remaining_sft_positions=remaining,planned_cumulative_recovery_physical_positions=1776439+physical,max_physical_passes_per_family=2,cloud_allowed=False,teacher_calls=0,maximum_wall_seconds=14400,maximum_generation_seconds_per_protocol=3600,heldout_references=str(QA/'development-references.jsonl'),retention_documents='data/english-recovery-corpus-v1/development.jsonl',retention_baseline='data/english-balanced-experiment-v2/mlx-nll.json',scheduled_check_updates=sorted({min(i,updates) for i in range(64,updates+64,64)}),maximum_source_retention_regression_nats=.1,generation_protocols={'grounded-100':str(QA/'development-100.json'),'regression-100':'configs/current-model-100-conversations-v1.json'},initial_grounded_capture_before_gradients=True,reserved_final_protocol=str(QA/'reserved-100.json'),reserved_final_execution_allowed=False,broad_correctness_target=.75,intermediate_qa_target_not_broad_acceptance=True,assessment='Actual separate student histories, all raw replies and direct semantic grading. SQuAD normalized exact-match/F1 auxiliary, never replaces task review or broad conversation score. Source grounding/privacy/license scope not independently certified.',inputs={str(p):sha(p) for p in paths if p.is_file()})
 PLAN.write_text(json.dumps(p,indent=2,sort_keys=True)+'\n');print('Frozen grounded plan',sha(PLAN),'bindings',len(p['inputs']),'positions',physical,'updates',updates)
if __name__=='__main__':main()

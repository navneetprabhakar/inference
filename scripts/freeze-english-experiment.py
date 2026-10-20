"""Freeze admitted language curriculum and finite paired learning protocol."""
# Creator: Navneet Prabhakar
from dataclasses import asdict
import json
from pathlib import Path
from slm.data.stream_hash import sha
from slm.data.english_foundation_adapter import build_curriculum
from slm.common.training import Recipe
from slm.data.schema import digest
from slm.data.english_corpus import save
ROOT=Path('data/english-recovery-experiment-v1');CORPUS=Path('data/english-recovery-corpus-v1');TOK=Path('data/iteration-two-foundation-tokenizers-v1/vocab-16384')
def main():
 if ROOT.exists():raise FileExistsError(ROOT)
 prep=json.loads((CORPUS/'preparation.json').read_text());policy=json.loads((CORPUS/'admission.json').read_text())
 if not prep['complete'] or not policy['training_approved']:raise ValueError('Complete exact finite admission and preparation required')
 for p,h in policy['inputs'].items():
  if sha(p)!=h:raise ValueError('Admitted source dependency changed')
 recipe=Recipe(lr=.0003,warmup_tokens=262144,eps=1e-6,loss_implementation='max-centered-target-tail-softplus-v1',embedding_implementation='dense-onehot-v1',accumulation_steps=8)
 ROOT.mkdir();components={s:str(CORPUS/s) for s in ['general','narrative']};mix=CORPUS/'language-mixture'
 language_total=prep['mixture']['planned_processed_positions']
 schedule=dict(lr=.0003,warmup_tokens=min(1000000,language_total//10),cooldown_tokens=min(8000000,language_total//5),final_lr_fraction=.1,accumulation_steps=8)
 curriculum=build_curriculum([dict(id='language',path=str(mix),components=components,dataset_hash=sha(mix/'manifest.json'),schedule=schedule)],TOK,ROOT/'curriculum',recipe=recipe,family_processed_cap=100000)
 base=json.loads(Path('configs/course-correction-v3.json').read_text())['checkpoint_registry']['language_phase_source']
 if sha(Path(base['model_path'])/'manifest.json')!=base['model_manifest_sha256']:raise ValueError('Own source foundation differs')
 p=dict(creator='Navneet Prabhakar',kind='finite-admitted-english-experiment-v1',source_model=base,tokenizer=str(TOK),corpus=str(CORPUS),recipe=asdict(recipe),curriculum_sha256=sha(ROOT/'curriculum/manifest.json'),curriculum_bindings=dict(language=dict(path=str(mix),components=components)),paired=dict(common_updates=32,continuation_updates=64,common_plus_each_arm_maximum_positions=786432,total_physical_positions=1310720,backend_order=['mlx_common','mlx_continuation','cuda_continuation'],minimum_document_nll_improvement=.02,maximum_mean_improvement_gap=.05,bootstrap_95_maximum_absolute_gap=.10),language=dict(maximum_positions=78000000,realized_positions=language_total,checkpoints=[5000000,10000000,20000000,40000000,language_total],minimum_nll_improvement=.1,maximum_slice_regression=.1,minimum_readable_topic_preserving_generations=70,stop_after_two_scheduled_slice_regressions=True,minimum_completion_remaining_vm_seconds=1800),evaluation=dict(dev_documents=500,prefixes=100,max_nll_positions_per_document=1024,max_generation_tokens=64,conversation_protocol='configs/current-model-100-conversations-v1.json',conversation_count=100,turns_per_conversation=3,assessment='Direct delegated expert, exact actual student history, task success first; no teacher answer substitution. Visible regression suite is not a new blind final test.'),budget='configs/main-learning-budget-authorization-v2.json',maximum_new_physical_positions=100000000,maximum_preliminary_positions=2000000,maximum_conditional_sft_positions=20000000,maximum_total_vm_hours=45,maximum_total_spend_usd=100,cloud_project='executespecv1',machine='g2-standard-4',gpu='NVIDIA L4',cloud_ready=False,training_readiness='Local paired initial execution allowed only after input hashes and focused tests pass; CUDA/language extension requires state/inference/useful-learning/resource gates. Never infer SFT admission.',initial_optimizer='Explicit fresh state for disjoint preliminary corpus; ordinary paired resumes preserve full state. Main-language transition after useful-portability comparison has an explicitly fresh optimizer/schedule on disjoint corpus.',original40Mcoverage_gate_passed=False,teacher_calls_authorized_by_this_experiment=0)
 p['inputs']={str(f):sha(f) for f in [CORPUS/'preparation.json',CORPUS/'admission.json',CORPUS/'development.jsonl',CORPUS/'generation-prefixes.json',CORPUS/'preliminary/manifest.json',ROOT/'curriculum/manifest.json','configs/english-recovery-execution-v1.json','configs/main-learning-budget-authorization-v2.json','src/slm/english_learning.py','src/slm/english_language_stage.py','scripts/run-english-learning.py','src/slm/data/english_corpus.py','src/slm/data/english_foundation_adapter.py',__file__,Path(base['model_path'])/'manifest.json',TOK/'manifest.json']}
 for f in ['src/slm/common/training.py','src/slm/common/curriculum.py','src/slm/common/checkpoint.py','src/slm/common/tokenizer.py','src/slm/backends/mlx_backend.py','src/slm/backends/torch_backend.py','src/slm/data/tokenized.py','src/slm/data/curriculum.py','src/slm/data/mixture.py','src/slm/eval/portability.py']:p['inputs'][f]=sha(f)
 save(ROOT/'plan.json',p);save('reports/english-experiment-freeze.json',dict(creator='Navneet Prabhakar',plan_sha256=sha(ROOT/'plan.json'),curriculum=curriculum,preliminary_physical_positions=1310720,maximum_all_new_positions=100000000,cloud_ready=False,student_learning_completed=False));print(json.dumps(dict(plan_sha256=sha(ROOT/'plan.json'),language_positions=language_total),indent=2))
if __name__=='__main__':main()

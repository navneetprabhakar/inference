"""Supplementary stable basic-fact check; primary provided-fact bank stays unchanged."""
import importlib.util,time,json,gc
from pathlib import Path
R=Path(__file__).resolve().parent;P=R.parents[1];V=R/'private'
spec=importlib.util.spec_from_file_location('fresh_knowledge_readonly',R/'run.py');r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
result=r.read(R/'result.json');assert not (R/'knowledge-result.json').exists()
r.started=r.read(R/'started.json')['epoch'];r.positions=result['inference_positions'];r.peak_rss=result['peak_rss_bytes']
r.save(R/'knowledge-freeze.json',dict(authority='User requested factual accuracy reassessment; supplemental basic world-knowledge check, separate from completed supplied-fact assessment.',scope='15 stable elementary facts per model, five three-turn conversations. No teacher, retrieval, training, selection or historical-clock changes.',bank_sha256=r.s.sha(V/'knowledge-bank.json'),script_sha256=r.s.sha(Path(__file__)),local_preparation_sha256=r.s.sha(V/'knowledge-prepare.py'),original_started_epoch=r.started,maximum_aggregate_positions=2000000,maximum_aggregate_wall_seconds=900,scoring='Manual semantic correctness for complete direct answers; word/digit equivalents accepted; unrelated extra factual claims rejected. Do not pool with provided-fact grounding totals.',limitations='Tiny primary-authored basic-fact check, not a representative knowledge benchmark. Added after primary supplied-fact review; separately frozen before supplementary inference.'))
from sentencepiece import SentencePieceProcessor
sp=SentencePieceProcessor(model_file=str(r.s.TOK));metrics={}
for name,config in r.read(R/'plan.json')['models'].items():
 r.frozen();r.s.SOURCE=P/config['path'];r.s.SOURCE_SHA=config['sha256'];e,c=r.s.load();metrics[name]=r.generate(e,c,r.read(V/'knowledge-bank.json'),sp,name+'-knowledge');assert e.local_step==0;del e,c;gc.collect()
r.frozen();r.save(R/'knowledge-result.json',dict(models=metrics,aggregate_inference_positions=r.positions,additional_positions=r.positions-result['inference_positions'],aggregate_elapsed_seconds=time.time()-r.started,peak_rss_bytes=r.peak_rss,training_updates=0,promoted=False,frozen_inputs_unchanged=True))
print(json.dumps(r.read(R/'knowledge-result.json'),indent=2))

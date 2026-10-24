"""Post-selection inference on previously exposed broader probes; no training or selection."""
import importlib.util,json,time,gc
from pathlib import Path
R=Path(__file__).resolve().parent;P=R.parents[1]
spec=importlib.util.spec_from_file_location('binding_secondary',R/'run.py');r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
result=r.read(R/'result.json');prior=P/'restart/short-answer-transfer-v1/private/test-encoded.json'
assert not (R/'secondary.json').exists(),'NO_AUTOMATIC_SECONDARY_RETRY'
r.started=r.read(R/'started.json')['epoch'];r.s.started=r.started;r.positions=result['total_positions'];r.updates_total=result['updates_consumed'];r.sft_total=result['sft_targets_consumed'];r.replay_total=result['replay_targets_consumed'];r.active_arm='read-only-broader-regression'
r.save(R/'secondary-freeze.json',dict(script_sha256=r.s.sha(Path(__file__)),bank=str(prior.relative_to(P)),bank_sha256=r.s.sha(prior),purpose='Read-only post-selection use of already-exposed prior probes; never a fresh independent test, never selects weights or thresholds.',maximum_additional_positions=1000000,maximum_wall_seconds=1800,original_started_epoch=r.started))
r.frozen();e,c=r.s.load()
import torch
state=torch.load(P/result['selected']['checkpoint'],map_location='cpu',weights_only=False)
e.params={new:e.mx.array(state['model'][old].numpy(),e.mx.float32) for old,new in c.mapping().items()};e.mx.eval(e.params);del state
from sentencepiece import SentencePieceProcessor
sp=SentencePieceProcessor(model_file=str(r.s.TOK));metrics=r.generate(e,c,r.read(prior),sp,'secondary-broader')
assert r.positions-result['total_positions']<=1000000
r.save(R/'secondary.json',dict(status='INFERENCE_ONLY_COMPLETE',metrics=metrics,additional_positions=r.positions-result['total_positions'],aggregate_positions=r.positions,aggregate_elapsed_seconds=time.time()-r.started,new_updates=0,checkpoint_selection_changed=False,source_unchanged=r.s.sha(r.s.SOURCE)==r.s.SOURCE_SHA,memory=e.memory()))
print(json.dumps(r.read(R/'secondary.json'),indent=2))

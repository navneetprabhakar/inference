"""CPU-only post-run verification and qualified timing projections."""
import json
import math
from pathlib import Path
import time
import psutil
import torch
from support import ROOT,CHECKPOINT,TARGETS,sha,mapping,window,save,Meter

report=json.loads((ROOT/'report.json').read_text())
confirmation=report['confirmation']
assert confirmation['status']=='COMPLETE'
assert report['full_training_authorized'] is False
assert report['original_checkpoint_sha256']=='53d17e68c90ecd57128975af93b5ff996a22c11640fa73c43a1ef37124e879ba'
meta=json.loads((ROOT/'confirmation/checkpoint.json').read_text())
assert sha(ROOT/'confirmation/checkpoint.pt')==meta['sha256']
state=torch.load(ROOT/'confirmation/checkpoint.pt',map_location='cpu',weights_only=False)
assert state['optimizer_step']==220+confirmation['completed_updates']
assert state['completed_targets']==state['optimizer_step']*TARGETS
assert state['scheduler']['step']==state['optimizer_step']
assert state['data_cursor']['completed_microbatches']==state['optimizer_step']*32
assert state['full_training_authorized'] is False and state['benchmark_branch'] is True
assert sum(state['model'][k].numel() for k in mapping())==15191712
assert torch.equal(state['model']['output.weight'],state['model']['tok_embeddings.weight'])
for value in state['model'].values():assert value.dtype==torch.float32 and torch.isfinite(value).all()
assert len(state['optimizer']['state'])==56
for item in state['optimizer']['state'].values():
    assert int(item['step'])==state['optimizer_step']
    for name in ['exp_avg','exp_avg_sq']:
        assert item[name].dtype==torch.float32 and torch.isfinite(item[name]).all()
assert 'mlx_rng_state' in state and 'torch_rng' in state and 'mps_rng' in state
for precision,expected in [('fp32','mlx.core.float32'),('bf16','mlx.core.bfloat16'),('fp16','mlx.core.float16')]:
    proof=json.loads((ROOT/'numerical-corrected'/(precision+'-dtype-proof.json')).read_text())
    for key in ['embedding','norm_output','matrix_weight','matrix_output','logits']:assert proof[key]==expected
    assert proof['master_weights']==proof['optimizer_moment']=='mlx.core.float32'
    assert report['numerical']['arms'][precision]['status']=='PASS'
for path,expected in json.loads((ROOT/'source-pins.json').read_text()).items():assert sha(path)==expected
jobs=json.loads((ROOT/'jobs.json').read_text());all_reaped=True
for job in jobs:
    supervision=json.loads((ROOT/(job['name']+'-supervisor.json')).read_text());assert supervision['worker_reaped']
    if psutil.pid_exists(job['pid']):assert abs(psutil.Process(job['pid']).create_time()-job['start_epoch'])>5
screens=[j for j in jobs if j['action']=='screen']
screen_seconds=sum(json.loads((ROOT/(j['name']+'-supervisor.json')).read_text())['elapsed_seconds'] for j in screens)
assert screen_seconds<=1800
for j in screens:
    assert json.loads((ROOT/(j['name']+'-supervisor.json')).read_text())['elapsed_seconds']<=300
bf16_seconds=sum(json.loads((ROOT/(j['name']+'-supervisor.json')).read_text())['elapsed_seconds'] for j in screens if j['name'] in ['mlx-bf16','mlx-bf16-corrected'])
assert bf16_seconds<=300
confirm_supervision=json.loads((ROOT/'confirmation-supervisor.json').read_text())
assert confirm_supervision['returncode']==0 and confirm_supervision['elapsed_seconds']<=3600
clock=json.loads((ROOT/'clock.json').read_text());elapsed=time.time()-clock['start_epoch']
assert elapsed<=10800 and Meter().total()<=300000000
original_baseline=json.loads((ROOT/'controller-started.json').read_text())['global_swap_baseline_bytes']
corrected_baseline=json.loads((ROOT/'corrective-controller-started.json').read_text())['global_swap_baseline_bytes']
assert original_baseline==corrected_baseline==report['resources']['swap_baseline_bytes']
data_receipt=json.loads((ROOT.parent/'mac15m-feasibility-v1/data-receipt.json').read_text())
for item in data_receipt['shards']:
    token_file=ROOT.parent/'mac15m-feasibility-v1/upstream/data/TinyStories_all_data'/(Path(item['shard']).stem+'.bin')
    assert sha(token_file)==item['token_sha256']
for earlier,later in zip(jobs,jobs[1:]):
    seconds=json.loads((ROOT/(earlier['name']+'-supervisor.json')).read_text())['elapsed_seconds']
    assert later['start_epoch']>=earlier['start_epoch']+seconds-.1
rows=[json.loads(s) for s in (ROOT/'confirmation/updates.jsonl').read_text().splitlines()]
last=rows[-1]['end'];r30=window(rows,last-1800,last);r10=window(rows,last-600,last)
assert abs(r30-confirmation['final_30_minute_tokens_per_second'])<1e-6
F=13107200000
projections=dict(allowance_factor=1.2,unchanged_full_recipe_targets=F,
    full_recipe_hours_from_final30=F/r30/3600*1.2,
    full_recipe_hours_from_final10=F/r10/3600*1.2,
    remaining_hours_from_original_checkpoint_if_approved=(F-220*TARGETS)/r30/3600*1.2,
    remaining_hours_from_benchmark_checkpoint_if_approved=(F-state['completed_targets'])/r30/3600*1.2,
    caveat='Observed-throughput projections. Battery/AC power changed during this benchmark; this is not a controlled constant-power backend comparison. No full training is authorized.')
report['final_10_minute_tokens_per_second']=r10
report['timing_validity']='MEASURED_WITH_BATTERY_TO_AC_VARIATION; NOT_A_CONTROLLED_CONSTANT_POWER_BACKEND_COMPARISON'
report['projections']=projections
report['material_gain_gate_observed_pass']=r30/7814.865715956613>=1.5
report['verification']='verification.json'
save(ROOT/'report.json',report)
verification=dict(status='PASS_CPU_ONLY_NO_MODEL_UPDATES',checkpoint_sha256=meta['sha256'],
    model_parameters=15191712,all_saved_model_and_optimizer_tensors_finite=True,
    all_saved_master_weights_and_moments_FP32=True,optimizer_states=56,
    optimizer_step=state['optimizer_step'],completed_targets=state['completed_targets'],
    source_pins_unchanged=True,original_checkpoint_unchanged=True,true16bit_compute_dtype_proofs_verified=True,
    all_GPU_workers_reaped=True,screening_seconds_including_discarded_partial=screen_seconds,
    logical_BF16_arm_seconds_including_discarded_partial=bf16_seconds,
    confirmation_supervised_seconds=confirm_supervision['elapsed_seconds'],total_elapsed_seconds=elapsed,
    original_swap_baseline_preserved=True,aggregate_reserved_positions=Meter().total(),
    all_50_token_shards_unchanged=True,serialized_GPU_job_execution_verified=True,
    power_condition_variation_disclosed=True,full_training_authorized=False)
save(ROOT/'verification.json',verification)
print(json.dumps(dict(sustained30=r30,sustained10=r10,projections=projections,verification=verification),indent=2))

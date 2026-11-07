"""Metadata-only benchmark spec preparation. No checkpoint/model loads or launch."""
import hashlib,json,sys,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import mlx_full_benchmark_control as c
OUT=Path(__file__).resolve().parent

def read(p):return json.loads(Path(p).read_text())
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
 foundation=read(ROOT/'reports/base-foundation-100m/budget.json');supervisor=read(ROOT/'runs/optimizer-ablation-v1/supervisor.json');c.require(supervisor['state']=='completed','expected queue endpoint required')
 source={k:foundation[k]for k in ('corpus','manifest_sha256','validation_blocks_sha256','diagnostics','diagnostics_sha256')};source.update(parent=supervisor['parent'],source_offset=99999744)
 corpus=Path(source['corpus']);manifest=read(corpus/'manifest.json');blocks=read(corpus/'validation-blocks.json');offsets=[b['start']for b in blocks if b['max_length']>=513][:2];c.require(len(offsets)==2,'two predetermined validation windows')
 data=dict(train_path=str(corpus/'fineweb-train.u16'),train_sha256=manifest['shards']['fineweb-train']['sha256'],validation_path=str(corpus/'fineweb-validation.u16'),validation_sha256=manifest['shards']['fineweb-validation']['sha256'],source_offset=99999744,slice_targets=16777216,validation_offsets=offsets)
 for k in ('train_path','validation_path'):c.require(Path(data[k]).is_file(),'explicit shard path exists')
 python={k:str(ROOT/v/'bin/python')for k,v in [('torch','.venv'),('mlx','.venv-mlx-own-base')]}
 versions={k:json.loads(subprocess.check_output([v,'-c','import importlib.metadata as m,json,sys; print(json.dumps({"python":sys.version,"'+k+'":m.version("'+k+'"),"numpy":m.version("numpy")}))'],text=True))for k,v in python.items()}
 files=['mlx_full_benchmark_control.py','verify_mlx_full_benchmark_control.py','mlx_full_benchmark_worker.py','verify_mlx_full_benchmark_worker.py','mlx_own_base_adapter.py','mlx_own_base_source.py','verify_mlx_own_base_adapter.py','mlx_train_core.py','own_base_neutral_state.py','own_base_dev_run.py','optimizer_ablation_train.py','gpt2.py','train.py','tokenizer.py','guards.py','base_run_control.py','base_train.py','checkpoint.py','pretrain.py','pretrained_base.py','reports/mlx-own-base-full-benchmark/PROTOCOL.md','reports/mlx-own-base-full-benchmark/CONTROLLER-NOTES.md','reports/mlx-own-base-full-benchmark/prepare_spec.py']
 run=ROOT/'runs/own-base-mlx-full-benchmark-01';phases=c.expected_phase_plan()
 spec=dict(schema=1,state='pending_root_review',run=str(run),worker='mlx_full_benchmark_worker.py',python=python,versions=versions,source_spec=source,data=data,configuration=dict(microbatch=2,length=512,accumulation=8,lr=6e-5),slice_targets=16777216,targets_per_update=8192,period_limits=c.PERIOD_LIMITS,limits=dict(active_seconds=10800,calendar_seconds=21600,attempted_targets=c.TOKEN_LIMIT,output_bytes=c.OUTPUT_LIMIT,free_disk_bytes=c.DISK_FLOOR,rss_bytes=18*1024**3,swap_growth_bytes=1024**3,gpu_active_bytes=12*1024**3,telemetry_seconds=30,max_retries=0),driver_telemetry_policy='MLX0.32.4 null with reason; mandatory active/cache/peak and OS guards',phases=phases,frozen_phase_plan=phases,stop_paths=[str(ROOT/'runs/STOP'),str(run/'STOP'),str(ROOT/'runs/own-base-foundation-01/STOP')]+[str(ROOT/f'runs/optimizer-ablation-v1-{x}/STOP')for x in ('preserve-095','reset-095','reset-scaled')],code_sha256={n:digest(ROOT/n)for n in files},tolerances=dict(causal_prefix_max=1e-6,loss_abs=1e-4,logit_rms=1e-4,logit_max=1e-3,gradient_relative_l2=1e-3,gradient_max=1e-4,norm_relative=1e-3,weight_max=5e-5,update_delta_relative=0.02,moment_max=1e-5,resume_exact=True))
 spec['terminal_supervisors']={name:dict(path=str(ROOT/relative),sha256=digest(ROOT/relative))for name,relative in [('foundation','runs/own-base-foundation-01-supervisor.json'),('optimizer','runs/optimizer-ablation-v1/supervisor.json')]}
 for receipt in spec['terminal_supervisors'].values():
  terminal=read(receipt['path']);c.require(terminal['state']=='completed' and terminal.get('worker_exit_code')==0,'successful terminal supervisor required')
 spec['benchmark_identity']=dict(name='own124m-fp32-feasibility-v1',source=source['parent'],source_offset=99999744,configuration=spec['configuration'],tokenizer=manifest['tokenizer'],versions=versions)
 path=OUT/'activation-draft.json';c.require(not path.exists(),'refuse overwriting draft');path.write_text(json.dumps(spec,indent=2)+'\n');print(dict(path=str(path),sha256=digest(path),phases=len(phases),state='pending_root_review'))
if __name__=='__main__':main()

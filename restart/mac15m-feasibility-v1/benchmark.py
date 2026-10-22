"""One bounded MPS feasibility run. There is deliberately no full-training mode.

The unchanged pinned upstream model, tokenizer, dataset and AdamW factory are
used. This harness adds a one-hour boundary, telemetry and complete checkpoints.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import signal
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
UPSTREAM = ROOT/'upstream'
RUN = ROOT/'run'
CAP = 3600
TOKENS_PER_UPDATE = 131072
FULL_TOKENS = 13107200000
GIB = 1024**3

def save(path, value):
    tmp = path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value, indent=2)+'\n')
    tmp.replace(path)

def append(path, value):
    with path.open('a') as out:
        out.write(json.dumps(value)+'\n'); out.flush()

def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def rate_at(step):
    if step < 1000: return 0.0005*step/1000
    return 0.0005*0.5*(1+math.cos(math.pi*(step-1000)/(100000-1000)))

def swap_bytes():
    value = subprocess.check_output(['/usr/sbin/sysctl','vm.swapusage'], text=True)
    match = re.search(r'used =\s*([\d.]+)([MG])', value)
    if not match: raise RuntimeError('Cannot read swap telemetry')
    return float(match[1])*(1024**2 if match[2]=='M' else GIB)

def window_rate(rows, start, end):
    """Prorate only the boundary-crossing update; denominator includes pauses."""
    if end <= start: return None
    tokens = sum(r['targets']*max(0,min(end,r['end'])-max(start,r['start']))/(r['end']-r['start']) for r in rows)
    return tokens/(end-start)

def launch():
    import psutil
    prepared = json.loads((ROOT/'data-receipt.json').read_text())
    if prepared['status'] != 'PREPARED_NO_TRAINING': raise RuntimeError('Data not prepared')
    if RUN.exists(): raise FileExistsError('One approved feasibility attempt only')
    RUN.mkdir()
    sources = [ROOT/'benchmark.py', *(UPSTREAM/name for name in ['model.py','tinystories.py','tokenizer.py','tokenizer.model'])]
    pins = {str(p):digest(p) for p in sources}
    save(RUN/'source-pins.json',pins)
    contract = dict(scope='Preparation plus one-hour MPS feasibility only', full_training_authorized=False,
                    seconds_cap=CAP, maximum_updates=100000, seed=1337,
                    parameters=15191712, microbatch=16, accumulation=32, context=256,
                    targets_per_update=TOKENS_PER_UPDATE, full_recipe_targets=FULL_TOKENS,
                    projected_overhead_factor=1.2, sustained_gate_tokens_per_second=14000,
                    process_rss_cap_bytes=12*GIB, mps_driver_cap_bytes=12*GIB,
                    free_disk_floor_bytes=60*GIB, additional_swap_cap_bytes=512*1024**2,
                    no_cpu_operator_fallback=True, no_full_training_mode=True,
                    data_receipt_sha256=digest(ROOT/'data-receipt.json'))
    save(RUN/'contract.json',contract)
    baseline = swap_bytes()
    save(RUN/'host.json',dict(platform=platform.platform(), swap_baseline_bytes=baseline,
                             physical_memory_bytes=psutil.virtual_memory().total,
                             started_epoch=time.time()))
    env = dict(os.environ, PYTORCH_ENABLE_MPS_FALLBACK='0', TOKENIZERS_PARALLELISM='false',
               OMP_NUM_THREADS='4', MKL_NUM_THREADS='4', PYTHONUNBUFFERED='1')
    started = time.monotonic(); deadline = started+CAP
    log = (RUN/'worker.log').open('x')
    child = subprocess.Popen([sys.executable,str(ROOT/'benchmark.py'),'worker'],cwd=UPSTREAM,
                             env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    save(RUN/'worker-identity.json',dict(pid=child.pid, parent_pid=os.getpid(), started_epoch=time.time()))
    stop = None; peak_rss = 0; peak_swap_growth = 0; deadline_notified = False
    critical_since = None; last_thermal = None
    try:
        while child.poll() is None:
            now = time.monotonic()
            try:
                rss = psutil.Process(child.pid).memory_info().rss
            except psutil.NoSuchProcess: break
            swap = swap_bytes(); free = psutil.disk_usage(ROOT).free
            peak_rss=max(peak_rss,rss); peak_swap_growth=max(peak_swap_growth,swap-baseline)
            if last_thermal is None or now-last_thermal>30:
                therm=subprocess.check_output(['/usr/bin/pmset','-g','therm'],text=True,stderr=subprocess.STDOUT)
                append(RUN/'thermal.jsonl',dict(elapsed=now-started,raw=therm))
                critical=bool(re.search(r'Thermal_Level\s*=\s*(?:[2-9]|[1-9][0-9]+)',therm))
                critical_since=(critical_since or now) if critical else None
                last_thermal=now
            append(RUN/'resources.jsonl',dict(elapsed=now-started,rss_bytes=rss,
                    swap_used_bytes=swap,swap_growth_bytes=swap-baseline,free_disk_bytes=free))
            if rss>12*GIB: stop='RSS_CAP'
            elif free<60*GIB: stop='DISK_RESERVE'
            elif swap-baseline>512*1024**2: stop='SWAP_GROWTH_CAP'
            elif critical_since and now-critical_since>=60: stop='SUSTAINED_THERMAL_PRESSURE'
            if stop:
                save(RUN/'stop-request.json',dict(reason=stop,elapsed=now-started))
            if now>=deadline-20 and not deadline_notified:
                save(RUN/'stop-request.json',dict(reason='ONE_HOUR_BOUNDARY',elapsed=now-started))
                deadline_notified=True
            if now>=deadline:
                stop=stop or 'ONE_HOUR_EXTERNAL_DEADLINE'
                os.killpg(child.pid,signal.SIGTERM)
                try: child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid,signal.SIGKILL); child.wait()
                break
            time.sleep(min(5,max(.1,deadline-now)))
    finally:
        if child.poll() is None:
            os.killpg(child.pid,signal.SIGTERM)
            try: child.wait(timeout=5)
            except subprocess.TimeoutExpired: os.killpg(child.pid,signal.SIGKILL); child.wait()
        log.close()
        save(RUN/'supervisor.json',dict(status='STOPPED_FULL_RUN_PAUSED',worker_returncode=child.returncode,
             reason=stop,elapsed_seconds=time.monotonic()-started,peak_process_rss_bytes=peak_rss,
             maximum_additional_global_swap_bytes=peak_swap_growth,worker_reaped=True))
    summarize()

def worker():
    import numpy as np
    import torch
    sys.path.insert(0,str(UPSTREAM))
    from model import Transformer,ModelArgs
    from tinystories import Task
    for name,h in json.loads((RUN/'source-pins.json').read_text()).items():
        if digest(Path(name)) != h: raise RuntimeError('Source pin changed')
    contract=json.loads((RUN/'contract.json').read_text())
    if contract['full_training_authorized'] or contract['seconds_cap']!=CAP:
        raise RuntimeError('Only one-hour feasibility authorized')
    with (RUN/'worker-started.json').open('x') as f:
        json.dump(dict(pid=os.getpid(),started_epoch=time.time()),f)
    started=time.monotonic(); deadline=started+CAP
    def elapsed():return time.monotonic()-started
    def check():
        if (RUN/'stop-request.json').exists():raise InterruptedError(json.loads((RUN/'stop-request.json').read_text())['reason'])
        if time.monotonic()>=deadline-20:raise InterruptedError('ONE_HOUR_BOUNDARY')
    if not torch.backends.mps.is_available():raise RuntimeError('MPS unavailable; no fallback')
    torch.set_num_threads(4); torch.manual_seed(1337); torch.mps.manual_seed(1337)
    args=ModelArgs(dim=288,n_layers=6,n_heads=6,n_kv_heads=6,vocab_size=32000,
                   multiple_of=32,max_seq_len=256,dropout=0.0)
    model=Transformer(args).to(device='mps',dtype=torch.float32)
    count=sum(p.numel() for p in model.parameters())
    if count!=15191712:raise RuntimeError('Unexpected parameter count')
    optimizer=model.configure_optimizers(.1,.0005,(.9,.95),'mps')
    save(RUN/'model-config.json',dict(**vars(args),parameters=count,dtype='float32',device='mps',torch_version=torch.__version__))
    step=0; tokens=0; batches=0; reserved_tokens=0; durations=[]; latest_checkpoint=0
    peak_driver=0; peak_allocated=0
    def mem():
        nonlocal peak_driver,peak_allocated
        allocated=torch.mps.current_allocated_memory();driver=torch.mps.driver_allocated_memory()
        peak_allocated=max(peak_allocated,allocated);peak_driver=max(peak_driver,driver)
        if driver>12*GIB:raise RuntimeError('MPS_DRIVER_MEMORY_CAP')
        return dict(mps_allocated_bytes=allocated,mps_driver_bytes=driver)
    def cpu_tree(value):
        if isinstance(value,torch.Tensor):return value.detach().cpu()
        if isinstance(value,dict):return {k:cpu_tree(v) for k,v in value.items()}
        if isinstance(value,list):return [cpu_tree(v) for v in value]
        if isinstance(value,tuple):return tuple(cpu_tree(v) for v in value)
        return value
    def checkpoint():
        nonlocal latest_checkpoint
        torch.mps.synchronize()
        state=dict(model=cpu_tree(model.state_dict()),optimizer=cpu_tree(optimizer.state_dict()),
                   model_args=vars(args),optimizer_step=step,completed_targets=tokens,reserved_targets=reserved_tokens,
                   scheduler=dict(step=step,full_max_updates=100000,warmup=1000,peak_lr=.0005),
                   torch_rng=torch.get_rng_state(),mps_rng=torch.mps.get_rng_state(),numpy_rng=np.random.get_state(),
                   data_cursor=dict(completed_microbatches=batches,num_workers=0,upstream_seed=42,
                                    recovery='Recreate unchanged upstream stream; skip completed microbatches before restoring RNG. No skipped batch receives an optimizer update.'),
                   contract_sha256=digest(RUN/'contract.json'),sources_sha256=digest(RUN/'source-pins.json'),
                   data_receipt_sha256=digest(ROOT/'data-receipt.json'),full_training_authorized=False)
        temp=RUN/'checkpoint.tmp.pt';torch.save(state,temp);temp.replace(RUN/'checkpoint.pt')
        save(RUN/'checkpoint.json',dict(step=step,completed_targets=tokens,reserved_targets=reserved_tokens,
             sha256=digest(RUN/'checkpoint.pt'),elapsed_seconds=elapsed(),full_training_paused=True))
        latest_checkpoint=time.monotonic()
    def validation(n):
        model.eval();vals=[]
        iterator=Task.iter_batches(batch_size=16,device='mps',num_workers=0,split='val',max_seq_len=256,vocab_size=32000,vocab_source='llama2')
        with torch.no_grad():
            for _ in range(n):
                check();x,y=next(iterator);model(x,y);vals.append(float(model.last_loss));mem()
        torch.mps.synchronize();model.train()
        return dict(nll=statistics.mean(vals),targets=n*16*256,batches=n)
    stop='ONE_HOUR_BOUNDARY';valid_initial=None;valid_final=None
    try:
        checkpoint()
        valid_initial=validation(10);save(RUN/'initial-validation.json',valid_initial)
        stream=Task.iter_batches(batch_size=16,device='mps',num_workers=0,split='train',max_seq_len=256,vocab_size=32000,vocab_source='llama2')
        model.train();last_progress=0
        while step<100000:
            check()
            expected=statistics.median(durations[-5:]) if durations else 120
            if time.monotonic()+max(40,expected*1.5)+20>=deadline:break
            rate=rate_at(step)
            for group in optimizer.param_groups:group['lr']=rate
            optimizer.zero_grad(set_to_none=True)
            begin=elapsed();loss_sum=0.0
            reserved_tokens+=TOKENS_PER_UPDATE
            append(RUN/'reservations.jsonl',dict(step=step+1,targets=TOKENS_PER_UPDATE,elapsed=begin))
            for micro in range(32):
                check();x,y=next(stream);model(x,y)
                loss=model.last_loss/32
                loss_sum+=float(loss.detach())
                if not math.isfinite(loss_sum):raise RuntimeError('NONFINITE_LOSS')
                loss.backward();mem()
            norm=float(torch.nn.utils.clip_grad_norm_(model.parameters(),1.0))
            if not math.isfinite(norm):raise RuntimeError('NONFINITE_GRADIENT')
            optimizer.step();torch.mps.synchronize()
            step+=1;tokens+=TOKENS_PER_UPDATE;batches+=32
            end=elapsed();durations.append(end-begin)
            row=dict(step=step,targets=TOKENS_PER_UPDATE,total_targets=tokens,start=begin,end=end,
                     seconds=end-begin,tokens_per_second=TOKENS_PER_UPDATE/(end-begin),loss=loss_sum,
                     gradient_norm=norm,learning_rate=rate,**mem())
            append(RUN/'updates.jsonl',row)
            save(RUN/'progress.json',row)
            print(json.dumps(row),flush=True)
            if time.monotonic()-latest_checkpoint>=600:checkpoint()
        if time.monotonic()<deadline-60 and not (RUN/'stop-request.json').exists():
            valid_final=validation(10);save(RUN/'final-validation.json',valid_final)
    except InterruptedError as e:stop=str(e)
    except BaseException as e:
        stop=type(e).__name__+': '+str(e)
        print(stop,flush=True)
        raise
    finally:
        optimizer.zero_grad(set_to_none=True)
        # An interrupted microbatch accumulation never changes model parameters.
        # Preserve its charged reservation and only the last committed data cursor.
        checkpoint()
        save(RUN/'worker-result.json',dict(status='FEASIBILITY_STOPPED_FULL_TRAINING_PAUSED',reason=stop,
             completed_updates=step,completed_targets=tokens,reserved_targets=reserved_tokens,
             elapsed_seconds=elapsed(),peak_mps_driver_bytes=peak_driver,peak_mps_allocated_bytes=peak_allocated,
             initial_validation=valid_initial,final_validation=valid_final,full_training_authorized=False))

def summarize():
    rows=[json.loads(s) for s in (RUN/'updates.jsonl').read_text().splitlines()] if (RUN/'updates.jsonl').exists() else []
    supervisor=json.loads((RUN/'supervisor.json').read_text())
    result=json.loads((RUN/'worker-result.json').read_text()) if (RUN/'worker-result.json').exists() else {}
    end=rows[-1]['end'] if rows else 0
    trailing=window_rate(rows,end-1800,end) if end>=1800 else None
    first=window_rate(rows,rows[0]['start'],rows[0]['start']+1800) if rows and end-rows[0]['start']>=1800 else None
    seconds=sum(r['seconds'] for r in rows)
    avg=sum(r['targets'] for r in rows)/seconds if seconds else None
    gate=trailing is not None and trailing>=14000 and supervisor['worker_returncode']==0 and supervisor['reason'] is None
    report=dict(status='FEASIBILITY_COMPLETE_FULL_TRAINING_PAUSED' if supervisor['worker_returncode']==0 else 'FEASIBILITY_STOPPED_FULL_TRAINING_PAUSED',
        full_training_authorized=False,full_training_started=False,
        model_parameters=15191712,completed_updates=len(rows),completed_training_targets=sum(r['targets'] for r in rows),
        full_recipe_targets=FULL_TOKENS,first_30_minute_tokens_per_second=first,
        final_30_minute_tokens_per_second=trailing,overall_training_tokens_per_second=avg,
        throughput_method='Final1800 wall seconds ending at last committed update; boundary update prorated by elapsed overlap. Includes intervening checkpoint pauses; training positions only.',
        sustained_gate_tokens_per_second=14000,throughput_and_resource_gate_pass=gate,
        projected_full_run_hours_with_20_percent_overhead=FULL_TOKENS/trailing/3600*1.2 if trailing else None,
        projected_remaining_hours_with_20_percent_overhead=(FULL_TOKENS-sum(r['targets'] for r in rows))/trailing/3600*1.2 if trailing else None,
        projection_caveat='Projection, not measured completion time. Sustained cooling, OS workload and later evaluations can change runtime.',
        memory=dict(peak_process_rss_bytes=supervisor['peak_process_rss_bytes'],
                    peak_mps_driver_bytes=result.get('peak_mps_driver_bytes'),peak_mps_allocated_bytes=result.get('peak_mps_allocated_bytes'),
                    additional_global_swap_bytes=supervisor['maximum_additional_global_swap_bytes'],
                    unified_memory_note='RSS and MPS allocations overlap in unified memory; do not add these peaks.'),
        supervisor=supervisor,worker=result)
    save(ROOT/'report.json',report);print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['launch','worker','summarize'])
    action=parser.parse_args().action
    {'launch':launch,'worker':worker,'summarize':summarize}[action]()

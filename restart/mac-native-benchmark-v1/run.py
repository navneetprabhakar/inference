"""Approved three-hour benchmark controller; deliberately no full-training mode."""
import argparse
import concurrent.futures
import datetime
import gc
import json
import math
import os
from pathlib import Path
import re
import signal
import statistics
import subprocess
import sys
import time
import traceback
import numpy as np
from support import ROOT,PROJECT,REFERENCE,CHECKPOINT,UPSTREAM,TARGETS,GIB,Stream,Meter,save,append,sha,window,mapping

def swap():
    s=subprocess.check_output(['/usr/sbin/sysctl','vm.swapusage'],text=True)
    m=re.search(r'used =\s*([\d.]+)([MG])',s)
    if not m:raise RuntimeError('SWAP_TELEMETRY_UNAVAILABLE')
    return float(m[1])*(1024**2 if m[2]=='M' else GIB)

def make_engine(kind,micro):
    from engines import TorchEngine,MLXEngine
    return TorchEngine(micro) if kind=='mps' else MLXEngine(kind,micro)

def release(engine):
    del engine;gc.collect()
    import torch
    torch.mps.empty_cache()
    import mlx.core as mx
    mx.clear_cache()

def numerical(out,deadline):
    meter=Meter()
    def check():
        if (ROOT/'global-stop.json').exists():raise RuntimeError('GLOBAL_STOP')
        if time.time()>=deadline-10:raise TimeoutError('PREPARATION_DEADLINE')
    def val(engine):
        check();meter.reserve(4096,'numerical-validation');return engine.validation(validation)
    fixture=Stream(skip_sequences=112640).batch(2)
    validation=Stream(split='val').batch(16)
    def grads(engine):
        check();meter.reserve(512,'numerical-gradient');return engine.gradient(fixture)
    reference=make_engine('mps',16)
    refweights=reference.weights();refloss,refgrad=grads(reference)
    reference.apply_gradients(refgrad);after=reference.weights()
    delta={k:after[k]-refweights[k] for k in after}
    np.savez(out/'reference-gradients.npz',**refgrad)
    refmeta=dict(loss=refloss,gradient_norm=math.sqrt(sum(float(np.square(x.astype(np.float64)).sum()) for x in refgrad.values())))
    del reference;gc.collect();release(None)
    reference=make_engine('mps',16);stream=Stream(skip_sequences=112640)
    initialval=val(reference)
    for step in range(10):
        check();a=stream.batch(512);meter.reserve(TARGETS,'numerical-mps-fixed-work');loss,norm=reference.update(a,check)
        append(out/'reference-updates.jsonl',dict(step=step+1,loss=loss,gradient_norm=norm))
    finalval=val(reference)
    refmeta.update(initial_validation_nll=initialval,after_10_updates_validation_nll=finalval)
    save(out/'reference.json',refmeta)
    del reference;gc.collect();release(None)
    results={};fp32_pass=False
    for kind in ['fp32','bf16','fp16']:
        check();engine=None
        try:
            if kind!='fp32' and not fp32_pass:
                results[kind]=dict(status='INELIGIBLE_REFERENCE_MLX_FP32_FAILED');continue
            engine=make_engine(kind,16);save(out/(kind+'-dtype-proof.json'),engine.dtype_proof);value,gradient=grads(engine)
            numerator=sum(float(np.square((gradient[k]-refgrad[k]).astype(np.float64)).sum()) for k in gradient)
            denominator=sum(float(np.square(refgrad[k].astype(np.float64)).sum()) for k in gradient)
            dot=sum(float((gradient[k].astype(np.float64)*refgrad[k]).sum()) for k in gradient)
            gg=sum(float(np.square(gradient[k].astype(np.float64)).sum()) for k in gradient)
            cosine=dot/math.sqrt(max(gg*denominator,1e-30));relative=math.sqrt(numerator/max(denominator,1e-30))
            finite=all(np.isfinite(v).all() for v in gradient.values())
            result=dict(loss=value,absolute_loss_difference=abs(value-refloss),gradient_relative_L2_error=relative,
                        gradient_cosine=cosine,all_gradient_tensors_finite=finite,loss_scale=engine.scale)
            if not finite:raise ValueError('NONFINITE_GRADIENT')
            if kind=='fp32':
                engine.apply_gradients(gradient);candidate=engine.weights()
                de=sum(float(np.square(((candidate[k]-refweights[k])-delta[k]).astype(np.float64)).sum()) for k in candidate)
                dn=sum(float(np.square(v.astype(np.float64)).sum()) for v in delta.values())
                result['one_update_delta_relative_L2_error']=math.sqrt(de/max(dn,1e-30))
                passed=result['absolute_loss_difference']<=.0001 and relative<=.001 and result['one_update_delta_relative_L2_error']<=.001
            else:passed=result['absolute_loss_difference']<=.02 and cosine>=.99
            del engine;engine=None;gc.collect();release(None)
            if passed:
                engine=make_engine(kind,16);stream=Stream(skip_sequences=112640)
                for step in range(10):
                    check();a=stream.batch(512);meter.reserve(TARGETS,'numerical-'+kind+'-fixed-work');loss,norm=engine.update(a,check)
                    append(out/(kind+'-updates.jsonl'),dict(step=step+1,loss=loss,gradient_norm=norm))
                validation_nll=val(engine)
                result['after_10_updates_validation_nll']=validation_nll
                result['after_10_updates_validation_difference']=abs(validation_nll-finalval)
                if kind!='fp32':passed=passed and abs(validation_nll-finalval)<=.05
                weights=engine.weights();passed=passed and all(np.isfinite(v).all() for v in weights.values())
            result['status']='PASS' if passed else 'REJECTED_NUMERICAL_TOLERANCE'
            results[kind]=result
            if kind=='fp32':fp32_pass=passed
            save(out/'acceptance-progress.json',results)
        except BaseException as e:
            if any(s in str(e) for s in ['GPU_MEMORY_CAP','AGGREGATE_POSITION_CAP','GLOBAL_STOP','PREPARATION_DEADLINE']):raise
            results[kind]=dict(status='REJECTED_IMPLEMENTATION_OR_NUMERICAL_ERROR',error=type(e).__name__+': '+str(e),traceback=traceback.format_exc())
            save(out/'acceptance-progress.json',results)
        finally:
            if engine is not None:del engine
            gc.collect();release(None)
    save(out/'result.json',dict(status='NUMERICAL_COMPLETE',reference=refmeta,arms=results,charged_positions=meter.total()))

def training(out,kind,micro,deadline,confirm):
    import torch
    started=time.monotonic();start_epoch=time.time();meter=Meter()
    def elapsed():return time.monotonic()-started
    def check():
        if (ROOT/'global-stop.json').exists():raise RuntimeError('GLOBAL_STOP')
        if time.time()>=deadline-10:raise InterruptedError('PHASE_TIME_BOUNDARY')
    engine=make_engine(kind,micro)
    if hasattr(engine,'dtype_proof'):save(out/'dtype-proof.json',engine.dtype_proof)
    if engine.origin['optimizer_step']!=220:raise ValueError('Unexpected benchmark origin')
    setup_seconds=elapsed();stream=Stream(skip_sequences=112640)
    rows=[];durations=[];last_checkpoint=time.monotonic();last_memory=None
    checkpoint_metadata=None;equal_work_check=None
    def checkpoint():
        nonlocal last_checkpoint,checkpoint_metadata
        state=engine.checkpoint();step=engine.base_step+engine.local_step
        state.update(optimizer_step=step,completed_targets=engine.origin['completed_targets']+len(rows)*TARGETS,
                     reserved_targets=engine.origin['completed_targets']+len(rows)*TARGETS,
                     benchmark_branch=True,full_training_authorized=False,
                     scheduler=dict(step=step,full_max_updates=100000,warmup=1000,peak_lr=.0005),
                     data_cursor=dict(completed_microbatches=7040+len(rows)*32,num_workers=0,upstream_seed=42,
                     recovery='Recreate immutable upstream sequence order and skip completed_microbatches*16 sequences.'),
                     benchmark_origin_sha256=sha(CHECKPOINT),benchmark_kind=kind,microbatch=micro,
                     benchmark_source_pins_sha256=sha(ROOT/'source-pins.json'))
        tmp=out/'checkpoint.tmp.pt';torch.save(state,tmp);tmp.replace(out/'checkpoint.pt')
        checkpoint_metadata=dict(sha256=sha(out/'checkpoint.pt'),step=step,targets=state['completed_targets'],elapsed=elapsed())
        save(out/'checkpoint.json',checkpoint_metadata);last_checkpoint=time.monotonic()
    status='COMPLETE';reason='PHASE_TIME_BOUNDARY'
    pool=concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future=pool.submit(stream.batch,512)
    try:
        while True:
            check()
            expected=statistics.median(durations[-5:]) if durations else 45
            if time.time()+max(15,expected*1.5)+15>=deadline:break
            begin=elapsed();a=future.result();future=pool.submit(stream.batch,512)
            meter.reserve(TARGETS,('confirmation-' if confirm else 'screen-')+kind+'-'+str(micro))
            loss,norm=engine.update(a,check);engine.sync();end=elapsed();last_memory=engine.memory()
            row=dict(update=len(rows)+1,targets=TARGETS,start=begin,end=end,seconds=end-begin,
                     tokens_per_second=TARGETS/(end-begin),loss=loss,gradient_norm=norm,**last_memory)
            rows.append(row);durations.append(end-begin);append(out/'updates.jsonl',row);save(out/'progress.json',row)
            print(json.dumps(row),flush=True)
            if len(rows)==10:
                meter.reserve(4096,'screen-equal-work-validation-'+kind+'-'+str(micro))
                observed=engine.validation(Stream(split='val').batch(16))
                reference_dir=ROOT/('numerical-corrected' if (ROOT/'precision-correction.json').exists() else 'numerical')
                expected_nll=json.loads((reference_dir/'reference.json').read_text())['after_10_updates_validation_nll']
                equal_work_check=dict(validation_nll=observed,reference_nll=expected_nll,absolute_difference=abs(observed-expected_nll))
                save(out/'equal-work-validation.json',equal_work_check)
                if not math.isfinite(observed) or abs(observed-expected_nll)>.05:
                    status='REJECTED_NUMERICAL_TOLERANCE';reason='Equal-work validation difference exceeds0.05';break
            if confirm and time.monotonic()-last_checkpoint>=600:checkpoint()
    except InterruptedError as e:reason=str(e)
    except BaseException as e:
        status='STOPPED';reason=type(e).__name__+': '+str(e);raise
    finally:
        pool.shutdown(wait=True,cancel_futures=True)
        if confirm and status=='COMPLETE':checkpoint()
        last=rows[-1]['end'] if rows else 0
        start=rows[0]['start'] if rows else 0
        total=sum(r['targets'] for r in rows)
        measured=window(rows,start,last) if last>start else None
        sustained=window(rows,last-1800,last) if last-start>=1800 else None
        first=window(rows,start,start+1800) if last-start>=1800 else None
        # Screening excludes only the first compiled update; confirmation reports wall-clock windows.
        warm=rows[1:] if len(rows)>1 else rows
        screen_rate=sum(r['targets'] for r in warm)/(warm[-1]['end']-warm[0]['start']) if warm else None
        save(out/'result.json',dict(status=status,reason=reason,kind=kind,microbatch=micro,accumulation=512//micro,
            completed_updates=len(rows),completed_positions=total,elapsed_seconds=elapsed(),setup_seconds=setup_seconds,
            first_update_including_compilation_seconds=rows[0]['seconds'] if rows else None,
            screening_training_tokens_per_second=screen_rate,wall_training_tokens_per_second=measured,
            first_30_minute_tokens_per_second=first,final_30_minute_tokens_per_second=sustained,
            observed_peak_GPU_bytes=max((r['peak_active_or_driver_bytes'] for r in rows),default=0),
            final_memory=last_memory,checkpoint=checkpoint_metadata,full_training_authorized=False))

def worker(args):
    out=ROOT/args.name
    if out.exists():raise FileExistsError('One execution per frozen arm name')
    out.mkdir()
    save(out/'started.json',dict(pid=os.getpid(),started_epoch=time.time(),kind=args.kind,deadline=args.deadline))
    try:
        for name,h in json.loads((ROOT/'source-pins.json').read_text()).items():
            if sha(name)!=h:raise RuntimeError('Frozen implementation changed')
        if args.action=='numeric':numerical(out,args.deadline)
        else:training(out,args.kind,args.micro,args.deadline,args.action=='confirm')
    except BaseException as e:
        save(out/'failure.json',dict(error=type(e).__name__+': '+str(e),traceback=traceback.format_exc()))
        raise

def controller(resume=False):
    import psutil
    clock=json.loads((ROOT/'clock.json').read_text());contract=json.loads((ROOT/'contract.json').read_text())
    if not contract['benchmark_authorized'] or contract['full_training_authorized']:raise RuntimeError('Wrong approval scope')
    if (ROOT/'controller-started.json').exists() and not resume:raise FileExistsError('One bounded controller only')
    if resume:
        correction=json.loads((ROOT/'precision-correction.json').read_text())
        if correction['resource_breach'] or time.time()>=clock['preparation_deadline_epoch']:raise RuntimeError('Corrective preparation not eligible')
        baseline=correction['original_resource_baseline_bytes']
        save(ROOT/'corrective-controller-started.json',dict(pid=os.getpid(),epoch=time.time(),global_swap_baseline_bytes=baseline))
    else:
        baseline=swap();save(ROOT/'controller-started.json',dict(pid=os.getpid(),epoch=time.time(),global_swap_baseline_bytes=baseline))
    import importlib.metadata
    packages=Path(sys.prefix)/'lib/python3.12/site-packages'
    pins=[ROOT/'support.py',ROOT/'engines.py',ROOT/'run.py',ROOT/'contract.json',UPSTREAM/'model.py']
    pins += [packages/'mlx_lm/models'/n for n in ['llama.py','base.py','rope_utils.py','activations.py']]
    pins += [packages/'mlx/optimizers/optimizers.py']
    save(ROOT/'source-pins.json',{str(p):sha(p) for p in pins})
    save(ROOT/'runtime-versions.json',{n:importlib.metadata.version(n) for n in ['mlx','mlx-lm','torch','numpy','tokenizers','sentencepiece','psutil']})
    previous=json.loads((ROOT/'overall-resources.json').read_text()) if resume else {}
    overall_peak_RSS=previous.get('peak_process_RSS_bytes',0);max_swap=previous.get('maximum_additional_swap_bytes',0)
    thermal_since=None;last_thermal=0
    started_jobs=json.loads((ROOT/'jobs.json').read_text()) if resume else []
    def runjob(action,name,kind='fp32',micro=16,seconds=300,deadline=None):
        nonlocal overall_peak_RSS,max_swap,thermal_since,last_thermal
        if (ROOT/'global-stop.json').exists():raise RuntimeError('GLOBAL_RESOURCE_STOP')
        now=time.time();end=min(deadline or now+seconds,clock['deadline_epoch']-900)
        if end<=now+20:raise TimeoutError('Insufficient authorized phase time')
        log=(ROOT/(name+'.log')).open('x')
        cmd=[sys.executable,str(ROOT/'run.py'),action,'--name',name,'--kind',kind,'--micro',str(micro),'--deadline',str(end)]
        env=dict(os.environ,PYTORCH_ENABLE_MPS_FALLBACK='0',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',TOKENIZERS_PARALLELISM='false',PYTHONUNBUFFERED='1')
        child=subprocess.Popen(cmd,cwd=UPSTREAM,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        started_jobs.append(dict(name=name,pid=child.pid,action=action,start_epoch=now,deadline_epoch=end))
        save(ROOT/'jobs.json',started_jobs)
        reason=None;peak_rss=0
        try:
            while child.poll() is None:
                now=time.time()
                try:rss=psutil.Process(child.pid).memory_info().rss
                except psutil.NoSuchProcess:break
                peak_rss=max(peak_rss,rss);overall_peak_RSS=max(overall_peak_RSS,rss)
                current_swap=swap();growth=current_swap-baseline;max_swap=max(max_swap,growth)
                free=psutil.disk_usage(ROOT).free
                if now-last_thermal>=30:
                    therm=subprocess.check_output(['/usr/bin/pmset','-g','therm'],text=True,stderr=subprocess.STDOUT)
                    append(ROOT/'thermal.jsonl',dict(epoch=now,job=name,raw=therm))
                    critical=bool(re.search(r'Thermal_Level\s*=\s*(?:[2-9]|[1-9][0-9]+)',therm))
                    thermal_since=(thermal_since or now) if critical else None;last_thermal=now
                append(ROOT/'resources.jsonl',dict(epoch=now,job=name,RSS_bytes=rss,global_swap_growth_bytes=growth,free_disk_bytes=free))
                if rss>12*GIB:reason='RSS_CAP'
                elif growth>512*1024**2:reason='SWAP_GROWTH_CAP'
                elif free<60*GIB:reason='DISK_FLOOR'
                elif thermal_since and now-thermal_since>=60:reason='SUSTAINED_THERMAL_PRESSURE'
                if reason:
                    save(ROOT/'global-stop.json',dict(reason=reason,epoch=now,job=name));break
                if now>=end:
                    reason='PHASE_HARD_DEADLINE';break
                time.sleep(min(3,max(.1,end-now)))
        finally:
            if child.poll() is None:
                os.killpg(child.pid,signal.SIGTERM)
                try:child.wait(timeout=5)
                except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
            log.close()
            save(ROOT/(name+'-supervisor.json'),dict(returncode=child.returncode,reason=reason,elapsed_seconds=time.time()-started_jobs[-1]['start_epoch'],peak_RSS_bytes=peak_rss,worker_reaped=True))
            save(ROOT/'overall-resources.json',dict(peak_process_RSS_bytes=overall_peak_RSS,maximum_additional_swap_bytes=max_swap,swap_baseline_bytes=baseline))
        failure=ROOT/name/'failure.json'
        if failure.exists():
            message=json.loads(failure.read_text())['error']
            if any(x in message for x in ['GPU_MEMORY_CAP','AGGREGATE_POSITION_CAP','GLOBAL_STOP']):
                save(ROOT/'global-stop.json',dict(reason=message,epoch=time.time(),job=name));raise RuntimeError(message)
        return json.loads((ROOT/name/'result.json').read_text()) if (ROOT/name/'result.json').exists() else dict(status='NO_RESULT',error=failure.read_text() if failure.exists() else reason)
    try:
        numeric=runjob('numeric','numerical-corrected' if resume else 'numerical',deadline=clock['preparation_deadline_epoch'])
        if numeric.get('status')!='NUMERICAL_COMPLETE':raise RuntimeError('Numerical preparation did not complete')
        eligible={k for k,v in numeric['arms'].items() if v['status']=='PASS'}
        save(ROOT/'stage.json',dict(stage='SCREENING',eligible=sorted(eligible),epoch=time.time()))
        screens=json.loads((ROOT/'screening.json').read_text()) if resume else []
        def screen_remaining():
            used=sum(json.loads((ROOT/(j['name']+'-supervisor.json')).read_text())['elapsed_seconds']
                     for j in started_jobs if j['action']=='screen' and (ROOT/(j['name']+'-supervisor.json')).exists())
            return 1800-used
        settings=[('control-mps','mps',16,300),('mlx-fp32','fp32',16,300),('mlx-bf16','bf16',16,300),('mlx-fp16','fp16',16,300)]
        if resume:
            settings=[('mlx-bf16-corrected','bf16',16,300-correction['bf16_screening_seconds_already_consumed']),('mlx-fp16','fp16',16,300)]
        for name,kind,micro,arm_seconds in settings:
            if kind!='mps' and kind not in eligible:
                screens.append(dict(name=name,status='SKIPPED_NUMERICAL_REJECTION',kind=kind,microbatch=micro));continue
            remaining=screen_remaining()
            result=runjob('screen',name,kind,micro,seconds=min(arm_seconds,remaining));result['name']=name;screens.append(result)
            save(ROOT/'screening.json',screens)
        mixed=[r for r in screens if r.get('kind') in ['bf16','fp16'] and r.get('status')=='COMPLETE' and r.get('screening_training_tokens_per_second')]
        if mixed:
            fastest=max(mixed,key=lambda r:r['screening_training_tokens_per_second'])['kind']
            for micro in [32,64]:
                remaining=screen_remaining()
                if remaining<30:break
                result=runjob('screen','mlx-'+fastest+'-batch'+str(micro),fastest,micro,seconds=min(300,remaining))
                result['name']='mlx-'+fastest+'-batch'+str(micro);screens.append(result);save(ROOT/'screening.json',screens)
        viable=[r for r in screens if r.get('status')=='COMPLETE' and r.get('completed_updates',0)>=10 and r.get('screening_training_tokens_per_second')]
        if not viable:raise RuntimeError('No numerically eligible screening arm completed')
        winner=max(viable,key=lambda r:r['screening_training_tokens_per_second'])
        save(ROOT/'winner.json',winner)
        save(ROOT/'stage.json',dict(stage='ONE_HOUR_CONFIRMATION',winner=winner['name'],epoch=time.time()))
        runjob('confirm','confirmation',winner['kind'],winner['microbatch'],seconds=3600)
    except BaseException as e:
        save(ROOT/'controller-failure.json',dict(error=type(e).__name__+': '+str(e),traceback=traceback.format_exc()))
    finally:
        summarize()

def summarize():
    report=dict(status='BENCHMARK_STOPPED_FULL_TRAINING_PAUSED',benchmark_only=True,full_training_authorized=False,
                full_training_started=False,aggregate_reserved_positions=Meter().total())
    for label,name in [('numerical','numerical/result.json'),('screening','screening.json'),('winner','winner.json'),
                       ('confirmation','confirmation/result.json'),('resources','overall-resources.json'),
                       ('failure','controller-failure.json'),('global_stop','global-stop.json'),('precision_correction','precision-correction.json')]:
        p=ROOT/name
        if p.exists():report[label]=json.loads(p.read_text())
    if (ROOT/'numerical-corrected/result.json').exists():report['numerical']=json.loads((ROOT/'numerical-corrected/result.json').read_text())
    if report.get('confirmation',{}).get('status')=='COMPLETE':report['status']='BENCHMARK_COMPLETE_FULL_TRAINING_PAUSED'
    speed=report.get('confirmation',{}).get('final_30_minute_tokens_per_second')
    if speed:
        report.update(sustained_speedup_vs_original=speed/7814.865715956613,
                      projected_full_hours_with_20_percent_overhead=13107200000/speed/3600*1.2,
                      fourteen_day_throughput_gate_pass=speed>=14000)
    clock=json.loads((ROOT/'clock.json').read_text());report['total_wall_seconds_since_approval']=time.time()-clock['start_epoch']
    report['original_checkpoint_sha256']=sha(CHECKPOINT)
    save(ROOT/'report.json',report);save(ROOT/'stage.json',dict(stage='STOPPED_FULL_TRAINING_PAUSED',epoch=time.time()))
    print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['launch','resume','numeric','screen','confirm','summarize'])
    p.add_argument('--name');p.add_argument('--kind',default='fp32');p.add_argument('--micro',type=int,default=16);p.add_argument('--deadline',type=float)
    args=p.parse_args()
    if args.action=='launch':controller()
    elif args.action=='resume':controller(resume=True)
    elif args.action=='summarize':summarize()
    else:worker(args)

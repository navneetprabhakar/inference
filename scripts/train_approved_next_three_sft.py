"""The sole resumable Stage-2 trainer; limits are enforced in code."""
import argparse, fcntl, hashlib, json, math, os, signal, time
from pathlib import Path
import numpy as np
import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as optim
from mlx.utils import tree_flatten, tree_map, tree_unflatten
from benchmark_mlx import Model
from sft_common import ROOT, configure_memory, memory_stats, masked_loss
from train_local import atomic_json, health as host_health

STOP=False
def request_stop(*_):
    global STOP; STOP=True
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def health(): return {**host_health(),**memory_stats()}
def reason(h,base):
    if h['thermal_state']>=3:return 'critical_thermal'
    if h['free_disk_bytes']<15*2**30:return 'disk_reserve'
    if h['mlx_peak_bytes']>12*2**30 or h['mlx_allocator_bytes']>12*2**30:return 'mlx_memory'
    if h.get('swap_used_mb') is not None and h['swap_used_mb']-base['swap_used_mb']>1024:return 'swap_growth'

def main(a):
    signal.signal(signal.SIGINT,request_stop);signal.signal(signal.SIGTERM,request_stop)
    cfgp=ROOT/'configs/approved_next_three_sft_v1.json'; cfg=json.loads(cfgp.read_text()); data=ROOT/'data/approved-next-three-sft-v1'; manifest=json.loads((data/'manifest.json').read_text())
    paths={'config':cfgp,'candidate':ROOT/'data/author-review-v2/reviewed-candidate.jsonl','candidate_validation':ROOT/'reports/author-review-v2/derived-candidate-validation.json','tool_replay_source':ROOT/'data/sft-v3/train.jsonl','tokenizer':ROOT/'data/sft-v3/tokenizer.json','episodes':data/'episodes.npz','order':data/'order.json'}
    for n,h in manifest['hashes'].items():
        if sha(paths[n])!=h: raise RuntimeError('hash mismatch '+n)
    out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True);lock=(out/'.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if (out/'latest.json').exists() and not a.resume: raise RuntimeError('output exists; only --resume is permitted')
    base=health(); configure_memory(); ckpt=ROOT/cfg['base_checkpoint']; arr=dict(np.load(data/'episodes.npz'));meta=json.loads((data/'order.json').read_text())
    state={'status':'initializing','nonpadding_input_tokens':0,'supervised_assistant_tokens':0,'steps':0,'cursor':0,'active_seconds':0.0,'started_unix':time.time(),'candidate_exposures':{},'config_sha256':sha(cfgp),'mixture_manifest_sha256':sha(data/'manifest.json'),'base_checkpoint':str(ckpt.relative_to(ROOT)),'base_checkpoint_sha256':sha(ckpt/'model.safetensors'),'limits':{'nonpadding_input_tokens':cfg['max_nonpadding_input_tokens'],'novel_candidate_passes':cfg['max_novel_candidate_passes'],'wallclock_seconds':cfg['max_active_seconds']},'initial_health':base}
    master=Model(768,12,16384);master.load_weights(str(ckpt/'model.safetensors'));compute=Model(768,12,16384);compute.update(tree_map(lambda x:x.astype(mx.bfloat16),master.parameters()));opt=optim.AdamW(cfg['learning_rate'],betas=[.9,.95],weight_decay=.1,bias_correction=True)
    if a.resume:
        folder=out/json.loads((out/'latest.json').read_text())['directory']; saved=json.loads((folder/'state.json').read_text())
        for key in ['config_sha256','mixture_manifest_sha256','base_checkpoint_sha256','limits']:
            if saved[key]!=state[key]: raise RuntimeError('resume provenance mismatch '+key)
        state=saved;master.load_weights(str(folder/'model.safetensors'));opt.state=tree_unflatten(list(mx.load(str(folder/'optimizer.npz')).items()))
    mx.eval(master.parameters(),compute.parameters(),opt.state);grad=nn.value_and_grad(compute,masked_loss)
    def snapshot(status):
        state.update(status=status,updated_unix=time.time(),wallclock_elapsed_seconds=time.time()-state['started_unix'],health=health());atomic_json(out/'status.json',state);return dict(state)
    def checkpoint(status):
        dest=out/f'checkpoint-{state["nonpadding_input_tokens"]:012d}-{time.time_ns()}';tmp=out/(dest.name+'.partial');tmp.mkdir();mx.eval(master.parameters(),opt.state);master.save_weights(str(tmp/'model.safetensors'));mx.savez(str(tmp/'optimizer.npz'),**dict(tree_flatten(opt.state)));saved=snapshot(status);saved['model_sha256']=sha(tmp/'model.safetensors');atomic_json(tmp/'state.json',saved);os.replace(tmp,dest);atomic_json(out/'latest.json',{'directory':dest.name,'model_sha256':saved['model_sha256']})
    last=time.monotonic()
    while state['cursor']+1<len(meta):
        why=reason(health(),base)
        if STOP or (out/'STOP').exists():checkpoint('stopped_run_specific_stop');return 2
        if why:checkpoint('stopped_'+why);return 3
        if time.time()-state['started_unix']>=cfg['max_active_seconds']:checkpoint('stopped_wallclock');return 4
        ix=[state['cursor'],state['cursor']+1];nonpad=int(sum(arr['length'][i]-1 for i in ix))
        if state['nonpadding_input_tokens']+nonpad>cfg['max_nonpadding_input_tokens']:break
        exposures=dict(state['candidate_exposures'])
        for i in ix:
            if meta[i]['source']=='candidate': exposures[meta[i]['id']]=exposures.get(meta[i]['id'],0)+1
        if any(v>cfg['max_novel_candidate_passes'] for v in exposures.values()):raise RuntimeError('novel data pass limit exceeded')
        value,g=grad(compute,mx.array(arr['ids'][ix]),mx.array(arr['mask'][ix]));mx.eval(value,g);g,norm=optim.clip_grad_norm(g,1.0);mx.eval(norm)
        if not math.isfinite(float(value)) or not math.isfinite(float(norm)):checkpoint('stopped_nonfinite');return 5
        opt.update(master,tree_map(lambda x:x.astype(mx.float32),g));mx.eval(master.parameters(),opt.state);compute.update(tree_map(lambda x:x.astype(mx.bfloat16),master.parameters()));mx.eval(compute.parameters())
        state.update(cursor=state['cursor']+2,steps=state['steps']+1,nonpadding_input_tokens=state['nonpadding_input_tokens']+nonpad,supervised_assistant_tokens=state['supervised_assistant_tokens']+int(arr['mask'][ix].sum()),candidate_exposures=exposures)
        now=time.monotonic();state['active_seconds']+=now-last;last=now
        if state['steps']%cfg['checkpoint_every_steps']==0:checkpoint('running')
    checkpoint('completed');return 0

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--resume',action='store_true');raise SystemExit(main(p.parse_args()))

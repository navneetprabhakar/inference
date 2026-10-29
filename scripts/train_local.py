"""Resumable local-only MLX training. Benchmark and pilot always initialize separately."""
import argparse,ctypes,fcntl,hashlib,json,math,os,re,resource,shutil,signal,subprocess,time
from pathlib import Path
import numpy as np
import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as optim
from mlx.utils import tree_flatten,tree_map,tree_unflatten
from benchmark_mlx import Model

STOP=False

def request_stop(*_):
    global STOP
    STOP=True

def atomic_json(path,obj):
    path=Path(path);tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(obj,indent=2)+'\n');os.replace(tmp,path)

def power():
    return 'AC Power' in subprocess.check_output(['pmset','-g','batt'],text=True)

def thermal():
    ctypes.CDLL('/System/Library/Frameworks/Foundation.framework/Foundation')
    o=ctypes.CDLL('/usr/lib/libobjc.A.dylib')
    o.objc_getClass.argtypes=[ctypes.c_char_p];o.objc_getClass.restype=ctypes.c_void_p
    o.sel_registerName.argtypes=[ctypes.c_char_p];o.sel_registerName.restype=ctypes.c_void_p
    o.objc_msgSend.argtypes=[ctypes.c_void_p,ctypes.c_void_p];o.objc_msgSend.restype=ctypes.c_void_p
    info=o.objc_msgSend(o.objc_getClass(b'NSProcessInfo'),o.sel_registerName(b'processInfo'))
    return int(o.objc_msgSend(info,o.sel_registerName(b'thermalState')) or 0)

def health():
    s=subprocess.check_output(['sysctl','vm.swapusage'],text=True)
    match=re.search(r'used = ([\d.]+)M',s)
    return {'ac_power':power(),'thermal_state':thermal(),'swap_used_mb':float(match.group(1)) if match else None,'rss_peak_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'mlx_peak_bytes':mx.get_peak_memory(),'free_disk_bytes':shutil.disk_usage('.').free}

class Corpus:
    def __init__(self,root,seed=42,state=None):
        self.root=Path(root);self.seed=seed;self.rng=np.random.default_rng(seed)
        self.arrays={s:np.memmap(self.root/f'{s}-train.bin',dtype=np.uint16,mode='r') for s in ['fineweb','tinystories']}
        self.cursors={s:0 for s in self.arrays};self.epochs={s:0 for s in self.arrays};self.counts={s:0 for s in self.arrays}
        if state:
            assert state['seed']==seed
            self.rng.bit_generator.state=state['rng'];self.cursors=state['cursors'];self.epochs=state['epochs'];self.counts=state['counts']
        self.orders={s:self.order(s) for s in self.arrays}
    def order(self,s):
        salt=0 if s=='fineweb' else 100000
        return np.random.default_rng(self.seed+salt+self.epochs[s]).permutation((len(self.arrays[s])-1)//512)
    def batch(self):
        s='fineweb' if self.rng.random()<.8 else 'tinystories';rows=[]
        for _ in range(2):
            if self.cursors[s]>=len(self.orders[s]):
                self.cursors[s]=0;self.epochs[s]+=1;self.orders[s]=self.order(s)
            start=int(self.orders[s][self.cursors[s]])*512;self.cursors[s]+=1
            rows.append(np.asarray(self.arrays[s][start:start+513],dtype=np.int32))
        return s,mx.array(np.stack(rows))
    def state(self):
        return {'seed':self.seed,'rng':self.rng.bit_generator.state,'cursors':self.cursors,'epochs':self.epochs,'counts':self.counts}

def make_model(d=768,layers=12,vocab=16384,seed=42):
    mx.random.seed(seed);master=Model(d,layers,vocab);compute=Model(d,layers,vocab)
    compute.update(tree_map(lambda x:x.astype(mx.bfloat16),master.parameters()));mx.eval(master.parameters(),compute.parameters())
    return master,compute

def loss(model,tokens,valid):
    values=nn.losses.cross_entropy(model(tokens[:,:-1]).astype(mx.float32),tokens[:,1:],reduction='none').reshape(-1)
    return values[:valid].mean()

def save_checkpoint(out,master,opt,state):
    start=time.monotonic();folder=out/f"checkpoint-{state['tokens']:012d}-{time.time_ns()}";tmp=out/(folder.name+'.partial');tmp.mkdir()
    mx.eval(master.parameters(),opt.state);master.save_weights(str(tmp/'model.safetensors'))
    mx.savez(str(tmp/'optimizer.npz'),**dict(tree_flatten(opt.state)))
    atomic_json(tmp/'state.json',state);os.replace(tmp,folder)
    atomic_json(out/'latest.json',{'directory':folder.name})
    # Only remove superseded checkpoints generated in this run directory.
    complete=sorted([p for p in out.glob('checkpoint-*') if p.is_dir() and not p.name.endswith('.partial')],key=lambda p:p.stat().st_mtime)
    for old in complete[:-2]:shutil.rmtree(old)
    return time.monotonic()-start

def load_checkpoint(out,master,opt):
    folder=out/json.loads((out/'latest.json').read_text())['directory']
    master.load_weights(str(folder/'model.safetensors'))
    opt.state=tree_unflatten(list(mx.load(str(folder/'optimizer.npz')).items()))
    mx.eval(master.parameters(),opt.state)
    return json.loads((folder/'state.json').read_text())

def evaluate(model,data,batches=8):
    result={}
    for s in ['fineweb','tinystories']:
        arr=np.memmap(data/f'{s}-validation.bin',dtype=np.uint16,mode='r');values=[]
        for i in range(batches):
            start=i*1024;batch=mx.array(np.stack([np.asarray(arr[start+j*512:start+j*512+513],dtype=np.int32) for j in range(2)]))
            v=loss(model,batch,1024);mx.eval(v);values.append(float(v))
        result[s]=sum(values)/len(values)
    return result

def run(a):
    signal.signal(signal.SIGTERM,request_stop);signal.signal(signal.SIGINT,request_stop)
    data=a.data.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    lock=(out/'.lock').open('a');fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    assert 0<a.tokens<=100_000_000 and 0<a.seconds<=3600
    code_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(__file__).with_name('benchmark_mlx.py')]}
    atomic_json(out/'status.json',{'status':'initializing','mode':a.mode,'pid':os.getpid(),'updated_at':time.time()})
    if (out/'latest.json').exists() and not a.resume:raise RuntimeError('Existing checkpoint: use --resume')
    manifest=json.loads((data/'manifest.json').read_text());manifest_sha=hashlib.sha256((data/'manifest.json').read_bytes()).hexdigest()
    # Hash the actual token files and tokenizer, not just their names.
    for v in manifest['sources'].values():
        assert hashlib.sha256((data/v['path']).read_bytes()).hexdigest()==v['sha256']
    assert hashlib.sha256((data/'tokenizer.json').read_bytes()).hexdigest()==manifest['tokenizer_sha256']
    master,compute=make_model(vocab=manifest['vocab_size'],seed=a.seed)
    opt=optim.AdamW(learning_rate=3e-4,betas=[.9,.95],weight_decay=.1,bias_correction=True)
    state={'tokens':0,'steps':0,'active_seconds':0.,'data_manifest_sha256':manifest_sha,'mode':a.mode,'target_tokens':a.tokens,'seed':a.seed,'architecture':{'hidden':768,'layers':12,'vocab':manifest['vocab_size']},'parameter_count':sum(p.size for _,p in tree_flatten(master.parameters())),'initial_validation':None,'code_hashes':code_hashes}
    if a.resume:
        state=load_checkpoint(out,master,opt)
        assert state['code_hashes']==code_hashes
        assert state['data_manifest_sha256']==manifest_sha and state['mode']==a.mode and state['target_tokens']==a.tokens and state['seed']==a.seed
        compute.update(tree_map(lambda x:x.astype(mx.bfloat16),master.parameters()))
    corpus=Corpus(data,a.seed,state.get('corpus'));grad=nn.value_and_grad(compute,loss)
    if state['initial_validation'] is None:state['initial_validation']=evaluate(compute,data)
    start_health=health();state.setdefault('initial_health',start_health)
    last=time.monotonic();last_progress=last;last_checkpoint=last;last_eval_tokens=state['tokens'];window_tokens=state['tokens'];window_time=state['active_seconds'];recent=[];checkpoint_seconds=[];norm_value=0.;value=0.
    def snapshot(status):
        h=health();obj={**state,'status':status,'last_loss':value,'gradient_norm':norm_value,'health':h,'updated_at':time.time(),'corpus':corpus.state()};atomic_json(out/'status.json',obj);return obj
    def checkpoint(status):
        saved=snapshot(status);seconds=save_checkpoint(out,master,opt,saved);checkpoint_seconds.append(seconds);return seconds
    while state['tokens']<a.tokens and (a.mode!='benchmark' or state['active_seconds']<a.seconds):
        if STOP or (out/'STOP').exists():
            checkpoint('stopped');return 2
        if time.monotonic()-last_progress>=15 or state['steps']==0:
            h=health()
            if not h['ac_power'] or h['thermal_state']>=3:
                state.setdefault('pause_events',[]).append({'time':time.time(),'health':h})
                checkpoint('paused_power_or_critical_thermal')
                while not STOP:
                    time.sleep(10);h=health()
                    if h['ac_power'] and h['thermal_state']<3:break
                last=time.monotonic();last_progress=last;last_checkpoint=last
                if STOP:checkpoint('stopped');return 2
            if h['free_disk_bytes']<15*2**30 or h['mlx_peak_bytes']>12*2**30 or (h['swap_used_mb'] is not None and h['swap_used_mb']-state['initial_health']['swap_used_mb']>1024):
                checkpoint('stopped_resource_limit');return 3
        # Average microbatch gradients by the number of actual target tokens.
        remaining=min(8192,a.tokens-state['tokens']);acc=None;weighted_loss=0.;used=0
        while used<remaining:
            source,tokens=corpus.batch();valid=min(1024,remaining-used);v,g=grad(compute,tokens,valid)
            g=tree_map(lambda x:x.astype(mx.float32)*(valid/remaining),g)
            acc=g if acc is None else tree_map(lambda x,y:x+y,acc,g)
            mx.eval(v,acc);weighted_loss+=float(v)*valid;used+=valid;corpus.counts[source]+=valid
        acc,norm=optim.clip_grad_norm(acc,1.0);mx.eval(norm);norm_value=float(norm);value=weighted_loss/used
        if not math.isfinite(value) or not math.isfinite(norm_value):
            checkpoint('stopped_nonfinite');return 4
        progress=state['tokens']/max(1,a.tokens);warmup=min(1.,(state['tokens']+used)/2_000_000)
        lr=3e-4*warmup*(.1+.9*.5*(1+math.cos(math.pi*progress)))
        opt.learning_rate=lr;opt.update(master,acc);mx.eval(master.parameters(),opt.state)
        compute.update(tree_map(lambda x:x.astype(mx.bfloat16),master.parameters()));mx.eval(compute.parameters())
        state['tokens']+=used;state['steps']+=1;state['learning_rate']=lr
        now=time.monotonic();state['active_seconds']+=now-last;last=now
        if now-last_checkpoint>=300:
            checkpoint('running');last_checkpoint=time.monotonic()
        if state['tokens']-last_eval_tokens>=5_000_000:
            state['validation']=evaluate(compute,data);last_eval_tokens=state['tokens']
        if now-last_progress>=60:
            duration=state['active_seconds']-window_time;rate=(state['tokens']-window_tokens)/max(duration,.001)
            event={'tokens':state['tokens'],'active_seconds':state['active_seconds'],'tokens_per_second':rate,'loss':value,'gradient_norm':norm_value,'health':health(),'time':time.time()}
            with (out/'metrics.jsonl').open('a') as f:f.write(json.dumps(event)+'\n')
            recent.append(event);state['recent_tokens_per_second']=rate;snapshot('running');print(json.dumps(event),flush=True)
            window_time=state['active_seconds'];window_tokens=state['tokens'];last_progress=now
        if state['active_seconds']>24*3600:
            checkpoint('stopped_24h_active_limit');return 5
    state['validation']=evaluate(compute,data);checkpoint('completed');final_health=health()
    result={'mode':a.mode,'tokens':state['tokens'],'steps':state['steps'],'active_seconds':state['active_seconds'],'overall_tokens_per_second':state['tokens']/max(state['active_seconds'],.001),'initial_validation':state['initial_validation'],'final_validation':state['validation'],'health':final_health,'checkpoint_seconds':checkpoint_seconds,'master_weights':'float32','compute':'bfloat16','optimizer':'float32 AdamW','target_tokens_exact':a.tokens}
    if a.mode=='benchmark':
        tail=[r['tokens_per_second'] for r in recent[-5:]];head=[r['tokens_per_second'] for r in recent[:5]]
        tail_rate=sum(tail)/len(tail) if tail else 0.;head_rate=sum(head)/len(head) if head else 0.
        checks={'sustained_30_minutes':state['active_seconds']>=1800,'enough_windows':len(recent)>=25,'ac_power':final_health['ac_power'],'uninterrupted_on_ac':not state.get('pause_events'),'no_critical_thermal':all(r['health']['thermal_state']<3 for r in recent),'memory_under_12gib':final_health['mlx_peak_bytes']<12*2**30,'rss_under_18gib':final_health['rss_peak_bytes']<18*2**30,'swap_growth_under_1gib':final_health['swap_used_mb']-state['initial_health']['swap_used_mb']<1024,'tail_at_least_1400_tokens_per_second':tail_rate>=1400,'tail_at_least_60pct_initial':tail_rate>=.6*head_rate,'validation_improved':sum(state['validation'].values())<sum(state['initial_validation'].values())}
        result.update({'checks':checks,'feasible':all(checks.values()),'tail_tokens_per_second':tail_rate,'pilot_hours_at_tail_rate':100_000_000/tail_rate/3600 if tail_rate else None})
    atomic_json(out/'result.json',result);print(json.dumps(result),flush=True);return 0
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=['benchmark','pilot'],required=True);p.add_argument('--data',type=Path,default=Path('data/pilot-v1'));p.add_argument('--output',type=Path,required=True);p.add_argument('--tokens',type=int,default=100_000_000);p.add_argument('--seconds',type=int,default=1800);p.add_argument('--seed',type=int,default=42);p.add_argument('--resume',action='store_true');a=p.parse_args();raise SystemExit(run(a))

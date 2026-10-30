"""Continue the existing 100M model, with a hard 300M total-token ceiling."""
import argparse,fcntl,hashlib,json,math,os,signal,time
from pathlib import Path
import numpy as np
import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as optim
from mlx.utils import tree_map,tree_unflatten
from benchmark_mlx import Model
from train_local import atomic_json,health,loss,save_checkpoint
STOP=False
# Compatible predecessor: only the AC-power pause policy changed. Preserve all
# model, optimizer, sampler, loss, and learning-rate state when resuming it.
AC_ONLY_PREDECESSOR='3e5e05d386955ec78f11a89427c2daf1452ff437ae998054472c230aad149ca7'
def compatible_code(previous,current):
    return previous.keys()==current.keys() and all(h==current[n] or (n=='train_continuation.py' and h==AC_ONLY_PREDECESSOR) for n,h in previous.items())
def stop(*_):
    global STOP
    STOP=True
class FreshCorpus:
    def __init__(self,root,state=None):
        self.root=Path(root);self.array=np.memmap(self.root/'train.bin',dtype=np.uint16,mode='r');self.order=np.random.default_rng(314159).permutation((len(self.array)-1)//512)
        self.cursor=state['cursor'] if state else 0;self.source_counts=dict(state['source_counts']) if state else {'fineweb':0,'wikipedia':0,'pressbooks':0};self.ranges=json.loads((self.root/'manifest.json').read_text())['source_ranges']
    def batch(self,valid=1024):
        rows=[];remaining=valid
        for _ in range(2):
            if self.cursor>=len(self.order):raise RuntimeError('Fresh corpus exhausted: replay is forbidden')
            start=int(self.order[self.cursor])*512;self.cursor+=1;rows.append(np.asarray(self.array[start:start+513],dtype=np.int32));count=min(512,remaining);remaining-=count
            for s,(lo,hi) in self.ranges.items():
                if lo<=start<hi:self.source_counts[s]+=count;break
        return mx.array(np.stack(rows))
    def state(self):return {'cursor':self.cursor,'source_counts':self.source_counts,'seed':314159,'replay':False}
def learning_rate(total_tokens):
    added=total_tokens-100_000_000
    if added<2_000_000:return 3e-5+7e-5*max(0,added)/2_000_000
    progress=min(1.,(added-2_000_000)/198_000_000)
    return 1e-5+9e-5*.5*(1+math.cos(math.pi*progress))
def validation(model,data):
    out={}
    for name in ['fineweb','wikipedia','pressbooks']:
        a=np.memmap(data/f'{name}-validation.bin',dtype=np.uint16,mode='r');values=[]
        for i in range(8):
            rows=np.stack([np.asarray(a[(i*2+j)*512:(i*2+j)*512+513],dtype=np.int32) for j in range(2)]);v=loss(model,mx.array(rows),1024);mx.eval(v);values.append(float(v))
        out[name]=sum(values)/len(values)
    return out

def run(a):
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    root=Path(__file__).resolve().parents[1];data=root/'data/continuation-v1';out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    lock=(out/'.lock').open('a');fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    assert a.target_total in [200_000_000,300_000_000]
    if (out/'latest.json').exists() and not a.resume:raise RuntimeError('Existing run: use --resume')
    manifest=json.loads((data/'manifest.json').read_text());data_hash=hashlib.sha256((data/'manifest.json').read_bytes()).hexdigest()
    assert manifest['train_tokens']>=205_000_000
    assert manifest['final_verification']['exact_overlap_with_prior_documents_or_prior_evaluation']==0
    assert manifest['final_verification']['cross_split_group_overlap']==0
    for key,expected in [('train.bin',manifest['train_sha256']),('tokenizer.json',manifest['tokenizer_sha256'])]:assert hashlib.sha256((data/key).read_bytes()).hexdigest()==expected
    assert manifest['tokenizer_sha256']==json.loads((root/'data/pilot-v1/manifest.json').read_text())['tokenizer_sha256']
    code_hashes={name:hashlib.sha256((root/'scripts'/name).read_bytes()).hexdigest() for name in ['train_continuation.py','benchmark_mlx.py','train_local.py']}
    origin=out/json.loads((out/'latest.json').read_text())['directory'] if a.resume else a.from_checkpoint.resolve()
    previous=json.loads((origin/'state.json').read_text());assert previous['tokens']<=a.target_total<=300_000_000
    assert previous['tokens']>=100_000_000
    if 'continuation_data_sha256' in previous:
        assert previous['continuation_data_sha256']==data_hash and compatible_code(previous['continuation_code_hashes'],code_hashes)
    else:assert previous['tokens']==100_000_000
    master=Model(768,12,16384);master.load_weights(str(origin/'model.safetensors'))
    compute=Model(768,12,16384);compute.update(tree_map(lambda x:x.astype(mx.bfloat16),master.parameters()))
    opt=optim.AdamW(3e-5,betas=[.9,.95],weight_decay=.1,bias_correction=True);opt.state=tree_unflatten(list(mx.load(str(origin/'optimizer.npz')).items()));mx.eval(master.parameters(),compute.parameters(),opt.state)
    assert int(opt.step)==previous['steps'],'Optimizer and checkpoint step counters disagree'
    corpus=FreshCorpus(data,previous.get('fresh_corpus'))
    state={'tokens':previous['tokens'],'steps':previous['steps'],'continuation_active_seconds':previous.get('continuation_active_seconds',0.),'continuation_data_sha256':data_hash,'continuation_code_hashes':code_hashes,'origin_checkpoint':str(origin),'target_total_tokens':a.target_total,'absolute_token_ceiling':300_000_000,'initial_health':previous.get('continuation_initial_health',health()),'initial_validation':validation(compute,data)}
    state['power_policy']='continue_on_battery';state['resumed_code_hashes']=previous.get('continuation_code_hashes');state['continuation_initial_health']=state['initial_health'];start_tokens=state['tokens'];start_active=state['continuation_active_seconds'];value=norm_value=0.
    def snapshot(status):
        obj={**state,'status':status,'health':health(),'last_loss':value,'gradient_norm':norm_value,'fresh_corpus':corpus.state(),'updated_at':time.time(),'pid':os.getpid()};atomic_json(out/'status.json',obj);return obj
    def checkpoint(status):return save_checkpoint(out,master,opt,snapshot(status))
    snapshot('initialized');grad=nn.value_and_grad(compute,loss)
    last=time.monotonic();last_progress=last;last_checkpoint=last;last_health=0.;last_eval=state['tokens'];window_tokens=state['tokens'];window_time=state['continuation_active_seconds']
    while state['tokens']<a.target_total:
        if STOP or (out/'STOP').exists():checkpoint('stopped');return 2
        if time.monotonic()-last_health>=15:
            h=health();last_health=time.monotonic()
            if h['thermal_state']>=3:
                checkpoint('paused_critical_thermal')
                while not STOP and not (out/'STOP').exists():
                    time.sleep(10);h=health()
                    if h['thermal_state']<3:break
                last=time.monotonic();last_progress=last;last_checkpoint=last
                if STOP or (out/'STOP').exists():checkpoint('stopped');return 2
            if h['free_disk_bytes']<15*2**30 or h['mlx_peak_bytes']>12*2**30 or h['swap_used_mb']-state['initial_health']['swap_used_mb']>1024:checkpoint('stopped_resource_limit');return 3
        count=min(8192,a.target_total-state['tokens']);used=0;acc=None;weighted=0.
        while used<count:
            valid=min(1024,count-used);t=corpus.batch(valid);v,g=grad(compute,t,valid);g=tree_map(lambda x:x.astype(mx.float32)*(valid/count),g);acc=g if acc is None else tree_map(lambda x,y:x+y,acc,g);mx.eval(v,acc);weighted+=float(v)*valid;used+=valid
        acc,norm=optim.clip_grad_norm(acc,1.);mx.eval(norm);norm_value=float(norm);value=weighted/count
        if not math.isfinite(value) or not math.isfinite(norm_value):checkpoint('stopped_nonfinite');return 4
        lr=learning_rate(state['tokens']);opt.learning_rate=lr;opt.update(master,acc);mx.eval(master.parameters(),opt.state);compute.update(tree_map(lambda x:x.astype(mx.bfloat16),master.parameters()));mx.eval(compute.parameters())
        state['tokens']+=count;state['steps']+=1;state['learning_rate']=lr;now=time.monotonic();state['continuation_active_seconds']+=now-last;last=now
        if now-last_checkpoint>=300:checkpoint('running');last_checkpoint=time.monotonic()
        if state['tokens']-last_eval>=5_000_000:state['validation']=validation(compute,data);last_eval=state['tokens']
        if now-last_progress>=60:
            rate=(state['tokens']-window_tokens)/max(.001,state['continuation_active_seconds']-window_time);state['recent_tokens_per_second']=rate
            event={'total_tokens':state['tokens'],'added_tokens':state['tokens']-100_000_000,'tokens_per_second':rate,'loss':value,'health':health(),'time':time.time()}
            with (out/'metrics.jsonl').open('a') as f:f.write(json.dumps(event)+'\n')
            snapshot('running');print(json.dumps(event),flush=True);window_time=state['continuation_active_seconds'];window_tokens=state['tokens'];last_progress=now
        if state['continuation_active_seconds']>36*3600:checkpoint('stopped_36h_continuation_limit');return 5
    state['validation']=validation(compute,data);checkpoint('completed')
    result={**state,'status':'completed','stage_tokens':state['tokens']-start_tokens,'stage_active_seconds':state['continuation_active_seconds']-start_active,'source_counts':corpus.source_counts,'optimizer_step':int(opt.step),'cloud_spend_usd':0,'paid_api_spend_usd':0}
    atomic_json(out/'result.json',result);return 0
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--from-checkpoint',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--target-total',type=int,required=True);p.add_argument('--resume',action='store_true');a=p.parse_args();raise SystemExit(run(a))

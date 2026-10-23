"""Shared, approval-bound clocks, accounting, resources and immutable engine adapter."""
import hashlib,importlib.util,json,math,os,sqlite3,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
PROJECT=ROOT.parents[1]; OLD=PROJECT/'restart/foundation-stage3-v1'
UPSTREAM=PROJECT/'restart/mac15m-feasibility-v1/upstream'
PYTHON=PROJECT/'restart/mac-native-benchmark-v1/venv/bin/python'
GIB=1024**3

def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for block in iter(lambda:f.read(4*1024**2),b''):h.update(block)
    return h.hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n');tmp.replace(p)
def check_clock(clock,phase,now=None,reserve=True):
    assert clock['schema_version']==1 and clock['phase']==phase,'CLOCK_SCHEMA_OR_PHASE'
    assert clock['deadline_epoch']-clock['started_epoch']==clock['wall_seconds_cap'],'CLOCK_DURATION'
    if (time.time() if now is None else now)>=clock['deadline_epoch']-(clock['shutdown_reserve_seconds'] if reserve else 0):raise TimeoutError('AUTHORIZED_PHASE_DEADLINE')
def check(phase,reserve=True):
    if (ROOT/'STOP.json').exists():raise RuntimeError('TERMINAL_STOP')
    check_clock(read(ROOT/'clock.json'),phase,reserve=reserve)
def freeze_check(phase):
    freeze=read(ROOT/f'{phase}-freeze.json')
    for name,digest in freeze['files'].items():assert sha(PROJECT/name)==digest,'FROZEN_SOURCE_CHANGED: '+name
    return freeze
class Meter:
    def __init__(self,phase):
        self.phase=phase;self.db=sqlite3.connect(ROOT/'work.sqlite',timeout=20)
        self.db.execute('CREATE TABLE IF NOT EXISTS work(id INTEGER PRIMARY KEY,phase TEXT,kind TEXT,positions INTEGER,epoch REAL)')
    def reserve(self,n,kind):
        check(self.phase);assert isinstance(n,int) and n>=0
        self.db.execute('BEGIN IMMEDIATE')
        phase=self.db.execute('SELECT COALESCE(SUM(positions),0) FROM work WHERE phase=?',(self.phase,)).fetchone()[0]
        total=self.db.execute('SELECT COALESCE(SUM(positions),0) FROM work').fetchone()[0]
        cap={'R0':2000000,'R1':72000000,'R2':82000000}[self.phase]
        if phase+n>cap or total+n>156000000:self.db.rollback();raise RuntimeError('POSITION_CAP')
        self.db.execute('INSERT INTO work(phase,kind,positions,epoch) VALUES(?,?,?,?)',(self.phase,kind,n,time.time()));self.db.commit()
    def total(self):return self.db.execute('SELECT COALESCE(SUM(positions),0) FROM work WHERE phase=?',(self.phase,)).fetchone()[0]
def resources(pid):
    import psutil
    proc=psutil.Process(pid);members=[proc]+proc.children(recursive=True)
    rss=sum(p.memory_info().rss for p in members if p.is_running())
    swap=subprocess.run(['/usr/sbin/sysctl','-n','vm.swapusage'],capture_output=True,text=True,check=True,timeout=5).stdout
    import re
    used=float(re.search(r'used = ([0-9.]+)M',swap).group(1))*1024**2
    free=psutil.disk_usage(PROJECT).free
    power=subprocess.run(['/usr/bin/pmset','-g','batt'],capture_output=True,text=True,check=True,timeout=5).stdout
    thermal=subprocess.run(['/usr/bin/pmset','-g','therm'],capture_output=True,text=True,check=True,timeout=5).stdout
    if rss>12*GIB:raise RuntimeError('RSS_CAP')
    if used>401342464+512*1024**2:raise RuntimeError('SWAP_CAP')
    if free<60*GIB:raise RuntimeError('DISK_FLOOR')
    if 'AC Power' not in power:raise RuntimeError('AC_REQUIRED')
    return dict(epoch=time.time(),rss_bytes=rss,global_swap_bytes=int(used),free_disk_bytes=free,AC=True,thermal=thermal)
def original_rate(step):
    return .0005*step/1000 if step<1000 else .00025*(1+math.cos(math.pi*(step-1000)/99000))
def load_engine(path,precision='bf16',schedule=None):
    # Reuse frozen, previously exercised arithmetic. Patch only injected inputs,
    # never the historical source, receipts, clocks or closed work ledger.
    import torch
    torch.set_num_threads(4)
    spec=importlib.util.spec_from_file_location('engine_support',OLD/'engine_support.py');support=importlib.util.module_from_spec(spec);spec.loader.exec_module(support);sys.modules['engine_support']=support
    spec=importlib.util.spec_from_file_location('resolution_engine',OLD/'engine.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    state=torch.load(path,map_location='cpu',weights_only=False)
    mod.origin=lambda:state;mod.rate=schedule or original_rate
    engine=mod.MLXEngine(precision,16)
    assert 'mlx_rng_state' in state
    for i,x in enumerate(state['mlx_rng_state']):engine.mx.random.state[i][...] = engine.mx.array(x)
    engine.mx.eval(engine.mx.random.state);finite(engine)
    return engine,support.Stream

def finite(engine):
    mx=engine.mx;arrays=list(engine.params.values())
    for opt,names in [(engine.om,engine.matrix),(engine.on,engine.norm)]:arrays += [opt.state[k][field] for k in names for field in ['m','v']]
    good=mx.all(mx.stack([mx.all(mx.isfinite(v)) for v in arrays]));mx.eval(good)
    if not bool(good):raise RuntimeError('NONFINITE_MASTER_OR_MOMENT')
def bind(engine):
    from mlx.utils import tree_unflatten
    engine.model.update(tree_unflatten([(k,v.astype(engine.dtype)) for k,v in engine.params.items()]))
    return engine.model

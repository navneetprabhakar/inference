"""Pure launch planning and VM-side bounded staging. No implicit provisioning.

The plan command never calls GCP or writes a spend ledger. Root must reserve the
returned whole-campaign projection before executing its create argv. Staging is
an explicit server-only operation against hash-pinned, private GCS artifacts.
"""
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, math, os
from pathlib import Path
import re, shutil, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from cloud_training.nano_package import TOKENIZER_SHA, relative, sha
from cloud_training.campaign_budget import forecast
from cloud_training.nano_retention import _prefix, _validate_receipt

BUCKET='gs://forge-ownbase-a100-20261110/'
BATCH=524288
HORIZON=19074

def uri(value):
    if not isinstance(value,str) or not value.startswith(BUCKET) or not re.fullmatch(r'gs://[A-Za-z0-9._/-]+(?:#[0-9]+)?',value) or '..' in value.split('/'):
        raise ValueError('Explicit project-private GCS object required')
    return value

def digest(value):
    if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{64}',value): raise ValueError('SHA256 required')
    return value

def data_index(index):
    if index.get('schema')!=1 or index.get('tokenizer_sha256')!=TOKENIZER_SHA: raise ValueError('Final tokenizer data index required')
    relative(index['campaign_path']); digest(index['campaign_sha256'])
    seen=set()
    for item in index['files']:
        relative(item['path']); uri(item['uri']); digest(item['sha256'])
        if item['path'] in seen or type(item['bytes']) is not int or item['bytes']<=0: raise ValueError('Duplicate/invalid data object')
        seen.add(item['path'])
    if index['campaign_path'] not in seen: raise ValueError('Campaign manifest missing from inventory')
    if next(x['sha256'] for x in index['files'] if x['path']==index['campaign_path'])!=index['campaign_sha256']: raise ValueError('Campaign hash mismatch')
    return index

def select_resume(journal, config):
    if journal.get('schema')!=1 or journal.get('campaign_prefix')!=config['backup_prefix'] or journal.get('lease_phase')!='ready': raise ValueError('Authoritative journal is not ready')
    identity=journal['identity']
    expected={'phase':'base','initialization':'own_random','tokenizer_sha256':TOKENIZER_SHA,'campaign_sha256':config['campaign_sha256']}
    if any(identity.get(k)!=v for k,v in expected.items()): raise ValueError('Resume campaign identity mismatch')
    if any(e['state'] not in ('committed','deleted') for e in journal['entries']): raise ValueError('Interrupted journal operation')
    live=[]
    for e in journal['entries']:
        _validate_receipt(e['receipt'],config['backup_prefix'])
        if e['receipt']['identity']!=identity: raise ValueError('Mixed checkpoint identities')
        if e['state']=='committed': live.append(e['receipt'])
    if not live: raise ValueError('No committed resume checkpoint')
    latest=max(live,key=lambda r:r['step'])
    if latest['step']!=config['resume_step']: raise ValueError('Authoritative step changed; reforecast/review lease')
    return latest

def lease_controls(config):
    """Operational lease/save cadence, deliberately outside numerical identity."""
    kind=config.get('launch_kind','production')
    if kind not in ('pilot','production'): raise ValueError('Explicit pilot/production launch kind required')
    seconds=config['max_runtime_seconds']
    cap=10800 if kind=='pilot' else 21600
    if type(seconds) is not int or not 1200<=seconds<=cap:
        raise ValueError('Lease must be 20min..3h for pilot or 20min..6h for production')
    cadence=config.get('checkpoint_seconds',900)
    if type(cadence) is not int or cadence not in (900,1800): raise ValueError('Checkpoint cadence must be900 or1800seconds')
    return seconds,cadence

def build_plan(config, ledger, qualification, price, index, *, now=None):
    """Validate reviewed evidence and return argv; does not reserve or create."""
    now=now or dt.datetime.now(dt.timezone.utc)
    data_index(index)
    if config.get('schema')!=1 or config.get('campaign_sha256')!=index['campaign_sha256']: raise ValueError('Launch/campaign mismatch')
    _prefix(config['backup_prefix']); uri(config['backup_prefix'])
    for key in ('bundle_uri','config_uri','index_uri'): uri(config[key])
    for key in ('bundle_sha256','config_sha256','index_sha256','kernel_sha256'): digest(config[key])
    if not re.fullmatch(r'forge-ownbase-[a-z0-9-]{1,40}',config['run_id']): raise ValueError('Invalid run id')
    if not re.fullmatch(r'[a-z]+-[a-z0-9]+[0-9]-[a-z]',config['zone']): raise ValueError('Invalid GCP zone')
    seconds,_=lease_controls(config)
    step=config['resume_step']
    if type(step) is not int or not 0<=step<HORIZON or (config['mode']=='fresh' and step!=0) or config['mode'] not in ('fresh','resume'): raise ValueError('Invalid initial/resume step')
    limit=config.get('max_updates')
    if limit is not None and (type(limit) is not int or limit<1 or step+limit>HORIZON): raise ValueError('Invalid pilot bound')
    if config.get('depth')!=16 or config.get('microbatch') not in (1,2,4,8,16): raise ValueError('Unqualified geometry')
    kind=config.get('launch_kind','production')
    if kind not in ('pilot','production'): raise ValueError('Explicit pilot/production launch kind required')
    if qualification.get('restart_verified') is not True or qualification.get('campaign_sha256')!=index['campaign_sha256']: raise ValueError('Reviewed benchmark restart/data qualification required')
    if kind=='pilot':
        if limit is None or limit>32 or qualification.get('training_admitted') is not True: raise ValueError('Pilot requires admitted data and <=32 bounded updates')
    elif qualification.get('production_ready') is not True:
        raise ValueError('Production requires reviewed fresh-process two-lease recovery proof')
    queue_seconds=config.get('request_valid_seconds',0)
    if queue_seconds not in (0,1800): raise ValueError('Capacity request must be immediate or bounded30min')
    for key in ('depth','microbatch','deterministic','deterministic_attention'):
        if qualification.get(key)!=config.get(key): raise ValueError('Numerical qualification mismatch: '+key)
    if any(type(config.get(k)) is not bool for k in ('deterministic','deterministic_attention')): raise ValueError('Explicit numerical modes required')
    checked=dt.datetime.fromisoformat(price['checked_utc'].replace('Z','+00:00'))
    if checked.tzinfo is None or not 0<=(now-checked).total_seconds()<=86400: raise ValueError('Fresh price evidence required')
    rate=price['usd_per_hour']
    if isinstance(rate,bool) or not isinstance(rate,(float,int)) or not math.isfinite(rate) or not 0<rate<=2.5 or price.get('machine_type')!='a2-highgpu-1g' or price.get('provisioning_model')!='FLEX_START' or not price.get('source'): raise ValueError('Price outside reviewed envelope')
    projection=forecast(remaining_tokens=(HORIZON-step)*BATCH,tokens_per_second=qualification['tokens_per_second'],overhead_fraction=config['overhead_fraction'],setup_hours=config['remaining_setup_hours'])
    if ledger.get('cap_usd')!=100 or any(a['state'].startswith(('reserved','running','queued')) for a in ledger['allocations']): raise ValueError('Cap mismatch or outstanding GPU allocation')
    amounts=[ledger['ancillary_reserve_usd'],*[a['reserved_usd'] for a in ledger['allocations']]]
    if any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or x<0 for x in amounts): raise ValueError('Invalid financial ledger')
    if projection['remaining_compute_envelope_usd']<seconds/3600*2.5: raise ValueError('Shorten final lease to remaining campaign forecast')
    spent=sum(a['reserved_usd'] for a in ledger['allocations'])
    if spent+ledger['ancillary_reserve_usd']+10+max(projection['remaining_compute_envelope_usd'],seconds/3600*2.5)>100: raise ValueError('Whole campaign exceeds remaining budget')
    command=['gcloud','compute','instances','create',config['run_id'],'--project=executespecv1','--zone='+config['zone'],'--machine-type=a2-highgpu-1g','--provisioning-model=FLEX_START','--image=pytorch-2-9-cu129-ubuntu-2404-nvidia-580-v20261029','--image-project=deeplearning-platform-release','--boot-disk-size=200GB','--boot-disk-type=pd-balanced','--boot-disk-auto-delete','--maintenance-policy=TERMINATE','--no-restart-on-failure','--max-run-duration='+str(seconds)+'s','--instance-termination-action=DELETE','--no-address','--subnet=default','--service-account=forge-ownbase-bench@executespecv1.iam.gserviceaccount.com','--scopes=https://www.googleapis.com/auth/devstorage.read_write','--labels=purpose=ownbase-training,budget=usd100','--request-valid-for-duration='+str(queue_seconds)+'s','--metadata='+','.join(k+'='+str(config[v]) for k,v in [('bundle-uri','bundle_uri'),('code-sha256','bundle_sha256'),('config-uri','config_uri'),('config-sha256','config_sha256')]),'--metadata-from-file=startup-script=cloud_training/nano_server.sh','--quiet','--format=json']
    if queue_seconds: command.append('--async')
    return {'schema':1,'status':'review_only_not_reserved','projection':projection,'lease_hours':seconds/3600,'create_argv':command,'required_before_execution':['campaign_budget.reserve with this projection and reviewed receipt paths','confirm zero existing project ownbase GPU instances/requests','confirm private bucket IAM and subnet Private Google Access','confirm complete 10B campaign inventory and exact authoritative ready journal','reconcile provider deletion and ledger after every lease']}

def run_cloud(args,deadline):
    remaining=deadline-time.time()
    if remaining<=0: raise TimeoutError('Staging deadline expired')
    return subprocess.check_output(['gcloud','storage',*args,'--quiet'],text=True,timeout=remaining)

def fetch(source,target,expected,deadline,bytes_expected=None):
    uri(source); digest(expected); target=Path(target)
    target.parent.mkdir(parents=True,exist_ok=True)
    if any(p.is_symlink() for p in [target,*target.parents]): raise ValueError('Symlink destination rejected')
    if target.exists():
        if sha(target)==expected and (bytes_expected is None or target.stat().st_size==bytes_expected): return
        raise ValueError('Existing file differs; no overwrite')
    partial=target.with_suffix(target.suffix+'.partial')
    run_cloud(['cp',source,str(partial)],deadline)
    if sha(partial)!=expected or (bytes_expected is not None and partial.stat().st_size!=bytes_expected): raise ValueError('Downloaded object integrity mismatch')
    partial.replace(target)

def fetch_inventory(index,root,deadline):
    data_index(index)
    root=Path(root)
    # Independent unique destinations only; all workers share one hard deadline.
    def fetch_item(item):
        fetch(item['uri'],root/'data'/item['path'],item['sha256'],deadline,item['bytes'])
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(fetch_item,index['files']))

def stage(config,root,deadline):
    root=Path(root).resolve(); root.mkdir(parents=True,exist_ok=True)
    fetch(config['index_uri'],root/'data-index.json',config['index_sha256'],deadline)
    index=data_index(json.loads((root/'data-index.json').read_text()))
    if index['campaign_sha256']!=config['campaign_sha256']: raise ValueError('Campaign identity mismatch')
    if sha(root/'tokenizer/tokenizer.pkl')!=TOKENIZER_SHA: raise ValueError('Wrong bundled tokenizer')
    if shutil.disk_usage(root).free<sum(x['bytes'] for x in index['files'])+20*1024**3: raise ValueError('Insufficient staging/checkpoint disk headroom')
    fetch_inventory(index,root,deadline)
    from cloud_training.nano_train import read_campaign
    campaign=read_campaign(root/'data'/index['campaign_path'])
    if sum(e['_rows'] for e in campaign['train'])*2048 < HORIZON*BATCH: raise ValueError('Full immutable 10B-token inventory required before retained pilot')
    resume=None
    if config['mode']=='resume':
        journal_uri=config['backup_prefix']+'/retention-journal.json'
        first=json.loads(run_cloud(['objects','describe',journal_uri,'--format=json'],deadline))
        raw=run_cloud(['cat',journal_uri],deadline)
        second=json.loads(run_cloud(['objects','describe',journal_uri,'--format=json'],deadline))
        if not first.get('generation') or first['generation']!=second.get('generation'): raise ValueError('Journal changed while reading')
        receipt=select_resume(json.loads(raw),config)
        resume=root/'resume'; resume.mkdir(exist_ok=False)
        for name in ('payload.pt','metadata.json','manifest.json','COMMITTED'):
            run_cloud(['cp',receipt['remote_prefix']+'/'+name,str(resume/name)],deadline)
        from cloud_training.nano_checkpoint import validate_bundle
        if validate_bundle(resume)!=receipt['manifest']: raise ValueError('Checkpoint differs from trusted receipt')
        metadata=json.loads((resume/'metadata.json').read_text())
        if metadata['identity']!=receipt['identity'] or metadata['step']!=config['resume_step']: raise ValueError('Resume metadata differs')
    return root/'data'/index['campaign_path'],resume

def worker(config,root,deadline):
    _,cadence=lease_controls(config)
    campaign,resume=stage(config,root,deadline-600)
    argv=[sys.executable,'-u','-m','cloud_training.nano_train','--campaign',str(campaign),'--repo',str(Path(root)/'nanochat-source'),'--output',str(Path(root)/'results'),'--backup-prefix',config['backup_prefix'],'--deadline-utc',dt.datetime.fromtimestamp(deadline,dt.timezone.utc).isoformat(),'--depth',str(config['depth']),'--microbatch',str(config['microbatch']),'--kernel-path',str(Path(root)/'kernel'),'--kernel-sha',config['kernel_sha256'],'--checkpoint-seconds',str(cadence)]
    argv+=['--tokenizer-dir',str(Path(root)/'tokenizer')]
    if resume: argv+=['--resume',str(resume)]
    if config.get('max_updates') is not None: argv+=['--max-updates',str(config['max_updates'])]
    for key in ('deterministic','deterministic_attention'):
        if config[key]: argv+=['--'+key.replace('_','-')]
    # Train handles TERM/update-boundary checkpoint; outer timeout guards hangs.
    return subprocess.call(['timeout','--signal=TERM','--kill-after=60s',str(max(1,int(deadline-time.time()))),*argv])

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('action',choices=['plan','worker']); p.add_argument('--config',required=True); p.add_argument('--ledger'); p.add_argument('--qualification'); p.add_argument('--price'); p.add_argument('--index'); p.add_argument('--root',default='.'); p.add_argument('--deadline',type=float)
    a=p.parse_args(); config=json.loads(Path(a.config).read_text())
    # Self-hash belongs to the plan envelope, never inside the hashed config.
    config['config_sha256']=sha(a.config)
    if a.action=='worker':
        if a.deadline is None: p.error('--deadline required')
        raise SystemExit(worker(config,a.root,a.deadline))
    load=lambda name:json.loads(Path(getattr(a,name)).read_text())
    print(json.dumps(build_plan(config,load('ledger'),load('qualification'),load('price'),load('index')),indent=2))

"""Verified own-base SFT development export; never release promotion or serving.

No model instantiation/device selection. Real export is explicit and CPU-only;
all preparation tests use tiny synthetic checkpoint fixtures.
"""
import os
for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','VECLIB_MAXIMUM_THREADS','MKL_NUM_THREADS'):
    os.environ[_key]='1'
from contextlib import contextmanager
from copy import deepcopy
import fcntl
import hashlib
import json
import math
from pathlib import Path
import resource
import shutil
import sys
import time
import torch
import checkpoint
import own_base_sft_train as trainer
from own_base_sft_control import WORK,valid_work
from base_run_control import _write
from tokenizer import ASSETS
ROOT=Path(__file__).resolve().parent
STATUS='candidate_for_development_not_release'
CPU_SECONDS=600;RSS_BYTES=3*1024**3;DISK_FLOOR=20*1024**3;OUTPUT_LIMIT=1024**3


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',', ':'),allow_nan=False).encode()

def digest(path,check=lambda:None):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):check();h.update(block)
    return h.hexdigest()


def own_path(path):
    p=Path(path)
    if not p.is_absolute() or p!=p.resolve() or not p.is_relative_to(ROOT) or any(x.is_symlink() for x in (p,*p.parents)):
        raise ValueError('artifact must be a canonical non-symlink own-root path')
    return p


def output_path(path):
    p=own_path(path)
    if p.parent!=ROOT/'own-base-candidates':raise ValueError('export must be a direct own-base-candidates child')
    return p


def pin(path,check=lambda:None):
    p=own_path(path)
    return dict(path=str(p),sha256=digest(p,check),bytes=p.stat().st_size)


def verify_pin(item,check=lambda:None):
    p=own_path(item['path']);check()
    if not p.is_file() or p.stat().st_size!=item['bytes'] or digest(p,check)!=item['sha256']:raise ValueError('pinned artifact changed')
    return p


@contextmanager
def lock(path,exclusive):
    path=own_path(path)
    if not path.is_file():raise ValueError('existing canonical lock required')
    with path.open('rb') as stream:
        fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB if exclusive else fcntl.LOCK_SH|fcntl.LOCK_NB)
        try:yield
        finally:fcntl.flock(stream,fcntl.LOCK_UN)


def state_shapes(config):
    if set(config)!={'vocabulary','context','width','heads','depth'} or any(type(x)!=int or x<=0 for x in config.values()):raise ValueError('invalid GPT2 config')
    v,c,w,h,d=(config[k] for k in ('vocabulary','context','width','heads','depth'))
    if w%h or c>1024:raise ValueError('unsupported GPT2 architecture')
    shapes={'tokens.weight':(v,w),'positions.weight':(c,w)}
    for i in range(d):
        prefix=f'blocks.{i}.'
        for name,shape in [('before_attention.weight',(w,)),('before_attention.bias',(w,)),('before_mlp.weight',(w,)),('before_mlp.bias',(w,)),('qkv.weight',(3*w,w)),('qkv.bias',(3*w,)),('attention_out.weight',(w,w)),('attention_out.bias',(w,)),('mlp.0.weight',(4*w,w)),('mlp.0.bias',(4*w,)),('mlp.2.weight',(w,4*w)),('mlp.2.bias',(w,))]:shapes[prefix+name]=shape
    shapes.update({'final_norm.weight':(w,),'final_norm.bias':(w,)})
    count=sum(math.prod(shape) for shape in shapes.values())
    if count>200_000_000:raise ValueError('parameter cap exceeded')
    return shapes,count


def verify_weights(state,config,check=lambda:None):
    shapes,count=state_shapes(config)
    if not isinstance(state,dict) or state.keys()!=shapes.keys():raise ValueError('bare GPT2 tensor inventory differs')
    for name,shape in shapes.items():
        check();value=state[name]
        if not isinstance(value,torch.Tensor) or value.device.type!='cpu' or tuple(value.shape)!=shape or value.dtype!=torch.float32 or not bool(torch.isfinite(value).all()):raise ValueError('invalid model tensor')
    return count


def verify_optimizer(opt,config,step,beta2,lr,check=lambda:None):
    shapes,_=state_shapes(config)
    groups=[[shape for shape in shapes.values() if len(shape)>=2],[shape for shape in shapes.values() if len(shape)<2]]
    if set(opt)!={'state','param_groups'} or len(opt['param_groups'])!=2:raise ValueError('optimizer inventory')
    ids=[]
    for index,(group,expected) in enumerate(zip(opt['param_groups'],groups)):
        if (tuple(group['betas'])!=(.9,beta2) or group['eps']!=1e-8 or group['weight_decay']!=(.1 if index==0 else 0.) or
            group.get('amsgrad',False) or group.get('maximize',False) or
            not math.isclose(group['lr'],lr,rel_tol=1e-12,abs_tol=0.) or len(group['params'])!=len(expected)):
            raise ValueError('fresh-selected-recipe optimizer hyperparameters differ')
        for pid,shape in zip(group['params'],expected):
            check();ids.append(pid);state=opt['state'][pid]
            if set(state)!={'step','exp_avg','exp_avg_sq'} or float(state['step'])!=step:raise ValueError('optimizer step/moment inventory')
            for name in ('exp_avg','exp_avg_sq'):
                value=state[name]
                if value.device.type!='cpu' or tuple(value.shape)!=shape or value.dtype!=torch.float32 or not bool(torch.isfinite(value).all()):raise ValueError('invalid optimizer moments')
            if bool((state['exp_avg_sq']<0).any()):raise ValueError('negative optimizer second moment')
    if len(set(ids))!=len(ids) or set(ids)!=set(opt['state']):raise ValueError('optimizer parameter identity mismatch')


def source_metadata(run,check=lambda:None):
    run=own_path(run)
    if run.parent!=ROOT/'runs':raise ValueError('canonical direct SFT run required')
    ledger=json.loads((run/'campaign.json').read_text());signature=ledger.pop('sha256')
    if hashlib.sha256(canonical(ledger)).hexdigest()!=signature:raise ValueError('SFT ledger checksum')
    frozen=json.loads((run/'campaign-spec.json').read_text())
    if ledger['spec']!=frozen or ledger['state']!='completed':raise ValueError('exact completed SFT campaign required')
    entry=ledger['checkpoints'][0]
    if not checkpoint.FILE_NAME.fullmatch(entry['file']) or Path(entry['file']).name!=entry['file']:raise ValueError('checkpoint filename')
    if entry!=json.loads((run/'latest.json').read_text())[0] or entry['file'] not in json.loads((run/'protected.json').read_text()):raise ValueError('endpoint must be latest and protected')
    artifact=dict(path=str(run/entry['file']),sha256=entry['sha256'],bytes=entry['bytes']);verify_pin(artifact,check)
    return ledger,frozen,entry


def verify_source(run,check=lambda:None):
    """SFT-specific verifier: reconstruct exact masked schedule, not base offsets."""
    run=own_path(run);check();ledger,frozen,entry=source_metadata(run,check);identity=frozen['identity'];spec=identity['protocol']
    for source_spec in spec['datasets']:
        for key in ('receipt','admission','verification'):own_path(source_spec[key]['path'])
    for key in ('hardware_preflight','optimizer_report','optimizer_experiment'):own_path(spec[key]['path'])
    for name,expected in ASSETS.items():
        if digest(own_path(ROOT/'data/tokenizer'/name),check)!=expected:raise ValueError('actual tokenizer asset differs')
    trainer.validate_launch(spec,run);check()
    parent,branch,parent_receipt=trainer.verified_parent(spec);check()
    parent_own=deepcopy(parent['identity']['initialization'])
    parent_mps=parent['mps_rng'].detach().clone()
    del parent  # Release full optimizer/weights before mapping the SFT endpoint.
    source=run/entry['file'];payload=torch.load(source,map_location='cpu',weights_only=True,mmap=True)
    if (payload['identity']!=identity or payload['campaign_id']!=ledger['campaign_id'] or payload['spec_sha256']!=hashlib.sha256(canonical(frozen)).hexdigest()):raise ValueError('SFT payload campaign identity differs')
    if any(frozen[k]!=spec[k] for k in ('active_seconds','calendar_seconds','lease_seconds')) or identity['seed']!=spec['seed'] or identity['corpus']!=spec['datasets'] or identity['scheduler']!=spec['scheduler']:raise ValueError('SFT protocol/campaign configuration mismatch')
    if identity['model']!=spec['model'] or identity['tokenizer']!=ASSETS or identity['torch_version']!=str(torch.__version__):raise ValueError('SFT model/tokenizer/torch identity')
    own=identity['initialization']
    if (identity['parent']!=parent_receipt or identity['optimizer_initialization']!='fresh_selected_beta2' or
        identity['beta2']!=trainer.BETAS[branch] or own.get('mode')!='own_pretraining' or
        own['path']!=str(Path(parent_receipt['run'])/parent_receipt['checkpoint']['file']) or own['sha256']!=parent_receipt['checkpoint']['sha256'] or
        not own.get('random_lineage_root') or own['random_lineage_root']!=parent_own['random_lineage_root']):raise ValueError('selected own-parent lineage mismatch')
    data=trainer.Sources(spec['datasets'],check=check);plan=trainer.updates(data,spec);steps=len(plan)
    if not steps or payload['step']!=steps or payload['cursor']!=steps or ledger['step']!=steps:raise ValueError('SFT endpoint data cursor not exact')
    expected={k:0 for k in WORK};by_source={s['name']:{k:0 for k in WORK} for s in spec['datasets']};positions=[0,0,0,0]
    for batch in plan:
        check();work=trainer.work_for(data,batch,spec['microbatch']);name=data.rows['train'][batch[0]]['_source']
        for k in WORK:expected[k]+=work[k];by_source[name][k]+=work[k]
        for index in batch:
            _,labels=data.row('train',index)
            for pos,label in enumerate(labels):
                if label!=-100:
                    if pos+1>=1024:raise ValueError('position beyond served context')
                    positions[(pos+1)//256]+=1
    if (payload['committed_work']!=expected or ledger['committed_work']!=expected or payload['trained_tokens']!=expected['assistant_targets'] or
        ledger['trained_tokens']!=expected['assistant_targets'] or payload['position_exposure']!=positions):raise ValueError('committed masked/input/position accounting differs')
    milestones=sorted({0,steps}|set(range(spec['validation_updates'],steps,spec['validation_updates'])))
    if [row['step'] for row in payload['history']]!=milestones:raise ValueError('incomplete development evaluation history')
    for item in payload['history']:
        if set(item['sources'])!=set(by_source):raise ValueError('development source inventory')
        for source_spec in spec['datasets']:
            name=source_spec['name'];indices=[i for i,row in enumerate(data.rows['validation']) if row['_source']==name][:source_spec['validation_rows']]
            cost=trainer.work_for(data,indices,spec['evaluation_microbatch'],'validation');observed=item['sources'][name]
            if (observed['targets']!=cost['evaluation_targets'] or observed['rows']!=len(indices) or observed['physical_split']!=source_spec['development_split'] or
                observed['precision']!='fp32' or not math.isfinite(observed['masked_ce']) or observed['masked_ce']<0):raise ValueError('invalid source development receipt')
            for k in WORK:by_source[name][k]+=cost[k]
    valid_work(ledger['reserved_work'])
    if (identity['work_limits']!=spec['work_limits'] or frozen['token_limit']!=spec['work_limits']['assistant_targets'] or
        identity['source_work_limits']!={s['name']:s['work_limits'] for s in spec['datasets']} or
        ledger['reserved_tokens']!=ledger['reserved_work']['assistant_targets'] or set(ledger['reserved_by_source'])!=set(by_source)):
        raise ValueError('immutable work ceiling/source identity differs')
    for source_spec in spec['datasets']:
        name=source_spec['name'];attempted=ledger['reserved_by_source'][name];valid_work(attempted)
        if any(not by_source[name][k]<=attempted[k]<=source_spec['work_limits'][k] for k in WORK):raise ValueError('source attempts outside required work/ceiling')
    if any(sum(v[k] for v in ledger['reserved_by_source'].values())!=ledger['reserved_work'][k] or ledger['reserved_work'][k]>spec['work_limits'][k] for k in WORK):raise ValueError('global/source attempted accounting differs')
    if not 0<=ledger['active_seconds']<=frozen['active_seconds']:raise ValueError('SFT active budget exceeded')
    count=verify_weights(payload['model'],identity['model'],check)
    verify_optimizer(payload['optimizer'],identity['model'],steps,identity['beta2'],trainer.learning_rate(steps-1,steps,spec['scheduler']),check)
    cpu=payload['cpu_rng'];mps=payload['mps_rng']
    if cpu.device.type!='cpu' or cpu.dtype!=torch.uint8 or cpu.ndim!=1:raise ValueError('invalid CPU RNG layout')
    torch.Generator(device='cpu').set_state(cpu)
    if mps.device.type!='cpu' or mps.dtype!=torch.uint8 or mps.ndim!=1 or mps.numel()==0 or mps.shape!=parent_mps.shape or parent_mps.dtype!=torch.uint8:raise ValueError('MPS RNG layout differs from verified own parent')
    verification=dict(steps=steps,committed_work=expected,attempted_work=ledger['reserved_work'],attempted_by_source=ledger['reserved_by_source'],position_exposure=positions,parameter_count=count,
                      cpu_rng_sha256=hashlib.sha256(cpu.numpy().tobytes()).hexdigest(),mps_rng_sha256=hashlib.sha256(mps.numpy().tobytes()).hexdigest(),
                      rng_scope='CPU Generator accepted state; MPS opaque CPU bytes match verified-parent layout under pinned torch. No MPS restoration executed.')
    lineage=dict(selected_parent=parent_receipt,random_lineage_root=own['random_lineage_root'])
    del parent_mps,data
    return payload,ledger,frozen,entry,verification,lineage


def proof_artifacts(run,spec,check=lambda:None):
    paths=set()
    def add(p):paths.add(own_path(p))
    def add_pin(value):
        if isinstance(value,dict):
            if 'path' in value and 'sha256' in value and isinstance(value['path'],str):add(value['path'])
            for child in value.values():add_pin(child)
        elif isinstance(value,list):
            for child in value:add_pin(child)
    for name in ('campaign.json','campaign-spec.json','latest.json','protected.json'):add(run/name)
    entry=json.loads((run/'latest.json').read_text())[0];add(run/entry['file'])
    add_pin(spec)
    for name in spec['code_sha256']:add(ROOT/name)
    for name in ASSETS:add(ROOT/'data/tokenizer'/name)
    for source in spec['datasets']:
        directory=Path(source['receipt']['path']).parent
        for split in ('train',source['development_split']):
            for suffix in ('inputs.u16','labels.u16','index.jsonl'):add(directory/f'{split}.{suffix}')
    report=json.loads(Path(spec['optimizer_report']['path']).read_text())
    for receipt in report['receipts'].values():
        path=own_path(receipt['run'])
        for name in ('campaign.json','campaign-spec.json','latest.json','protected.json','validation.json'):add(path/name)
        add(path/receipt['checkpoint']['file'])
    parent=report['common']['parent'];path=own_path(parent['run'])
    for name in ('campaign.json','campaign-spec.json','latest.json','protected.json'):add(path/name)
    add(path/parent['checkpoint'])
    import pretrained_base
    add(pretrained_base.PRE_SFT_REPORT)
    foundation=json.loads((path/'campaign-spec.json').read_text())['identity']['protocol']
    original=own_path(ROOT/foundation['parent_checkpoint']['path']);add(original)
    for name in ('config.json','status.json','protected.json'):add(original.parent/name)
    for name in ('watchdog.json','hardware-candidate.json','preflight-ledger.json','selection.json'):
        add(Path(spec['hardware_preflight']['path']).parent/name)
    return [pin(p,check) for p in sorted(paths)]


def export_candidate(run,destination):
    """Explicit CPU export, bounded and non-overwriting; never called by tests on real runs."""
    os.nice(10);torch.set_num_threads(1);started=time.monotonic();run=own_path(run);destination=output_path(destination)
    if destination.exists():raise FileExistsError('existing export directory refused')
    def check():
        if time.monotonic()-started>=CPU_SECONDS:raise RuntimeError('export CPU wall ceiling')
        peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
        if peak>RSS_BYTES:raise RuntimeError('export RSS ceiling')
        if any(p.exists() for p in (ROOT/'runs/STOP',run/'STOP',destination/'STOP')):raise RuntimeError('explicit STOP')
        if shutil.disk_usage(ROOT).free<DISK_FLOOR:raise RuntimeError('export disk floor')
        if destination.exists() and sum(p.stat().st_size for p in destination.iterdir() if p.is_file())>OUTPUT_LIMIT:raise RuntimeError('export output ceiling')
    check()
    with lock(ROOT/'runs/mps.lock',True),lock(run/'.checkpoint.lock',False):
        check();payload,ledger,frozen,entry,verification,lineage=verify_source(run,check)
        config=frozen['identity']['model'];_,count=state_shapes(config)
        if shutil.disk_usage(ROOT).free<DISK_FLOOR+count*4+64*1024**2:raise RuntimeError('export forecast lacks disk headroom')
        artifacts=proof_artifacts(run,frozen['identity']['protocol'],check)
        destination.parent.mkdir(exist_ok=True);destination.mkdir()
        temporary=destination/'.weights.tmp'
        try:
            _write(destination/'export-start.json',dict(status='export_started_not_admitted',source=str(run),source_checkpoint=entry,exporter_sha256=digest(__file__),limits=dict(seconds=CPU_SECONDS,rss_bytes=RSS_BYTES,output_bytes=OUTPUT_LIMIT)))
            check();torch.save({key:payload['model'][key] for key in state_shapes(config)[0]},temporary)
            with temporary.open('rb') as stream:os.fsync(stream.fileno())
            check();weight_sha=digest(temporary,check);weight_file=destination/f'weights-{weight_sha}.pt';temporary.replace(weight_file);checkpoint.sync_dir(destination)
            exported=torch.load(weight_file,map_location='cpu',weights_only=True,mmap=True)
            verify_weights(exported,config,check)
            for key in exported:
                check()
                if not torch.equal(exported[key],payload['model'][key]):raise ValueError('exported weights differ from source')
            del exported
            for artifact in artifacts:verify_pin(artifact,check)
            manifest=dict(schema=1,status=STATUS,model_config=config,parameter_count=count,tokenizer=ASSETS,torch_version=str(torch.__version__),weights=dict(file=weight_file.name,sha256=weight_sha,bytes=weight_file.stat().st_size),
                          source=dict(run=str(run),checkpoint=entry,ledger_sha256=digest(run/'campaign.json'),campaign_spec_sha256=digest(run/'campaign-spec.json')),
                          own_lineage=lineage,runtime_sha256=frozen['identity']['protocol']['code_sha256'],exporter_sha256=digest(__file__),proof_artifacts=artifacts,verification=verification,
                          limits=dict(seconds=CPU_SECONDS,rss_bytes=RSS_BYTES,output_bytes=OUTPUT_LIMIT),seconds=time.monotonic()-started,release_approved=False)
            check();_write(destination/'manifest.json',manifest);check()
            return dict(manifest=str(destination/'manifest.json'),manifest_sha256=digest(destination/'manifest.json'),status=STATUS)
        except BaseException as error:
            # Only the temporary file created by this invocation can be removed.
            temporary.unlink(missing_ok=True)
            _write(destination/'failure.json',dict(status='export_failed_not_admitted',error=type(error).__name__,reason=str(error),seconds=time.monotonic()-started))
            raise


def verify_candidate_manifest(manifest_path,expected_manifest_sha256,*,check=lambda:None):
    path=own_path(manifest_path);output_path(path.parent);check()
    if path.name!='manifest.json' or digest(path,check)!=expected_manifest_sha256 or (path.parent/'failure.json').exists():raise ValueError('candidate manifest changed/incomplete')
    manifest=json.loads(path.read_text())
    if manifest.get('schema')!=1 or manifest.get('status')!=STATUS or manifest.get('release_approved') is not False or manifest.get('exporter_sha256')!=digest(__file__,check):raise ValueError('unsupported/unverified development export')
    _,count=state_shapes(manifest['model_config'])
    if manifest['parameter_count']!=count or manifest['tokenizer']!=ASSETS or manifest['torch_version']!=str(torch.__version__):raise ValueError('candidate configuration/tokenizer/version changed')
    for name,expected in ASSETS.items():
        if digest(own_path(ROOT/'data/tokenizer'/name),check)!=expected:raise ValueError('tokenizer asset changed')
    run=own_path(manifest['source']['run'])
    with lock(run/'.checkpoint.lock',False):
        artifacts=manifest['proof_artifacts'];paths=[a['path'] for a in artifacts]
        if len(set(paths))!=len(paths):raise ValueError('duplicate proof artifact')
        for artifact in artifacts:verify_pin(artifact,check)
        ledger,frozen,entry=source_metadata(run,check)
        if artifacts!=proof_artifacts(run,frozen['identity']['protocol'],check):raise ValueError('source proof inventory incomplete or changed')
        if (entry!=manifest['source']['checkpoint'] or digest(run/'campaign.json',check)!=manifest['source']['ledger_sha256'] or
            digest(run/'campaign-spec.json',check)!=manifest['source']['campaign_spec_sha256'] or frozen['identity']['model']!=manifest['model_config'] or
            frozen['identity']['initialization']['random_lineage_root']!=manifest['own_lineage']['random_lineage_root'] or
            frozen['identity']['parent']!=manifest['own_lineage']['selected_parent']):raise ValueError('export source ancestry changed')
    weights=manifest['weights']
    if weights['file']!=f"weights-{weights['sha256']}.pt" or Path(weights['file']).name!=weights['file']:raise ValueError('unsafe exported weight filename')
    verify_pin(dict(path=str(path.parent/weights['file']),sha256=weights['sha256'],bytes=weights['bytes']),check)
    return manifest


def load_candidate(manifest_path,expected_manifest_sha256,*,check=lambda:None):
    manifest=verify_candidate_manifest(manifest_path,expected_manifest_sha256,check=check);path=Path(manifest_path).parent/manifest['weights']['file'];check()
    # Verify and deserialize the same descriptor, never reopen a verified pathname.
    path=own_path(path);expected=manifest['weights']
    with path.open('rb') as stream:
        before=os.fstat(stream.fileno())
        def verify_open_file():
            stream.seek(0);h=hashlib.sha256();size=0
            while chunk:=stream.read(1024*1024):
                check();h.update(chunk);size+=len(chunk)
            if size!=expected['bytes'] or h.hexdigest()!=expected['sha256']:raise ValueError('opened candidate weights changed')
        verify_open_file();stream.seek(0)
        state=torch.load(stream,map_location='cpu',weights_only=True)
        verify_open_file();after=os.fstat(stream.fileno());current=path.stat()
        if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns) or (after.st_dev,after.st_ino)!=(current.st_dev,current.st_ino):raise ValueError('candidate weights identity changed during load')
    verify_weights(state,manifest['model_config'],check)
    return state,manifest


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('run',type=Path);parser.add_argument('destination',type=Path);parser.add_argument('--export-reviewed',action='store_true');args=parser.parse_args()
    if not args.export_reviewed:parser.error('explicit reviewed export required; no promotion or launch')
    print(json.dumps(export_candidate(args.run,args.destination)))

"""Finite own-base SFT with exact resume and assistant-token-weighted loss.

Inputs must be explicitly admitted canonical JSONL conversations. This does not
admit data, provision a GPU, replace a base checkpoint, run Python tool frames or
claim conversation quality from language loss. Use a separately reserved lease.
"""
from __future__ import annotations
import argparse
import fcntl
import hashlib
import json
import math
import os
import re
from pathlib import Path
import signal
import subprocess
import sys
import time

if __package__ in (None,''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cloud_training.nano_benchmark import BATCH, PINNED_REVISION, atomic_json, deterministic_attention
from cloud_training.nano_chat_format import VERSION, encode_conversation
from cloud_training.nano_data import sha256_file
from cloud_training.nano_train import CloudJournal, deadline_timestamp, numerical_identity

NATIVE_IGNORE = -1  # Pinned nanochat GPT.forward, distinct from export labels -100.
SEQUENCE = 2048


def sft_schedule(progress, step):
    if not 0 <= progress <= 1 or step < 0:
        raise ValueError('Invalid SFT progress')
    return (1.0 if progress <= .5 else 2*(1-progress)), .85 + .10*min(step/300,1)


def batch_recipe(batch_tokens, microbatch):
    """Explicit position-token batch, not assistant-target batch; never repeats data."""
    if type(batch_tokens) is not int or not 32768<=batch_tokens<=BATCH or batch_tokens%SEQUENCE:
        raise ValueError("Effective batch must be32768..524288 and divisible by2048")
    rows=batch_tokens//SEQUENCE
    if type(microbatch) is not int or microbatch<1 or rows%microbatch:
        raise ValueError("Microbatch must divide effective batch rows")
    return {"batch_tokens":batch_tokens,"rows_per_update":rows,"lr_batch_scale":math.sqrt(batch_tokens/BATCH)}


def reset_sft_lrs(optimizer, fresh_lrs, batch_scale=1.0):
    """Fresh LR ×0.8×sqrt(batch/reference), retaining moments from the parent.

    Square-root scaling is an explicit conservative heuristic, not an assertion
    of equivalent AdamW/Muon dynamics; select targeted settings on held-out dev.
    """
    if isinstance(batch_scale,bool) or not isinstance(batch_scale,(int,float)) or not math.isfinite(batch_scale) or not 0<batch_scale<=1:
        raise ValueError("Invalid LR batch scale")
    if len(optimizer.param_groups)!=len(fresh_lrs):
        raise ValueError('Optimizer group mismatch')
    for group,lr in zip(optimizer.param_groups,fresh_lrs):
        group['lr']=group['initial_lr']=lr*.8*batch_scale
        if group.get('kind')=='muon':group['weight_decay']=0.0


def load_manifest(path, tokenizer_sha):
    path=Path(path).resolve();m=json.loads(path.read_text())
    if m.get('schema')!=1 or m.get('training_admitted') is not True or m.get('format_version')!=VERSION:
        raise ValueError('Admitted SFT manifest with exact format version required')
    if m.get('tokenizer_sha256')!=tokenizer_sha or m.get('context_tokens')!=SEQUENCE:
        raise ValueError('SFT tokenizer/context mismatch')
    admission=m.get('admission',{});receipt=path.parent/admission.get('receipt','')
    if not receipt.is_file() or sha256_file(receipt)!=admission.get('sha256'):
        raise ValueError('Missing/changed SFT admission receipt')
    review=json.loads(receipt.read_text())
    expected=[m.get(k,{}).get('sha256') for k in ('train','validation')]
    if (review.get('training_admitted') is not True or review.get('tokenizer_sha256')!=tokenizer_sha
        or review.get('format_version')!=VERSION or review.get('jsonl_sha256')!=expected):
        raise ValueError('SFT admission does not bind exact train/development files')
    if expected[0]==expected[1]:raise ValueError('Train/development files overlap')
    for split in ('train','validation'):
        item=m[split];file=(path.parent/item['file']).resolve()
        if sha256_file(file)!=item['sha256']:raise ValueError('Changed SFT JSONL')
        item['_file']=str(file)
    m['_sha256']=sha256_file(path)
    return m


class JsonlConversations:
    """Hash-bound offsets and lengths; full conversations are encoded on demand."""
    def __init__(self,path,tokenizer,expected_sha):
        self.path=Path(path);self.tokenizer=tokenizer;self.sha=expected_sha
        if sha256_file(path)!=expected_sha:raise ValueError('JSONL identity changed')
        self.offsets=[];self.lengths=[];self.target_counts=[];self.fingerprints=set();self.row_fingerprints=[]
        with self.path.open('rb') as f:
            while True:
                offset=f.tell();line=f.readline(1_048_577)
                if not line:break
                if len(line)>1_048_576:raise ValueError('Overlarge JSONL conversation')
                row=json.loads(line)
                rendered=self._render(row)
                fingerprint=hashlib.sha256(json.dumps({'messages':row['messages'],'policies':row.get('policies')},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
                if fingerprint in self.fingerprints:raise ValueError('Duplicate SFT conversation')
                self.fingerprints.add(fingerprint);self.row_fingerprints.append(fingerprint)
                self.offsets.append(offset);self.lengths.append(len(rendered['ids']))
                self.target_counts.append(sum(rendered['mask'][1:]))
        if not self.offsets:raise ValueError('Empty SFT dataset')

    def _render(self,row):
        if type(row)!=dict or 'messages' not in row:raise ValueError('Canonical conversation required')
        rendered=encode_conversation(self.tokenizer,row['messages'],policies=row.get('policies'),context=SEQUENCE)
        if not any(rendered['mask'][1:]):raise ValueError('No assistant supervision')
        return rendered

    def __len__(self):return len(self.offsets)

    def get(self,index):
        with self.path.open('rb') as f:
            f.seek(self.offsets[index]);row=json.loads(f.readline())
        fingerprint=hashlib.sha256(json.dumps({'messages':row['messages'],'policies':row.get('policies')},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        if fingerprint!=self.row_fingerprints[index]:raise ValueError('Conversation content changed since preflight')
        rendered=self._render(row)
        if len(rendered['ids'])!=self.lengths[index] or sum(rendered['mask'][1:])!=self.target_counts[index]:
            raise ValueError('Conversation changed since preflight')
        return rendered['ids'],rendered['mask']


class BestFitConversations:
    """Pinned best-fit algorithm, finite buffer100; no epoch wrap or truncation."""
    def __init__(self,dataset,*,capacity=2049,buffer_size=100):
        if capacity<2 or buffer_size<1 or any(n>capacity for n in dataset.lengths):
            raise ValueError('Conversation does not fit a complete row')
        self.dataset=dataset;self.capacity=capacity;self.buffer_size=buffer_size
        self.next_index=0;self.buffer=[];self.consumed=0;self.rows=0

    def state_dict(self):
        return {'dataset_sha256':self.dataset.sha,'next_index':self.next_index,'buffer':self.buffer.copy(),
                'consumed':self.consumed,'rows':self.rows,'capacity':self.capacity,'buffer_size':self.buffer_size}

    def load_state_dict(self,state):
        if state.get('dataset_sha256')!=self.dataset.sha or state.get('capacity')!=self.capacity or state.get('buffer_size')!=self.buffer_size:
            raise ValueError('SFT cursor identity mismatch')
        cursor,buf,consumed,rows=state.get('next_index'),state.get('buffer'),state.get('consumed'),state.get('rows')
        if type(cursor)is not int or not 0<=cursor<=len(self.dataset) or not isinstance(buf,list) or len(buf)>self.buffer_size:
            raise ValueError('Invalid SFT cursor')
        if any(type(i)is not int or not 0<=i<cursor for i in buf) or len(set(buf))!=len(buf) or type(consumed)is not int or consumed!=cursor-len(buf) or type(rows)is not int or rows<0:
            raise ValueError('Invalid pending conversation buffer')
        self.next_index,self.buffer,self.consumed,self.rows=cursor,buf.copy(),consumed,rows

    def next_indices(self):
        selected=[];remaining=self.capacity
        while remaining:
            while len(self.buffer)<self.buffer_size and self.next_index<len(self.dataset):
                self.buffer.append(self.next_index);self.next_index+=1
            fitting=[i for i in self.buffer if self.dataset.lengths[i]<=remaining]
            if not fitting:break
            chosen=max(fitting,key=lambda i:self.dataset.lengths[i])
            self.buffer.remove(chosen);selected.append(chosen)
            remaining-=self.dataset.lengths[chosen];self.consumed+=1
        if not selected:
            if self.buffer or self.next_index<len(self.dataset):raise ValueError('Unpackable complete conversation')
            raise StopIteration
        self.rows+=1
        return selected

    def next_row(self):
        ids=[];mask=[]
        for index in self.next_indices():
            x,m=self.dataset.get(index);ids.extend(x);mask.extend(m)
        n=self.capacity-len(ids)
        ids.extend([self.dataset.tokenizer.get_bos_token_id()]*n);mask.extend([0]*n)
        return ids[:-1],[token if supervised else NATIVE_IGNORE for token,supervised in zip(ids[1:],mask[1:])]


def count_packed_rows(dataset):
    packing=BestFitConversations(dataset)
    while True:
        try:packing.next_indices()
        except StopIteration:return packing.rows


def collect_update(packing, microbatch, rows_per_update=256):
    """CPU rows only; count all valid labels BEFORE any accumulated backward."""
    batches=[];finished=False
    for _ in range(math.ceil(rows_per_update/microbatch)):
        xs=[];ys=[]
        for _ in range(min(microbatch,rows_per_update-len(batches)*microbatch)):
            try:x,y=packing.next_row()
            except StopIteration:finished=True;break
            xs.append(x);ys.append(y)
        if not xs:break
        while len(xs)<microbatch:
            xs.append([packing.dataset.tokenizer.get_bos_token_id()]*(packing.capacity-1))
            ys.append([NATIVE_IGNORE]*(packing.capacity-1))
        batches.append((xs,ys))
        if finished:break
    count=sum(t!=NATIVE_IGNORE for _,ys in batches for row in ys for t in row)
    return batches,count


def backward_weighted(model,batches,total_targets,*,device,stop_check=lambda:False):
    """Global valid-target denominator; works with uneven/zero-target microbatches."""
    import torch
    if total_targets<=0:raise ValueError('Positive supervised target count required')
    actual=sum(t!=NATIVE_IGNORE for _,ys in batches for row in ys for t in row)
    if actual!=total_targets:raise ValueError('Assistant target denominator mismatch')
    summed=0.0
    for xs,ys in batches:
        if stop_check():raise InterruptedError('Lease/signal during SFT accumulation')
        x=torch.tensor(xs,dtype=torch.long,device=device);y=torch.tensor(ys,dtype=torch.long,device=device)
        loss=model(x,y,loss_reduction='sum')
        if not bool(torch.isfinite(loss)):raise FloatingPointError('Nonfinite SFT loss')
        (loss/total_targets).backward();summed+=float(loss.detach())
    return summed/total_targets


def evaluate_fixed(model,dataset,*,rows,microbatch,device):
    import torch
    from cloud_training.nano_checkpoint import capture_rng,restore_rng_state
    if type(rows)is not int or not 1<=rows<=512 or type(microbatch)is not int or microbatch<1:
        raise ValueError('Fixed development evaluation must use1..512rows and positive microbatch')
    rng=capture_rng();modes=[(m,m.training) for m in model.modules()]
    pack=BestFitConversations(dataset);losses=[];targets=0
    try:
        model.eval()
        with torch.inference_mode():
            while pack.rows<rows:
                batches,count=collect_update(pack,microbatch,min(rows-pack.rows,microbatch))
                if not batches:break
                for xs,ys in batches:
                    x=torch.tensor(xs,dtype=torch.long,device=device);y=torch.tensor(ys,dtype=torch.long,device=device)
                    loss=model(x,y,loss_reduction='sum')
                    if not bool(torch.isfinite(loss)):raise FloatingPointError('Nonfinite development loss')
                    losses.append(float(loss));targets+=sum(t!=NATIVE_IGNORE for row in ys for t in row)
        if not targets:raise ValueError('No development assistant targets')
        return {'purpose':'masked_development_loss_not_conversation_acceptance','rows':pack.rows,
                'assistant_targets':targets,'cross_entropy_nats':math.fsum(losses)/targets,'dataset_sha256':dataset.sha}
    finally:
        for module,mode in modes:module.training=mode
        restore_rng_state(rng)


def replace_best_pin(journal,new_uri):
    """Only unpin prior best after the new committed best is already journaled."""
    from copy import deepcopy
    value=deepcopy(journal)
    found=[e for e in value['entries'] if e['receipt']['remote_prefix']==new_uri]
    if len(found)!=1 or found[0]['state']!='committed' or 'best' not in found[0]['pins']:
        raise ValueError('New committed best must be published before replacing old pin')
    for entry in value['entries']:
        if entry['receipt']['remote_prefix']!=new_uri:
            entry['pins']=[p for p in entry['pins'] if p!='best']
    return value


def ensure_separate_output(base,output):
    base,output=Path(base).resolve(),Path(output).resolve()
    if output==base or output in base.parents or base in output.parents:
        raise ValueError('SFT output must be separate from immutable base bundle')
    return base,output


def validate_base_metadata(base,expected_manifest_sha,tokenizer_sha):
    from cloud_training.nano_checkpoint import validate_bundle
    base=Path(base).resolve();validate_bundle(base)
    if sha256_file(base/'manifest.json')!=expected_manifest_sha:raise ValueError('Base bundle identity mismatch')
    metadata=json.loads((base/'metadata.json').read_text());identity=metadata['identity']
    if identity.get('phase')!='base' or identity.get('initialization')!='own_random' or identity.get('revision')!=PINNED_REVISION:
        raise ValueError('Only an identified own random-initialized base is permitted')
    if identity.get('tokenizer_sha256')!=tokenizer_sha:raise ValueError('Base/tokenizer mismatch')
    cfg=identity.get('config',{});depth=cfg.get('n_layer')
    if metadata['step']<1:raise ValueError('Base must have retained training updates')
    if depth not in (12,16) or cfg!={'sequence_len':2048,'vocab_size':32768,'n_layer':depth,'n_embd':depth*64,
                                  'n_head':depth//2,'n_kv_head':depth//2,'window_pattern':'SSSL'}:
        raise ValueError('Unsupported own-base configuration')
    return metadata


def validate_parent_chain(parent, expected_sha, tokenizer_sha, *, stage, ancestors=()):
    """Verify every referenced immutable ancestor bundle, ending at own random base.

    Embedded identities alone are insufficient. Targeted warm-start requires all
    ancestor bundles locally; each edge binds an exact manifest hash + identity.
    Hashes establish integrity inside trusted project storage, not authenticity.
    """
    from cloud_training.nano_checkpoint import validate_bundle
    if stage not in ('general','targeted'): raise ValueError('Unknown SFT stage')
    locations={}
    for path in [parent,*ancestors]:
        path=Path(path).resolve();validate_bundle(path)
        key=sha256_file(path/'manifest.json')
        if key in locations: raise ValueError('Duplicate ancestor bundle')
        locations[key]=path
    if expected_sha not in locations or locations[expected_sha]!=Path(parent).resolve(): raise ValueError('Parent manifest mismatch')
    seen=set()
    def visit(key,expected_identity=None):
        if key in seen or len(seen)>=8: raise ValueError('Cyclic/overlong checkpoint lineage')
        if key not in locations: raise ValueError('Every ancestor bundle is required')
        seen.add(key);path=locations[key]
        meta=json.loads((path/'metadata.json').read_text());identity=meta['identity']
        if expected_identity is not None and identity!=expected_identity: raise ValueError('Ancestor identity mismatch')
        if meta['step']<1 or identity.get('revision')!=PINNED_REVISION or identity.get('tokenizer_sha256')!=tokenizer_sha:
            raise ValueError('Ancestor requires retained own-model updates and identical tokenizer/revision')
        if identity.get('phase')=='base':
            validate_base_metadata(path,key,tokenizer_sha)
            return meta,key
        if identity.get('phase')!='sft' or identity.get('format_version')!=VERSION:
            raise ValueError('Only own SFT/base lineage permitted')
        if not re.fullmatch('[0-9a-f]{64}',identity.get('source_manifest_sha256','')):
            raise ValueError('SFT ancestor requires dataset identity')
        parent_sha=identity.get('parent_bundle_manifest_sha256',identity.get('base_bundle_manifest_sha256'))
        parent_identity=identity.get('parent_identity',identity.get('base_identity'))
        if not isinstance(parent_identity,dict): raise ValueError('Missing parent identity')
        root,root_sha=visit(parent_sha,parent_identity)
        if identity.get('config')!=root['identity']['config']: raise ValueError('Ancestor architecture mismatch')
        if identity.get('base_bundle_manifest_sha256')!=root_sha or identity.get('base_identity')!=root['identity']:
            raise ValueError('SFT root provenance mismatch')
        return root,root_sha
    root,root_sha=visit(expected_sha)
    parent_meta=json.loads((Path(parent)/'metadata.json').read_text())
    wanted='base' if stage=='general' else 'sft'
    if parent_meta['identity']['phase']!=wanted: raise ValueError(stage+' stage requires '+wanted+' parent')
    if set(locations)!=seen: raise ValueError('Unused ancestor bundles rejected')
    return parent_meta,root,root_sha


def run(args):
    if args.deterministic:
        os.environ["CUBLAS_WORKSPACE_CONFIG"]=":4096:8"
    import torch
    from cloud_training.nano_checkpoint import save_bundle,load_bundle,capture_rng,restore_rng_state,validate_bundle
    from cloud_training.l4_recovery_check import upload_bundle
    from cloud_training.nano_retention import record_upload
    base,out=ensure_separate_output(args.base,args.output)
    tokenizer_dir=Path(args.tokenizer).resolve()
    if sha256_file(tokenizer_dir/'tokenizer.pkl')!=args.tokenizer_sha:raise ValueError('Tokenizer file identity mismatch')
    base_meta,root_meta,root_sha=validate_parent_chain(base,args.base_manifest_sha,args.tokenizer_sha,stage=args.stage,ancestors=args.ancestor)
    for ancestor in args.ancestor: ensure_separate_output(ancestor,out)
    recipe=batch_recipe(args.batch_tokens,args.microbatch)
    manifest=load_manifest(args.manifest,args.tokenizer_sha)
    if args.stage=='targeted' and manifest['_sha256']==base_meta['identity'].get('source_manifest_sha256'):
        raise ValueError('Targeted stage requires a distinct explicitly admitted dataset')
    repo=Path(args.repo).resolve()
    if subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()!=PINNED_REVISION or subprocess.check_output(['git','-C',str(repo),'status','--porcelain'],text=True).strip():
        raise ValueError('Pinned clean upstream checkout required')
    sys.path.insert(0,str(repo))
    from nanochat.tokenizer import RustBPETokenizer
    tok=RustBPETokenizer.from_directory(str(tokenizer_dir))
    train=JsonlConversations(manifest['train']['_file'],tok,manifest['train']['sha256'])
    dev=JsonlConversations(manifest['validation']['_file'],tok,manifest['validation']['sha256'])
    if train.fingerprints&dev.fingerprints:raise ValueError('Train/development conversation overlap')
    total_rows=count_packed_rows(train);horizon=math.ceil(total_rows/recipe["rows_per_update"])
    if horizon<2:raise ValueError('Finite SFT corpus too small for this schedule; no automatic replay or zero-LR-only run')
    if args.validate_only:
        print(json.dumps({'status':'admitted_inputs_verified_not_GPU_qualified','packed_rows':total_rows,
                          'planned_updates':horizon,'stage':args.stage,**recipe,'assistant_targets':sum(train.target_counts)},indent=2));return 0
    if not torch.__version__.startswith('2.9.') or not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise ValueError('Pinned torch2.9 CUDA BF16 required')
    import nanochat.flash_attention as attention
    if args.kernel_path:
        from kernels import get_local_kernel
        attention._fa3=get_local_kernel(Path(args.kernel_path),'flash_attn3').flash_attn_interface
        attention.HAS_FA3=True;attention.USE_FA3=attention._resolve_use_fa3()
    if args.deterministic:
        torch.use_deterministic_algorithms(True)
        torch.backends.cudnn.benchmark=False
        torch.backends.cudnn.deterministic=True
    attention_deterministic=bool(args.deterministic_attention or (args.deterministic and attention.USE_FA3))
    if attention_deterministic: deterministic_attention(attention)
    from nanochat.gpt import GPT,GPTConfig
    from nanochat.common import COMPUTE_DTYPE
    if COMPUTE_DTYPE!=torch.bfloat16:raise ValueError('BF16 activations required')
    torch.set_num_threads(args.cpu_threads)
    config=GPTConfig(**base_meta['identity']['config'])
    with torch.device('meta'):model=GPT(config)
    model.to_empty(device='cuda');model.init_weights();model.train()
    optimizer=model.setup_optimizer(unembedding_lr=.008,embedding_lr=.3,matrix_lr=.02,weight_decay=0.0,scalar_lr=.5)
    fresh_lrs=[g['lr'] for g in optimizer.param_groups]
    load_bundle(base,model=model,optimizer=optimizer,expected_identity=base_meta['identity'])
    reset_sft_lrs(optimizer,fresh_lrs,recipe["lr_batch_scale"])
    torch.manual_seed(args.seed);torch.cuda.manual_seed_all(args.seed)
    files=('nano_sft.py','nano_chat_format.py','nano_checkpoint.py','nano_train.py','nano_retention.py','l4_recovery_check.py')
    identity={'phase':'sft','stage':args.stage,'parent_bundle_manifest_sha256':args.base_manifest_sha,
              'parent_identity':base_meta['identity'],'revision':PINNED_REVISION,'config':vars(config),'tokenizer_sha256':args.tokenizer_sha,
              'format_version':VERSION,'base_bundle_manifest_sha256':root_sha,'base_identity':root_meta['identity'],
              'source_manifest_sha256':manifest['_sha256'],'horizon_updates':horizon,'packed_rows':total_rows,
              'batch_tokens':args.batch_tokens,'lr_batch_scale':recipe['lr_batch_scale'],
              'numerical_mode':numerical_identity(torch,attention_deterministic=attention_deterministic),'microbatch':args.microbatch,'seed':args.seed,'torch':torch.__version__,
              'attention':'fa3' if attention.USE_FA3 else 'sdpa','kernel_sha256':args.kernel_sha,
              'eval_rows':args.eval_rows,'eval_every_updates':args.eval_every_updates,
              'adapter_hashes':{f:sha256_file(Path(__file__).parent/f) for f in files}}
    packing=BestFitConversations(train);step=0;trained_targets=0;best_dev=None;best_step=None
    if args.resume:
        restored=load_bundle(args.resume,model=model,optimizer=optimizer,expected_identity=identity)
        step=restored['metadata']['step'];packing.load_state_dict(restored['data_state']['packing'])
        if restored['data_state']['next_batch']!=step:raise ValueError('SFT next-update mismatch')
        trained_targets=restored['metadata']['loop']['trained_targets'];best_dev=restored['metadata']['loop']['best_dev'];best_step=restored['metadata']['loop']['best_step']
    out.mkdir(parents=True,exist_ok=True)
    journal=CloudJournal(out/'retention-journal.json',campaign_prefix=args.backup_prefix,identity=identity,resume_step=step if args.resume else None)
    compiled=torch.compile(model,dynamic=False)
    deadline=deadline_timestamp(args.deadline_utc);cutoff=deadline-args.checkpoint_reserve_seconds
    if time.time()>=cutoff:raise ValueError('Insufficient lease after preflight')
    interrupted=[]
    def handle(sig,frame):interrupted.append(sig)
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,handle)
    def stopping():return bool(interrupted) or time.time()>=cutoff
    max_step=min(horizon,step+args.max_updates) if args.max_updates else horizon
    status={'status':'running','identity':identity,'step':step,'assistant_targets':trained_targets}
    last_save=time.monotonic();last_saved=step if args.resume else None
    def checkpoint(reason,pin=False):
        nonlocal last_save,last_saved
        if last_saved==step:return
        journal.deadline=time.monotonic()+min(args.checkpoint_reserve_seconds,deadline-time.time())
        path=out/f'step-{step:08d}'
        save_bundle(path,model=model,optimizer=optimizer,metadata={'step':step,'identity':identity,'reason':reason,
                   'loop':{'trained_targets':trained_targets,'best_dev':best_dev,'best_step':best_step}},
                   data_state={'exact':True,'next_batch':step,'packing':packing.state_dict()})
        journal.set_phase('checkpoint_upload_in_progress',step=step)
        receipt=upload_bundle(path,remote_prefix=args.backup_prefix,timeout=min(args.checkpoint_reserve_seconds,journal.deadline-time.monotonic()))
        pins=(['final'] if step==horizon else [])+(['best'] if step==best_step else [])
        record_upload(journal.path,receipt,campaign_prefix=args.backup_prefix,pins=pins)
        journal.set_phase('ready')
        # Publish the new best before unpinning the old best; at most one best is retained.
        if step==best_step:
            data=replace_best_pin(json.loads(journal.path.read_text()),receipt['remote_prefix'])
            atomic_json(journal.path,data);journal.persist()
        if deadline-time.time()>args.checkpoint_reserve_seconds and journal.deadline-time.monotonic()>60:
            status['retention']=journal.prune(timeout=min(180,max(1,journal.deadline-time.monotonic()-30)))
        status['last_checkpoint']={'step':step,'path':str(path),'upload':receipt}
        atomic_json(out/'progress.json',status)
        journal.deadline=None;last_save=time.monotonic();last_saved=step
        import shutil
        local=sorted(out.glob('step-[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]'))
        for old in local[:-2]:
            if int(old.name.split('-')[1])!=best_step:
                validate_bundle(old);shutil.rmtree(old)
    if not stopping():
        status['development_start']=evaluate_fixed(model,dev,rows=args.eval_rows,microbatch=args.microbatch,device=next(model.parameters()).device)
        initial_dev=status['development_start']['cross_entropy_nats']
        if best_dev is None or initial_dev<best_dev:best_dev,best_step=initial_dev,step
    if not args.resume:checkpoint('initial_warm_started_sft')
    reason='dataset_complete' if max_step==horizon else 'pilot_update_limit'
    while step<max_step:
        if stopping():reason='lease_or_signal';break
        cursor,rng=packing.state_dict(),capture_rng()
        batches,count=collect_update(packing,args.microbatch,recipe["rows_per_update"])
        if not batches:reason='dataset_complete';break
        torch.cuda.synchronize();tick=time.monotonic()
        try:
            loss=backward_weighted(compiled,batches,count,device=next(model.parameters()).device,stop_check=stopping)
            torch.nn.utils.get_total_norm([p.grad for p in model.parameters() if p.grad is not None],error_if_nonfinite=True)
        except (InterruptedError,FloatingPointError,RuntimeError) as error:
            model.zero_grad(set_to_none=True);packing.load_state_dict(cursor);restore_rng_state(rng)
            reason='lease_or_signal' if isinstance(error,InterruptedError) else 'training_failure'
            status['error']=str(error);break
        lr,momentum=sft_schedule(cursor["consumed"]/len(train),step)
        for group in optimizer.param_groups:
            group['lr']=group['initial_lr']*lr
            if group['kind']=='muon':group['momentum']=momentum;group['weight_decay']=0.0
        optimizer.step();model.zero_grad(set_to_none=True);torch.cuda.synchronize()
        step+=1;trained_targets+=count
        status.update(step=step,assistant_targets=trained_targets,train_loss=loss,
                      consumed_conversations=packing.consumed,packed_rows=packing.rows,update_seconds=time.monotonic()-tick)
        new_best=False
        if (step%args.eval_every_updates==0 or step==max_step) and not stopping():
            ev=evaluate_fixed(model,dev,rows=args.eval_rows,microbatch=args.microbatch,device=next(model.parameters()).device)
            status['development']=ev
            if best_dev is None or ev['cross_entropy_nats']<best_dev:
                best_dev,best_step=ev['cross_entropy_nats'],step;new_best=True
        with (out/'updates.jsonl').open('a') as f:f.write(json.dumps(status,allow_nan=False)+'\n')
        atomic_json(out/'progress.json',status)
        if new_best or time.monotonic()-last_save>=args.checkpoint_seconds:checkpoint('development_best' if new_best else 'periodic')
    checkpoint(reason,pin=step==horizon)
    status.update(status='complete' if step==horizon else 'stopped',reason=reason,
                  step=step,assistant_targets=trained_targets,best_development_loss=best_dev,best_development_step=best_step,
                  acceptance='Not evaluated by this worker; use independent actual conversation/tool tests.')
    atomic_json(out/'result.json',status)
    return 2 if reason=='training_failure' else 0


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('manifest','base','base-manifest-sha','tokenizer','tokenizer-sha','repo','output'):
        p.add_argument('--'+name,required=True)
    p.add_argument('--validate-only',action='store_true')
    p.add_argument('--stage',choices=('general','targeted'),default='general')
    p.add_argument('--ancestor',action='append',default=[],help='Each immutable ancestor bundle required for targeted SFT lineage')
    p.add_argument('--batch-tokens',type=int,default=BATCH,help='Effective position tokens/update;32768 recommended initial targeted experiment')
    p.add_argument('--deterministic',action='store_true')
    p.add_argument('--deterministic-attention',action='store_true')
    p.add_argument('--resume');p.add_argument('--backup-prefix');p.add_argument('--deadline-utc')
    p.add_argument('--kernel-path');p.add_argument('--kernel-sha')
    p.add_argument('--microbatch',type=int,default=4);p.add_argument('--cpu-threads',type=int,default=4)
    p.add_argument('--seed',type=int,default=103);p.add_argument('--max-updates',type=int)
    p.add_argument('--eval-rows',type=int,default=128);p.add_argument('--eval-every-updates',type=int,default=200)
    p.add_argument('--checkpoint-seconds',type=int,default=900);p.add_argument('--checkpoint-reserve-seconds',type=int,default=300)
    a=p.parse_args()
    try: batch_recipe(a.batch_tokens,a.microbatch)
    except ValueError as error: p.error(str(error))
    if min(a.cpu_threads,a.eval_rows,a.eval_every_updates,a.checkpoint_seconds,a.checkpoint_reserve_seconds)<1:
        p.error('Invalid batch/interval settings')
    if a.eval_rows>512:p.error('Development loss budget capped at512rows')
    if a.max_updates is not None and a.max_updates<1:p.error('Positive max-updates required')
    if bool(a.kernel_path)!=bool(a.kernel_sha):p.error('Kernel path and hash required together')
    if not a.validate_only:
        if not a.deadline_utc or not a.backup_prefix:p.error('Reserved lease deadline and backup-prefix required')
        if not a.checkpoint_reserve_seconds<deadline_timestamp(a.deadline_utc)-time.time()<=21600:p.error('Deadline must allow reserve and be within6hours')
    os.environ.setdefault('HF_HUB_OFFLINE','1');os.environ.setdefault('WANDB_MODE','disabled')
    os.environ.setdefault('PYTORCH_ALLOC_CONF','expandable_segments:True')
    _,out=ensure_separate_output(a.base,a.output)
    for ancestor in a.ancestor: ensure_separate_output(ancestor,out)
    out.mkdir(parents=True,exist_ok=True)
    with (out/'.writer.lock').open('a+b') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        return run(a)


if __name__=='__main__':raise SystemExit(main())

"""Finite reviewed-data reference pilots. No downloads, teacher calls or cloud launch."""
from contextlib import ExitStack
from dataclasses import asdict,fields
import json
import os
import re
from pathlib import Path
import shutil
import tempfile
import time
import numpy as np
from slm.common.config import Config,initialize
from slm.common.training import Trainer,Recipe,recipe_from_state
from slm.common.curriculum import CurriculumTrainer
from slm.common.tokenizer import BPE
from slm.data.tokenized import ShardBatches,sha,stamp,document_tokens,example_format
from slm.data.mixture import MixtureBatches
from slm.data.curriculum import CurriculumBatches
from slm.data.review_stream import open_checked
from slm.data.schema import digest


def read(path):
    def pairs(items):
        result={}
        for k,v in items:
            if k in result:raise ValueError('Duplicate JSON field')
            result[k]=v
        return result
    with Path(path).open('rb') as f:data=f.read(16*1024*1024+1)
    if len(data)>16*1024*1024:raise ValueError('Bounded pilot metadata required')
    return json.loads(data,object_pairs_hook=pairs,parse_constant=lambda v:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def resolve_paths(spec,base):
    # Saved specs use absolute host bindings; logical identity contains hashes, not paths.
    spec=json.loads(json.dumps(spec));base=Path(base)
    if not isinstance(spec,dict) or not {'tokenizer','releases','data'}<=set(spec) or not isinstance(spec['releases'],dict) or not isinstance(spec['data'],dict):
        raise ValueError('Complete pilot path bindings required')
    def path(value):
        p=Path(value);return str((base/p).resolve() if not p.is_absolute() else p.resolve())
    spec['tokenizer']=path(spec['tokenizer']);spec['releases']={k:path(v) for k,v in spec['releases'].items()}
    data=spec['data'];data['path']=path(data['path'])
    if data['kind']=='mixture':data['bindings']={k:path(v) for k,v in data['bindings'].items()}
    elif data['kind']=='curriculum':
        data['bindings']={k:{'path':path(v['path']),'components':{c:path(p) for c,p in v['components'].items()}} for k,v in data['bindings'].items()}
    return spec


def integer(value,low=1,high=2**53-1):
    if type(value) is not int or not low<=value<=high:raise ValueError('Bounded integer setting required')
    return value


def write(path,value):
    path=Path(path);temp=path.with_name('.'+path.name+'.tmp')
    with temp.open('x') as f:
        json.dump(value,f,sort_keys=True,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(temp,path)
    fd=os.open(path.parent,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)


def leaves(data):
    if isinstance(data,ShardBatches):return [data]
    if isinstance(data,MixtureBatches):return data.inventory.data
    return [part for mixed in data.inventory.data for part in mixed.inventory.data]


def open_data(spec,tokenizer):
    kind=spec.get('kind');required={'kind','path','fingerprint'}|({'bindings'} if kind in ('mixture','curriculum') else set())
    if set(spec)!=required:raise ValueError('Explicit data binding fields required')
    if kind=='tokens':return ShardBatches(spec['path'],tokenizer,spec['fingerprint'])
    if kind=='mixture':return MixtureBatches(spec['path'],spec['bindings'],tokenizer,spec['fingerprint'])
    if kind=='curriculum':return CurriculumBatches(spec['path'],spec['bindings'],tokenizer,spec['fingerprint'])
    raise ValueError('Unknown pilot data kind')


def verify_leaf(leaf,approved,bpe):
    """Re-encode approved content: rehashed masks/arrays alone cannot invent training data."""
    index=0;buffer=[];encoded=0
    approved.clear_seen()
    def check(tokens,mask):
        nonlocal index
        if index>=len(leaf):raise ValueError('Reviewed stream exceeds token batches')
        wanted=(tokens[:-1],tokens[1:],mask[1:]);actual=leaf[index]
        if any(not np.array_equal(a[0],b) for a,b in zip(actual,wanted)):
            raise ValueError('Token payload differs from reviewed source content')
        index+=1
    with (leaf.path/'lineage.jsonl').open() as f:
        for line in f:
            r=json.loads(line);id=r['example_id'];e=approved.get(id)
            if not approved.claim(id) or e is None:raise ValueError('Unapproved or repeated leaf record identity')
            expected={'record_sha256':digest(e),'content_sha256':digest(e['messages']),'source':e['source'],
                'source_revision':e['source_revision'],'parent_group_id':e['parent_group_id'],
                'split_group':e['validation_results']['split_group'],'split':'train'}
            if any(r.get(k)!=v for k,v in expected.items()):raise ValueError('Leaf lineage differs from approved release')
            m=leaf.manifest
            if e['content_category'] not in m['allowed_categories'] or (m.get('allowed_sources') is not None and e['source'] not in m['allowed_sources']):
                raise ValueError('Leaf source/category filter differs')
            if example_format(e)!=leaf.message_format:raise ValueError('Leaf message format differs')
            result,reason=document_tokens(bpe,e,m['objective'],m['context_length'])
            if reason:raise ValueError('Ineligible reviewed record in leaf')
            tokens,mask=result;contribution=len(tokens)-int(m['objective']=='sft' or encoded==0)
            counts=(len(tokens),contribution,contribution if m['objective']=='foundation' else sum(mask[1:]))
            if counts!=(r['encoded_positions'],r['prediction_positions'],r['supervised_positions']):raise ValueError('Leaf record token accounting differs')
            encoded+=len(tokens)
            if m['objective']=='sft':check(tokens,mask)
            else:
                buffer.extend(tokens);context=m['context_length'];start=0
                while len(buffer)-start>context:
                    chunk=buffer[start:start+context+1];check(chunk,[0]+[1]*context);start+=context
                buffer=buffer[start:]
    if leaf.manifest['objective']=='foundation' and len(buffer)>1:check(buffer,[0]+[1]*(len(buffer)-1))
    if not encoded or index!=len(leaf):raise ValueError('Unreviewed extra token batches')


class Inputs:
    def __init__(self,spec):
        self.stack=ExitStack();self.guards={}
        try:
            required={'version','config','recipe','seed','tokenizer','data','releases','limits','checkpoint','scope'}
            if set(spec)!=required or type(spec['version']) is not int or spec['version']!=1:raise ValueError('Complete versioned pilot specification required')
            if spec['scope'] not in ('synthetic_mechanics','language_pilot'):raise ValueError('Explicit run scope required')
            if set(spec['recipe'])!={f.name for f in fields(Recipe)}:raise ValueError('Complete explicit recipe required')
            for name in ('lr','beta1','beta2','eps','decay','clip'):
                if type(spec['recipe'][name]) not in (int,float):raise ValueError('Numeric recipe settings required')
            self.config=Config(**spec['config']);self.recipe=Recipe(**spec['recipe']);integer(spec['seed'],0,2**32-1)
            if set(spec['limits'])!={'updates','processed_positions'}:raise ValueError('Finite cumulative ceilings required')
            for v in spec['limits'].values():integer(v)
            if set(spec['checkpoint'])!={'every_updates','keep'}:raise ValueError('Explicit checkpoint cadence/retention required')
            integer(spec['checkpoint']['every_updates']);integer(spec['checkpoint']['keep'],2,100)
            self.data=self.stack.enter_context(open_data(spec['data'],spec['tokenizer']))
            if self.data.vocab_size!=self.config.vocab_size or self.data.max_length>self.config.max_seq_len:raise ValueError('Pilot vocabulary/context mismatch')
            if isinstance(self.data,CurriculumBatches) and self.recipe!=self.data.base_recipe:raise ValueError('Pilot recipe differs from curriculum')
            bpe=BPE.load(spec['tokenizer']);parts=leaves(self.data)
            if not isinstance(spec['releases'],dict) or set(spec['releases'])!={d.manifest['release_manifest_sha256'] for d in parts}:
                raise ValueError('Every leaf needs its exact reviewed release')
            approved={};self.research_limits=None
            for fingerprint,path in spec['releases'].items():
                root=Path(path)
                if sha(root/'manifest.json')!=fingerprint:raise ValueError('Reviewed release fingerprint differs')
                approved[fingerprint]=self.stack.enter_context(open_checked(root))
                if getattr(approved[fingerprint],'research_limits',None):self.research_limits=approved[fingerprint].research_limits
                self.pin_tree(root)
            if self.research_limits:
                caps=self.research_limits
                if (len(approved)!=1 or len(parts)!=1 or isinstance(self.data,CurriculumBatches)
                    or spec['scope']!='language_pilot' or parts[0].manifest['objective']!='foundation'
                    or self.config.parameter_count>caps['max_parameters']
                    or any(spec['limits'][k]>caps[k] for k in ('updates','processed_positions'))):
                    raise ValueError('Bounded research scope/objective/model/training limit exceeded')
                if isinstance(self.data,MixtureBatches) and any(c['max_passes']>caps['max_passes'] for c in self.data.manifest['components']):
                    raise ValueError('Research repeat-exposure limit exceeded')
            for part in parts:verify_leaf(part,approved[part.manifest['release_manifest_sha256']],bpe)
            self.pin_tree(Path(spec['tokenizer']))
            self.plan={'version':1,'config':self.config.to_dict(),'recipe':asdict(self.recipe),'seed':spec['seed'],
                'initialization':'canonical-random-fp32-v1','tokenizer_hash':self.data.tokenizer_hash,
                'data_hash':self.data.fingerprint,'data_kind':spec['data']['kind'],'release_hashes':sorted(approved),
                'limits':spec['limits'],'checkpoint':spec['checkpoint'],'scope':spec['scope'],
                'reference_sources':{str(p.relative_to(Path(__file__).parent)):sha(p) for p in
                    [Path(__file__),*[Path(__file__).parent/name for name in ('common/training.py','common/curriculum.py','common/config.py',
                        'common/checkpoint.py','common/tokenizer.py','common/tool_serialization.py','common/supervision.py',
                        'data/tokenized.py','data/mixture.py','data/curriculum.py','data/review.py','data/review_stream.py','data/research_admission.py',
                        'data/context.py','data/foundation_research.py','data/dialogue_language.py','data/dialogue_screen.py','data/quality_audit.py','data/build.py','data/staging.py',
                        'backends/torch_backend.py','backends/mlx_backend.py','eval/stage.py','eval/conversation.py')]]}}
            for name in self.plan['reference_sources']:
                path=Path(__file__).parent/name;self.guards[path.resolve()]=stamp(path)
            self.identity=digest(self.plan);self.check()
        except BaseException:self.stack.close();raise
    def pin_tree(self,root):
        self.guards[root.resolve()]=stamp(root)
        for p in root.rglob('*'):self.guards[p.resolve()]=stamp(p)
    def check(self):
        for p,before in self.guards.items():
            if stamp(p)!=before:raise ValueError('Reviewed release/tokenizer changed during pilot')
        self.data.counts(0)
    def close(self):self.stack.close()


def verify_checkpoint(path,inputs):
    path=Path(path)
    if {p.name for p in path.iterdir()}!={'manifest.json','binding.json','state'}:raise ValueError('Pilot checkpoint file set differs')
    manifest=read(path/'manifest.json')
    if set(manifest)!={'binding.json','state/manifest.json'}:raise ValueError('Invalid pilot checkpoint wrapper')
    for name,want in manifest.items():
        if sha(path/name)!=want:raise ValueError('Pilot checkpoint wrapper checksum differs')
    binding=read(path/'binding.json')
    if set(binding)!={'version','plan','plan_hash','passed_gates'} or type(binding['version']) is not int or binding['version']!=1 or binding['plan_hash']!=inputs.identity or binding['plan']!=inputs.plan:
        raise ValueError('Pilot resume plan/config/recipe/data/seed differs')
    hashes=read(path/'state/manifest.json')
    expected={'model/config.json','model/model.safetensors','model/manifest.json','optimizer.safetensors','state.json'}
    if set(hashes)!=expected or {str(p.relative_to(path/'state')) for p in (path/'state').rglob('*') if p.is_file()}!={*expected,'manifest.json'}:raise ValueError('Invalid training state manifest')
    for name,want in hashes.items():
        if sha(path/'state'/name)!=want:raise ValueError('Training checkpoint checksum differs')
    state=read(path/'state/state.json');cls=CurriculumTrainer if isinstance(inputs.data,CurriculumBatches) else Trainer
    recipe=recipe_from_state(state);cls._validate_state(state,inputs.data,recipe)
    if recipe!=inputs.recipe or state['tokenizer_hash']!=inputs.data.tokenizer_hash or state['dataset_hash']!=inputs.data.fingerprint:
        raise ValueError('Checkpoint data/recipe/tokenizer differs')
    from slm.common.checkpoint import load
    config,weights=load(path/'state/model')
    if config!=inputs.config:raise ValueError('Checkpoint architecture differs')
    from safetensors.numpy import load_file
    raw=load_file(str(path/'state/optimizer.safetensors'))
    wanted={f'{slot}:{k}' for k in weights for slot in ('m','v')} if state['step'] else set()
    if set(raw)!=wanted:raise ValueError('Incomplete optimizer state')
    for name,value in raw.items():
        if value.shape!=weights[name.split(':',1)[1]].shape or value.dtype!=np.float32 or not np.isfinite(value).all() or (name.startswith('v:') and (value<0).any()):
            raise ValueError('Invalid optimizer tensor before restore')
    passed=binding['passed_gates']
    if not isinstance(passed,dict):raise ValueError('Invalid passed-stage inventory')
    if isinstance(inputs.data,CurriculumBatches):
        progress=inputs.data.progress(state['cursor']);completed=[r['id'] for r in progress['stages'] if r['status']=='complete']
        active=next((r for r in progress['stages'] if r['status']=='active'),None)
        required=completed if active and active['cursor'] else completed[:-1]
        if not set(passed)<=set(completed) or not set(required)<=set(passed):raise ValueError('Checkpoint bypasses an unreviewed stage exit')
    elif passed:raise ValueError('Non-curriculum checkpoint has stage gates')
    return binding,state


def stage_gate(bundle,model_hash,inputs):
    from slm.eval.stage import assess
    required={'suite','result','policy','suite_review','output_review','baseline','baseline_review'}
    if set(bundle)!=required:raise ValueError('Complete stage evidence bindings required')
    docs={k:read(p) if p is not None else None for k,p in bundle.items()}
    identity=docs['result']['identity']
    if (identity.get('model_manifest_sha256')!=model_hash or identity.get('tokenizer_manifest_sha256')!=inputs.data.tokenizer_hash
        or identity.get('architecture')!=inputs.config.to_dict() or identity.get('decoding')!='raw-cached-greedy-v1'
        or identity.get('embedding_implementation')!=inputs.recipe.embedding_implementation):raise ValueError('Stage result is not bound to the current student checkpoint')
    root=Path(__file__).parent
    if identity.get('inference_sha256')!=sha(root/'inference/greedy.py') or identity.get('backend_sha256') not in (sha(root/'backends/torch_backend.py'),sha(root/'backends/mlx_backend.py')):
        raise ValueError('Stage result lacks reference student decoder provenance')
    result=assess(docs['suite'],docs['result'],docs['policy'],suite_review=docs['suite_review'],output_review=docs['output_review'],baseline=docs['baseline'],baseline_review=docs['baseline_review'])
    return {'decision':result['decision'],'model_hash':model_hash,'result_hash':digest(result),
        'evidence_hashes':{k:sha(p) if p is not None else None for k,p in bundle.items()}}


def synchronize(backend,device):
    if backend=='mlx':
        import mlx.core as mx
        mx.synchronize()
    elif device.startswith('cuda'):
        import torch
        torch.cuda.synchronize(device)


def save_checkpoint(output,trainer,inputs,passed_gates):
    root=output/'checkpoints';root.mkdir(exist_ok=True)
    destination=root/f'{trainer.step:012d}-{digest(passed_gates)[:12]}'
    if destination.exists():
        verify_checkpoint(destination,inputs);return destination
    temp=Path(tempfile.mkdtemp(prefix='.pilot-',dir=root))
    try:
        trainer.save(temp/'state')
        write(temp/'binding.json',{'version':1,'plan':inputs.plan,'plan_hash':inputs.identity,'passed_gates':passed_gates})
        write(temp/'manifest.json',{'binding.json':sha(temp/'binding.json'),'state/manifest.json':sha(temp/'state/manifest.json')})
        verify_checkpoint(temp,inputs);os.rename(temp,destination)
        fd=os.open(root,os.O_RDONLY)
        try:os.fsync(fd)
        finally:os.close(fd)
        write(output/'latest.json',{'checkpoint':str(destination.relative_to(output)),'manifest_sha256':sha(destination/'manifest.json'),'step':trainer.step})
        complete=[p for p in root.iterdir() if p.is_dir() and re.fullmatch(r'[0-9]{12}-[a-f0-9]{12}',p.name) and not p.is_symlink()]
        for p in complete:verify_checkpoint(p,inputs)
        complete.sort(key=lambda p:(int(p.name[:12]),len(read(p/'binding.json')['passed_gates']),p.name))
        for old in complete[:-inputs.plan['checkpoint']['keep']]:
            # Only complete, same-plan checkpoints created in this attempt can be pruned.
            verify_checkpoint(old,inputs);shutil.rmtree(old)
    except BaseException:shutil.rmtree(temp,ignore_errors=True);raise
    return destination


def run(spec,output,*,backend='torch',device='cpu',resume=None,max_new_updates=1000000,wall_seconds=3600.,gates=None):
    output=Path(output).resolve();gates={} if gates is None else {key:{k:str(Path(v).resolve()) if v is not None else None for k,v in bundle.items()} for key,bundle in gates.items()}
    integer(max_new_updates)
    if type(wall_seconds) not in (int,float) or not np.isfinite(wall_seconds) or wall_seconds<=0:raise ValueError('Positive finite soft wall limit required')
    if backend not in ('torch','mlx') or (backend=='mlx' and device!='default') or (backend=='torch' and device!='cpu' and not device.startswith('cuda')):
        raise ValueError('Explicit torch cpu/cuda or mlx default device required; no fallback')
    if output.exists():raise FileExistsError(output)
    spec=resolve_paths(spec,Path.cwd())
    started=time.perf_counter();inputs=Inputs(spec);trainer=None;latest=None;passed={};events=None;created=False
    timing={'preflight':time.perf_counter()-started,'initialization_restore':0.,'updates':0.,'checkpoints':0.,'evaluation':0.}
    try:
        if inputs.research_limits and device.startswith('cuda'):raise ValueError('This research admission permits local MLX/CPU only; no CUDA training authorization')
        roots=[Path(spec['tokenizer']),*[Path(p) for p in spec['releases'].values()],*[p.path for p in leaves(inputs.data)],inputs.data.path]
        if resume:roots.append(Path(resume))
        target=output.resolve()
        for root in roots:
            root=root.resolve()
            if target==root or root in target.parents or target in root.parents:raise ValueError('Output overlaps immutable input/checkpoint')
        stage_ids={s['id'] for s in inputs.data.manifest['stages']} if isinstance(inputs.data,CurriculumBatches) else set()
        if not isinstance(gates,dict) or not set(gates)<=stage_ids:raise ValueError('Stage evidence inventory differs')
        for bundle in gates.values():
            if not isinstance(bundle,dict) or set(bundle)!={'suite','result','policy','suite_review','output_review','baseline','baseline_review'}:raise ValueError('Complete stage evidence bindings required')
            for path in bundle.values():
                if path is not None:read(path);inputs.guards[Path(path).resolve()]=stamp(path)
        initial={'step':0,'tokens':0,'supervised_tokens':0,'cursor':0}
        if resume:
            inputs.pin_tree(Path(resume))
            binding,state=verify_checkpoint(resume,inputs);initial={k:state[k] for k in initial};passed=binding['passed_gates']
            if not isinstance(passed,dict):raise ValueError('Invalid stage gate receipts')
            for stage,receipt in passed.items():
                if stage not in gates or stage_gate(gates[stage],receipt['model_hash'],inputs)!=receipt or receipt['decision']!='screen_passed':
                    raise ValueError('Prior stage acceptance evidence differs or is absent')
            latest=Path(resume)
        if initial['step']>spec['limits']['updates'] or initial['tokens']>spec['limits']['processed_positions']:raise ValueError('Checkpoint exceeds run ceilings')
        # Check hardware before creating an attempt. MLX selects its default device explicitly.
        from slm.eval.portability import environment,memory_snapshot
        env=environment(backend,device)
        inputs.check();output.mkdir(parents=True);created=True;write(output/'run.json',{'version':1,'spec':spec,'logical_plan':inputs.plan,'plan_hash':inputs.identity,
            'resume_manifest_sha256':sha(Path(resume)/'manifest.json') if resume else None,'backend':backend,'device':device,'environment':env,
            'wall_limit_scope':'Soft, checked at safe boundaries; in-flight updates/checkpoints may exceed it. Not a spend guarantee.'})
        write(output/'spec.json',spec)
        events=(output/'events.jsonl').open('x');cls=CurriculumTrainer if isinstance(inputs.data,CurriculumBatches) else Trainer
        tick=time.perf_counter()
        trainer=cls.resume(Path(resume)/'state',inputs.data,backend,device,inputs.data.tokenizer_hash) if resume else cls(inputs.config,initialize(inputs.config,spec['seed']),inputs.data,backend,device,inputs.recipe,inputs.data.tokenizer_hash)
        synchronize(backend,device);timing['initialization_restore']=time.perf_counter()-tick
        reason='unknown';count=0
        def save():
            nonlocal latest
            tick=time.perf_counter();inputs.check();latest=save_checkpoint(output,trainer,inputs,passed);timing['checkpoints']+=time.perf_counter()-tick
        while True:
            inputs.check()
            if isinstance(inputs.data,CurriculumBatches):
                progress=inputs.data.progress(trainer.cursor);done=progress['completed_stages']
                if done:
                    stage=progress['stages'][done-1]['id']
                    if stage not in passed:
                        save()
                        if stage in gates:
                            tick=time.perf_counter();receipt=stage_gate(gates[stage],sha(latest/'state/model/manifest.json'),inputs);timing['evaluation']+=time.perf_counter()-tick
                            if receipt['decision']=='screen_passed':passed[stage]=receipt
                        if stage not in passed:reason='stage_review_required';break
            if trainer.step>=spec['limits']['updates']:reason='update_target_reached';break
            if trainer.cursor>=len(inputs.data):reason='data_exhausted_before_target';break
            if count>=max_new_updates:reason='invocation_update_limit';break
            if time.perf_counter()-started>=wall_seconds:reason='soft_wall_limit';break
            _,end=trainer._update_context();after=inputs.data.counts(end)[0]
            if after>spec['limits']['processed_positions']:reason='position_ceiling_before_next_atomic_update';break
            tick=time.perf_counter();result=trainer.update();synchronize(backend,device);elapsed=time.perf_counter()-tick
            timing['updates']+=elapsed;count+=1
            events.write(json.dumps({'event':'update','seconds':elapsed,**result},sort_keys=True,allow_nan=False)+'\n');events.flush();os.fsync(events.fileno())
            if trainer.step%spec['checkpoint']['every_updates']==0 or result.get('stage_completed'):save()
        save();inputs.check()
        new_tokens=trainer.tokens-initial['tokens'];new_supervised=trainer.supervised_tokens-initial['supervised_tokens']
        report={'version':1,'scope':spec['scope'],'plan_hash':inputs.identity,'status':reason,'completed_update_target':reason=='update_target_reached',
            'initial':initial,'final':{'step':trainer.step,'cursor':trainer.cursor,'tokens':trainer.tokens,'supervised_tokens':trainer.supervised_tokens},
            'executed_this_invocation':{'updates':count,'processed_positions':new_tokens,'supervised_positions':new_supervised},
            'timing_seconds':timing,'total_seconds':time.perf_counter()-started,'processed_positions_per_update_second':new_tokens/timing['updates'] if timing['updates'] else None,
            'supervised_positions_per_update_second':new_supervised/timing['updates'] if timing['updates'] else None,
            'memory':memory_snapshot(backend,device),'latest_checkpoint':str(latest),'latest_manifest_sha256':sha(latest/'manifest.json'),
            'passed_stage_gates':passed,'events_sha256':sha(output/'events.jsonl'),'production_accepted':False,
            'language_capability_proved':False,'scope_note':'Finite reference execution. Logical counts exclude previously executed discarded work; prior attempt logs remain separate.'}
        write(output/'report.json',report);return report
    except BaseException as exc:
        if created:
            candidates=[latest] if latest else []
            if (output/'checkpoints').is_dir():candidates+=sorted((p for p in (output/'checkpoints').iterdir() if p.is_dir() and not p.is_symlink() and re.fullmatch(r'[0-9]{12}-[a-f0-9]{12}',p.name)),reverse=True)
            recovery=None
            for candidate in candidates:
                try:verify_checkpoint(candidate,inputs);recovery=str(candidate);break
                except Exception:continue  # Best-effort recovery must also tolerate invalid tensor headers.
            write(output/'failure.json',{'error_type':type(exc).__name__,'latest_checkpoint':recovery,
                'failed_latest_candidate':str(latest) if latest else None,'complete':False,
                'scope':'Verified checkpoint structure/plan only; resume still revalidates all source and stage inputs. Update events are not checkpoints.'})
        raise
    finally:
        if events is not None:events.close()
        inputs.close()


def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--spec',required=True);p.add_argument('--output');p.add_argument('--preflight-only',action='store_true')
    p.add_argument('--backend',choices=['torch','mlx'],default='torch');p.add_argument('--device',default='cpu');p.add_argument('--resume')
    p.add_argument('--max-new-updates',type=int,default=1000000);p.add_argument('--wall-seconds',type=float,default=3600);p.add_argument('--gates',help='Stage ID to evaluation-file bindings JSON')
    a=p.parse_args();spec=resolve_paths(read(a.spec),Path(a.spec).resolve().parent)
    if a.preflight_only:
        inputs=Inputs(spec)
        try:print(json.dumps({'plan_hash':inputs.identity,'parameters':inputs.config.parameter_count,'batches':len(inputs.data),'positions':inputs.data.counts(len(inputs.data)),'training_started':False},sort_keys=True))
        finally:inputs.close()
        return
    if not a.output:p.error('--output is required for execution')
    gate_bindings=read(a.gates) if a.gates else None
    if gate_bindings is not None:
        base=Path(a.gates).resolve().parent
        gate_bindings={key:{k:str((base/Path(v)).resolve()) if v is not None else None for k,v in bundle.items()} for key,bundle in gate_bindings.items()}
    report=run(spec,a.output,backend=a.backend,device=a.device,resume=a.resume,max_new_updates=a.max_new_updates,wall_seconds=a.wall_seconds,gates=gate_bindings)
    print(json.dumps({k:report[k] for k in ('status','completed_update_target','final','latest_checkpoint','production_accepted')},sort_keys=True))


if __name__=='__main__':main()

"""Portable synthetic v3 curriculum state; mechanics are separate from trajectory gates."""
from contextlib import contextmanager
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
from safetensors.numpy import load_file
from slm.common.config import Config,initialize
from slm.common.checkpoint import load
from slm.common.tokenizer import train_core
from slm.common.training import Recipe
from slm.common.curriculum import CurriculumTrainer
from slm.data.review import prepare,release
from slm.data.tokenized import build_shards,sha
from slm.data.mixture import build_mixture
from slm.data.curriculum import build_curriculum,CurriculumBatches
from slm.eval.portability import environment,memory_snapshot,write_manifest,validate_bundle


def create(output,config,backend='mlx',device='cpu'):
    root=Path(output);root.mkdir(parents=True,exist_ok=False)
    # Test-only hand-authored fixtures; this never approves a public dataset.
    sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'tests'))
    from test_review import fixture_snapshot,approved_packet
    rng=np.random.default_rng(2101)
    words=[''.join(rng.choice(list('abcdefghijklmnopqrstuvwxyz'),12)) for _ in range(24000)]
    bpe=train_core([' '.join(words)]*2,config.vocab_size,min_frequency=1)
    if bpe.vocab_size!=config.vocab_size:raise ValueError('Exact synthetic vocabulary required')
    bpe.save(root/'tokenizer',{'scope':'Synthetic transfer mechanics, not a production tokenizer'})
    stages=[];bindings={}
    for sid,objective,k,budget in [('foundation','foundation',3,64),('conversation','sft',2,18),('replay','foundation',2,64)]:
        part=root/sid;part.mkdir();fixture_snapshot(part/'raw',kind='prose' if objective=='foundation' else 'dialogue',source_name=sid)
        prepare(part/'raw',part/'review.json',30);approved_packet(part/'review.json');release(part/'raw',part/'review.json',part/'release')
        shard=build_shards(part/'release',root/'tokenizer',part/'tokens',objective,context_length=32,shard_positions=128)
        comp=[{'id':sid,'path':part/'tokens','dataset_hash':shard['dataset_hash'],'weight':1,'max_passes':1,'max_positions':100000}]
        mixed=build_mixture(comp,root/'tokenizer',part/'mixture',objective=objective,budget=budget,minimum=1,group_cap=100000,seed='portable-v3-mechanics')
        schedule={'lr':.0003 if objective=='foundation' else .0001,'warmup_tokens':0,'cooldown_tokens':0,'final_lr_fraction':1,'accumulation_steps':k}
        bindings[sid]={'path':str(part.relative_to(root)/'mixture'),'components':{sid:str(part.relative_to(root)/'tokens')}}
        stages.append({'id':sid,'path':part/'mixture','components':{sid:part/'tokens'},'dataset_hash':mixed['dataset_hash'],'schedule':schedule})
    recipe=Recipe(embedding_implementation='dense-onehot-v1',warmup_tokens=0)
    plan=build_curriculum(stages,root/'tokenizer',root/'plan',recipe=recipe,family_processed_cap=100000)
    if plan['microbatches']>12 or plan['processed_positions']>256 or plan['optimizer_updates']!=3:raise ValueError('Synthetic budget differs')
    (root/'fixture.json').write_text(json.dumps({'version':1,'bindings':bindings,'dataset_hash':plan['dataset_hash'],
        'architecture':config.to_dict(),'scope':'Three finite synthetic stages; no public/teacher approval'},indent=2)+'\n')
    with open_data(root,verify=False) as data:
        trainer=CurriculumTrainer(config,initialize(config,317),data,backend,device)
        first=trainer.update();trainer.save(root/'initial')
        if data.progress(trainer.cursor)['next_stage']!='conversation':raise AssertionError('Origin must end at first stage boundary')
    write_manifest(root)
    return {'passed':True,'bundle_sha256':validate_bundle(root),'parameters':config.parameter_count,'first_update':first,
        'plan':plan,'environment':environment(backend,device),'synthetic_only':True}


@contextmanager
def open_data(root,verify=True):
    root=Path(root)
    if verify:validate_bundle(root)
    fixture=json.loads((root/'fixture.json').read_text())
    bindings={sid:{'path':root/v['path'],'components':{k:root/p for k,p in v['components'].items()}} for sid,v in fixture['bindings'].items()}
    with CurriculumBatches(root/'plan',bindings,root/'tokenizer',fixture['dataset_hash']) as data:yield data


def exact_import(trainer,checkpoint):
    checkpoint=Path(checkpoint);config,weights=load(checkpoint/'model')
    expected={f'weight:{k}':v for k,v in weights.items()};expected.update(load_file(str(checkpoint/'optimizer.safetensors')))
    tensors={f'weight:{k}':v for k,v in trainer.params.items()}
    tensors.update({f'{slot}:{k}':v[i] for k,v in trainer.moments.items() for i,slot in enumerate(('m','v'))})
    if expected.keys()!=tensors.keys():raise AssertionError('Imported tensor inventory differs')
    original,actual=hashlib.sha256(),hashlib.sha256()
    for name,e in sorted(expected.items()):
        a=trainer.impl.export({'value':tensors[name]})['value']
        if a.shape!=e.shape or a.dtype!=e.dtype:raise AssertionError('Imported shape/dtype differs')
        header=str((name,e.shape,e.dtype.str)).encode();original.update(header);actual.update(header)
        original.update(e.tobytes(order='C'));actual.update(a.tobytes(order='C'))
    if original.digest()!=actual.digest():raise AssertionError('Imported state values differ')
    state=json.loads((checkpoint/'state.json').read_text())
    counters={k:getattr(trainer,k) for k in ('step','cursor','tokens','supervised_tokens')}
    if any(counters[k]!=state[k] for k in counters) or asdict(trainer.recipe)!=state['recipe']:raise AssertionError('Imported counters/recipe differ')
    return {'passed':True,'tensors_checked':len(expected),'values_checked':sum(v.size for v in expected.values()),
        'source_content_sha256':original.hexdigest(),'imported_content_sha256':actual.hexdigest(),'counters':counters}


def continue_(fixture,checkpoint,output,backend='torch',device='cuda'):
    output=Path(output)
    if output.exists():raise FileExistsError(output)
    fixture_hash=validate_bundle(fixture)
    with open_data(fixture) as data:
        trainer=CurriculumTrainer.resume(checkpoint,data,backend,device)
        imported=exact_import(trainer,checkpoint);before=data.progress(trainer.cursor)
        update=trainer.update();after=data.progress(trainer.cursor)
        values=0
        for name,w in trainer.params.items():
            for tensor in (w,)+trainer.moments[name]:
                a=trainer.impl.export({'value':tensor})['value'];values+=a.size
                if not np.isfinite(a).all():raise FloatingPointError('Nonfinite continued state')
        output.mkdir(parents=True);trainer.save(output/'checkpoint')
        report={'passed':True,'synthetic_only':True,'fixture_bundle_sha256':fixture_hash,'parameters':trainer.config.parameter_count,
            'environment':environment(backend,device),'exact_import':imported,'before':before,'update':update,'after':after,
            'all_final_values_finite':True,'values_checked':values,'memory':memory_snapshot(backend,device),
            'scope':'One finite v3 optimizer update and exact state import; not an independent trajectory or language acceptance'}
    (output/'continuation.json').write_text(json.dumps(report,indent=2)+'\n');return report


def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    a=sub.add_parser('create');a.add_argument('--config',required=True)
    a=sub.add_parser('continue');a.add_argument('--fixture',required=True);a.add_argument('--checkpoint',required=True)
    for a in sub.choices.values():
        a.add_argument('--output',required=True);a.add_argument('--backend',choices=['mlx','torch'],required=True);a.add_argument('--device',default='cpu')
    args=p.parse_args()
    report=create(args.output,Config(**json.loads(Path(args.config).read_text())),args.backend,args.device) if args.action=='create' else continue_(args.fixture,args.checkpoint,args.output,args.backend,args.device)
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()

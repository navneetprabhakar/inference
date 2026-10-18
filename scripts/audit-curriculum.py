#!/usr/bin/env python3
"""Bounded synthetic reviewed-mixture curriculum audit; not language training."""
# Creator: Navneet Prabhakar
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
import tempfile
import time
import numpy as np
from slm.common.config import Config,initialize
from slm.common.tokenizer import train_core
from slm.common.training import Recipe
from slm.common.curriculum import CurriculumTrainer
from slm.data.review import prepare,release
from slm.data.tokenized import build_shards,sha
from slm.data.mixture import build_mixture
from slm.data.curriculum import build_curriculum,CurriculumBatches
from slm.eval.accumulation import exact_state
from slm.eval.portability import environment,memory_snapshot


def run(config,output,backend='mlx',device='cpu',embedding='dense-onehot-v1'):
    output=Path(output)
    if output.exists():raise FileExistsError(output)
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
    from test_review import fixture_snapshot,approved_packet
    rng=np.random.default_rng(1601)
    words=[''.join(rng.choice(list('abcdefghijklmnopqrstuvwxyz'),12)) for _ in range(24000)]
    bpe=train_core([' '.join(words)]*2,config.vocab_size,min_frequency=1)
    if bpe.vocab_size!=config.vocab_size:raise ValueError('Synthetic tokenizer did not reach exact configured vocabulary')
    recipe=Recipe(embedding_implementation=embedding,warmup_tokens=0,accumulation_steps=3)
    history=[];checks=[]
    with tempfile.TemporaryDirectory(prefix='slm-curriculum-audit-') as name:
        root=Path(name);tok=root/'tokenizer';bpe.save(tok,{'scope':'Synthetic mechanics only; not a production tokenizer candidate'})
        stages=[];bindings={}
        for sid,objective,k in [('foundation','foundation',3),('conversation','sft',2)]:
            part=root/sid;part.mkdir();fixture_snapshot(part/'raw',kind='prose' if objective=='foundation' else 'dialogue',source_name=sid)
            prepare(part/'raw',part/'review.json',30);approved_packet(part/'review.json');release(part/'raw',part/'review.json',part/'release')
            shard=build_shards(part/'release',tok,part/'tokens',objective,context_length=32,shard_positions=128)
            comp=[{'id':sid,'path':part/'tokens','dataset_hash':shard['dataset_hash'],'weight':1,'max_passes':1,'max_positions':100000}]
            budget=64 if objective=='foundation' else 18
            mixed=build_mixture(comp,tok,part/'mixture',objective=objective,budget=budget,minimum=1,group_cap=100000,seed='bounded-curriculum')
            schedule={'lr':.0003 if objective=='foundation' else .0001,'warmup_tokens':0,'cooldown_tokens':0,'final_lr_fraction':1,'accumulation_steps':k}
            bind={'path':part/'mixture','components':{sid:part/'tokens'}};bindings[sid]=bind
            stages.append({'id':sid,'dataset_hash':mixed['dataset_hash'],'schedule':schedule,**bind})
        plan=build_curriculum(stages,tok,root/'plan',recipe=recipe,family_processed_cap=100000)
        if plan['microbatches']>12 or plan['processed_positions']>256:raise ValueError('Audit fixture exceeded explicit neural budget')
        with CurriculumBatches(root/'plan',bindings,tok,plan['dataset_hash']) as data:
            a=CurriculumTrainer(config,initialize(config,317),data,backend,device)
            first=a.update();a.save(root/'boundary')
            checkpoint_bytes=sum(p.stat().st_size for p in (root/'boundary').rglob('*') if p.is_file())
            checkpoint_hash=sha(root/'boundary/manifest.json')
            b=CurriculumTrainer.resume(root/'boundary',data,backend,device);checks.append(exact_state(a,b));history.append(first)
            while a.cursor<len(data):
                started=time.perf_counter();left=a.update();right=b.update()
                if left!=right:raise AssertionError('Curriculum own-resume metrics differ')
                checks.append(exact_state(a,b));history.append({**left,'two_branches_seconds':time.perf_counter()-started})
            progress=data.progress(a.cursor)
            report={'passed':True,'synthetic_only':True,'parameters':config.parameter_count,'architecture':config.to_dict(),
                'environment':environment(backend,device),'base_recipe':asdict(recipe),'plan':plan,'final_progress':progress,
                'history':history,'exact_state_checks':checks,'checkpoint_bytes':checkpoint_bytes,'checkpoint_manifest_sha256':checkpoint_hash,
                'logical_updates':a.step,'logical_processed_positions':a.tokens,'logical_supervised_positions':a.supervised_tokens,
                'executed_updates':a.step+b.step-first['step'],'executed_processed_positions':a.tokens+b.tokens-first['tokens'],
                'memory':memory_snapshot(backend,device),'temporary_fixtures_and_checkpoint_removed':True,
                'scope':'Short synthetic two-stage own-resume mechanics, not language quality, sustained throughput, actual CUDA or independent cross-backend trajectory acceptance',
                'source_sha256':{str(p):sha(p) for p in map(Path,['src/slm/common/training.py','src/slm/common/curriculum.py','src/slm/data/curriculum.py','scripts/audit-curriculum.py'])}}
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x') as f:f.write(json.dumps(report,indent=2)+'\n')
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',required=True);p.add_argument('--output',required=True)
    p.add_argument('--backend',choices=['mlx','torch'],default='mlx');p.add_argument('--device',default='cpu')
    p.add_argument('--embedding',choices=['dense-onehot-v1','native-gather-v1'],default='dense-onehot-v1')
    a=p.parse_args();r=run(Config(**json.loads(Path(a.config).read_text())),a.output,a.backend,a.device,a.embedding)
    print(json.dumps({k:r[k] for k in ('passed','parameters','logical_updates','logical_processed_positions','executed_processed_positions','memory')},indent=2))


if __name__=='__main__':main()

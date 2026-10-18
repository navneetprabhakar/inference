#!/usr/bin/env python3
"""Bounded synthetic CLI pilot/resume evidence. Never uses real public/teacher data."""
# Creator: Navneet Prabhakar
from dataclasses import asdict
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import numpy as np
from safetensors.numpy import load_file
from slm.common.config import Config
from slm.common.training import Recipe
from slm.common.tokenizer import train_core
from slm.data.schema import Source,make_example
from slm.data.curation import curate
from slm.data.review import prepare,release
from slm.data.tokenized import build_shards,sha


def audit(root,report_file):
    root,report_file=Path(root).resolve(),Path(report_file)
    if root.exists() or report_file.exists():raise FileExistsError('Fresh audit locations required')
    # Explicitly simulated review decisions are confined to this synthetic fixture.
    root.mkdir(parents=True);raw=root/'raw';raw.mkdir()
    card=b'Handcrafted pilot execution fixture, not a language corpus.';license=b'Synthetic mechanics fixture only; no real source/account permission.'
    (raw/'card.txt').write_bytes(card);(raw/'license.txt').write_bytes(license)
    src=Source('pilot_mechanics_fixture','a'*40,'https://example.org/synthetic-pilot','synthetic-fixture-only',
        hashlib.sha256(license).hexdigest(),hashlib.sha256(card).hexdigest(),('handcrafted-synthetic-fixture',))
    examples=[make_example(src,str(i),str(i),[{'role':'user','content':f'Synthetic question number {i}.'},
        {'role':'assistant','content':f'Synthetic answer number {i}.'}],official_split='train',language='en',content_category='sfw') for i in range(30)]
    items,curation=curate(examples,{src.source_id:src})
    for split in ('train','validation','test'):
        rows=[e for e in items if e.split==split]
        if rows:(raw/f'{split}-00000.jsonl').write_text(''.join(json.dumps(e.to_dict())+'\n' for e in rows))
    (raw/'sources.json').write_text(json.dumps({src.source_id:asdict(src)}))
    (raw/'manifest.json').write_text(json.dumps({'version':1,'release':'sample_only','files':{p.name:sha(p) for p in raw.iterdir()}}))
    prepare(raw,root/'fixture-review.json',30);packet=json.loads((root/'fixture-review.json').read_text());packet.update(reviewer='Navneet Prabhakar',human_attestation=True)
    for s in packet['source_reviews'].values():s.update(approved=True,terms_reviewed=True,allowed_categories=['sfw'],evidence_note='Simulated synthetic-fixture decision only, no actual human/source approval.')
    for e in packet['examples'].values():e['decision'].update(approved=True,english_verified=True,privacy_verified=True,quality_verified=True,
        content_category='sfw',upstream_partition=e['record']['official_split'],partition_evidence='Synthetic fixture partition.')
    (root/'fixture-review.json').write_text(json.dumps(packet));release(raw,root/'fixture-review.json',root/'reviewed')
    train_core([m['content'] for e in examples for m in e.messages],512).save(root/'tokenizer',{'scope':'Synthetic pilot mechanics, not production tokenizer'})
    tokens=build_shards(root/'reviewed',root/'tokenizer',root/'tokens','sft',context_length=64,shard_positions=128)
    from slm.common.tokenizer import BPE
    spec={'version':1,'config':Config(vocab_size=BPE.load(root/'tokenizer').vocab_size,max_seq_len=64).to_dict(),
        'recipe':asdict(Recipe(accumulation_steps=2,embedding_implementation='dense-onehot-v1')),'seed':731,
        'tokenizer':str(root/'tokenizer'),'data':{'kind':'tokens','path':str(root/'tokens'),'fingerprint':tokens['dataset_hash']},
        'releases':{sha(root/'reviewed/manifest.json'):str(root/'reviewed')},'limits':{'updates':3,'processed_positions':10000},
        'checkpoint':{'every_updates':1,'keep':2},'scope':'synthetic_mechanics'}
    (root/'spec.json').write_text(json.dumps(spec,indent=2)+'\n')
    results={};exact={}
    for backend,device in [('torch','cpu'),('mlx','default')]:
        def execute(name,extra):
            output=root/name
            cmd=[sys.executable,'-m','slm.train','--spec',str(root/'spec.json'),'--output',str(output),'--backend',backend,'--device',device,*extra]
            result=subprocess.run(cmd,capture_output=True,text=True,check=True,timeout=90)
            results[name]={'stdout_sha256':hashlib.sha256(result.stdout.encode()).hexdigest(),'report':json.loads((output/'report.json').read_text()),'report_sha256':sha(output/'report.json')}
            return results[name]['report']
        full=execute(backend+'-full',[]);first=execute(backend+'-first',['--max-new-updates','1'])
        second=execute(backend+'-resumed',['--resume',first['latest_checkpoint']])
        assert full['final']==second['final'] and second['executed_this_invocation']['updates']==2
        count=0
        for name in ('model/model.safetensors','optimizer.safetensors'):
            a=load_file(str(Path(full['latest_checkpoint'])/'state'/name));b=load_file(str(Path(second['latest_checkpoint'])/'state'/name))
            assert a.keys()==b.keys()
            for k,v in a.items():np.testing.assert_array_equal(v,b[k]);count+=v.size
        exact[backend]={'same_backend_resume_exact':True,'values_compared':count,'final':full['final']}
    assert all(not v['report']['production_accepted'] and not v['report']['language_capability_proved'] for v in results.values())
    report={'creator':'Navneet Prabhakar','scope':'Six separate-process tiny synthetic pilot invocations, not 1M/10M language training',
        'real_public_or_teacher_examples':0,'real_human_reviews':0,'real_source_approvals':0,'real_language_pilot_completed':False,
        'synthetic_fixture_source':src.source_id,'synthetic_review_flags_simulated':True,'results':results,'exact_resume':exact,
        'actual_cuda_wrapper_validated':False,'new_teacher_launches':0,'cloud_jobs':0,
        'source_sha256':{p:sha(p) for p in ('src/slm/train.py','scripts/audit-pilot-runner.py','tests/test_train.py')},
        'spec_sha256':sha(root/'spec.json'),'tokenizer_manifest_sha256':sha(root/'tokenizer/manifest.json')}
    report_file.parent.mkdir(parents=True,exist_ok=True)
    with report_file.open('x') as f:f.write(json.dumps(report,indent=2)+'\n')
    return {'separate_process_invocations':6,'exact_resume_backends':list(exact),'real_language_pilot_completed':False}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);p.add_argument('--report',required=True);a=p.parse_args();print(json.dumps(audit(a.output,a.report),sort_keys=True))

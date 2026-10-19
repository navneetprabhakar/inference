"""Freeze or execute one next call under the separately authorized20-call envelope."""
# Creator: Navneet Prabhakar
import argparse
from dataclasses import asdict
import fcntl
import json
from pathlib import Path
import shutil
import sqlite3
import time
from slm.data.evaluation_exclusions import EvaluationExclusions
from slm.data.stream_hash import sha
from slm.teacher.english_batch import EnglishBatchCLI, EnglishRecipe, checked_batch, generate_batch, continuations
from slm.teacher.english_seeds import batches
from slm.teacher.journal import Journal

ROOT=Path('data/english-teacher-20call-v1').resolve()
CONFIG=Path('configs/english-teacher-20call-authorization-v1.json')
SOURCES=[__file__,'src/slm/teacher/english_batch.py','src/slm/teacher/english_seeds.py',
         'src/slm/teacher/sol.py','src/slm/teacher/cli.py','src/slm/teacher/journal.py',
         'src/slm/teacher/scenarios.py','src/slm/teacher/styles.py','src/slm/teacher/workflow.py',
         'src/slm/data/evaluation_exclusions.py','src/slm/data/holdout.py']


def read(path):return json.loads(Path(path).read_text())
def save(path,obj):
    with Path(path).open('x') as f:
        f.write(json.dumps(obj,sort_keys=True,ensure_ascii=False,indent=2)+'\n');f.flush()
        import os
        os.fsync(f.fileno())


def freeze():
    cfg=read(CONFIG)
    if cfg['authorized'] is not True or cfg['maximum_additional_launches']!=20:raise ValueError('Explicit20-call authorization required')
    if ROOT.exists():raise FileExistsError('Retain existing attempt and journal')
    historical={};total=0
    for path in cfg['historical_journals']:
        db=sqlite3.connect('file:'+str(Path(path).resolve())+'?mode=ro',uri=True)
        try:total+=db.execute('SELECT COUNT(*) FROM requests').fetchone()[0]
        finally:db.close()
        historical[path]=sha(path)
    if total!=20:raise ValueError('Historical pilot count must remain20')
    exc=read('configs/future-intake-evaluation-exclusions-v1.json')
    guard=EvaluationExclusions(exc['inventory'],exc['inventory_sha256'])
    packet=[checked_batch(b,guard) for b in batches()]
    if len(packet)!=20 or sum(map(len,packet))!=182:raise ValueError('Exact finite seed curriculum required')
    recipe=EnglishRecipe();ROOT.mkdir();(ROOT/'records').mkdir();(ROOT/'sources').mkdir()
    Journal(ROOT/'journal.sqlite',0,cfg['authorization_id'],20)
    save(ROOT/'batches.json',packet)
    bindings={str(Path(p)):sha(p) for p in SOURCES}
    for i,p in enumerate(SOURCES):shutil.copyfile(p,ROOT/'sources'/f'{i:02d}-{Path(p).name}')
    save(ROOT/'plan.json',dict(creator='Navneet Prabhakar',kind='english-teacher-20call-v1',
        root=str(ROOT),authorization=cfg,authorization_sha256=sha(CONFIG),recipe=asdict(recipe),
        bindings=bindings,historical_journals=historical,prior_reserved_calls=20,
        new_maximum_calls=20,maximum_total_historical_plus_new=40,
        evaluation_inventory=exc['inventory'],evaluation_inventory_sha256=exc['inventory_sha256'],
        batches_sha256=sha(ROOT/'batches.json'),frozen_at_epoch=time.time(),deadline_epoch=time.time()+3600,
        initial_single_call_gate=2,semantic_families=20,candidate_instances=182,training_approved=False))
    save(ROOT/'freeze.json',dict(plan_sha256=sha(ROOT/'plan.json')))
    print(json.dumps(dict(status='frozen',calls=20,candidate_instances=182,semantic_families=20)),flush=True)


def checked():
    plan=read(ROOT/'plan.json')
    if plan['root']!=str(ROOT) or sha(ROOT/'plan.json')!=read(ROOT/'freeze.json')['plan_sha256']:
        raise ValueError('Frozen execution identity changed')
    if sha(CONFIG)!=plan['authorization_sha256'] or sha(ROOT/'batches.json')!=plan['batches_sha256']:
        raise ValueError('Authorization or batches changed')
    for path,want in {**plan['bindings'],**plan['historical_journals']}.items():
        if sha(path)!=want:raise ValueError('Frozen source or historical ledger changed: '+path)
    return plan


def next_call():
    with (ROOT/'execution.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        plan=checked();cfg=plan['authorization'];packet=read(ROOT/'batches.json')
        existing=sorted((ROOT/'records').glob('*.json'))
        if [p.name for p in existing]!=[f'{i:02d}.json' for i in range(len(existing))]:raise ValueError('Missing completed batch record')
        index=len(existing)
        if index>=20:print(json.dumps(dict(status='all20calls_recorded')));return
        if time.time()+135>=plan['deadline_epoch']:raise TimeoutError('Insufficient remaining original pilot time')
        if index>=2:
            gate=read(ROOT/'initial-direct-review.json')
            if gate.get('passed') is not True or gate.get('record_sha256')!=[sha(p) for p in existing[:2]]:
                raise ValueError('Direct reviewed initial two-call gate required')
        journal=Journal(ROOT/'journal.sqlite',0,cfg['authorization_id'],20)
        guard=EvaluationExclusions(plan['evaluation_inventory'],plan['evaluation_inventory_sha256'])
        for path in existing:
            prior=read(path)
            if prior['plan_sha256']!=sha(ROOT/'plan.json') or continuations(prior,journal,guard)!=prior['continuation_candidates']:
                raise ValueError('Previous record/continuation identity changed')
            if not all(r['automated_passed'] for r in prior['results']):
                raise ValueError('Prior quality failure unresolved; no further automatic calls')
        provider=EnglishBatchCLI(cfg['cli_executable']);provider.diagnostic_dir=ROOT/'captures'
        record=generate_batch(journal,provider,EnglishRecipe(**plan['recipe']),packet[index],guard)
        record['plan_sha256']=sha(ROOT/'plan.json')
        record['continuation_candidates']=continuations(record,journal,guard)
        checked();save(ROOT/'records'/f'{index:02d}.json',record)
        print(json.dumps(dict(call=index+1,candidates=len(record['results']),automated_passed=sum(r['automated_passed'] for r in record['results']),usage=record['usage'],cache_hit=record['cache_hit'])),flush=True)
        if not all(r['automated_passed'] for r in record['results']):raise ValueError('Automated quality failure retained; direct review before further execution')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['freeze','next'])
    args=p.parse_args();freeze() if args.action=='freeze' else next_call()

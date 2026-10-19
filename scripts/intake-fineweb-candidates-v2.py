"""Bounded distributed FineWeb intake; provisional rows remain unadmitted."""
# Creator: Navneet Prabhakar
from collections import Counter
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import sqlite3
import subprocess
import sys
import time
from slm.common.tokenizer import BPE
from slm.data.evaluation_exclusions import EvaluationExclusions
from slm.data.intake_cache import IntakeCache
from slm.data.intake_transport import once,Unavailable
from slm.data.intake_ledger import IntakeLedger
from slm.data.parquet_ranges import BoundedParquet,ExactRanges,Limits
from slm.data.parquet_selection import compatible_group,select
from slm.data.prose_intake_quality import assess
from slm.data.schema import digest
from slm.data.tokenized import sha

ROOT=Path('data/fineweb-candidate-intake-v1')
PLAN=Path('configs/fineweb-candidate-intake-execution-v2.json')


def read(p):return json.loads(Path(p).read_text())
def encoded(v):return (json.dumps(v,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n').encode()
def save(p,v):
    raw=encoded(v)
    if p.parent==ROOT:
        other=sum(f.stat().st_size for f in ROOT.iterdir() if f.is_file() and f.suffix=='.json' and f!=p)
        if other+len(raw)>1048576:raise ValueError('Auxiliary output cap exceeded')
    p.write_bytes(raw)


def summary(choice,rows,payload):
    return dict(file=choice['file'],group=choice['group'],rows=len(rows),rows_sha256=hashlib.sha256(payload).hexdigest(),
        provisional_quality_pass=sum(r['provisional_quality_pass'] for r in rows),
        actual_student_bpe_text_tokens=sum(r['actual_student_bpe_text_tokens'] for r in rows),
        provisional_pass_text_tokens=sum(r['actual_student_bpe_text_tokens'] for r in rows if r['provisional_quality_pass']),
        reason_counts=dict(Counter(reason for r in rows for reason in r['decision']['reasons'])),
        crawl_counts=dict(Counter(r['row']['dump'] for r in rows)))


def worker():
    plan=read(PLAN)
    for p,h in plan['input_bindings'].items():
        if sha(p)!=h:raise ValueError('Pinned FineWeb intake input changed')
    ledger=IntakeLedger(ROOT/'charges',plan['ledger_contract']);cache=IntakeCache(ROOT/'cache',ledger)
    stage='initialization'
    try:
        if not ledger.db.execute('SELECT 1 FROM attempts WHERE key=?',('prior-prefix-probe',)).fetchone():
            ledger.reserve('prior-prefix-probe',**plan['prior_probe_charge']);ledger.finish('prior-prefix-probe',raw=b'')
        if not ledger.db.execute('SELECT 1 FROM attempts WHERE key=?',('auxiliary-artifacts',)).fetchone():
            ledger.reserve('auxiliary-artifacts',output_bytes=1048576);ledger.finish('auxiliary-artifacts',raw=b'')
        inventory=read(plan['inventory']);by_file={i['path']:i for i in inventory}
        if len(by_file)!=14:raise ValueError('Pinned fourteen-file inventory required')
        spec=read('configs/future-intake-evaluation-exclusions-v1.json');guard=EvaluationExclusions(spec['inventory'],spec['inventory_sha256'])
        bpe=BPE.load(plan['tokenizer']);heldouts=read(plan['heldout_map']);judgments=plan['known_judgments']
        work=ROOT/'language';work.mkdir(exist_ok=True)
        def reader_for(item):
            name=item['path'];url=f"https://huggingface.co/datasets/HuggingFaceFW/fineweb-edu/resolve/{plan['revision']}/{name}"
            class Transport(ExactRanges):
                def get(self,start,length):
                    inherited=plan['inherited_ranges'].get(name+':'+str(start)+':'+str(length))
                    if inherited:
                        if sha(inherited['path'])!=inherited['sha256']:raise ValueError('Prior retained range differs')
                        raw=Path(inherited['path']).read_bytes()
                        if len(raw)!=length:raise ValueError('Prior range size differs')
                        return raw
                    return once(cache,'range/'+name+'/'+str(start)+'/'+str(length),length,lambda:super(Transport,self).get(start,length))
            return BoundedParquet(Transport(url,item['size'],'"'+item['xetHash']+'"',Limits(**plan['range_limits'])))
        censuses={}
        stage='metadata_census'
        for i,item in enumerate(inventory):
            ledger.check_time();reader=reader_for(item)
            if set(reader.metadata.schema.names)!=set(plan['fields']):raise ValueError('Pinned FineWeb columns differ')
            groups=[g for j in range(reader.metadata.num_row_groups) if (g:=compatible_group(reader,j)) is not None]
            if not groups:raise ValueError('No compatible group in selected file')
            censuses[item['path']]=groups;cache.publish('census/'+item['path'],encoded(groups))
            print(json.dumps(dict(metadata_files=i+1,compatible_groups=len(groups))),flush=True)
        excluded={(r['file'],r['group']) for r in plan['excluded_prior_groups']}
        choices=select(censuses,plan['selection_seed'],49,4,excluded)
        if len(choices)!=49:raise ValueError('Insufficient compatible distributed groups')
        cache.publish('selection',encoded(choices))
        completed=[];skipped=[]
        for i,choice in enumerate(choices):
            ledger.check_time();name=choice['file'];group=choice['group'];stem=name+'/'+str(group['index']);key='rows/'+stem
            stage='group/'+stem
            if stem in plan['known_skipped_groups']:
                skipped.append(plan['known_skipped_groups'][stem]);continue
            if shutil.disk_usage('.').free<plan['minimum_free_disk_bytes']:raise ValueError('Free disk reserve reached')
            if sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file())>plan['maximum_work_disk_bytes']:raise ValueError('Work disk cap reached')
            payload=cache.existing(key)
            if payload is not None:
                rows=[json.loads(line) for line in payload.splitlines()]
                if len(rows)!=group['rows']:raise ValueError('Completed group count differs')
                state=ledger.db.execute('SELECT state FROM attempts WHERE key=?',('decode/'+stem,)).fetchone()
                if state==('pending',):ledger.finish('decode/'+stem,raw=b'')
                elif state!=('complete',):raise ValueError('Completed group lacks decode reservation')
            else:
                reader=reader_for(by_file[name]);actual=compatible_group(reader,group['index'])
                if actual!=group:raise ValueError('Selected group metadata differs')
                if ledger.db.execute('SELECT 1 FROM attempts WHERE key=?',('decode/'+stem,)).fetchone():raise ValueError('Uncertain decode cannot replay')
                ledger.reserve('decode/'+stem,rows=group['rows'])
                try:table=reader.read_group(group['index'])
                except Unavailable:
                    skipped.append(dict(file=name,group=group,reserved_rows=group['rows'],reason='Transfer/validation unavailable; no retry, reservation retained.'));continue
                raw_rows=table.to_pylist();del table
                stage='quality/'+stem;decisions=assess(raw_rows,guard,plan['detector'],work,judgments,heldouts);rows=[]
                for j,(raw,decision) in enumerate(zip(raw_rows,decisions)):
                    rows.append(dict(source='HuggingFaceFW/fineweb-edu',revision=plan['revision'],file=name,
                        row_group=group['index'],row_in_group=j,row=raw,raw_record_sha256=digest(raw),**decision,
                        provisional_quality_pass=decision['decision']['candidate'],
                        actual_student_bpe_text_tokens=len(bpe.encode(raw['text'])),training_approved=False,partition=None,
                        pending='Global exact/near/seed overlap, preserved ancestry and finite corpus admission.'))
                payload=b''.join(encoded(r) for r in rows);cache.publish(key,payload);ledger.finish('decode/'+stem,raw=b'')
            done=summary(choice,rows,payload);completed.append(done);save(ROOT/f'group-{i:02d}.json',done)
            save(ROOT/'progress.json',dict(groups=len(completed),rows=sum(r['rows'] for r in completed),reserved=ledger.totals()))
            print(json.dumps(dict(groups=len(completed),rows=sum(r['rows'] for r in completed),provisional=sum(r['provisional_quality_pass'] for r in completed))),flush=True)
            for p,h in plan['input_bindings'].items():
                if sha(p)!=h:raise ValueError('Frozen input changed during FineWeb intake')
        snapshot=ledger.snapshot();save(ROOT/'ledger-snapshot.json',snapshot)
        report=dict(creator='Navneet Prabhakar',kind='actual-fineweb-distributed-candidate-intake-v2',complete=True,
            plan_sha256=sha(PLAN),groups=completed,skipped_groups=skipped,source_execution_phases=plan['source_execution_phases'],rows=sum(r['rows'] for r in completed),
            source_files=len({r['file'] for r in completed}),
            actual_student_bpe_text_tokens=sum(r['actual_student_bpe_text_tokens'] for r in completed),
            provisional_quality_pass=sum(r['provisional_quality_pass'] for r in completed),
            provisional_pass_text_tokens=sum(r['provisional_pass_text_tokens'] for r in completed),
            selection_sha256=hashlib.sha256(cached_selection:=cache.existing('selection')).hexdigest(),
            reserved=snapshot['reserved'],ledger_snapshot_sha256=sha(ROOT/'ledger-snapshot.json'),
            new_successful_body_bytes=sum(r['actual_body_bytes'] or 0 for r in snapshot['attempts']),
            inherited_successful_body_bytes=plan['prior_probe_successful_body_bytes'],
            inherited_rows=1000,training_approved=False,model_updates=0,teacher_calls=0,cloud_spend=0,
            scope='Distributed pinned FineWeb candidate groups; original text/metadata retained. Existing source/window/encoding/repetition/privacy/evaluation/known-nonapproval/direct-heldout screens only. No global grouping, source-wide quality or corpus admission; no hard RSS bound.')
        save(ROOT/'report.json',report);save(Path('reports/fineweb-candidate-intake.json'),report)
    except BaseException as error:
        save(ROOT/'continuation-failure-v2.json',dict(complete=False,stage=stage,error_type=type(error).__name__,
            message='Bounded intake stopped; retained charges and artifacts, no automatic replay.',ledger=ledger.snapshot()))
        raise SystemExit('FineWeb intake stopped; inspect retained stage/evidence') from None
    finally:ledger.close()


def main():
    if '--worker' in sys.argv:worker();return
    plan=read(PLAN)
    if ROOT.exists() and '--resume' not in sys.argv:raise FileExistsError('Intake already attempted; confirm process before explicit resume')
    if shutil.disk_usage('.').free<plan['minimum_free_disk_bytes']:raise ValueError('Insufficient initial free disk')
    ROOT.mkdir(exist_ok=True)
    with (ROOT/'supervisor.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if (ROOT/'report.json').exists():raise ValueError('Completed FineWeb intake cannot replay')
        if read(ROOT/'plan.json')!=read(plan['original_plan']):raise ValueError('Original FineWeb plan changed')
        if (ROOT/'continuation-plan-v2.json').exists():
            if read(ROOT/'continuation-plan-v2.json')!=plan:raise ValueError('Immutable FineWeb continuation changed')
        else:save(ROOT/'continuation-plan-v2.json',plan)
        remaining=plan['ledger_contract']['wall_seconds']
        if (ROOT/'charges/ledger.sqlite').exists():
            db=sqlite3.connect(f'file:{(ROOT/"charges/ledger.sqlite").resolve()}?mode=ro',uri=True)
            deadline=db.execute('SELECT deadline FROM job').fetchone()[0];db.close();remaining=min(remaining,deadline-time.time())
        if remaining<=0:raise ValueError('Original FineWeb deadline expired')
        child=subprocess.Popen([sys.executable,__file__,'--worker'],start_new_session=True)
        try:
            code=child.wait(timeout=remaining)
            if code:raise SystemExit(code)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid,signal.SIGKILL);child.wait()
            save(ROOT/'supervisor-timeout.json',dict(complete=False,independent_wall_stop=True,automatic_retry=False))
            raise SystemExit('Finite FineWeb supervisor stopped owned process group') from None


if __name__=='__main__':main()

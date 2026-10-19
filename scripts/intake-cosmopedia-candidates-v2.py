"""Finite pinned acquisition and provisional screening; never training admission."""
# Creator: Navneet Prabhakar
from collections import Counter
import json
import os
import hashlib
import re
import unicodedata
from pathlib import Path
import shutil
import signal
import sqlite3
import subprocess
import sys
import time
import fcntl
from slm.common.tokenizer import BPE
from slm.data.cosmopedia_seed import extract
from slm.data.detector_projection import fasttext_line
from slm.data.evaluation_exclusions import EvaluationExclusions
from slm.data.intake_cache import IntakeCache
from slm.data.intake_ledger import IntakeLedger
from slm.data.parquet_ranges import BoundedParquet, ExactRanges, Limits
from slm.data.prose_screen import windows
from slm.data.quality_audit import PATTERNS, LIMITS as LID_LIMITS, predict, top_scores
from slm.data.schema import digest
from slm.data.tokenized import sha

ROOT=Path('data/cosmopedia-candidate-intake-v1')
PLAN=Path('configs/cosmopedia-candidate-intake-execution-v2.json')


def read(p):return json.loads(Path(p).read_text())
def encoded(v):return (json.dumps(v,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n').encode()
def save(p,v):
    raw=encoded(v)
    if p.parent==ROOT:
        other=sum(f.stat().st_size for f in ROOT.iterdir() if f.is_file() and f.suffix=='.json' and f!=p)
        if other+len(raw)>1048576:raise ValueError('Precharged auxiliary output cap exceeded')
    p.write_bytes(raw)


def group_info(reader,index):
    g=reader.metadata.row_group(index);cs=[g.column(i) for i in range(g.num_columns)]
    if not cs:return None
    spans=[(c.dictionary_page_offset if c.has_dictionary_page else c.data_page_offset,c.total_compressed_size) for c in cs]
    start=min(s for s,n in spans);stop=max(s+n for s,n in spans);declared=sum(c.total_uncompressed_size for c in cs)
    lim=reader.transport.limits
    if (g.num_rows>lim.group_rows or declared<0 or declared>lim.group_declared_uncompressed_bytes
        or stop-start>lim.group_compressed_bytes or start<4 or stop>reader.footer_start
        or any(c.file_path or c.total_uncompressed_size<0 or n<=0 for c,(s,n) in zip(cs,spans))):return None
    return dict(index=index,rows=g.num_rows,declared_bytes=declared,compressed_interval_bytes=stop-start)


def quality(rows,guard,plan,work):
    prepared=[];parts=[]
    for raw in rows:
        reasons=[];seed=None
        if (set(raw)!=set(plan['fields']) or any(not isinstance(raw.get(k),str) for k in plan['string_fields'])
            or type(raw.get('token_length')) is not int):raise ValueError('Pinned six-field row schema differs')
        if not 1<=len(raw['text'])<=200000:reasons.append('text_length_scope')
        words=re.findall(r'\w+',raw['text'].casefold())
        if len(words)<50:reasons.append('short_text_scope')
        if words and max(Counter(words).values())/len(words)>.15:reasons.append('word_repetition_signal')
        if '\ufffd' in raw['text'] or any(unicodedata.category(c)=='Cc' and c not in '\n\t\r' for c in raw['text']):reasons.append('encoding_signal')
        if raw['seed_data']!='fineweb':reasons.append('unsupported_seed_constituent')
        else:
            try:seed=extract(raw)
            except ValueError:reasons.append('unresolved_exact_seed_profile')
        prompt_family='HuggingFaceTB/smollm-corpus:cosmopedia-v2:prompt:'+digest(raw['prompt'])
        if prompt_family in plan['nonapproval_prompt_families']:reasons.append('known_prompt_nonapproval')
        if seed and seed['proposed_exact_seed_family'] in plan['nonapproval_seed_families']:reasons.append('known_seed_nonapproval')
        isolation=guard.inspect_record(raw)
        if isolation['blocked']:reasons.append('protected_evaluation_text')
        privacy={field:[name for name,p in PATTERNS.items() if p.search(raw[field])] for field in ('prompt','text')}
        if any(privacy.values()):reasons.append('privacy_or_credential_signal')
        own=[]
        if not reasons:
            for field in ('prompt','text'):
                current=windows(raw[field])
                if not current:reasons.append('no_language_windows')
                for part in current:
                    own.append(dict(field=field,start=part['start'],end=part['end'],prediction_index=len(parts)))
                    parts.append(part['text'])
        prepared.append(dict(raw=raw,reasons=reasons,seed=seed,prompt_family=prompt_family,isolation=isolation,privacy=privacy,windows=own))
    if len(parts)>LID_LIMITS['max_windows']:raise ValueError('Per-group full language coverage exceeds detector cap')
    inp=work/'language-input.txt';out=work/'language-predictions.txt'
    payload=''.join(fasttext_line(p)+'\n' for p in parts).encode()
    if len(payload)>LID_LIMITS['max_input_bytes']:raise ValueError('Language input scope exceeded')
    inp.write_bytes(payload)
    scores=[]
    if parts:
        predict(Path(plan['detector']['binary']),Path(plan['detector']['model']),inp,out,LID_LIMITS)
        lines=out.read_text().splitlines()
        if len(lines)!=len(parts):raise ValueError('Incomplete language window output')
        scores=[top_scores(line) for line in lines]
    for row in prepared:
        for part in row['windows']:
            part['scores']=scores[part.pop('prediction_index')]
        if row['windows'] and any(not p['scores'] or p['scores'][0]['language']!='en' or p['scores'][0]['score']<.8 for p in row['windows']):
            row['reasons'].append('window_english_signal')
        row['classifier_projection']=dict(rule='fasttext-line-escape-v1',original_source_unchanged=True)
    for p in (inp,out,work/'detector.stderr'):
        if p.exists():p.unlink()
    return prepared


def summarize(name,output,payload,chosen):
    return dict(file=name,group=chosen,rows=len(output),rows_cache_key='rows/'+name,
        rows_sha256=hashlib.sha256(payload).hexdigest(),
        provisional_quality_pass=sum(r['provisional_quality_pass'] for r in output),
        actual_student_bpe_text_tokens=sum(r['actual_student_bpe_text_tokens'] for r in output),
        provisional_pass_text_tokens=sum(r['actual_student_bpe_text_tokens'] for r in output if r['provisional_quality_pass']),
        reason_counts=dict(Counter(reason for r in output for reason in r['reasons'])),
        seed_counts=dict(Counter(r['row']['seed_data'] for r in output)),
        audience_counts=dict(Counter(r['row']['audience'] for r in output)),
        format_counts=dict(Counter(r['row']['format'] for r in output)))


def worker():
    plan=read(PLAN)
    for p,h in plan['input_bindings'].items():
        if sha(p)!=h:raise ValueError('Intake input binding changed')
    ledger=IntakeLedger(ROOT/'charges',plan['ledger_contract']);cache=IntakeCache(ROOT/'cache',ledger)
    try:
        if not ledger.db.execute('SELECT 1 FROM attempts WHERE key=?',('inherited-metadata',)).fetchone():
            ledger.reserve('inherited-metadata',**plan['inherited_metadata_charge']);ledger.finish('inherited-metadata',raw=b'')
        if not ledger.db.execute('SELECT 1 FROM attempts WHERE key=?',('auxiliary-artifacts',)).fetchone():
            ledger.reserve('auxiliary-artifacts',output_bytes=1048576);ledger.finish('auxiliary-artifacts',raw=b'')
        guard_spec=read('configs/future-intake-evaluation-exclusions-v1.json')
        guard=EvaluationExclusions(guard_spec['inventory'],guard_spec['inventory_sha256'])
        bpe=BPE.load(plan['tokenizer']);inventory=read(plan['inventory'])
        selected=sorted(inventory,key=lambda i:digest([plan['selection_seed'],i['path']]))[:50]
        completed=[];skipped=[]
        language_work=ROOT/'language-v2';language_work.mkdir(exist_ok=True)
        for file_index,item in enumerate(selected):
            ledger.check_time()
            if shutil.disk_usage('.').free<plan['minimum_free_disk_bytes']:raise ValueError('Free disk reserve reached')
            if sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file())>plan['maximum_work_disk_bytes']:raise ValueError('Work disk cap reached')
            name=item['path'];output_key='rows/'+name
            if name in plan['skip_uncertain_files']:
                skipped.append(plan['skip_uncertain_files'][name]);continue
            existing=cache.existing(output_key)
            if existing is not None:
                recovered=[json.loads(line) for line in existing.splitlines()]
                chosen=json.loads(cache.existing('metadata/'+name))
                if len(recovered)!=chosen['rows']:raise ValueError('Completed row count differs')
                state=ledger.db.execute('SELECT state FROM attempts WHERE key=?',('decode/'+name,)).fetchone()
                if state==('pending',):ledger.finish('decode/'+name,raw=b'')
                elif state!=('complete',):raise ValueError('Completed rows lack decode reservation')
                done=summarize(name,recovered,existing,chosen);save(ROOT/f'file-{file_index:02d}.json',done)
                completed.append(done);continue
            url=f"https://huggingface.co/datasets/HuggingFaceTB/smollm-corpus/resolve/{plan['revision']}/{name}"
            class Transport(ExactRanges):
                def get(self,start,length):
                    inherited=plan['inherited_ranges'].get(name+':'+str(start)+':'+str(length))
                    if inherited:
                        if sha(inherited['path'])!=inherited['sha256']:raise ValueError('Inherited metadata interval differs')
                        raw=Path(inherited['path']).read_bytes()
                        if len(raw)!=length:raise ValueError('Inherited interval size differs')
                        return raw
                    return cache.fetch('range/'+name+'/'+str(start)+'/'+str(length),length,
                        lambda:super(Transport,self).get(start,length))
            reader=BoundedParquet(Transport(url,item['size'],'"'+item['xetHash']+'"',Limits(**plan['range_limits'])))
            if set(reader.metadata.schema.names)!=set(plan['fields']):raise ValueError('Pinned Parquet fields differ')
            compatible=[g for i in range(reader.metadata.num_row_groups) if (g:=group_info(reader,i)) is not None]
            if not compatible:raise ValueError('No row group fits unchanged limits')
            chosen=min(compatible,key=lambda g:digest([plan['selection_seed'],name,g['index']]))
            cache.publish('metadata/'+name,encoded(chosen))
            row_key='decode/'+name
            if ledger.db.execute('SELECT 1 FROM attempts WHERE key=?',(row_key,)).fetchone():raise ValueError('Uncertain prior decode cannot repeat')
            ledger.reserve(row_key,rows=chosen['rows'])
            table=reader.read_group(chosen['index']);raw_rows=table.to_pylist();del table
            screened=quality(raw_rows,guard,plan,language_work);output=[]
            for local,r in enumerate(screened):
                raw=r.pop('raw');seed=r.pop('seed')
                if seed:seed={k:v for k,v in seed.items() if k!='seed_excerpt'}
                output.append(dict(source='HuggingFaceTB/smollm-corpus',revision=plan['revision'],file=name,
                    row_group=chosen['index'],row_in_group=local,row=raw,raw_record_sha256=digest(raw),
                    seed=seed,**r,actual_student_bpe_text_tokens=len(bpe.encode(raw['text'])),
                    provisional_quality_pass=not r['reasons'],training_approved=False,partition=None,
                    pending='Global exact/near/seed overlap and ancestral-heldout checks, finite membership admission.'))
            payload=b''.join(encoded(r) for r in output);cache.publish(output_key,payload)
            ledger.finish(row_key,raw=b'')
            done=summarize(name,output,payload,chosen)
            save(ROOT/f'file-{file_index:02d}.json',done);completed.append(done)
            save(ROOT/'progress.json',dict(files=len(completed),rows=sum(r['rows'] for r in completed),reserved=ledger.totals()))
            print(json.dumps(dict(files=len(completed),rows=sum(r['rows'] for r in completed),provisional=sum(r['provisional_quality_pass'] for r in completed))),flush=True)
            for p,h in plan['input_bindings'].items():
                if sha(p)!=h:raise ValueError('Frozen intake input changed during execution')
        snapshot=ledger.snapshot();save(ROOT/'ledger-snapshot.json',snapshot)
        report=dict(creator='Navneet Prabhakar',kind='actual-cosmopedia-bounded-candidate-intake-v2',complete=True,
            plan_sha256=sha(PLAN),files=completed,skipped_uncertain_files=skipped,source_execution_phases=plan['source_execution_phases'],rows=sum(r['rows'] for r in completed),
            provisional_quality_pass=sum(r['provisional_quality_pass'] for r in completed),
            provisional_pass_text_tokens=sum(r['provisional_pass_text_tokens'] for r in completed),
            actual_student_bpe_text_tokens=sum(r['actual_student_bpe_text_tokens'] for r in completed),
            reserved=snapshot['reserved'],ledger_snapshot_sha256=sha(ROOT/'ledger-snapshot.json'),
            new_successful_body_bytes=sum(r['actual_body_bytes'] or 0 for r in snapshot['attempts']),
            inherited_successful_body_bytes=plan['inherited_successful_body_bytes'],
            training_approved=False,model_updates=0,teacher_calls=0,cloud_spend=0,
            scope='Pinned clustered candidate intake with exact seed, original prompt/body exclusion, privacy signals and full-window English checks for otherwise eligible rows. Provisional passes require global duplicate/heldout screening and corpus admission. No hard-RSS guarantee, paraphrase isolation or factual certification.')
        save(ROOT/'report.json',report);save(Path('reports/cosmopedia-candidate-intake.json'),report)
    except BaseException as error:
        save(ROOT/'continuation-failure-v2.json',dict(complete=False,error_type=type(error).__name__,message='Intake stopped; preserve cache and conservative charges. No automatic retries.',ledger=ledger.snapshot()))
        raise SystemExit('Finite intake stopped; inspect retained evidence without replay') from None
    finally:ledger.close()


def main():
    if '--worker' in sys.argv:worker();return
    plan=read(PLAN)
    if ROOT.exists() and '--resume' not in sys.argv:raise FileExistsError('Existing attempt; inspect authoritative process before explicit resume')
    ROOT.mkdir(exist_ok=True)
    with (ROOT/'supervisor.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if (ROOT/'report.json').exists():raise ValueError('Completed intake cannot replay')
        if read(ROOT/'plan.json')!=read(plan['original_plan']):raise ValueError('Original immutable intake plan changed')
        if (ROOT/'continuation-plan-v2.json').exists():
            if read(ROOT/'continuation-plan-v2.json')!=plan:raise ValueError('Immutable continuation plan changed')
        else:save(ROOT/'continuation-plan-v2.json',plan)
        remaining=plan['ledger_contract']['wall_seconds']
        if (ROOT/'charges/ledger.sqlite').exists():
            db=sqlite3.connect(f'file:{(ROOT/"charges/ledger.sqlite").resolve()}?mode=ro',uri=True)
            deadline=db.execute('SELECT deadline FROM job').fetchone()[0];db.close();remaining=min(remaining,deadline-time.time())
        if remaining<=0:raise ValueError('Original intake deadline expired')
        child=subprocess.Popen([sys.executable,__file__,'--worker'],start_new_session=True)
        try:
            code=child.wait(timeout=remaining)
            if code:raise SystemExit(code)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid,signal.SIGKILL);child.wait()
            save(ROOT/'supervisor-timeout.json',dict(complete=False,independent_wall_stop=True,automatic_retry=False))
            raise SystemExit('Finite supervisor stopped owned intake process group') from None


if __name__=='__main__':main()

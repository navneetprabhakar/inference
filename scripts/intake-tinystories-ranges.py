"""Finite narrative acquisition: protect official heldouts, then sparse train ranges."""
# Creator: Navneet Prabhakar
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
from urllib.parse import quote
import urllib.request
from slm.data.intake_cache import IntakeCache
from slm.data.intake_ledger import IntakeLedger
from slm.data.parquet_ranges import ExactRanges, Limits
from slm.data.story_segments import segments
from slm.data.tokenized import sha

ROOT=Path('data/tinystories-range-intake-v1')
PLAN=Path('configs/tinystories-range-intake-v1.json')


def encoded(v):return (json.dumps(v,sort_keys=True,ensure_ascii=False)+'\n').encode()
def save(p,v):p.write_bytes(encoded(v))


def worker():
    plan=json.loads(PLAN.read_text())
    for p,h in plan['input_bindings'].items():
        if sha(p)!=h:raise ValueError('Pinned narrative input changed')
    ledger=IntakeLedger(ROOT/'charges',plan['ledger_contract']);cache=IntakeCache(ROOT/'cache',ledger)
    stage='initialization'
    try:
        ledger.reserve('prior-source-preparation',**plan['prior_source_charge']);ledger.finish('prior-source-preparation',raw=b'')
        ledger.reserve('auxiliary-artifacts',output_bytes=1048576);ledger.finish('auxiliary-artifacts',raw=b'')
        inventory={r['path']:r for r in json.loads(Path(plan['inventory']).read_text()) if r['type']=='file'}
        completed=[]
        for request in plan['requests']:
            stage=request['key'];ledger.check_time()
            if shutil.disk_usage('.').free<plan['minimum_free_disk_bytes']:raise ValueError('Free disk reserve reached')
            if sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file())>plan['maximum_work_disk_bytes']:raise ValueError('Work disk cap reached')
            item=inventory[request['file']];start=request['start'];length=request['length']
            url=f"https://huggingface.co/datasets/roneneldan/TinyStories/resolve/{plan['revision']}/{quote(item['path'])}"
            if request['kind']=='evaluation_prompts':
                def producer():
                    req=urllib.request.Request(url,headers={'Accept-Encoding':'identity'})
                    with urllib.request.urlopen(req,timeout=45) as response:
                        if response.status!=200 or response.headers.get('Content-Encoding','identity')!='identity':raise ValueError('Identity prompt response required')
                        raw=response.read(length+1)
                    if len(raw)!=length:raise ValueError('Prompt file size differs')
                    blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
                    if blob!=item['oid']:raise ValueError('Git prompt content identity differs')
                    raw.decode('utf-8',errors='strict')
                    return raw
                raw=cache.fetch('body/'+stage,length,producer)
                summary=dict(request=request,body_sha256=hashlib.sha256(raw).hexdigest(),records=0,
                    protection_status='Full raw evaluation artifact retained; structured prompt extraction required before admission.')
            else:
                transport=ExactRanges(url,item['size'],'"'+item['xetHash']+'"',Limits(network_bytes=length+1,requests=1))
                raw=cache.fetch('body/'+stage,length,lambda:transport.get(start,length))
                if request['kind']=='official_validation':
                    if hashlib.sha256(raw).hexdigest()!=item['lfs']['oid']:raise ValueError('Full official validation LFS digest differs')
                ledger.reserve('parse/'+stage,rows=plan['max_records_per_range'])
                rows=segments(raw,start,item['size'],max_records=plan['max_records_per_range'])
                if not rows:raise ValueError('No complete stories in retained range')
                payload=b''.join(encoded(dict(source='roneneldan/TinyStories',revision=plan['revision'],
                    file=item['path'],source_group=item['path']+':'+str(r['start']),row=r,
                    partition='validation' if request['kind']=='official_validation' else None,
                    training_approved=False,provisional_quality_pass=False,
                    pending='Official heldout protection and cross-source family/near grouping; narrative quality review and finite admission.')) for r in rows)
                cache.publish('records/'+stage,payload);ledger.finish('parse/'+stage,raw=b'')
                summary=dict(request=request,body_sha256=hashlib.sha256(raw).hexdigest(),records=len(rows),
                    records_sha256=hashlib.sha256(payload).hexdigest(),text_bytes=sum(r['end']-r['start'] for r in rows),
                    full_file_lfs_verified=request['kind']=='official_validation',
                    discarded_boundary_bytes=len(raw)-sum(r['end']-r['start'] for r in rows)-raw.count(b'<|endoftext|>')*len(b'<|endoftext|>'))
            completed.append(summary);cache.publish('summary/'+stage,encoded(summary))
            print(json.dumps(dict(completed=len(completed),file=item['path'],kind=request['kind'],records=summary['records'])),flush=True)
        for p,h in plan['input_bindings'].items():
            if sha(p)!=h:raise ValueError('Pinned narrative input changed during acquisition')
        snapshot=ledger.snapshot();save(ROOT/'ledger-snapshot.json',snapshot)
        result=dict(creator='Navneet Prabhakar',kind='actual-bounded-tinystories-range-intake-v1',complete=True,
            plan_sha256=sha(PLAN),revision=plan['revision'],requests=completed,reserved=snapshot['reserved'],
            successful_body_bytes=sum(r['actual_body_bytes'] or 0 for r in snapshot['attempts'])+plan['prior_source_successful_body_bytes'],
            narrative_train_records=sum(r['records'] for r in completed if r['request']['kind']=='train_range'),
            official_validation_records=sum(r['records'] for r in completed if r['request']['kind']=='official_validation'),
            training_approved=False,model_updates=0,teacher_calls=0,cloud_spend=0,
            scope='Byte-exact complete story records and raw published evaluation prompts; no quality approval, token sizing, global isolation or training admission. Sparse boundary fragments discarded without text repair. Official validations retain upstream partition, not a new independent benchmark.')
        save(ROOT/'report.json',result);save(Path('reports/tinystories-range-intake.json'),result)
    except BaseException as error:
        save(ROOT/'failure.json',dict(complete=False,error_type=type(error).__name__,stage=stage,
            message='Bounded narrative acquisition stopped; retain charges and outputs; no automatic retry.',ledger=ledger.snapshot()))
        raise SystemExit('Narrative intake stopped; inspect retained evidence') from None
    finally:ledger.close()


def main():
    if '--worker' in sys.argv:worker();return
    if ROOT.exists():raise FileExistsError('Narrative acquisition already attempted')
    ROOT.mkdir();save(ROOT/'plan.json',json.loads(PLAN.read_text()))
    child=subprocess.Popen([sys.executable,__file__,'--worker'],start_new_session=True)
    try:
        code=child.wait(timeout=3600)
        if code:raise SystemExit(code)
    except BaseException:
        if child.poll() is None:
            os.killpg(child.pid,signal.SIGKILL);child.wait()
        raise


if __name__=='__main__':main()

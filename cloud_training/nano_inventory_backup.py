"""Serial backup of completed, unadmitted corpus shards; never reads SQLite.

Run only after other inventory uploaders stop. Paths in the atomic progress report
are relative to --workspace. Metadata is published after verified payload upload.
"""
from __future__ import annotations
import argparse
import base64
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

PREFIX='gs://forge-ownbase-a100-20261110/ownbase-v2/corpus-inventory'
TERMINAL={'bounded_corpus_packed_review_pending','stopped_incomplete'}


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def atomic(path,value):
    path=Path(path);part=path.with_suffix(path.suffix+'.partial')
    with part.open('w') as f:
        json.dump(value,f,sort_keys=True,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(part,path)
    fd=os.open(path.parent,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)


def acquire_lock(path):
    handle=Path(path).open('a+b')
    try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BaseException:handle.close();raise
    return handle


def inspect_entry(entry,split,tokenizer,workspace):
    if not entry.get('manifest_sha256') or not entry.get('directory'):
        return None  # Producer has not published a completed entry.
    directory=(Path(workspace)/entry['directory']).resolve()
    if not re.fullmatch(r'shard_[0-9]+',directory.name):raise ValueError('Invalid shard name')
    manifest,audit=directory/'manifest.json',directory/'audit.json'
    if not manifest.is_file() or not audit.is_file():return None
    if sha(manifest)!=entry['manifest_sha256']:raise ValueError('Changed completed manifest')
    m=json.loads(manifest.read_text());a=json.loads(audit.read_text())
    if a!=entry:raise ValueError('Completed audit differs from atomic progress entry')
    if (m.get('training_admitted') is not False or a.get('training_admitted') is not False
        or m.get('split')!=split or m.get('tokenizer_sha256')!=tokenizer
        or m.get('file')!='rows.u16' or m.get('sequence_length')!=2048 or m.get('vocab_size')!=32768
        or m.get('schema')!=1 or m.get('format')!='uint16-le-fixed-T-plus-1'
        or a.get('rows')!=m.get('rows') or a.get('targets')!=m.get('target_tokens')
        or m.get('target_tokens')!=m.get('rows',0)*2048):raise ValueError('Shard identity or completion mismatch')
    payload=directory/'rows.u16'
    if not payload.is_file() or payload.stat().st_size!=m['bytes'] or m['bytes']!=m['rows']*2049*2:
        raise ValueError('Incomplete payload size')
    return {'key':split+'/'+directory.name,'directory':str(directory),'manifest_sha256':sha(manifest),
            'audit_sha256':sha(audit),'payload_sha256':m['sha256'],'bytes':m['bytes'],
            'payload_mtime_ns':payload.stat().st_mtime_ns,'training_admitted':False}


def command(args,deadline):
    remaining=deadline-time.monotonic()
    if remaining<=0:raise TimeoutError('Backup lease expired')
    return subprocess.run(['gcloud','storage',*args],capture_output=True,text=True,
                          timeout=min(600,remaining),check=True).stdout


def remote_metadata(uri,expected,deadline,runner):
    try:raw=runner(['cat',uri],deadline)
    except subprocess.CalledProcessError as exc:
        error=(exc.stderr or '')
        if re.search(r'\b404\b|No URLs matched|NotFound',error):return False
        raise
    if hashlib.sha256(raw.encode()).hexdigest()!=expected:raise ValueError('Existing remote metadata mismatch: '+uri)
    return True


def upload(entry,deadline,runner=command):
    directory=Path(entry['directory']);prefix=PREFIX+'/'+entry['key']
    for name,key in [('manifest.json','manifest_sha256'),('audit.json','audit_sha256')]:
        remote_metadata(prefix+'/'+name,entry[key],deadline,runner)
    h=hashlib.sha256();md5=hashlib.md5()
    with (directory/'rows.u16').open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):
            if time.monotonic()>=deadline:raise TimeoutError('Backup lease expired during hash')
            h.update(chunk);md5.update(chunk)
    if h.hexdigest()!=entry['payload_sha256']:raise ValueError('Completed payload SHA mismatch')
    runner(['cp','--no-clobber',str(directory/'rows.u16'),prefix+'/rows.u16'],deadline)
    remote=json.loads(runner(['objects','describe',prefix+'/rows.u16','--format=json'],deadline))
    expected_md5=base64.b64encode(md5.digest()).decode()
    if int(remote.get('size',-1))!=entry['bytes'] or remote.get('md5_hash',remote.get('md5Hash'))!=expected_md5:
        raise ValueError('Remote payload size/checksum mismatch after no-clobber')
    for name,key in [('audit.json','audit_sha256'),('manifest.json','manifest_sha256')]:
        if sha(directory/name)!=entry[key]:raise ValueError('Local metadata changed before publication')
        runner(['cp','--no-clobber',str(directory/name),prefix+'/'+name],deadline)
        if not remote_metadata(prefix+'/'+name,entry[key],deadline,runner):raise ValueError('Remote publication missing')
    return dict(entry,remote_prefix=prefix,remote_md5=expected_md5,
                transfer='gcloud checksums plus remote MD5/size; metadata SHA256 readback',
                independent_remote_payload_sha256=False)


def scan(report_path,workspace,receipt_path,deadline,*,dry_run=False,runner=command):
    report=json.loads(Path(report_path).read_text())
    if report.get('training_admitted') is not False:raise ValueError('Only unadmitted prep inventory accepted')
    path=Path(receipt_path)
    receipt=json.loads(path.read_text()) if path.exists() else {'schema':1,'prefix':PREFIX,'entries':{}}
    if receipt.get('schema')!=1 or receipt.get('prefix')!=PREFIX:raise ValueError('Receipt scope mismatch')
    pending=[];incomplete=0
    for split in ('train','validation'):
        if not isinstance(report.get(split),list):raise ValueError('Missing report split list')
        for candidate in report[split]:
            if time.monotonic()>=deadline:raise TimeoutError('Backup lease expired')
            entry=inspect_entry(candidate,split,report['tokenizer_sha256'],workspace)
            if entry is None:incomplete+=1;continue
            old=receipt['entries'].get(entry['key'])
            if old:
                if any(old.get(k)!=v for k,v in entry.items()):raise ValueError('Previously backed-up local shard changed')
                continue
            pending.append(entry['key'])
            if dry_run and sha(Path(entry['directory'])/'rows.u16')!=entry['payload_sha256']:
                raise ValueError('Completed payload SHA mismatch')
            if not dry_run:
                receipt['entries'][entry['key']]=upload(entry,deadline,runner)
                atomic(path,receipt)
    return {'status':report['status'],'pending':pending,'incomplete_entries':incomplete,
            'terminal_all_uploaded':report['status'] in TERMINAL and not incomplete and (not pending or not dry_run),
            'training_admitted':False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--report',required=True);p.add_argument('--receipt',required=True)
    p.add_argument('--workspace',default='.');p.add_argument('--deadline-seconds',type=int,required=True)
    p.add_argument('--poll-seconds',type=int,default=120);p.add_argument('--dry-run',action='store_true')
    a=p.parse_args()
    if not 0<a.deadline_seconds<=28800 or a.poll_seconds<60:p.error('Deadline must be <=8h; polling >=60s')
    os.nice(10)  # Yield local CPU to the corpus producer.
    path=Path(a.receipt);path.parent.mkdir(parents=True,exist_ok=True)
    with acquire_lock(Path(a.workspace).resolve()/'.nano-inventory-backup.lock'):
        deadline=time.monotonic()+a.deadline_seconds
        while time.monotonic()<deadline:
            result=scan(a.report,a.workspace,path,deadline,dry_run=a.dry_run)
            print(json.dumps(result),flush=True)
            if a.dry_run or result['terminal_all_uploaded']:return
            wake=min(deadline,time.monotonic()+a.poll_seconds)
            while time.monotonic()<wake:time.sleep(min(60,wake-time.monotonic()))


if __name__=='__main__':main()

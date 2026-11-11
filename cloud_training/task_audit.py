"""Append-only task evidence journal; timestamps distinguish observation from event."""
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path


def append(path, task, status, summary, *, evidence=(), occurred_utc=None):
    if status not in ('completed','in_progress','pending','blocked','decision','failed'):
        raise ValueError('Explicit task status required')
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    refs=[]
    for name in evidence:
        p=Path(name)
        refs.append({'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    with path.open('a+',encoding='utf8') as f:
        fcntl.flock(f,fcntl.LOCK_EX);f.seek(0);lines=f.read().splitlines()
        previous=hashlib.sha256(lines[-1].encode()).hexdigest() if lines else None
        record={'sequence':len(lines)+1,'observed_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
                'occurred_utc':occurred_utc,'task':task,'status':status,'summary':summary,
                'evidence':refs,'previous_record_sha256':previous}
        f.seek(0,2);f.write(json.dumps(record,sort_keys=True)+'\n');f.flush();os.fsync(f.fileno())
    return record


def render(log_path, board_path, output_path):
    events=[json.loads(line) for line in Path(log_path).read_text().splitlines() if line.strip()]
    board=json.loads(Path(board_path).read_text())
    latest={e['task']:e for e in events}
    lines=['OWN-BASE TRAINING AUDIT', 'Updated: '+dt.datetime.now(dt.timezone.utc).isoformat(),
           'Authorized total GCP cap: $100. Estimates are not final invoices.',
           'Objective: usable conversation and calculator/conversion calls from our own random base.',
           '', 'CURRENT TASKS']
    for item in board['tasks']:
        event=latest.get(item['id']);status=event['status'] if event else item['status']
        lines.append(f"[{status.upper()}] {item['id']}: {event['summary'] if event else item['description']}")
    lines+=['','AUDIT TRAIL (observed timestamps; historical event times may be unknown)']
    for e in events:
        lines.append(f"{e['sequence']:03d} {e['observed_utc']} [{e['status']}] {e['task']}: {e['summary']}")
        lines.extend('    Evidence: '+r['path']+' SHA256='+r['sha256'] for r in e['evidence'])
    Path(output_path).write_text('\n'.join(lines)+'\n')

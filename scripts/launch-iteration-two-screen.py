#!/usr/bin/env python3
"""Reserve one frozen optimizer screen; no retries or additional exposure."""
# Creator: Navneet Prabhakar
import argparse
from datetime import datetime,timezone
import fcntl
import json
from pathlib import Path
import subprocess
import sys
from slm.data.schema import digest
from slm.data.tokenized import sha
from slm.train import run


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--trial',required=True,choices=['lr-0003','lr-0010']);args=parser.parse_args()
    root=Path('data/iteration-two-experiment-v1').resolve();protocol=json.loads((root/'protocol.json').read_text())
    freeze=json.loads(Path('reports/milestone-forty-eight-experiment-freeze.json').read_text())
    if sha(root/'protocol.json')!=freeze['protocol_sha256'] or digest(protocol['groups'])!=protocol['groups_sha256']:raise ValueError('Frozen protocol differs')
    for path,want in protocol['source_sha256'].items():
        if sha(path)!=want:raise ValueError('Frozen experiment implementation differs')
    spec_path=root/(args.trial+'.json')
    if sha(spec_path)!=protocol['specs'][args.trial]['spec_file_sha256']:raise ValueError('Frozen trial spec differs')
    # This lock remains held for the entire real run; reservations are durable.
    with (root/'execution.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if args.trial=='lr-0010':
            first=root/'runs/lr-0003/report.json'
            if not first.exists() or json.loads(first.read_text())['final']!=dict(step=256,cursor=256,tokens=262144,supervised_tokens=262144):raise ValueError('Complete first screen required before second')
        reservations=root/'reservations';reservations.mkdir(exist_ok=True)
        with (reservations/(args.trial+'.json')).open('x') as out:
            json.dump(dict(creator='Navneet Prabhakar',trial=args.trial,protocol_sha256=sha(root/'protocol.json'),
                plan_hash=protocol['plan_hashes'][args.trial],reserved_processed_positions=262144,
                reserved_at_utc=datetime.now(timezone.utc).isoformat(),launch_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
                note='Reservation persists on failure. No automatic retry or reset.'),out,indent=2)
        report=run(json.loads(spec_path.read_text()),root/'runs'/args.trial,backend='mlx',device='default',
            max_new_updates=256,wall_seconds=protocol['invocation']['screen_soft_wall_seconds'])
        if report['plan_hash']!=protocol['plan_hashes'][args.trial]:raise ValueError('Actual trial plan differs')
        print(json.dumps({k:report[k] for k in ('plan_hash','status','final','latest_checkpoint')},indent=2),flush=True)


if __name__=='__main__':main()

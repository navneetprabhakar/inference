"""Root-only SFT candidate custody. No scoring or disclosure of protected cases."""
import argparse
from collections import Counter
import json
from pathlib import Path
import resource
import shutil
import signal
import sqlite3
import sys
import time

from checkpoint import checksum
from pretrain import atomic_status
from protect_language_mixture import ROOT, PRIVATE, PRIVATE_SHA, HISTORICAL, augment, candidate_history
from protect_split import Shield, DEV_SHA, SEALED_SHA
from protect_validation_b import BShield, B_SHA
from language_overlap_index import TextOverlapIndex


def protected_index(guard):
    guard()
    if checksum(PRIVATE) != PRIVATE_SHA:
        raise ValueError('private acceptance identity changed')
    shield = Shield()
    augment(shield, json.loads(PRIVATE.read_bytes()))
    historical = {}
    for version in ('sft-v1', 'sft-v2', 'sft-v3'):
        for split in ('dev', 'test'):
            path = HISTORICAL/version/(split+'.jsonl')
            if not path.is_file() or path.stat().st_size > 4*1024**2:
                raise ValueError('historical holdout missing or outside audited size bound')
            before = checksum(path)
            rows = 0
            with path.open() as stream:
                for line in stream:
                    guard()
                    if line.strip():
                        augment(shield, json.loads(line))
                        rows += 1
            if checksum(path) != before:
                raise ValueError('historical holdout changed while fingerprinting')
            historical[str(path)] = dict(sha256=before, rows=rows)
    shields = (shield, BShield())
    return TextOverlapIndex(shields), shields, historical


def screen(directory):
    directory = Path(directory).resolve()
    started = time.monotonic()
    if (directory/'custody.json').exists():
        raise FileExistsError('preserve existing custody receipt')
    def deadline(signum, frame):
        raise TimeoutError('custody wall-clock ceiling')
    signal.signal(signal.SIGALRM, deadline)
    signal.alarm(1800)
    def guard():
        if (ROOT/'runs/STOP').exists() or (directory/'STOP').exists():
            raise InterruptedError('explicit STOP')
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if sys.platform != 'darwin':
            peak *= 1024
        if time.monotonic()-started > 1800 or peak > 3*1024**3:
            raise RuntimeError('custody time or memory ceiling')
        if shutil.disk_usage(directory).free < 20*1024**3:
            raise RuntimeError('custody disk floor')
    guard()
    paths = {name: directory/name for name in
             ('candidates.sqlite', 'partial-candidate-manifest.json', 'candidate-verification.json')}
    pins = {name: checksum(path) for name, path in paths.items()}
    verification = json.loads(paths['candidate-verification.json'].read_bytes())
    if (verification.get('state') != 'PASS_pre_host_policy_not_admitted'
            or verification.get('failures', []) != []
            or type(verification.get('verified_rows')) is not int or verification['verified_rows'] <= 0
            or verification.get('database_sha256') != pins['candidates.sqlite']
            or verification.get('manifest_sha256') != pins['partial-candidate-manifest.json']):
        raise ValueError('matching complete independent verification required')
    index, shields, historical = protected_index(guard)
    denied = []
    counts = Counter()
    by_source = {}
    with sqlite3.connect(f'file:{paths["candidates.sqlite"]}?mode=ro', uri=True) as db:
        for identifier, source, split, text, raw_history in db.execute(
                'select doc_id,source,split,text,selected_history_json from documents'):
            guard()
            if not isinstance(text, str) or len(text.encode()) > 1024**2 or len(raw_history.encode()) > 1024**2:
                raise ValueError('candidate exceeds audited text-size bound')
            history = json.loads(raw_history)
            messages = candidate_history(text)
            messages.extend(dict(role='user', text=m['text']) for m in history if isinstance(m.get('text'), str))
            reject = index.matches_history(messages)
            if not reject and any('call' in m for m in history):
                reject = any(shield.reasons(history) for shield in shields)
            if reject:
                denied.append(identifier)
            counts['reviewed'] += 1
            counts['excluded'] += bool(reject)
            group = by_source.setdefault(source+'/'+split, dict(reviewed=0, excluded=0))
            group['reviewed'] += 1
            group['excluded'] += bool(reject)
            if counts['reviewed'] % 1000 == 0:
                atomic_status(directory/'custody-progress.json', dict(counts, seconds=time.monotonic()-started))
    if counts['reviewed'] != verification['verified_rows']:
        raise ValueError('candidate count differs from independent verification')
    if any(checksum(paths[name]) != sha for name, sha in pins.items()):
        raise ValueError('candidate identity changed during custody')
    receipt = dict(state='screened_not_admitted', training_admitted=False,
                   pins=pins, excluded_doc_ids=denied, counts=dict(counts), by_source=by_source,
                   protected_sha256=dict(A=DEV_SHA, B=B_SHA, release=SEALED_SHA, practical=PRIVATE_SHA),
                   historical_chat_holdouts=historical, index=index.statistics(),
                   seconds=time.monotonic()-started,
                   code_sha256={name: checksum(ROOT/name) for name in
                       ('protect_own_sft.py', 'protect_language_mixture.py', 'protect_split.py',
                        'protect_validation_b.py', 'language_overlap_index.py')},
                   method='Full parent and selected text exact/shape/eight-word/anchor screen plus structured protected call signatures. Approximate, not semantic-independence proof; no protected case is scored or disclosed.',
                   pending='Content quality review, runtime-policy transformation, target recount and final admission')
    atomic_status(directory/'custody.json', receipt)
    signal.alarm(0)
    print(json.dumps(dict(state=receipt['state'], counts=dict(counts), by_source=by_source,
                          seconds=receipt['seconds'], training_admitted=False), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    screen(parser.parse_args().directory)

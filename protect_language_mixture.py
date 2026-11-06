"""Root-custodian corpus screen; publish only source IDs and aggregate counts.

Private acceptance prompts/answers are read by this process, never printed or
passed to corpus builders or training. Matching is approximate, not proof of
semantic independence. No evaluation is performed.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import resource
import shutil
import signal
import sqlite3
import sys
import time

from checkpoint import checksum
from pretrain import atomic_status
from protect_split import Shield, DEV_SHA, SEALED_SHA, words, grams, shape, anchors, signature
from protect_validation_b import BShield, B_SHA
from language_overlap_index import TextOverlapIndex

ROOT = Path(__file__).resolve().parent
PRIVATE = ROOT/'runs/practical-usability-custody-01/cases.json'
PRIVATE_SHA = '1c2142d1636811a2e0ed984b2156878bf2bab70668a9dd670a02a25fa447bdff'
HISTORICAL = ROOT.parent/'inference-snapshot-20261105-c5b911b/data'


def values(value):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from values(item)
    elif isinstance(value, list):
        for item in value:
            yield from values(item)
    elif isinstance(value, str):
        yield value


def augment(shield, cases):
    for value in values(cases):
        if isinstance(value, dict):
            call = signature(value)
            if call is not None:
                shield.calls.add(call)
            continue
        tokens = words(value)
        if len(tokens) < 3:
            continue
        shield.exact.add(tuple(tokens))
        shield.shapes.add(shape(value))
        shield.grams.update(grams(value))
        terms = anchors(value)
        if len(terms) >= 3:
            index = len(shield.anchor_sets)
            shield.anchor_sets.append(terms)
            for term in terms:
                shield.by_anchor[term].add(index)


def candidate_history(text):
    # Always scan the full document as well as each role-delimited turn. A
    # whole-transcript comparison alone misses short held-out user prompts.
    history = [dict(role='user', text=text)]
    starts = list(re.finditer(r'^(User|Assistant): ', text, re.MULTILINE))
    for index, match in enumerate(starts):
        end = starts[index+1].start() if index+1 < len(starts) else len(text)
        history.append(dict(role='user', text=text[match.end():end].strip()))
    return history


def screen(directory, manifest_path=None):
    started = time.monotonic()
    directory = Path(directory).resolve()
    if (directory/'custody.json').exists():
        raise FileExistsError('custody receipt already exists; never overwrite a completed screen')
    def deadline(signum, frame):
        raise TimeoutError('custody wall-clock budget exhausted')
    signal.signal(signal.SIGALRM, deadline)
    signal.alarm(30*60)
    def guard():
        if (ROOT/'runs/STOP').exists() or (directory/'STOP').exists():
            raise InterruptedError('explicit STOP')
        if time.monotonic()-started > 30*60:
            raise TimeoutError('custody CPU time budget exhausted')
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if sys.platform != 'darwin':
            peak *= 1024
        if peak > 3*1024**3:
            raise MemoryError('custody peak RSS exceeded 3GiB')
        if shutil.disk_usage(directory).free < 20*1024**3:
            raise OSError('custody free disk below 20GiB')
    guard()
    database = directory/'candidates.sqlite'
    manifest_path = Path(manifest_path).resolve() if manifest_path else directory/'candidate-manifest.json'
    if manifest_path.parent != directory:
        raise ValueError('candidate manifest must belong to the screened directory')
    manifest_sha = checksum(manifest_path)
    manifest = json.loads(manifest_path.read_bytes())
    actual = checksum(database)
    expected = manifest.get('candidate_database_sha256', manifest.get('database_sha256'))
    if actual != expected:
        raise ValueError('candidate database is not frozen')
    verification_path = directory/'input-verification.json'
    verification_sha = checksum(verification_path)
    verification = json.loads(verification_path.read_bytes())
    if (verification.get('state') != 'passed_input_integrity_only'
            or verification.get('failures') != []
            or verification.get('candidate_database_sha256') != actual
            or verification.get('candidate_manifest_sha256') != manifest_sha):
        raise ValueError('matching independent input verification is required')
    private = PRIVATE.read_bytes()
    if hashlib.sha256(private).hexdigest() != PRIVATE_SHA:
        raise ValueError('private acceptance identity changed')
    shield = Shield()
    augment(shield, json.loads(private))
    del private
    historical_receipts = {}
    for version in ('sft-v1', 'sft-v2', 'sft-v3'):
        for split in ('dev', 'test'):
            path = HISTORICAL/version/(split+'.jsonl')
            if not path.is_file() or path.stat().st_size > 4*1024**2:
                raise ValueError('historical chat holdout missing or exceeds audited size bound')
            sha = checksum(path)
            count = 0
            with path.open() as stream:
                for line in stream:
                    guard()
                    if line.strip():
                        augment(shield, json.loads(line))
                        count += 1
            if checksum(path) != sha:
                raise ValueError('historical holdout changed during fingerprinting')
            historical_receipts[str(path)] = dict(sha256=sha, rows=count)
    overlap = TextOverlapIndex((shield, BShield()))
    del shield
    guard()
    counts, denied = Counter(), []
    with sqlite3.connect(f'file:{database}?mode=ro', uri=True) as connection:
        tables = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        if len(tables) != 1 or tables[0][0] not in ('documents', 'candidates', 'docs'):
            raise ValueError('expected one recognized candidate table')
        table = tables[0][0]
        for identifier, text in connection.execute(f'SELECT doc_id,text FROM {table}'):
            guard()
            if not isinstance(text, str) or len(text.encode()) > 1024**2:
                raise ValueError('candidate text exceeds audited per-document size bound')
            history = candidate_history(text)
            # Reasons are deliberately not linked back to individual held-out cases.
            rejected = overlap.matches_history(history)
            if rejected:
                denied.append(identifier)
            counts['reviewed'] += 1
            counts['excluded'] += rejected
            if counts['reviewed'] % 5000 == 0:
                atomic_status(directory/'custody-progress.json', dict(counts, seconds=time.monotonic()-started))
    if checksum(database) != actual:
        raise ValueError('candidate database changed during screening')
    if checksum(manifest_path) != manifest_sha:
        raise ValueError('candidate manifest changed during screening')
    if checksum(verification_path) != verification_sha:
        raise ValueError('input verification changed during screening')
    receipt = dict(state='cleared', candidate_database_sha256=actual, excluded_doc_ids=denied,
                   candidate_manifest=str(manifest_path), candidate_manifest_sha256=manifest_sha,
                   input_verification_sha256=verification_sha,
                   candidate_state=manifest.get('state'), training_admitted=False,
                   counts=dict(counts), seconds=time.monotonic()-started,
                   code_sha256=checksum(Path(__file__)),
                   matching_code_sha256=checksum(ROOT/'language_overlap_index.py'),
                   overlap_index=overlap.statistics(),
                   historical_chat_holdouts=historical_receipts,
                   protected_sha256={'A': DEV_SHA, 'B': B_SHA, 'release': SEALED_SHA, 'practical': PRIVATE_SHA},
                   method='Existing exact/shape/eight-word-shingle/lexical-anchor checks plus private practical acceptance text and rubric fingerprints. Does not prove semantic independence; sealed cases unscored and undisclosed.')
    atomic_status(directory/'custody.json', receipt)
    signal.alarm(0)
    print(json.dumps({k: v for k, v in receipt.items() if k != 'excluded_doc_ids'}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--manifest', type=Path)
    args = parser.parse_args()
    screen(args.directory, args.manifest)

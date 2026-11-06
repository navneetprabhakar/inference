"""Screen prospective base documents without exposing protected prompts to corpus builders."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sqlite3
import time

from checkpoint import checksum
from pretrain import atomic_status
from protect_split import DEV_SHA, SEALED_SHA, Shield
from protect_validation_b import B_SHA, BShield


def screen(directory):
    path = directory/'candidates.sqlite'
    manifest = json.loads((directory/'candidate-manifest.json').read_text())
    actual = checksum(path)
    expected = manifest.get('candidate_database_sha256', manifest.get('database_sha256'))
    if expected is None:
        raise ValueError('candidate manifest needs its database checksum')
    if actual != expected:
        raise ValueError('candidate database differs from its freeze')
    shields = (Shield(), BShield())
    connection = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    columns = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    if len(columns) != 1:
        raise ValueError('ambiguous candidate database tables')
    table = columns[0][0]
    if table not in ('documents', 'candidates', 'docs'):
        raise ValueError('unrecognized source table')
    denied, counts = [], Counter()
    started = time.monotonic()
    for doc_id, text in connection.execute(f'SELECT doc_id,text FROM {table}'):
        reasons = set()
        history = [{'role':'user', 'text':text}]
        for i, shield in enumerate(shields):
            reasons.update(f'{i}:{r}' for r in shield.reasons(history))
        if reasons:
            denied.append(doc_id)
            counts.update(reasons)
        counts['reviewed'] += 1
        if counts['reviewed'] % 5000 == 0:
            atomic_status(directory/'custody-progress.json', dict(reviewed=counts['reviewed'], excluded=len(denied), seconds=time.monotonic()-started))
    connection.close()
    receipt = dict(state='cleared', candidate_database_sha256=actual, excluded_doc_ids=denied,
                   counts=dict(counts), seconds=time.monotonic()-started,
                   protected_sha256={'A':DEV_SHA,'B':B_SHA,'release':SEALED_SHA},
                   method='Existing normalized exact, shape, eight-word shingle and lexical-anchor checks over full source text. This cannot prove semantic independence.')
    atomic_status(directory/'custody.json', receipt)
    print(json.dumps({k:v for k,v in receipt.items() if k!='excluded_doc_ids'},indent=2))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    screen(parser.parse_args().directory)

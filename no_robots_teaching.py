"""Reproducible, frozen, train-only human-authored instruction histories."""
from copy import deepcopy
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
from random import Random

ROOT=Path(__file__).resolve().parent
@lru_cache(maxsize=1)
def records():
    path=ROOT/'data/no-robots/train.jsonl'
    receipt=json.loads((ROOT/'reports/no-robots/receipt.json').read_text())
    if sha256(path.read_bytes()).hexdigest()!=receipt['sha256']:raise ValueError('No Robots train hash mismatch')
    rows=[json.loads(line) for line in path.open()]
    if any(r['official_split']!='train' for r in rows):raise ValueError('Unexpected source split')
    return rows

def examples(seed):
    histories=[deepcopy(r['history']) for r in records()]
    Random(seed).shuffle(histories)
    return histories

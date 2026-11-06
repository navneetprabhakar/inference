"""Root custody of the frozen four-call tool extension; no protected scoring or disclosure."""
import json
from collections import Counter
from pathlib import Path
import resource
import shutil
import signal
import sqlite3
import sys
import time

from checkpoint import checksum
from pretrain import atomic_status
from protect_own_sft import protected_index
from protect_language_mixture import ROOT, PRIVATE_SHA
from protect_split import DEV_SHA, SEALED_SHA
from protect_validation_b import B_SHA


def screen(directory):
    directory = Path(directory).resolve()
    receipt_path = directory/'custody.json'
    if receipt_path.exists():
        raise FileExistsError('preserve completed custody')
    started = time.monotonic()
    def deadline(*args):
        raise TimeoutError('custody time ceiling')
    signal.signal(signal.SIGALRM, deadline)
    signal.alarm(600)
    def guard():
        if (ROOT/'runs/STOP').exists() or (directory/'STOP').exists():
            raise InterruptedError('STOP')
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if sys.platform != 'darwin':
            rss *= 1024
        if rss > 3*1024**3 or time.monotonic()-started > 600:
            raise RuntimeError('resource ceiling')
        if shutil.disk_usage(directory).free < 20*1024**3:
            raise RuntimeError('disk floor')
    guard()
    paths = {n: directory/n for n in ('candidate-manifest.json', 'candidates.sqlite')}
    pins = {n: checksum(p) for n,p in paths.items()}
    manifest = json.loads(paths['candidate-manifest.json'].read_bytes())
    if (manifest['state'] != 'candidate_only_not_admitted' or manifest.get('failure') is not None
            or manifest['database']['sha256'] != pins['candidates.sqlite']):
        raise ValueError('complete matching frozen candidates required')
    if pins['candidate-manifest.json'] != '04b0b3342c172a11d7fe89719617a2466f333df76f98f664611d2c7d269b799a':
        raise ValueError('only the frozen four-call extension is supported')
    code = ('protect_own_tool_extension.py', 'protect_own_sft.py',
            'protect_language_mixture.py', 'protect_split.py',
            'protect_validation_b.py', 'language_overlap_index.py')
    code_pins = {n: checksum(ROOT/n) for n in code}
    index, shields, historical = protected_index(guard)
    denied, totals, groups = [], Counter(), {}
    with sqlite3.connect(f'file:{paths["candidates.sqlite"]}?mode=ro', uri=True) as db:
        if db.execute('pragma integrity_check').fetchone()[0] != 'ok':
            raise ValueError('SQLite integrity')
        for doc_id, family, split, raw, targets in db.execute(
                'select doc_id,family,split,original_lesson_json,target_tokens from documents'):
            guard()
            if len(raw.encode()) > 1024**2:
                raise ValueError('candidate size bound')
            original = json.loads(raw)
            history = original['history']
            # Full original parent and each individual utterance are screened.
            # Original structured proposals also go through every shield.
            texts = [dict(role='user', text=raw)]
            texts.extend(dict(role='user', text=m['text']) for m in history if 'text' in m)
            reject = index.matches_history(texts)
            reject = bool(reject or any(s.reasons(history) for s in shields))
            group = groups.setdefault(split, Counter())
            for counter in (totals, group):
                counter['reviewed'] += 1
                counter['excluded'] += reject
                counter['retained_targets'] += 0 if reject else targets
            if reject:
                denied.append(doc_id)
    expected = sum(r['retained'] for r in manifest['counts'].values())
    if expected != 40:
        raise ValueError('extension population changed')
    if totals['reviewed'] != expected:
        raise ValueError('manifest count mismatch')
    if any(checksum(p) != pins[n] for n,p in paths.items()):
        raise ValueError('input changed during custody')
    if any(checksum(ROOT/n) != sha for n,sha in code_pins.items()):
        raise ValueError('custody code changed')
    guard()
    result = dict(state='screened_not_admitted', training_admitted=False,
                  pins=pins, code_sha256=code_pins, excluded_doc_ids=denied,
                  counts=dict(totals), by_split={k:dict(v) for k,v in groups.items()},
                  protected_sha256=dict(A=DEV_SHA, B=B_SHA, release=SEALED_SHA, practical=PRIVATE_SHA),
                  historical_chat_holdouts=historical, index=index.statistics(),
                  seconds=time.monotonic()-started,
                  method='Original full parent and utterance text overlap plus all original structured call signatures; no protected scoring or disclosure.',
                  limitations='Approximate overlap screen, not semantic independence or correctness certification. Independent quality and final packing checks still required.')
    atomic_status(receipt_path, result)
    signal.alarm(0)
    print(json.dumps({k:result[k] for k in ('state','counts','by_split','seconds')}, indent=2))


if __name__ == '__main__':
    screen(sys.argv[1])

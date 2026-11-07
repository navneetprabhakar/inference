"""Pack independently verified grounded candidates after BOTH custody screens.

Produces no admission or GPU job. Original sources and completed outputs are immutable.
"""
import os
for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[name] = '1'
os.environ['TOKENIZERS_PARALLELISM'] = 'false'
import argparse
import array
from collections import Counter
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import resource
import shutil
import signal
import sqlite3
import sys
import time

from own_base_chat_rows import build_chat_rows
from own_base_tool_adapter import adapt_lesson
from tokenizer import load, ASSETS

ROOT = Path(__file__).resolve().parent
CODE = ('pack_grounded_sft.py', 'own_base_chat_rows.py', 'own_base_tool_adapter.py',
        'own_base_chat.py', 'own_base_sft_rows.py', 'dialogue.py', 'tokenizer.py',
        'tools/__init__.py', 'reports/grounded-curriculum-v1/custody/PACKING-PROTOCOL.md')
CAPS = {'chat': (540000, 60000), 'primary_tool': (270000, 30000),
        'four_call_extension': (90000, 10000)}

def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def read(path):
    return json.loads(Path(path).read_bytes())

def write(path, value):
    with Path(path).open('x') as f:
        json.dump(value, f, indent=2)
        f.write('\n')

def manifest_name(role):
    return 'partial-candidate-manifest.json' if role == 'chat' else 'candidate-manifest.json'

def validate_proofs(directory, role):
    """Require both screens to bind the same verified candidate, then union IDs."""
    names = ('candidates.sqlite', manifest_name(role), 'candidate-verification.json',
             'custody.json', 'public-development-custody.json', 'policy.json')
    if any((directory/n).is_symlink() for n in names):
        raise ValueError('candidate proof alias')
    pins = {n: sha(directory/n) for n in names}
    proof = read(directory/'candidate-verification.json')
    if (proof.get('state') not in {'PASS_pre_host_policy_not_admitted',
                                  'PASS_independent_grounded_candidates_not_admitted'}
            or proof.get('failures') != []
            or type(proof.get('verified_rows')) is not int or proof['verified_rows'] <= 0
            or proof.get('database_sha256') != pins['candidates.sqlite']
            or proof.get('manifest_sha256') != pins[manifest_name(role)]):
        raise ValueError('matching independent candidate proof required')
    manifest = read(directory/manifest_name(role))
    if manifest['database']['sha256'] != pins['candidates.sqlite']:
        raise ValueError('manifest database identity')
    if manifest.get('policy_sha256') != pins['policy.json']:
        raise ValueError('manifest policy identity')
    if manifest.get('state') != 'candidate_only_not_admitted' or manifest.get('failure') is not None:
        raise ValueError('complete candidate manifest required')
    exclusions = set()
    for filename, key in [('custody.json', 'pins'),
                          ('public-development-custody.json', 'candidate_pins')]:
        receipt = read(directory/filename)
        if (receipt.get('state') != 'screened_not_admitted'
                or receipt.get('training_admitted') is not False
                or receipt['counts']['reviewed'] != proof['verified_rows']):
            raise ValueError('complete custody required')
        bound = receipt[key]
        for name in ('candidates.sqlite', manifest_name(role)):
            if bound.get(name) != pins[name]:
                raise ValueError('custody candidate identity mismatch')
        if filename.startswith('public') or role == 'chat':
            if bound.get('candidate-verification.json') != pins['candidate-verification.json']:
                raise ValueError('custody independent proof mismatch')
        denied = receipt['excluded_doc_ids']
        if not isinstance(denied, list) or any(type(x) is not str for x in denied) or len(set(denied)) != len(denied):
            raise ValueError('invalid exclusion IDs')
        if len(denied) != receipt['counts']['excluded']:
            raise ValueError('custody exclusion count mismatch')
        exclusions.update(denied)
    return pins, exclusions, proof['verified_rows']

def encoded(values):
    if any(type(x) is not int or (x != -100 and not 0 <= x <= 50256) for x in values):
        raise ValueError('token outside frozen vocabulary')
    result = array.array('H', (65535 if x == -100 else x for x in values))
    if sys.byteorder != 'little':
        result.byteswap()
    return result.tobytes()

def positions(labels):
    result = dict.fromkeys(('0..255', '256..511', '512..767', '768..1023'), 0)
    for i, label in enumerate(labels):
        if label != -100:
            low = ((i+1)//256)*256
            result[f'{low}..{low+255}'] += 1
    return result

def pack(directory, destination, role):
    directory, destination = Path(directory).resolve(), Path(destination).resolve()
    if directory.parent != ROOT/'data' or destination.parent != ROOT/'data' or directory == destination:
        raise ValueError('canonical direct data children required')
    if destination.exists():
        raise FileExistsError('preserve existing packed output')
    started = time.monotonic()
    def check():
        if any(p.exists() for p in (ROOT/'runs/STOP', directory/'STOP', destination/'STOP')):
            raise InterruptedError('STOP')
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == 'darwin' else 1024)
        if time.monotonic()-started > 1800 or rss > 1024**3:
            raise RuntimeError('packing resource ceiling')
        if shutil.disk_usage(ROOT).free < 20*1024**3:
            raise RuntimeError('packing disk floor')
        if destination.exists() and sum(p.stat().st_size for p in destination.iterdir() if p.is_file()) > 1024**3:
            raise RuntimeError('packing output ceiling')
    def deadline(*args):
        raise TimeoutError('packing hard wall ceiling')
    signal.signal(signal.SIGALRM, deadline)
    signal.alarm(1800)
    try:
        check()
        pins, excluded, expected_count = validate_proofs(directory, role)
        runtime = {str(ROOT/n): sha(ROOT/n) for n in CODE}
        for name, expected in ASSETS.items():
            path = ROOT/'data/tokenizer'/name
            if sha(path) != expected:
                raise ValueError('tokenizer changed')
            runtime[str(path)] = expected
        frozen_pins = {str((directory/n).relative_to(ROOT)): h for n,h in pins.items()}
        frozen_pins.update({str(Path(p).relative_to(ROOT)): h for p,h in runtime.items()})
        destination.mkdir()
        write(destination/'freeze.json', dict(state='frozen_before_execution', role=role,
            source=str(directory), pins=frozen_pins, exclusion_union_count=len(excluded),
            limits=dict(seconds=1800, rss_bytes=1024**3, output_bytes=1024**3,
                        free_bytes=20*1024**3), training_admitted=False))
        tokenizer = load()
        counts = {s: Counter() for s in ('train', 'exposed-development')}
        offsets, exposure = Counter(), Counter()
        seen, families = set(), {}
        with ExitStack() as stack:
            db = stack.enter_context(sqlite3.connect(f'file:{directory}/candidates.sqlite?mode=ro', uri=True))
            db.row_factory = sqlite3.Row
            if db.execute('pragma integrity_check').fetchone()[0] != 'ok':
                raise ValueError('candidate integrity')
            streams = {s: [stack.enter_context((destination/f'{s}.{suffix}').open(mode))
                       for suffix, mode in [('inputs.u16','xb'), ('labels.u16','xb'), ('index.jsonl','x')]]
                       for s in counts}
            for item in db.execute('select * from documents order by doc_id'):
                check()
                did = item['doc_id']
                if did in seen:
                    raise ValueError('duplicate document')
                seen.add(did)
                split = 'exposed-development' if item['split'] == 'validation' else item['split']
                if split not in counts:
                    raise ValueError('unknown candidate split')
                if families.setdefault(item['family'], split) != split:
                    raise ValueError('cross-split family')
                co = counts[split]
                co['candidate_histories'] += 1
                if did in excluded:
                    co['excluded_histories'] += 1
                    continue
                if role == 'chat':
                    result = build_chat_rows(tokenizer, json.loads(item['selected_history_json']))
                    rows = result['rows']
                    history_sha = result['metadata']['original_history_sha256']
                else:
                    original = json.loads(item['original_lesson_json'])
                    result = adapt_lesson(original, tokenizer)
                    if result['source_lesson_sha256'] != did:
                        raise ValueError('original lesson identity')
                    rows = [t['row'] for t in result['turns']]
                    history_sha = hashlib.sha256(json.dumps(original['history'], sort_keys=True,
                        ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
                if sum(r.target_count for r in rows) != item['target_tokens'] or sum(len(r.inputs) for r in rows) != item['input_tokens']:
                    raise ValueError('independently verified candidate counts changed')
                co['histories'] += 1
                for turn, row in enumerate(rows):
                    pos = positions(row.labels)
                    record = dict(source=role, doc_id=did, turn=turn, family=item['family'],
                        split=split, offset=offsets[split], length=len(row.inputs),
                        target_count=row.target_count, original_history_sha256=history_sha,
                        position_exposure=pos)
                    if role != 'chat':
                        record['original_lesson_sha256'] = did
                    streams[split][0].write(encoded(row.inputs))
                    streams[split][1].write(encoded(row.labels))
                    streams[split][2].write(json.dumps(record, separators=(',', ':'))+'\n')
                    offsets[split] += len(row.inputs)
                    co['rows'] += 1
                    co['targets'] += row.target_count
                    exposure.update(pos)
        if len(seen) != expected_count or not excluded <= seen:
            raise ValueError('candidate/custody inventory mismatch')
        for split, cap in zip(('train', 'exposed-development'), CAPS[role]):
            if not 0 < counts[split]['targets'] <= cap:
                raise ValueError('empty or over-budget packed source')
        check()
        if validate_proofs(directory, role) != (pins, excluded, expected_count):
            raise ValueError('candidate proofs changed')
        if any(sha(path) != h for path,h in runtime.items()):
            raise ValueError('packing runtime changed')
        outputs = {p.name: dict(sha256=sha(p), bytes=p.stat().st_size)
                   for p in destination.iterdir() if p.name != 'freeze.json'}
        receipt = dict(state='prepared_for_diagnostic_pending_independent_verification',
            training_admitted=False, role=role, counts={s: dict(c) for s,c in counts.items()},
            exclusion_union_count=len(excluded), stream_tokens=dict(offsets),
            position_exposure=dict(exposure), freeze_sha256=sha(destination/'freeze.json'),
            outputs=outputs, seconds=time.monotonic()-started,
            limitations='One pass of retained complete histories; no refill, truncation, repetition, or admission. Independent packed-stream reload still required.')
        write(destination/'receipt.json', receipt)
        print(json.dumps(receipt['counts']))
        return receipt
    finally:
        signal.alarm(0)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('role', choices=CAPS)
    parser.add_argument('candidate_directory', type=Path)
    parser.add_argument('output_directory', type=Path)
    args = parser.parse_args()
    os.nice(10)
    pack(args.candidate_directory, args.output_directory, args.role)

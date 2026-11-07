"""Root-owned supplemental custody for the exposed 442-session development suite.

Does not replace historical/private custody, admit data, or score a student.
"""
from collections import Counter, defaultdict
import argparse
import hashlib
import json
from pathlib import Path
import resource
import shutil
import signal
import sqlite3
import sys
import time
from types import SimpleNamespace

from language_overlap_index import TextOverlapIndex
from own_base_dev_eval import resolve
from own_base_dev_run import read_inputs
from protect_language_mixture import augment, candidate_history
from protect_split import signature
from tools import FixtureSession

ROOT = Path(__file__).resolve().parent
SPEC = ROOT/'reports/own-base-dev-evaluation-v1/activation-v1.json'
SPEC_SHA = '44c7915f5f1d76f2389f14268f50e1fdfc71273b715658237097425a5114b0fd'
CODE = ('protect_grounded_public.py', 'language_overlap_index.py',
        'protect_language_mixture.py', 'protect_split.py',
        'own_base_dev_eval.py', 'own_base_dev_run.py', 'tools/__init__.py')


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def public_index(corpora, check=lambda: None):
    shield = SimpleNamespace(exact=set(), shapes=set(), grams=set(),
                             anchor_sets=[], by_anchor=defaultdict(set), calls=set())
    counts = Counter()
    for name, cases in corpora:
        for case in cases:
            check()
            session = FixtureSession()
            observations, proposals = [], []
            counts['sessions'] += 1
            for turn in case['turns']:
                counts['turns'] += 1
                augment(shield, [turn['user']])
                session.start_turn(**turn.get('policy', {'permit_calls': True}))
                observations.append([])
                proposals.append([])
                for expected in turn['calls']:
                    call = dict(name=expected['name'], arguments={
                        k: resolve(v, observations, proposals)
                        for k, v in expected['arguments'].items()})
                    key = signature(call)
                    if key is None:
                        raise ValueError('unresolved expected public call signature')
                    shield.calls.add(key)
                    proposals[-1].append(call)
                    observed = session.propose(json.dumps(call), assistant_call_boundary=True)
                    observations[-1].append(observed)
                    counts['expected_call_occurrences'] += 1
                if turn['answer']['mode'] == 'exact':
                    target = resolve(turn['answer']['value'], observations, proposals)
                    if not isinstance(target, str):
                        raise ValueError('exact public target must resolve to text')
                    augment(shield, [target])
    counts['unique_call_signatures'] = len(shield.calls)
    return TextOverlapIndex([shield]), shield.calls, dict(counts)


def structured_calls(value):
    if isinstance(value, dict):
        key = signature(value)
        if key is not None:
            yield key
        for child in value.values():
            yield from structured_calls(child)
    elif isinstance(value, list):
        for child in value:
            yield from structured_calls(child)


def candidate_content(row, kind):
    if kind == 'chat':
        if not isinstance(row['text'], str) or len(row['text'].encode()) > 1024**2:
            raise ValueError('candidate text bound')
        history = json.loads(row['selected_history_json'])
        texts = [row['text'], row['selected_history_json']]
        texts.extend(m['text'] for m in candidate_history(row['text']))
    else:
        original = json.loads(row['original_lesson_json'])
        history = original['history']
        texts = [row['original_lesson_json']]
    texts.extend(m['text'] for m in history if isinstance(m.get('text'), str))
    if any(not isinstance(t, str) or len(t.encode()) > 1024**2 for t in texts):
        raise ValueError('candidate text bound')
    return texts, history


def screen(directory, kind):
    directory = Path(directory).resolve()
    if not directory.is_relative_to(ROOT/'data'):
        raise ValueError('candidate directory must be under own data root')
    out = directory/'public-development-custody.json'
    if out.exists():
        raise FileExistsError('preserve completed supplemental custody')
    started = time.monotonic()
    def check():
        if (ROOT/'runs/STOP').exists() or (directory/'STOP').exists():
            raise InterruptedError('explicit STOP')
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if sys.platform != 'darwin':
            rss *= 1024
        if time.monotonic()-started > 1800 or rss > 3*1024**3:
            raise RuntimeError('custody resource ceiling')
        if shutil.disk_usage(directory).free < 20*1024**3:
            raise RuntimeError('custody disk floor')
    def deadline(*args):
        raise TimeoutError('custody hard time ceiling')
    signal.signal(signal.SIGALRM, deadline)
    signal.alarm(1800)
    try:
        check()
        code_pins = {n: digest(ROOT/n) for n in CODE}
        manifest_name = 'partial-candidate-manifest.json' if kind == 'chat' else 'candidate-manifest.json'
        paths = {n: directory/n for n in ('candidates.sqlite', manifest_name, 'candidate-verification.json')}
        if any(p.is_symlink() for p in paths.values()):
            raise ValueError('candidate artifact alias')
        pins = {n: digest(p) for n, p in paths.items()}
        verification = json.loads(paths['candidate-verification.json'].read_text())
        if (verification.get('state') not in {'PASS_pre_host_policy_not_admitted', 'PASS_independent_grounded_candidates_not_admitted'}
                or verification.get('failures') != []
                or verification.get('database_sha256') != pins['candidates.sqlite']
                or verification.get('manifest_sha256') != pins[manifest_name]
                or type(verification.get('verified_rows')) is not int
                or verification['verified_rows'] <= 0):
            raise ValueError('complete matching independent candidate verification required')
        if digest(SPEC) != SPEC_SHA:
            raise ValueError('exposed-suite activation changed')
        spec = json.loads(SPEC.read_text())
        corpora = read_inputs(spec, check)
        index, calls, inventory = public_index(corpora, check)
        if inventory['sessions'] != 442 or inventory['turns'] != 632:
            raise ValueError('incomplete public exclusion inventory')
        denied, counts, groups = [], Counter(), {}
        with sqlite3.connect(f'file:{paths["candidates.sqlite"]}?mode=ro', uri=True) as db:
            db.row_factory = sqlite3.Row
            if db.execute('pragma integrity_check').fetchone()[0] != 'ok':
                raise ValueError('candidate SQLite integrity')
            for row in db.execute('select * from documents order by doc_id'):
                check()
                texts, history = candidate_content(row, kind)
                rejected = any(index.matches(t) for t in texts) or any(c in calls for c in structured_calls(history))
                counts['reviewed'] += 1
                counts['excluded'] += bool(rejected)
                group = groups.setdefault(row['split'], Counter())
                group['reviewed'] += 1
                group['excluded'] += bool(rejected)
                if rejected:
                    denied.append(row['doc_id'])
        if counts['reviewed'] != verification['verified_rows']:
            raise ValueError('candidate verification row count mismatch')
        if any(digest(p) != pins[n] for n, p in paths.items()) or digest(SPEC) != SPEC_SHA:
            raise ValueError('custody inputs changed')
        if any(digest(ROOT/n) != expected for n, expected in code_pins.items()):
            raise ValueError('custody runtime changed')
        check()
        receipt = dict(state='screened_not_admitted', training_admitted=False,
                       candidate_pins=pins, suite_spec_sha256=SPEC_SHA,
                       suite_pins=spec['corpora'], inventory=inventory,
                       index=index.statistics(), excluded_doc_ids=denied,
                       counts=dict(counts), by_split={k: dict(v) for k, v in groups.items()},
                       code_sha256=code_pins,
                       seconds=time.monotonic()-started,
                       method='All exposed user text/exact textual targets and resolved expected call signatures; no student generation or scoring.',
                       limitations='Approximate lexical/structural exclusion, not semantic-independence proof. Lexical indexing omits targets shorter than three normalized words; generic short answers are not a semantic contamination test. Final admission must also apply unchanged historical/private custody and independent semantic verification.')
        with out.open('x') as stream:
            json.dump(receipt, stream, indent=2)
            stream.write('\n')
        print(json.dumps(dict(state=receipt['state'], counts=dict(counts), inventory=inventory)))
        return receipt
    finally:
        signal.alarm(0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind', choices=('chat', 'tool'))
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    screen(args.directory, args.kind)

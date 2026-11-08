"""Screen original TRAIN prose against the frozen newer public development suite."""
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import sqlite3
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from protect_grounded_public import SPEC, SPEC_SHA, CODE, public_index
from own_base_dev_run import read_inputs


def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def main():
    start = time.monotonic()
    folder = Path(__file__).parent
    output = folder / 'public-custody.json'
    assert not output.exists()
    source = ROOT / 'data/base-foundation-100m'
    audit = json.loads((folder / 'result.json').read_text())
    assert audit['state'] == 'PASS_existing_train_replay_integrity_not_admission'
    assert sha(source / 'manifest.json') == audit['manifest_sha256']
    manifest = json.loads((source / 'manifest.json').read_text())
    assert sha(source / 'documents.jsonl') == manifest['documents_sha256']
    assert sha(source / 'candidates.sqlite') == manifest['candidate_database_sha256']
    assert sha(SPEC) == SPEC_SHA
    pins = {name: sha(ROOT / name) for name in CODE}
    os.nice(10)

    def check():
        assert not any(p.exists() for p in (ROOT / 'runs/STOP', folder / 'STOP'))
        assert time.monotonic() - start < 1800
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if sys.platform != 'darwin':
            rss *= 1024
        assert rss < 3 * 1024**3 and shutil.disk_usage(ROOT).free >= 20 * 1024**3

    def deadline(*args):
        raise TimeoutError('public custody deadline')

    signal.signal(signal.SIGALRM, deadline)
    signal.alarm(1800)
    try:
        shield, calls, inventory = public_index(read_inputs(json.loads(SPEC.read_text()), check), check)
        assert inventory['sessions'] == 442 and inventory['turns'] == 632
        denied = []
        reviewed = 0
        with sqlite3.connect(f'file:{source}/candidates.sqlite?mode=ro', uri=True) as db:
            for line in (source / 'documents.jsonl').open():
                d = json.loads(line)
                if d['split'] != 'train':
                    continue
                check()
                row = db.execute('select doc_id, split, text from documents where priority=?',
                                 (d['order_sha256'],)).fetchone()
                assert row and row[:2] == (d['document_id'], 'train')
                assert hashlib.sha256(row[2].encode()).hexdigest() == d['raw_sha256']
                if shield.matches(row[2]):
                    denied.append(d['document_id'])
                reviewed += 1
        assert reviewed == audit['documents']
        assert sha(SPEC) == SPEC_SHA and all(sha(ROOT / n) == h for n, h in pins.items())
        check()
        result = dict(state='screened_not_admitted', training_admitted=False,
                      manifest_sha256=audit['manifest_sha256'], audit_sha256=sha(folder / 'result.json'),
                      specification_sha256=SPEC_SHA, code_sha256=pins, inventory=inventory,
                      reviewed=reviewed, excluded_doc_ids=denied, seconds=time.monotonic()-start,
                      scope='Full original TRAIN text only; existing public lexical matcher. No student scoring.',
                      limitations='Approximate lexical screen only; no semantic guarantee. Prose-embedded tool JSON is not parsed. Prior historical custody exclusions remain binding.')
        with output.open('x') as f:
            json.dump(result, f, indent=2)
            f.write('\n')
        print(json.dumps(dict(state=result['state'], reviewed=reviewed, excluded=len(denied), seconds=result['seconds'])))
    finally:
        signal.alarm(0)


if __name__ == '__main__':
    main()

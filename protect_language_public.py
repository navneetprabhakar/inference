"""Supplemental public exclusion of an immutable partial language snapshot.

No data admission, quality certification, private-case scoring or source rewrite.
"""
import json
from pathlib import Path
import resource
import shutil
import signal
import sqlite3
import sys
import time
from collections import Counter
from protect_grounded_public import ROOT, SPEC, SPEC_SHA, CODE, digest, public_index
from own_base_dev_run import read_inputs
from protect_language_mixture import candidate_history

SOURCE = ROOT/'data/language-mixture-v1'

def screen():
    output = SOURCE/'public-development-custody.json'
    if output.exists():
        raise FileExistsError('preserve existing supplemental receipt')
    started = time.monotonic()
    def check():
        if any(p.exists() for p in (ROOT/'runs/STOP', SOURCE/'STOP')):
            raise InterruptedError('STOP')
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform == 'darwin' else 1024)
        if time.monotonic()-started > 1800 or rss > 3*1024**3:
            raise RuntimeError('public custody resource ceiling')
        if shutil.disk_usage(ROOT).free < 20*1024**3:
            raise RuntimeError('disk floor')
    def deadline(*args):
        raise TimeoutError('public custody hard wall limit')
    signal.signal(signal.SIGALRM, deadline)
    signal.alarm(1800)
    try:
        check()
        names = ('candidates.sqlite', 'partial-candidate-manifest.json',
                 'candidate-verification.json', 'input-verification.json')
        if any((SOURCE/n).is_symlink() for n in names):
            raise ValueError('source artifact alias')
        pins = {n: digest(SOURCE/n) for n in names}
        manifest = json.loads((SOURCE/names[1]).read_bytes())
        proof = json.loads((SOURCE/names[2]).read_bytes())
        inputs = json.loads((SOURCE/names[3]).read_bytes())
        if proof['state'] != 'passed_partial_snapshot_integrity_only' or proof['failures'] != []:
            raise ValueError('complete partial-snapshot integrity proof required')
        if inputs['state'] != 'passed_input_integrity_only' or inputs['failures'] != []:
            raise ValueError('prior input integrity proof required')
        for obj in (manifest, proof, inputs):
            if obj['candidate_database_sha256'] != pins['candidates.sqlite']:
                raise ValueError('source database identity')
        for obj in (proof, inputs):
            if obj['candidate_manifest_sha256'] != pins[names[1]]:
                raise ValueError('source manifest identity')
        if proof['input_verification_sha256'] != pins[names[3]] or proof['counts'] != manifest['counts']:
            raise ValueError('source proof identity/counts')
        expected = sum(v for k,v in manifest['counts'].items() if k.endswith('_docs'))
        runtime = {n: digest(ROOT/n) for n in (*CODE, 'protect_language_public.py')}
        if digest(SPEC) != SPEC_SHA:
            raise ValueError('public evaluation identity')
        corpora = read_inputs(json.loads(SPEC.read_text()), check)
        index, _, inventory = public_index(corpora, check)
        if inventory['sessions'] != 442 or inventory['turns'] != 632:
            raise ValueError('public inventory incomplete')
        excluded, counts, by_source = [], Counter(), {}
        with sqlite3.connect(f'file:{SOURCE}/candidates.sqlite?mode=ro', uri=True) as db:
            if db.execute('pragma integrity_check').fetchone()[0] != 'ok':
                raise ValueError('snapshot integrity')
            for did, source, split, text in db.execute('select doc_id,source,split,text from documents order by doc_id'):
                check()
                if not isinstance(text, str) or len(text.encode()) > 1024**2:
                    raise ValueError('candidate text bound')
                reject = any(index.matches(m['text']) for m in candidate_history(text))
                group = by_source.setdefault(source+'/'+split, Counter())
                for counter in (counts, group):
                    counter['reviewed'] += 1
                    counter['excluded'] += bool(reject)
                if reject:
                    excluded.append(did)
        if counts['reviewed'] != expected:
            raise ValueError('incomplete snapshot scan')
        if any(digest(SOURCE/n) != h for n,h in pins.items()) or any(digest(ROOT/n) != h for n,h in runtime.items()):
            raise ValueError('source/runtime changed')
        check()
        receipt = dict(state='screened_not_admitted', training_admitted=False,
            source=str(SOURCE), pins=pins, suite_spec_sha256=SPEC_SHA,
            inventory=inventory, counts=dict(counts),
            by_source={k:dict(v) for k,v in by_source.items()},
            excluded_doc_ids=excluded, code_sha256=runtime,
            seconds=time.monotonic()-started,
            method='Full language text and role-delimited utterances against exposed public user/exact-target lexical index; no student scoring.',
            limitations='Original snapshot remains partial/unadmitted. Plain-text sources have no structured proposal fields; no claim of parsing arbitrary embedded call syntax. Short generic strings and semantic paraphrases can escape lexical matching. Any projection must also preserve legacy custody, quality exclusions, source provenance and independent verification.')
        with output.open('x') as f:
            json.dump(receipt, f, indent=2)
            f.write('\n')
        print(json.dumps(dict(counts=dict(counts), by_source=receipt['by_source'], seconds=receipt['seconds'])))
    finally:
        signal.alarm(0)

if __name__ == '__main__':
    screen()

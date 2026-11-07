"""Root-only lexical custody; no student scoring, splitting or admission."""
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

from protect_language_mixture import (ROOT, PRIVATE, PRIVATE_SHA, HISTORICAL,
    Shield, BShield, augment, candidate_history, TextOverlapIndex)
from protect_grounded_public import SPEC, SPEC_SHA, public_index, CODE
from own_base_dev_run import read_inputs
from protect_split import DEV, DEV_SHA, SEALED, SEALED_SHA
from protect_validation_b import B_CASES, B_SHA

SOURCE = ROOT / 'data/cosmopedia-explanatory-candidates-v1'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def screen():
    started = time.monotonic()
    output = SOURCE / 'custody.json'
    if output.exists():
        raise FileExistsError('preserve completed custody')
    def check():
        if any(p.exists() for p in (ROOT/'runs/STOP', SOURCE/'STOP')):
            raise InterruptedError('STOP')
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if sys.platform != 'darwin':
            rss *= 1024
        if time.monotonic()-started > 1800 or rss > 3*1024**3:
            raise RuntimeError('custody resource ceiling')
        if shutil.disk_usage(ROOT).free < 20*1024**3:
            raise RuntimeError('disk floor')
    def deadline(*args):
        raise TimeoutError('custody hard wall ceiling')
    signal.signal(signal.SIGALRM, deadline)
    signal.alarm(1800)
    os.nice(10)
    try:
        check()
        paths = {n: SOURCE/n for n in ('candidates.sqlite', 'receipt.json', 'candidate-verification.json')}
        if any(p.is_symlink() for p in paths.values()):
            raise ValueError('artifact alias')
        pins = {n: sha(p) for n,p in paths.items()}
        receipt = json.loads(paths['receipt.json'].read_text())
        proof = json.loads(paths['candidate-verification.json'].read_text())
        if (proof['state'] != 'PASS_independent_explanatory_candidates_not_admitted'
                or proof['failures'] != []
                or proof['database_sha256'] != pins['candidates.sqlite']
                or proof['receipt_sha256'] != pins['receipt.json']
                or proof['policy_sha256'] != receipt['policy_sha256']
                or proof['training_admitted'] is not False
                or receipt['training_admitted'] is not False
                or type(proof['verified_rows']) is not int or proof['verified_rows'] <= 0
                or receipt['state'] != 'candidate_projection_with_frozen_sample_not_admitted'
                or receipt['files']['candidates.sqlite']['sha256'] != pins['candidates.sqlite']
                or proof['verified_rows'] != receipt['counts']['retained_documents']):
            raise ValueError('matching independent verification required')
        code = set(CODE) | {'protect_cosmopedia_candidates.py', 'protect_validation_b.py'}
        code_pins = {n:sha(ROOT/n) for n in code}
        protected = {PRIVATE:PRIVATE_SHA, SPEC:SPEC_SHA, DEV:DEV_SHA,
                     SEALED:SEALED_SHA, B_CASES:B_SHA}
        if any(sha(p) != expected for p,expected in protected.items()):
            raise ValueError('protected identity changed')
        shield = Shield()
        augment(shield, json.loads(PRIVATE.read_bytes()))
        historical = {}
        for version in ('sft-v1','sft-v2','sft-v3'):
            for split in ('dev','test'):
                path = HISTORICAL/version/(split+'.jsonl')
                if not path.is_file() or path.stat().st_size > 4*1024**2:
                    raise ValueError('historical holdout bound')
                before = sha(path)
                rows = 0
                with path.open() as stream:
                    for line in stream:
                        check()
                        if line.strip():
                            augment(shield,json.loads(line)); rows += 1
                if sha(path) != before:
                    raise ValueError('historical input changed')
                historical[str(path)] = {'sha256':before,'rows':rows}
        private_index = TextOverlapIndex((shield,BShield()))
        del shield
        public, _, inventory = public_index(read_inputs(json.loads(SPEC.read_text()),check),check)
        if inventory['sessions'] != 442 or inventory['turns'] != 632:
            raise ValueError('incomplete public inventory')
        denied = []; reviewed = 0
        with sqlite3.connect(f'file:{paths["candidates.sqlite"]}?mode=ro',uri=True) as db:
            if db.execute('pragma quick_check').fetchone() != ('ok',):
                raise ValueError('candidate database integrity')
            for identifier,text,prompt in db.execute('select doc_id,text,prompt from documents order by row_id'):
                check()
                rejected = False
                for value in (text,prompt):
                    if not isinstance(value,str) or len(value.encode()) > 1024**2:
                        raise ValueError('candidate field bound')
                    for message in candidate_history(value):
                        if private_index.matches(message['text']) or public.matches(message['text']):
                            rejected = True
                if rejected:
                    denied.append(identifier)
                reviewed += 1
        if reviewed != proof['verified_rows']:
            raise ValueError('incomplete scan')
        if any(sha(p) != pins[n] for n,p in paths.items()) or any(sha(ROOT/n) != h for n,h in code_pins.items()):
            raise ValueError('candidate/runtime changed')
        if any(sha(p) != h for p,h in protected.items()):
            raise ValueError('protected input changed')
        if any(sha(p) != entry['sha256'] for p,entry in historical.items()):
            raise ValueError('historical input changed')
        check()
        result = dict(state='screened_not_admitted',training_admitted=False,
            candidate_pins=pins,code_sha256=code_pins,inventory=inventory,
            protected_sha256={str(p):h for p,h in protected.items()},
            historical_chat_holdouts=historical,excluded_doc_ids=denied,
            counts={'reviewed':reviewed,'excluded':len(denied)},seconds=time.monotonic()-started,
            scope='Full generated text and original prompt, plus role-delimited utterances, screened against historical/private and exposed public lexical indices. No private case text published; no student scoring.',
            limitations='Approximate lexical screening can miss semantic paraphrases and short answers. Role segmentation recognizes User/Assistant only; Alice/Bob dialogue is checked as full text, which can miss short embedded utterances. No semantic certification, embedded tool-call parser, historical training deduplication, family split or training admission.')
        with output.open('x') as stream:
            json.dump(result,stream,indent=2); stream.write('\n')
        print(json.dumps({'state':result['state'],'counts':result['counts']}))
    finally:
        signal.alarm(0)


if __name__ == '__main__':
    screen()

"""Root-only full-history custody; no scoring, private disclosure or admission."""
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

from protect_own_sft import protected_index
from protect_language_mixture import ROOT, PRIVATE, PRIVATE_SHA
from protect_grounded_public import SPEC, SPEC_SHA, CODE, public_index, structured_calls
from protect_split import DEV, DEV_SHA, SEALED, SEALED_SHA, signature
from protect_validation_b import B_CASES, B_SHA
from own_base_dev_run import read_inputs

D = ROOT/'data/everyday-source-review-v1'

def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def require(condition, reason):
    if not condition:
        raise ValueError(reason)

def main():
    start = time.monotonic()
    output = D/'custody.json'
    require(not output.exists(), 'preserve existing custody')
    os.nice(10)
    def check():
        require(not any(p.exists() for p in (ROOT/'runs/STOP', D/'STOP')), 'STOP')
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if sys.platform != 'darwin': rss *= 1024
        require(time.monotonic()-start < 600 and rss < 3*1024**3, 'custody resource ceiling')
        require(shutil.disk_usage(ROOT).free >= 20*1024**3, 'disk floor')
    def deadline(*args): raise TimeoutError('custody deadline')
    signal.signal(signal.SIGALRM, deadline)
    signal.alarm(600)
    try:
        check()
        paths = {n:D/n for n in ('review.sqlite','review-queue.jsonl','receipt.json','independent-extraction-verification.json')}
        require(not any(p.is_symlink() for p in paths.values()), 'artifact alias')
        pins = {n:sha(p) for n,p in paths.items()}
        receipt = json.loads(paths['receipt.json'].read_text())
        proof = json.loads(paths['independent-extraction-verification.json'].read_text())
        require(proof['state']=='PASS_extract_not_admitted' and proof['failures']==[] and proof['verified_rows']==1130 and proof['training_admitted'] is False, 'complete independent extraction proof')
        require(receipt['state']=='full_history_review_queue_not_admitted' and receipt['failure'] is None and receipt['training_admitted'] is False, 'complete extraction')
        require(proof['database_sha256']==receipt['database_sha256']==pins['review.sqlite'] and proof['queue_sha256']==receipt['queue_sha256']==pins['review-queue.jsonl'], 'proof corpus binding')
        require(proof['receipt_sha256']==pins['receipt.json'] and proof['policy_sha256']==receipt['policy_sha256'], 'proof receipt binding')
        protected = {PRIVATE:PRIVATE_SHA,SPEC:SPEC_SHA,DEV:DEV_SHA,SEALED:SEALED_SHA,B_CASES:B_SHA}
        require(all(sha(p)==h for p,h in protected.items()), 'protected identity')
        code = set(CODE)|{'protect_everyday_histories.py','protect_own_sft.py','protect_validation_b.py'}
        code_pins = {n:sha(ROOT/n) for n in code}
        private, shields, historical = protected_index(check)
        public, public_calls, inventory = public_index(read_inputs(json.loads(SPEC.read_text()),check),check)
        require(inventory['sessions']==442 and inventory['turns']==632, 'public inventory')
        denied=[]; counts={}; reviewed=0
        with sqlite3.connect(f'file:{D}/review.sqlite?mode=ro',uri=True) as db:
            require(db.execute('pragma quick_check').fetchone()==('ok',), 'database integrity')
            for identifier, raw, status in db.execute('select doc_id,messages_json,status from histories order by doc_id'):
                check(); require(len(raw.encode())<1024**2, 'history bound')
                messages=json.loads(raw)
                texts=[raw, '\n'.join(m['role']+': '+m['content'] for m in messages)]+[m['content'] for m in messages]
                rejected=any(private.matches(t) or public.matches(t) for t in texts)
                calls=list(structured_calls(messages))
                rejected = rejected or any(c in public_calls or any(c in s.calls for s in shields) for c in calls)
                if rejected: denied.append(identifier)
                group=counts.setdefault(status,dict(reviewed=0,excluded=0));group['reviewed']+=1;group['excluded']+=int(rejected);reviewed+=1
        require(reviewed==1130 and {k:v['reviewed'] for k,v in counts.items()}==receipt['counts'], 'complete history inventory')
        require(all(sha(p)==pins[n] for n,p in paths.items()), 'corpus changed')
        require(all(sha(ROOT/n)==h for n,h in code_pins.items()), 'runtime changed')
        require(all(sha(p)==h for p,h in protected.items()) and all(sha(p)==v['sha256'] for p,v in historical.items()), 'protected input changed')
        check()
        result=dict(state='screened_not_admitted',training_admitted=False,database_sha256=pins['review.sqlite'],pins=pins,excluded_doc_ids=denied,counts=counts,reviewed=reviewed,public_inventory=inventory,protected_sha256={str(p):h for p,h in protected.items()},historical_chat_holdouts=historical,code_sha256=code_pins,seconds=time.monotonic()-start,scope='Complete raw histories, role-joined text and every message screened against historical/private and public lexical indices; structured object call signatures screened. No private material emitted or student scored.',limitations='Approximate lexical matching does not certify semantic independence; tool-like JSON embedded in prose is not parsed. All prior excluded and unknown rows remain quarantined. Quality, framing, deduplication and admission remain separate.')
        with output.open('x') as f: json.dump(result,f,indent=2);f.write('\n')
        print(json.dumps(dict(state=result['state'],counts=counts,seconds=result['seconds'])))
    finally: signal.alarm(0)

if __name__=='__main__': main()

"""Root-only full-text custody for fresh broad candidates. No model scoring."""
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

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from protect_own_sft import protected_index
from protect_grounded_public import SPEC,SPEC_SHA,CODE,public_index
from protect_language_mixture import PRIVATE,PRIVATE_SHA
from protect_split import DEV,DEV_SHA,SEALED,SEALED_SHA
from protect_validation_b import B_CASES,B_SHA
from own_base_dev_run import read_inputs,atomic

D=ROOT/'data/fresh-broad-candidates-v1'


def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    start=time.monotonic();output=D/'custody.json';assert not output.exists();os.nice(10)
    def check():
        assert not (ROOT/'runs/STOP').exists() and not (D/'STOP').exists()
        assert time.monotonic()-start<7200 and shutil.disk_usage(ROOT).free>20*1024**3
        rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
        assert rss<4*1024**3
    def deadline(*args):raise TimeoutError('custody deadline')
    signal.signal(signal.SIGALRM,deadline);signal.alarm(7200)
    try:
        check();manifest=json.loads((D/'candidate-manifest.json').read_text())
        assert manifest['state']=='candidate_extraction_complete_not_admitted' and not manifest['training_admitted']
        candidate_sha=sha(D/'candidates.sqlite');manifest_sha=sha(D/'candidate-manifest.json')
        assert candidate_sha==manifest['candidate_database_sha256']
        protected={PRIVATE:PRIVATE_SHA,SPEC:SPEC_SHA,DEV:DEV_SHA,SEALED:SEALED_SHA,B_CASES:B_SHA}
        assert all(sha(p)==h for p,h in protected.items())
        code=set(CODE)|{'protect_own_sft.py','protect_validation_b.py','reports/fresh-broad-intake-v1/screen.py'}
        code_pins={n:sha(ROOT/n) for n in code}
        private,shields,historical=protected_index(check)
        public,calls,inventory=public_index(read_inputs(json.loads(SPEC.read_text()),check),check)
        assert inventory['sessions']==442 and inventory['turns']==632
        denied=[];denied_domains=set();counts={};reviewed=0
        with sqlite3.connect(f'file:{D}/candidates.sqlite?mode=ro',uri=True) as db:
            assert db.execute('pragma quick_check').fetchone()==('ok',)
            for identifier,domain,split,text in db.execute('select doc_id,domain,split,text from documents'):
                check();assert split in ('train','validation') and isinstance(text,str) and len(text)<=80000
                rejected=bool(private.matches(text) or public.matches(text))
                if rejected:denied.append(identifier);denied_domains.add(domain)
                c=counts.setdefault(split,dict(reviewed=0,excluded=0));c['reviewed']+=1;c['excluded']+=int(rejected);reviewed+=1
                if reviewed%10000==0:atomic(D/'custody-progress.json',dict(reviewed=reviewed,excluded=len(denied),seconds=time.monotonic()-start))
        assert reviewed==manifest['counts']['train_docs']+manifest['counts']['validation_docs']
        assert all(counts[s]['reviewed']==manifest['counts'][s+'_docs'] for s in counts)
        assert sha(D/'candidates.sqlite')==candidate_sha and sha(D/'candidate-manifest.json')==manifest_sha
        assert all(sha(p)==h for p,h in protected.items()) and all(sha(p)==v['sha256'] for p,v in historical.items())
        assert all(sha(ROOT/n)==h for n,h in code_pins.items());check()
        receipt=dict(state='screened_not_admitted',training_admitted=False,candidate_database_sha256=candidate_sha,
          candidate_manifest_sha256=manifest_sha,excluded_doc_ids=denied,excluded_domain_families=sorted(denied_domains),
          counts=counts,reviewed=reviewed,public_inventory=inventory,
          protected_sha256={str(p):h for p,h in protected.items()},historical_chat_holdouts=historical,
          code_sha256=code_pins,seconds=time.monotonic()-start,
          method='Full candidate prose screened against historical/private and public lexical indices. Whole matched domain families must be excluded in packing. No protected text emitted and no model scored.',
          limitations='Approximate lexical matching, not semantic independence. Prose-embedded tool JSON is not parsed. Candidate source replay verification, deduplication, quality review and admission remain separate.')
        atomic(output,receipt)
        summary={k:v for k,v in receipt.items() if k not in ('excluded_doc_ids','excluded_domain_families','protected_sha256','historical_chat_holdouts')}
        summary['excluded_documents']=len(denied);summary['excluded_domain_count']=len(denied_domains);summary['receipt_sha256']=sha(output)
        atomic(Path(__file__).parent/'custody-summary.json',summary)
        print(json.dumps(dict(reviewed=reviewed,excluded=len(denied),excluded_domains=len(denied_domains),seconds=receipt['seconds'])))
    finally:signal.alarm(0)


if __name__=='__main__':main()

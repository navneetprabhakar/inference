"""Check retained outputs, charges and screening provenance without new fetch/decode."""
# Creator: Navneet Prabhakar
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from slm.common.tokenizer import BPE
from slm.data.cosmopedia_seed import extract
from slm.data.evaluation_exclusions import EvaluationExclusions
from slm.data.prose_screen import windows
from slm.data.quality_audit import PATTERNS
from slm.data.schema import digest
from slm.data.tokenized import sha

ROOT=Path('data/cosmopedia-candidate-intake-v1')


def main():
    plan=json.loads(Path('configs/cosmopedia-candidate-intake-execution-v2.json').read_text())
    report=json.loads((ROOT/'report.json').read_text())
    assert report==json.loads(Path('reports/cosmopedia-candidate-intake.json').read_text())
    assert report['complete'] and report['plan_sha256']==sha('configs/cosmopedia-candidate-intake-execution-v2.json')
    for p,h in plan['input_bindings'].items():assert sha(p)==h,p
    db=sqlite3.connect(f'file:{(ROOT/"charges/ledger.sqlite").resolve()}?mode=ro',uri=True)
    operations={k:dict(charge=json.loads(c),state=s,actual=n,hash=h) for k,c,s,n,h in db.execute('SELECT key,charge,state,actual_bytes,body_sha256 FROM attempts')}
    payloads={k:(n,h) for k,n,h in db.execute('SELECT key,size,sha256 FROM payloads')}
    for key,(n,h) in payloads.items():
        path=ROOT/'cache'/(digest(key)+'.bin');assert not path.is_symlink() and path.stat().st_size==n and sha(path)==h
        assert operations[key]['state']=='complete'
    def cached(key):
        assert key in payloads
        return (ROOT/'cache'/(digest(key)+'.bin')).read_bytes()
    totals={k:sum(r['charge'][k] for r in operations.values()) for k in plan['ledger_contract']['limits']}
    assert totals==report['reserved']
    assert all(totals[k]<=limit for k,limit in plan['ledger_contract']['limits'].items())
    pending={k for k,r in operations.items() if r['state']!='complete'}
    assert pending=={'decode/'+name for name in plan['skip_uncertain_files']}
    job=db.execute('SELECT contract,deadline FROM job').fetchone();assert json.loads(job[0])==plan['ledger_contract']
    snapshot=json.loads((ROOT/'ledger-snapshot.json').read_text());assert snapshot['deadline_epoch_seconds']==job[1]
    assert sha(ROOT/'ledger-snapshot.json')==report['ledger_snapshot_sha256']
    db.close()
    spec=json.loads(Path('configs/future-intake-evaluation-exclusions-v1.json').read_text())
    guard=EvaluationExclusions(spec['inventory'],spec['inventory_sha256']);bpe=BPE.load(plan['tokenizer'])
    inventory=json.loads(Path(plan['inventory']).read_text());selection=sorted(inventory,key=lambda r:digest([plan['selection_seed'],r['path']]))[:50]
    expected={r['path'] for r in selection}-set(plan['skip_uncertain_files'])
    assert {r['file'] for r in report['files']}==expected and len(report['files'])==len(expected)
    all_text=Counter();pass_text=Counter();seed_families=Counter();raw_hashes=Counter();reasons=Counter();seeds=Counter();formats=Counter();audiences=Counter()
    rows=tokens=passed=pass_tokens=language_windows=protected=0
    for receipt in report['files']:
        name=receipt['file'];payload=cached('rows/'+name)
        assert hashlib.sha256(payload).hexdigest()==receipt['rows_sha256']
        records=[json.loads(line) for line in payload.splitlines()]
        chosen=json.loads(cached('metadata/'+name));assert chosen==receipt['group'] and len(records)==receipt['rows']==chosen['rows']
        assert operations['decode/'+name]['charge']['rows']==len(records)
        file_tokens=file_pass=file_pass_tokens=0
        for i,r in enumerate(records):
            raw=r['row'];assert r['file']==name and r['row_group']==chosen['index'] and r['row_in_group']==i
            assert r['revision']==plan['revision'] and r['training_approved'] is False and r['partition'] is None
            assert set(raw)==set(plan['fields']) and digest(raw)==r['raw_record_sha256']
            raw_hashes[r['raw_record_sha256']]+=1
            key=digest(' '.join(raw['text'].casefold().split()));all_text[key]+=1
            assert r['prompt_family']=='HuggingFaceTB/smollm-corpus:cosmopedia-v2:prompt:'+digest(raw['prompt'])
            isolation=guard.inspect_record(raw);assert isolation==r['isolation']
            privacy={field:[key for key,p in PATTERNS.items() if p.search(raw[field])] for field in ('prompt','text')}
            assert privacy==r['privacy']
            if isolation['blocked']:assert 'protected_evaluation_text' in r['reasons'];protected+=1
            if any(privacy.values()):assert 'privacy_or_credential_signal' in r['reasons']
            if r['seed'] is not None:
                seed=extract(raw);assert r['seed']=={k:v for k,v in seed.items() if k!='seed_excerpt'}
                seed_families[seed['proposed_exact_seed_family']]+=1
            else:assert not r['provisional_quality_pass']
            if r['windows']:
                expected_parts=[(field,p['start'],p['end']) for field in ('prompt','text') for p in windows(raw[field])]
                assert [(p['field'],p['start'],p['end']) for p in r['windows']]==expected_parts
                for p in r['windows']:
                    assert all(0<=s['score']<=1.001 for s in p['scores'])
                if any(not p['scores'] or p['scores'][0]['language']!='en' or p['scores'][0]['score']<.8 for p in r['windows']):
                    assert 'window_english_signal' in r['reasons']
            if r['provisional_quality_pass']:
                assert not r['reasons'] and r['windows'] and r['seed'] and not isolation['blocked'] and not any(privacy.values())
                assert r['prompt_family'] not in plan['nonapproval_prompt_families']
                assert r['seed']['proposed_exact_seed_family'] not in plan['nonapproval_seed_families']
                assert len(re.findall(r'\w+',raw['text']))>=50
                pass_text[key]+=1
            assert r['provisional_quality_pass']==(not r['reasons'])
            n=len(bpe.encode(raw['text']));assert n==r['actual_student_bpe_text_tokens']
            file_tokens+=n;file_pass+=r['provisional_quality_pass'];file_pass_tokens+=n if r['provisional_quality_pass'] else 0
            reasons.update(r['reasons']);seeds[raw['seed_data']]+=1;formats[raw['format']]+=1;audiences[raw['audience']]+=1
            language_windows+=len(r['windows']);rows+=1
        assert (file_tokens,file_pass,file_pass_tokens)==(receipt['actual_student_bpe_text_tokens'],receipt['provisional_quality_pass'],receipt['provisional_pass_text_tokens'])
        tokens+=file_tokens;passed+=file_pass;pass_tokens+=file_pass_tokens
    assert (rows,tokens,passed,pass_tokens)==(report['rows'],report['actual_student_bpe_text_tokens'],report['provisional_quality_pass'],report['provisional_pass_text_tokens'])
    assert rows+sum(r['reserved_rows'] for r in report['skipped_uncertain_files'])==totals['rows']
    result=dict(creator='Navneet Prabhakar',kind='actual-cosmopedia-candidate-check-v1',passed=True,
        intake_report_sha256=sha('reports/cosmopedia-candidate-intake.json'),checker_sha256=sha(__file__),
        published_files=len(report['files']),published_rows=rows,reserved_rows=totals['rows'],
        provisional_quality_pass=passed,actual_student_bpe_text_tokens=tokens,provisional_pass_text_tokens=pass_tokens,
        distinct_raw_records=len(raw_hashes),distinct_normalized_texts=len(all_text),
        distinct_provisional_normalized_texts=len(pass_text),duplicate_provisional_text_member_rows=sum(n-1 for n in pass_text.values()),
        distinct_parsed_exact_seed_families=len(seed_families),duplicate_seed_member_rows=sum(n-1 for n in seed_families.values()),
        language_windows_checked=language_windows,protected_evaluation_hits=protected,reason_counts=dict(reasons),
        seed_counts=dict(seeds),format_counts=dict(formats),audience_counts=dict(audiences),reserved=totals,
        retained_payloads_verified=len(payloads),uncertain_decode_replayed=False,training_approved=False,
        scope='All published rows, cached payload hashes, seed offsets/families, original prompt/body exclusions, privacy signals, recorded full-window scores and BPE counts checked; no new network, upstream row-group decode, detector inference or gradients. Exact repeats counted, not globally split/deduplicated. No semantic/factual/rights or near-heldout certification.')
    Path('reports/cosmopedia-candidate-intake-check.json').write_bytes((json.dumps(result,indent=2,sort_keys=True)+'\n').encode())
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()

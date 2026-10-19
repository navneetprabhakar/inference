"""Reconstruct retained prose screening and reconcile all bounded work."""
# Creator: Navneet Prabhakar
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3
from slm.common.tokenizer import BPE
from slm.data.evaluation_exclusions import EvaluationExclusions
from slm.data.parquet_selection import select
from slm.data.prose_screen import RULE,screen,windows
from slm.data.schema import digest
from slm.data.tokenized import sha

ROOT=Path('data/fineweb-candidate-intake-v1')


def main():
    plan=json.loads(Path('configs/fineweb-candidate-intake-execution-v2.json').read_text())
    result=json.loads((ROOT/'report.json').read_text())
    assert result==json.loads(Path('reports/fineweb-candidate-intake.json').read_text())
    assert result['complete'] and result['plan_sha256']==sha('configs/fineweb-candidate-intake-execution-v2.json')
    for p,h in plan['input_bindings'].items():assert sha(p)==h,p
    db=sqlite3.connect(f'file:{(ROOT/"charges/ledger.sqlite").resolve()}?mode=ro',uri=True)
    ops={k:dict(charge=json.loads(c),state=s,actual=n) for k,c,s,n in db.execute('SELECT key,charge,state,actual_bytes FROM attempts')}
    payloads={k:(n,h) for k,n,h in db.execute('SELECT key,size,sha256 FROM payloads')}
    for key,(n,h) in payloads.items():
        p=ROOT/'cache'/(digest(key)+'.bin');assert not p.is_symlink() and p.stat().st_size==n and sha(p)==h and ops[key]['state']=='complete'
    def cached(key):
        assert key in payloads
        return (ROOT/'cache'/(digest(key)+'.bin')).read_bytes()
    totals={k:sum(r['charge'][k] for r in ops.values()) for k in plan['ledger_contract']['limits']}
    assert totals==result['reserved'] and all(totals[k]<=v for k,v in plan['ledger_contract']['limits'].items())
    job=db.execute('SELECT contract,deadline FROM job').fetchone();assert json.loads(job[0])==plan['ledger_contract']
    snapshot=json.loads((ROOT/'ledger-snapshot.json').read_text());assert snapshot['deadline_epoch_seconds']==job[1]
    assert sha(ROOT/'ledger-snapshot.json')==result['ledger_snapshot_sha256'];db.close()
    names=[r['path'] for r in json.loads(Path(plan['inventory']).read_text())]
    censuses={name:json.loads(cached('census/'+name)) for name in names}
    excluded={(r['file'],r['group']) for r in plan['excluded_prior_groups']}
    choices=select(censuses,plan['selection_seed'],49,4,excluded)
    assert choices==json.loads(cached('selection')) and len(choices)==49
    by_key={r['file']+'/'+str(r['group']['index']):r for r in choices}
    completed={r['file']+'/'+str(r['group']['index']):r for r in result['groups']}
    skipped={r['file']+'/'+str(r['group']['index']):r for r in result['skipped_groups']}
    assert len(completed)==len(result['groups']) and len(skipped)==len(result['skipped_groups'])
    assert not set(completed)&set(skipped) and set(completed)|set(skipped)==set(by_key)
    for key in skipped:assert ops['decode/'+key]['state']=='pending'
    assert {k for k,v in ops.items() if v['state']!='complete' and k.startswith('decode/')}=={'decode/'+k for k in skipped}
    assert all(v['state']=='complete' or k.startswith(('decode/','range/')) for k,v in ops.items())
    heldouts=json.loads(Path(plan['heldout_map']).read_text());spec=json.loads(Path('configs/future-intake-evaluation-exclusions-v1.json').read_text())
    guard=EvaluationExclusions(spec['inventory'],spec['inventory_sha256']);bpe=BPE.load(plan['tokenizer'])
    reasons=Counter();crawls=Counter();raws=Counter();texts=Counter();accepted_texts=Counter();host_counts=Counter()
    total=passed=tokens=pass_tokens=window_count=heldout_hits=protected_hits=0
    from urllib.parse import urlparse
    for key,receipt in completed.items():
        payload=cached('rows/'+key);rows=[json.loads(line) for line in payload.splitlines()]
        assert hashlib.sha256(payload).hexdigest()==receipt['rows_sha256'] and len(rows)==receipt['rows']==receipt['group']['rows']
        assert ops['decode/'+key]['charge']['rows']==len(rows)
        ft=fp=fpt=0
        for i,r in enumerate(rows):
            raw=r['row'];group='HuggingFaceFW/fineweb-edu:'+raw['id']
            assert r['file']==receipt['file'] and r['row_group']==receipt['group']['index'] and r['row_in_group']==i
            assert r['source_group']==group and r['raw_record_sha256']==digest(raw) and r['revision']==plan['revision']
            assert r['training_approved'] is False and r['partition'] is None
            assert r['original_source_unchanged'] is True and r['classifier_projection']=='fasttext-line-escape-v1'
            isolation=guard.inspect_record(raw);assert isolation==r['isolation']
            if len(raw['text'])<=RULE['max_characters']:
                parts=windows(raw['text']);assert [(p['start'],p['end']) for p in parts]==[(p['start'],p['end']) for p in r['windows']]
                predicted=[p['scores'] for p in r['windows']]
                expected=screen(raw,predicted,guard.guard,plan['known_judgments'].get(group),heldouts.get(group))
                assert expected==r['decision']
            else:assert not r['decision']['candidate'] and 'length_scope' in r['decision']['reasons'] and not r['windows']
            assert r['provisional_quality_pass']==r['decision']['candidate']
            if r['provisional_quality_pass']:
                assert not isolation['blocked'] and group not in heldouts and plan['known_judgments'].get(group) not in ('defer','exclude')
            n=len(bpe.encode(raw['text']));assert n==r['actual_student_bpe_text_tokens']
            ft+=n;fp+=r['provisional_quality_pass'];fpt+=n if r['provisional_quality_pass'] else 0
            raws[r['raw_record_sha256']]+=1;normalized=digest(' '.join(raw['text'].casefold().split()));texts[normalized]+=1
            if r['provisional_quality_pass']:accepted_texts[normalized]+=1
            reasons.update(r['decision']['reasons']);crawls[raw['dump']]+=1
            try:host=urlparse(raw['url']).hostname
            except (ValueError,TypeError):host=None
            host_counts[host]+=1
            window_count+=len(r['windows']);total+=1;heldout_hits+=group in heldouts;protected_hits+=isolation['blocked']
        assert (ft,fp,fpt)==(receipt['actual_student_bpe_text_tokens'],receipt['provisional_quality_pass'],receipt['provisional_pass_text_tokens'])
        tokens+=ft;passed+=fp;pass_tokens+=fpt
    assert (total,passed,tokens,pass_tokens)==(result['rows'],result['provisional_quality_pass'],result['actual_student_bpe_text_tokens'],result['provisional_pass_text_tokens'])
    assert total+1000+sum(r['reserved_rows'] for r in skipped.values())==totals['rows']
    report=dict(creator='Navneet Prabhakar',kind='actual-fineweb-candidate-intake-check-v1',passed=True,
        intake_report_sha256=sha('reports/fineweb-candidate-intake.json'),checker_sha256=sha(__file__),
        published_groups=len(completed),skipped_groups=len(skipped),published_rows=total,reserved_rows=totals['rows'],inherited_rows=1000,
        source_files=result['source_files'],provisional_quality_pass=passed,actual_student_bpe_text_tokens=tokens,provisional_pass_text_tokens=pass_tokens,
        distinct_raw_records=len(raws),distinct_normalized_texts=len(texts),distinct_provisional_normalized_texts=len(accepted_texts),
        duplicate_provisional_text_member_rows=sum(n-1 for n in accepted_texts.values()),crawl_counts=dict(crawls),distinct_hosts=len(host_counts),
        reason_counts=dict(reasons),direct_ancestral_heldout_rows=heldout_hits,protected_evaluation_hits=protected_hits,
        language_windows_checked=window_count,retained_payloads_verified=len(payloads),reserved=totals,training_approved=False,
        scope='All retained payloads/selection/accounting/original-row digests and complete recorded window scores reconstruct provisional decisions and BPE counts. No refetch, upstream row decode or new detector/model inference. Exact repeats counted only; global cross-source near/seed/ancestral grouping and finite admission remain required.')
    Path('reports/fineweb-candidate-intake-check.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()

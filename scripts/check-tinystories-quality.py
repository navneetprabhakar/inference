"""Reconstruct actual full-window narrative decisions without detector replay."""
# Creator: Navneet Prabhakar
from collections import Counter
import json
from pathlib import Path
import sqlite3
from slm.data.evaluation_exclusions import EvaluationExclusions
from slm.data.narrative_screen import screen
from slm.data.prose_screen import RequestGuard,windows
from slm.data.schema import digest
from slm.data.tokenized import sha

ROOT=Path('data/tinystories-quality-v1')

def main():
    plan=json.loads(Path('configs/tinystories-quality-v1.json').read_text());result=json.loads((ROOT/'report.json').read_text())
    assert result['complete'] and result['plan_sha256']==sha('configs/tinystories-quality-v1.json')
    for p,h in plan['input_bindings'].items():assert sha(p)==h,p
    db=sqlite3.connect('file:'+str((ROOT/'charges/ledger.sqlite').resolve())+'?mode=ro',uri=True)
    ops={k:(json.loads(c),s) for k,c,s in db.execute('SELECT key,charge,state FROM attempts')}
    payloads={k:(n,h) for k,n,h in db.execute('SELECT key,size,sha256 FROM payloads')}
    def cached(key):
        p=ROOT/'cache'/(digest(key)+'.bin');assert not p.is_symlink()
        raw=p.read_bytes();assert len(raw)==payloads[key][0] and sha(p)==payloads[key][1] and ops[key][1]=='complete'
        return raw
    for key in payloads:cached(key)
    totals={k:sum(r[0][k] for r in ops.values()) for k in plan['ledger_contract']['limits']}
    assert totals==result['reserved'] and all(totals[k]<=v for k,v in plan['ledger_contract']['limits'].items())
    assert totals['rows']==81703 and totals['requests']==totals['body_bytes']==0
    assert all(s=='complete' for _,s in ops.values())
    spec=json.loads(Path('configs/future-intake-evaluation-exclusions-v1.json').read_text());prior=EvaluationExclusions(spec['inventory'],spec['inventory_sha256'])
    protection=json.loads(Path(plan['upstream_protection']).read_text());upstream=RequestGuard([p['text'] for p in protection['prompts']])
    heldout_keys=set(protection['normalized_validation_families'])
    judgments={(r['file'],r['start']):r['judgment'] for r in json.loads(Path(plan['direct_review']).read_text())['records']}
    measurements={}
    with Path(plan['measurements']).open() as inp:
        for line in inp:
            m=json.loads(line)
            if m['kind']=='train_range':measurements[(m['file'],m['start'])]=m
    intake=json.loads(Path(plan['intake_report']).read_text());summaries={r['key']:r for r in result['chunks']}
    reasons=Counter();seen=Counter();passed=ptokens=count=window_count=blocked_pass=reviewed=heldout=0
    checked_chunks=set()
    for item in intake['requests']:
        request=item['request']
        if request['kind']!='train_range':continue
        path=Path(plan['intake_cache'])/(digest('records/'+request['key'])+'.bin')
        assert sha(path)==item['records_sha256']
        source=[json.loads(line) for line in path.read_bytes().splitlines()]
        for start in range(0,len(source),plan['chunk_rows']):
            key=request['key']+'/'+str(start);checked_chunks.add(key);summary=summaries[key]
            rows=[json.loads(line) for line in cached('decisions/'+key).splitlines()];batch=source[start:start+plan['chunk_rows']]
            assert len(rows)==len(batch)==summary['rows'] and ops['assess/'+key][0]['rows']==len(rows)
            cp=ct=cpt=cw=0;cr=Counter()
            for r,raw in zip(rows,batch,strict=True):
                identity=(raw['file'],raw['row']['start']);m=measurements[identity]
                assert (r['file'],r['start'],r['end'],r['raw_text_sha256'],r['source_group'])==(raw['file'],raw['row']['start'],raw['row']['end'],raw['row']['raw_text_sha256'],raw['source_group'])
                parts=windows(raw['row']['text']);assert [(p['start'],p['end']) for p in parts]==[(p['start'],p['end']) for p in r['windows']]
                expected=screen(raw['row']['text'],[p['scores'] for p in r['windows']],prior.guard,upstream,heldout_keys,judgments.get(identity))
                assert expected==r['decision'];assert r['content_tokens']==m['content_tokens']
                assert r['training_approved'] is False and r['partition'] is None
                cp+=expected['candidate'];ct+=r['content_tokens'];cpt+=r['content_tokens'] if expected['candidate'] else 0;cw+=len(parts);cr.update(expected['reasons'])
                if expected['candidate']:seen[expected['normalized_text_sha256']]+=1
                if 'official_validation_exact' in expected['reasons']:heldout+=1;blocked_pass+=expected['candidate']
                if judgments.get(identity) in ('exclude','defer'):reviewed+=1;blocked_pass+=expected['candidate']
            assert (cp,ct,cpt,cw,dict(cr))==(summary['provisional_pass_rows'],summary['total_tokens'],summary['provisional_pass_tokens'],summary['windows'],summary['reasons'])
            passed+=cp;ptokens+=cpt;count+=len(rows);window_count+=cw;reasons.update(cr)
    assert checked_chunks==set(summaries)
    assert (count,passed,ptokens,window_count,dict(reasons))==(result['rows'],result['provisional_pass_rows'],result['provisional_pass_tokens'],result['windows'],result['reason_counts'])
    assert heldout==318 and reviewed==3 and blocked_pass==0
    report=dict(creator='Navneet Prabhakar',kind='actual-narrative-quality-check-v1',passed=True,intake_sha256=sha(ROOT/'report.json'),checker_sha256=sha(__file__),
        rows_checked=count,language_windows_checked=window_count,provisional_pass_rows=passed,provisional_pass_tokens=ptokens,
        official_validation_exact_blocked=heldout,direct_nonapprovals_blocked=reviewed,blocked_rows_passing=blocked_pass,
        distinct_normalized_provisional_texts=len(seen),duplicate_provisional_members=sum(n-1 for n in seen.values()),
        reason_counts=dict(reasons),retained_payloads_verified=len(payloads),model_updates=0,teacher_calls=0,cloud_spend=0,training_approved=False,
        scope='All original-story joins, measured BPE counts, recorded window coverage/scores, reconstructed decisions, payload hashes and ledger bounds. No detector replay or factual/privacy/category/global near/source admission.')
    Path('reports/tinystories-quality-check.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');print(json.dumps(report,indent=2));db.close()

if __name__=='__main__':main()

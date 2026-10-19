"""Read-only reconstruction of actual retained narrative bytes and partitions."""
# Creator: Navneet Prabhakar
import hashlib
import json
from pathlib import Path
import sqlite3
from slm.data.schema import digest
from slm.data.story_segments import DELIMITER
from slm.data.tokenized import sha

ROOT=Path('data/tinystories-range-intake-v1')
PLAN=Path('configs/tinystories-range-intake-v1.json')


def main():
    plan=json.loads(PLAN.read_text());result=json.loads((ROOT/'report.json').read_text())
    assert result['complete'] is True and result['plan_sha256']==sha(PLAN)
    assert json.loads((ROOT/'plan.json').read_text())==plan
    for p,h in plan['input_bindings'].items():assert sha(p)==h,p
    db=sqlite3.connect('file:'+str((ROOT/'charges/ledger.sqlite').resolve())+'?mode=ro',uri=True)
    payloads={k:(n,h) for k,n,h in db.execute('SELECT key,size,sha256 FROM payloads')}
    attempts={k:(json.loads(c),s,n,h) for k,c,s,n,h in db.execute('SELECT key,charge,state,actual_bytes,body_sha256 FROM attempts')}
    def payload(key):
        p=ROOT/'cache'/(digest(key)+'.bin');raw=p.read_bytes()
        assert not p.is_symlink() and (len(raw),hashlib.sha256(raw).hexdigest())==payloads[key]
        assert attempts[key][1]=='complete'
        return raw
    for key in payloads:payload(key)
    totals={k:sum(r[0][k] for r in attempts.values()) for k in plan['ledger_contract']['limits']}
    assert totals==result['reserved']
    assert all(totals[k]<=v for k,v in plan['ledger_contract']['limits'].items())
    inv={r['path']:r for r in json.loads(Path(plan['inventory']).read_text()) if r['type']=='file'}
    counts=dict(official_validation=0,train_range=0,evaluation_prompts=0);text_bytes=0
    normalized=set();duplicates=0
    for request,summary in zip(plan['requests'],result['requests'],strict=True):
        assert request==summary['request'];key=request['key'];raw=payload('body/'+key)
        assert len(raw)==request['length'] and hashlib.sha256(raw).hexdigest()==summary['body_sha256']
        assert json.loads(payload('summary/'+key))==summary
        item=inv[request['file']]
        if request['kind']=='evaluation_prompts':
            assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==item['oid']
            raw.decode('utf-8',errors='strict');continue
        if request['kind']=='official_validation':assert hashlib.sha256(raw).hexdigest()==item['lfs']['oid']
        rows=[json.loads(line) for line in payload('records/'+key).splitlines()]
        assert len(rows)==summary['records']
        assert attempts['parse/'+key][1]=='complete'
        # Independent delimiter-offset enumeration; no production segment parser.
        offset=0;spans=[]
        for part in raw.split(DELIMITER)[:-1]:
            if (offset>0 or request['start']==0) and part.decode('utf-8',errors='strict').strip():spans.append((offset,offset+len(part)))
            offset+=len(part)+len(DELIMITER)
        if request['start']+len(raw)==item['size']:
            tail=raw[offset:]
            if tail.decode('utf-8',errors='strict').strip():spans.append((offset,len(raw)))
        assert len(spans)==len(rows)
        for r,(left,right) in zip(rows,spans,strict=True):
            story=r['row'];assert story['start']==left+request['start'] and story['end']==right+request['start']
            body=raw[left:right];assert story['text'].encode('utf-8')==body
            assert hashlib.sha256(body).hexdigest()==story['raw_text_sha256']
            assert r['file']==request['file'] and r['revision']==plan['revision'] and r['source']=='roneneldan/TinyStories'
            assert r['source_group']==r['file']+':'+str(story['start'])
            assert r['training_approved'] is False and r['provisional_quality_pass'] is False
            assert r['partition']==('validation' if request['kind']=='official_validation' else None)
            assert story['end_kind']==('file_eof' if right==len(raw) else 'delimiter')
            text_bytes+=len(body)
            if request['kind']=='train_range':
                h=hashlib.sha256(body).hexdigest();duplicates+=h in normalized;normalized.add(h)
        counts[request['kind']]+=len(rows)
    assert counts['train_range']==result['narrative_train_records'] and counts['official_validation']==result['official_validation_records']
    report=dict(creator='Navneet Prabhakar',kind='actual-tinystories-range-intake-check-v1',passed=True,
        plan_sha256=sha(PLAN),report_sha256=sha(ROOT/'report.json'),verified_payloads=len(payloads),
        counts=counts,exact_train_text_duplicate_member_rows=duplicates,retained_story_text_bytes=text_bytes,
        model_updates=0,teacher_calls=0,cloud_spend=0,training_approved=False,
        scope='All retained payload hashes, ledger charges, full validation LFS identities, Git evaluation-prompt identity and every byte span/text/partition reconstructed. No content, language, privacy, near-family, token sizing or training admission claim.')
    Path('reports/tinystories-range-intake-check.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps(report,indent=2))
    db.close()


if __name__=='__main__':main()

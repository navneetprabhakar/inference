"""Measure proposed research exclusions on a frozen corpus; never admit training."""
# Creator: Navneet Prabhakar
from collections import Counter
from contextlib import ExitStack
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile
from slm.data.build import verify
from slm.data.schema import digest
from slm.data.staging import canonical,metadata
from slm.data.tokenized import sha,stamp
from slm.data.quality_audit import signals

FIELDS={'version','kind','status','source','population_manifest_sha256','audit_manifest_sha256',
        'review_sha256','minimum_english_top_score','screen_only','scope','limitations'}
SCOPE=re.compile(r'(?i)\b(?:porn\w*|sexual|erotic\w*|rape|genitals?|orgasm|suicid\w*|self[- ]harm|diagnos\w*|dosage|prescri\w*|legal advice|investment advice|tax advice|visa requirements?)\b')
IDENTITY=re.compile(r'(?i)\b(?:open\s?assistant|laion|as an? (?:ai|large) language model|created by openai|hello prompter)\b')
PLACEHOLDER=re.compile(r'\[(?:PROMPT|TARGETLANGUAGE)\]|\b(?:INSERT|REPLACE)[_ ](?:TEXT|PROMPT|LANGUAGE)\b')


def checked(policy):
    if (set(policy)!=FIELDS or type(policy['version']) is not int or policy['version']!=1 or policy['kind']!='oasst-research-screen-v1'
        or policy['status']!='proposed_not_admitted' or policy['source']!='OpenAssistant/oasst2'
        or policy['screen_only'] is not True or type(policy['minimum_english_top_score']) not in (int,float)
        or not .8<=policy['minimum_english_top_score']<=1
        or any(not re.fullmatch('[a-f0-9]{64}',policy[k]) for k in FIELDS if k.endswith('sha256'))
        or any(not isinstance(policy[k],str) or not policy[k].strip() for k in ('scope','limitations'))):
        raise ValueError('Pinned proposed-only dialogue screening policy required')


def reasons(record,audit,minimum_score):
    if audit['record_sha256']!=digest(record) or audit['split_group']!=record['validation_results']['split_group']:
        raise ValueError('Dialogue signal identity differs')
    s=audit['signals'];base=signals(record)
    if any(s.get(k)!=v for k,v in base.items()):raise ValueError('Structural/privacy signals differ')
    result=set();proof=record['validation_results'].get('dialogue_candidate')
    if record['source']!='OpenAssistant/oasst2' or not proof:return {'not_current_dialogue_candidate'}
    raw=proof['raw_nodes'];messages=record['messages'];lineage=record['lineage']
    if len(raw)!=len(messages) or len(raw)!=len(lineage):raise ValueError('Candidate node coverage differs')
    for key,node,message in zip(lineage,raw,messages):
        if node['message_id']!=key:raise ValueError('Candidate lineage differs')
        if (node.get('lang')!='en' or node.get('review_result') is not True or node.get('deleted') is not False
            or node.get('synthetic') is not False or node.get('model_name') is not None):raise ValueError('Candidate publisher eligibility differs')
        if node['text_sha256']!=digest(message['content']):result.add('text_transformed_after_raw_extraction')
    if s['privacy_findings'] or record['validation_results'].get('privacy_redactions',{}).get('email',0) or record['validation_results'].get('privacy_redactions',{}).get('phone',0):
        result.add('privacy_attention')
    if s['structural_or_cleaner_attention']:result.add('structural_attention')
    coverage=[0]*len(messages)
    for w in s['language_windows']:
        i=w.get('message');start=w.get('start');end=w.get('end')
        if (type(i) is not int or not 0<=i<len(messages) or type(start) is not int or type(end) is not int
            or start!=coverage[i] or not start<end<=len(messages[i]['content']) or end-start>2048):
            raise ValueError('Language window coverage differs')
        coverage[i]=end;top=w.get('top_scores')
        if w.get('status')!='scored' or not top or len(top)!=2:result.add('language_unscored_or_incomplete');continue
        if any(type(p.get('score')) not in (int,float) or not 0<=p['score']<=1.001 for p in top):raise ValueError('Invalid language score')
        if top[0]['language']!='en' or top[0]['score']<minimum_score:result.add('language_score_attention')
    if coverage!=[len(m['content']) for m in messages]:raise ValueError('Incomplete language window coverage')
    text='\n'.join(m['content'] for m in messages)
    if SCOPE.search(text):result.add('bounded_scope_attention')
    if IDENTITY.search(text):result.add('source_identity_or_role_artifact')
    if PLACEHOLDER.search(text):result.add('unfilled_template_attention')
    if '```' in text or re.search(r'(?m)^\s*(?:import \w|from \w.* import |def \w+\()',text):result.add('unverified_code_attention')
    return result


def screen(dataset,audit,review,policy_path,output):
    dataset,audit,review,policy_path,output=map(Path,(dataset,audit,review,policy_path,output))
    if output.exists():raise FileExistsError(output)
    policy=metadata(policy_path);checked(policy);verify(dataset);verify(audit)
    review_data=metadata(review)
    if (sha(dataset/'manifest.json')!=policy['population_manifest_sha256'] or sha(audit/'manifest.json')!=policy['audit_manifest_sha256']
        or sha(review)!=policy['review_sha256'] or review_data['audit_manifest_sha256']!=policy['audit_manifest_sha256']
        or metadata(audit/'manifest.json')['parent_dataset_manifest_sha256']!=policy['population_manifest_sha256']
        or review_data['human_attestation'] is not False or review_data['training_eligible'] is not False):
        raise ValueError('Screen population/audit/review binding differs')
    paths=[*dataset.iterdir(),*audit.iterdir(),review,policy_path,Path(__file__)]
    guards={p.resolve():stamp(p) for p in paths if p.is_file()}
    if sum(p.stat().st_size for p in guards)>256*1024**2:raise ValueError('Screen input byte limit exceeded')
    output.parent.mkdir(parents=True,exist_ok=True);temp=Path(tempfile.mkdtemp(prefix='.dialogue-screen-',dir=output.parent));db=None
    try:
        db=sqlite3.connect(temp/'work.sqlite');db.executescript('''PRAGMA cache_size=-8192; PRAGMA temp_store=FILE;
 PRAGMA max_page_count=262144;
 CREATE TABLE audits(eid TEXT PRIMARY KEY,data TEXT); CREATE TABLE blocked(gid TEXT PRIMARY KEY);
 CREATE TABLE reviewed(eid TEXT PRIMARY KEY,hash TEXT,gid TEXT,decision TEXT);
 CREATE TABLE rows(eid TEXT PRIMARY KEY,gid TEXT,split TEXT,data TEXT,reasons TEXT,candidate INTEGER);
 CREATE INDEX groups ON rows(gid);''')
        def lines(path):
            with path.open('rb') as f:
                while raw:=f.readline(1024**2+1):
                    if len(raw)>1024**2:raise ValueError('Screen record byte limit exceeded')
                    yield json.loads(raw)
        for n,row in enumerate(lines(audit/'signals.jsonl'),1):
            if n>30000:raise ValueError('Screen audit row limit exceeded')
            db.execute('INSERT INTO audits VALUES(?,?)',(row['example_id'],canonical(row)))
        for row in review_data['decisions']:
            if row['decision'] not in ('suitable_for_bounded_sfw_research_consideration','exclude','unresolved') or row['full_text_read'] is not True:
                raise ValueError('Unsupported or unread judgment')
            db.execute('INSERT INTO reviewed VALUES(?,?,?,?)',(row['example_id'],row['record_sha256'],row['split_group'],row['decision']))
            if row['decision']!='suitable_for_bounded_sfw_research_consideration':db.execute('INSERT OR IGNORE INTO blocked VALUES(?)',(row['split_group'],))
        n=0;raw_reasons=Counter()
        for split in ('train','validation','test'):
            for path in sorted(dataset.glob(split+'-*.jsonl')):
                for row in lines(path):
                    n+=1
                    if n>30000 or row['split']!=split:raise ValueError('Screen dataset row/split bound differs')
                    eid=row['example_id'];gid=row['validation_results']['split_group']
                    item=db.execute('SELECT data FROM audits WHERE eid=?',(eid,)).fetchone()
                    if item is None:raise ValueError('Missing audit row')
                    result=reasons(row,json.loads(item[0]),policy['minimum_english_top_score']);candidate='not_current_dialogue_candidate' not in result
                    decision=db.execute('SELECT hash,gid,decision FROM reviewed WHERE eid=?',(eid,)).fetchone()
                    if decision:
                        if decision[:2]!=(digest(row),gid):raise ValueError('Reviewed record differs')
                        if decision[2]!='suitable_for_bounded_sfw_research_consideration':result.add('review_excluded_or_unresolved')
                    raw_reasons.update(result)
                    if candidate and result:db.execute('INSERT OR IGNORE INTO blocked VALUES(?)',(gid,))
                    db.execute('INSERT INTO rows VALUES(?,?,?,?,?,?)',(eid,gid,split,canonical(row),canonical(sorted(result)),int(candidate)))
        if n!=db.execute('SELECT count(*) FROM audits').fetchone()[0]:raise ValueError('Audit coverage differs')
        if db.execute('SELECT count(*) FROM reviewed d LEFT JOIN rows r ON r.eid=d.eid WHERE r.eid IS NULL').fetchone()[0]:raise ValueError('Review outside population')
        counts=Counter();sources=Counter()
        with (temp/'screening.jsonl').open('w') as ledger,(temp/'candidates.jsonl').open('w') as out,ExitStack() as files:
            shards={}
            for eid,gid,split,data,flags,candidate,blocked in db.execute('SELECT r.*,b.gid FROM rows r LEFT JOIN blocked b ON b.gid=r.gid ORDER BY r.eid'):
                keep=bool(candidate and blocked is None);counts[('remaining_' if keep else 'quarantined_' if candidate else 'reference_')+split]+=1
                ledger.write(canonical(dict(example_id=eid,split_group=gid,split=split,record_sha256=digest(json.loads(data)),
                    reasons=json.loads(flags),group_quarantined=blocked is not None,candidate_remains=keep,training_eligible=False))+'\n')
                if keep:
                    out.write(data+'\n');sources[json.loads(data)['source']]+=1
                    if split not in shards:shards[split]=files.enter_context((temp/(split+'-00000.jsonl')).open('w'))
                    shards[split].write(data+'\n')
        db.commit();db.close();db=None;(temp/'work.sqlite').unlink()
        if any(stamp(p)!=before for p,before in guards.items()):raise ValueError('Screen inputs or code changed')
        report=dict(creator='Navneet Prabhakar',release='sample_only',training_eligible=False,counts=dict(counts),
            first_pass_record_reasons=dict(raw_reasons),candidate_sources=dict(sources),policy_sha256=sha(policy_path),
            population_manifest_sha256=policy['population_manifest_sha256'],audit_manifest_sha256=policy['audit_manifest_sha256'],
            review_sha256=sha(review),implementation_sha256=sha(__file__),candidates_sha256=sha(temp/'candidates.jsonl'),
            scope='Measured proposed research screen only. Whole-group quarantine preserves existing partitions and original labels. No source rights, quality certification, corpus admission or training eligibility.')
        (temp/'report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');shutil.copyfile(policy_path,temp/'policy.json')
        shutil.copyfile(dataset/'sources.json',temp/'sources.json')
        manifest=dict(version=1,release='sample_only',files={p.name:sha(p) for p in temp.iterdir() if p.is_file()})
        (temp/'manifest.json').write_text(canonical(manifest)+'\n');verify(temp);os.rename(temp,output);return report
    except BaseException:
        if db is not None:db.close()
        shutil.rmtree(temp,ignore_errors=True);raise


def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('dataset','audit','review','policy','output'):p.add_argument('--'+name,required=True)
    a=p.parse_args();print(json.dumps(screen(a.dataset,a.audit,a.review,a.policy,a.output),indent=2,sort_keys=True))


if __name__=='__main__':main()

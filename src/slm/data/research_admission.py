"""Self-contained, checked context-prose research releases; never human attestation."""
# Creator: Navneet Prabhakar
from collections import Counter
from contextlib import contextmanager
from copy import deepcopy
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from slm.data.build import verify
from slm.data.context import derive,checked_policy,SOURCE
from slm.data.schema import digest
from slm.data.staging import metadata,canonical
from slm.data.tokenized import sha
from slm.data.review_stream import Index,DEFAULT_LIMITS,limits_checked,guarded,lines

FIELDS={'version','kind','status','scope','review_mode','human_attestation','authorized_by','authorization_instruction',
    'source','source_evidence_decision','origin_manifest_sha256','population_manifest_sha256','audit_manifest_sha256',
    'extraction_file_sha256','development_review_file_sha256','minimum_english_top_score','quarantine_any_attention',
    'require_terminal_sentence_punctuation','quarantine_whole_derived_group','limits','risk_acceptance'}
CORE=('example_id','source','source_revision','license_record','parent_group_id','messages','official_split',
      'task','style','content_category','language','lineage','upstream_references')
PRIORITY={'train':0,'validation':1,'test':2}


def policy_checked(policy):
    if (set(policy)!=FIELDS or type(policy['version']) is not int or policy['version']!=1
        or policy['kind']!='context-prose-research-admission-v1' or policy['status']!='accepted_for_bounded_research'
        or policy['scope']!='local_foundation_smoke' or policy['review_mode']!='delegated_expert'
        or policy['human_attestation'] is not False or policy['authorized_by']!='Navneet Prabhakar' or policy['source']!=SOURCE
        or any(not isinstance(policy[k],str) or not policy[k].strip() for k in ('authorization_instruction','source_evidence_decision','risk_acceptance'))
        or any(not re.fullmatch('[a-f0-9]{64}',policy[k]) for k in FIELDS if k.endswith('sha256'))
        or any(policy[k] is not True for k in ('quarantine_any_attention','require_terminal_sentence_punctuation','quarantine_whole_derived_group'))
        or type(policy['minimum_english_top_score']) not in (float,int) or not .8<=policy['minimum_english_top_score']<=1):
        raise ValueError('Explicit bounded delegated research policy required')
    caps={'processed_positions':1048576,'updates':2048,'max_passes':2,'max_parameters':100000000}
    if set(policy['limits'])!=set(caps) or any(type(v) is not int or not 1<=v<=caps[k] for k,v in policy['limits'].items()):
        raise ValueError('Research limits exceed the local experiment contract')


def bundle(root,prefix,expected):
    path=root/(prefix+'manifest.json');manifest=metadata(path)
    if sha(path)!=expected or manifest.get('version')!=1:raise ValueError('Research snapshot identity differs')
    for name,want in manifest['files'].items():
        if Path(name).name!=name or name=='manifest.json' or sha(root/(prefix+name))!=want:
            raise ValueError('Research snapshot payload differs')
    return manifest


def rows(root,prefix,manifest,limits):
    for split in PRIORITY:
        for name in sorted(manifest['files']):
            if name.startswith(split+'-') and name.endswith('.jsonl'):
                for row in lines(root/(prefix+name),limits):
                    if row['split']!=split:raise ValueError('Research snapshot partition differs')
                    yield row


def eligible(record,audit,policy):
    if audit['record_sha256']!=digest(record) or audit['split_group']!=record['validation_results']['split_group']:
        raise ValueError('Research signal identity differs')
    s=audit['signals'];text=record['messages'][0]['content']
    from slm.data.quality_audit import signals
    base=signals(record)
    if any(s.get(k)!=v for k,v in base.items()):raise ValueError('Research structural/privacy signals differ')
    if s['attention'] or s['privacy_findings'] or s['structural_or_cleaner_attention']:return False,'attention'
    windows=s.get('language_windows',[]);end=0
    for window in windows:
        if (window.get('message')!=0 or window.get('start')!=end or type(window.get('end')) is not int
            or not end<window['end']<=len(text) or window['end']-end>2048):raise ValueError('Research language-window coverage differs')
        end=window['end'];scores=window.get('top_scores')
        if window.get('status')!='scored' or not scores or len(scores)!=2:return False,'language_unscored'
        if any(type(v.get('score')) not in (int,float) or not 0<=v['score']<=1.001 for v in scores):raise ValueError('Invalid research language score')
        if scores[0]['language']!='en' or scores[0]['score']<policy['minimum_english_top_score']:return False,'language_score'
    if not windows or end!=len(text):raise ValueError('Research language-window coverage incomplete')
    if not re.search(r'''[.!?]["'”’)]{0,3}$''',text):return False,'terminal_punctuation'
    return True,None


def admitted(record,policy):
    out=deepcopy(record);out['language']='en';out['content_category']='sfw'
    out['validation_results'].update(language_review='research_policy_assumed_en',content_review='research_scope_sfw_proxy',
        privacy_review='research_screened_not_individually_verified',quality_review='research_screened_not_individually_verified',
        privacy_scope='Bounded research screening; no individual human attestation.',
        research_admission={'policy_sha256':digest(policy),'population_record_sha256':digest(record),
            'scope':policy['scope'],'review_mode':'delegated_expert','human_attestation':False})
    return out


def populate(root,index):
    policy=metadata(root/'research-policy.json');policy_checked(policy)
    origin=bundle(root,'origin-',policy['origin_manifest_sha256'])
    population=bundle(root,'population-',policy['population_manifest_sha256'])
    audit=bundle(root,'audit-',policy['audit_manifest_sha256'])
    if audit.get('parent_dataset_manifest_sha256')!=policy['population_manifest_sha256']:raise ValueError('Research audit population differs')
    extraction=metadata(root/'extraction.json');checked_policy(extraction)
    if sha(root/'extraction.json')!=policy['extraction_file_sha256'] or extraction['parent_manifest_sha256']!=policy['origin_manifest_sha256']:
        raise ValueError('Research extraction binding differs')
    review=metadata(root/'development-review.json')
    if (sha(root/'development-review.json')!=policy['development_review_file_sha256'] or review.get('human_attestation') is not False
        or review.get('review_mode')!='delegated_expert' or review.get('quality_manifest_sha256')!=policy['audit_manifest_sha256']):
        raise ValueError('Research development-review binding differs')
    sources=metadata(root/'sources.json')
    if sources!=metadata(root/'population-sources.json') or sources!=metadata(root/'origin-sources.json'):raise ValueError('Research source registry differs')
    if SOURCE not in sources or sources[SOURCE]['license_id']!='cc-by-sa-3.0':raise ValueError('Research source terms differ')
    index.db.executescript('''CREATE TABLE origins(eid TEXT PRIMARY KEY,data TEXT) WITHOUT ROWID;
 CREATE TABLE population(eid TEXT PRIMARY KEY,data TEXT,gid TEXT,derived INTEGER) WITHOUT ROWID;
 CREATE TABLE signals(eid TEXT PRIMARY KEY,data TEXT) WITHOUT ROWID;
 CREATE TABLE blocked(gid TEXT PRIMARY KEY) WITHOUT ROWID;''')
    counts=Counter();reasons=Counter()
    for record in rows(root,'origin-',origin,index.limits):
        source=sources.get(record['source'])
        if source is None or record['source_revision']!=source['revision'] or record['license_record']!=digest(source):
            raise ValueError('Research origin/source provenance differs')
        index.db.execute('INSERT INTO origins VALUES(?,?)',(record['example_id'],canonical(record)));index.tick();counts['origin']+=1
        if counts['origin']>index.limits['max_records']:raise ValueError('Research origin record cap exceeded')
    for record in rows(root,'population-',population,index.limits):
        proof=record['validation_results'].get('context_derivation');eid=record['example_id'];gid=record['validation_results']['split_group']
        if not isinstance(gid,str) or not re.fullmatch('[a-f0-9]{64}',gid):raise ValueError('Research group identity invalid')
        lookup=index.db.execute('SELECT data FROM origins WHERE eid=?',(proof['parent_example_id'] if proof else eid,)).fetchone()
        if lookup is None:raise ValueError('Research origin record missing')
        parent=json.loads(lookup[0])
        if proof:
            expected,reason=derive(parent,extraction)
            if (reason is not None or any(record[k]!=expected[k] for k in CORE)
                or proof!=expected['validation_results']['context_derivation']):raise ValueError('Research context derivation differs')
        elif parent['split']=='train' or any(record[k]!=parent[k] for k in CORE):raise ValueError('Unexpected research population record')
        if PRIORITY[record['split']]<PRIORITY[parent['split']]:raise ValueError('Research parent heldout demoted')
        index.db.execute('INSERT INTO population VALUES(?,?,?,?)',(eid,canonical(record),gid,int(bool(proof))))
        index.tick();counts['population']+=1
        if counts['population']>index.limits['max_records']:raise ValueError('Research population cap exceeded')
    for row in lines(root/'audit-signals.jsonl',index.limits):
        current=index.db.execute('SELECT data FROM population WHERE eid=?',(row['example_id'],)).fetchone()
        if current is None or row['record_sha256']!=digest(json.loads(current[0])):raise ValueError('Research signal record differs')
        index.db.execute('INSERT INTO signals VALUES(?,?)',(row['example_id'],canonical(row)));index.tick();counts['signals']+=1
    if counts['signals']!=counts['population']:raise ValueError('Research signal coverage incomplete')
    # Freeze group quarantine before constructing any admitted output.
    for data,gid in index.db.execute('SELECT data,gid FROM population WHERE derived=1 ORDER BY eid'):
        record=json.loads(data);signal=json.loads(index.db.execute('SELECT data FROM signals WHERE eid=?',(record['example_id'],)).fetchone()[0])
        ok,reason=eligible(record,signal,policy)
        if not ok:index.db.execute('INSERT OR IGNORE INTO blocked VALUES(?)',(gid,));reasons[reason]+=1
    for data,gid in index.db.execute('SELECT data,gid FROM population WHERE derived=1 ORDER BY eid'):
        if index.db.execute('SELECT 1 FROM blocked WHERE gid=?',(gid,)).fetchone():counts['group_quarantined']+=1;continue
        record=json.loads(data);item=admitted(record,policy)
        if item['split']=='train':
            from slm.data.holdout import check_training_context
            check_training_context(item['messages'],(item['example_id'],item['parent_group_id'],gid))
        index.db.execute('INSERT INTO approved(eid,data,gid,split) VALUES(?,?,?,?)',(item['example_id'],canonical(item),gid,item['split']))
        counts['admitted_'+item['split']]+=1;index.tick()
    index.db.commit();index.research_limits=policy['limits'];index.research_scope=policy['scope']
    if not counts['admitted_train']:raise ValueError('No admitted research training records')
    return dict(counts=counts,exclusion_reasons=reasons,policy_sha256=digest(policy),limits=policy['limits'])


@contextmanager
def open_research(root,limits=None):
    root=Path(root);manifest=metadata(root/'manifest.json')
    if manifest.get('release')!='research_training' or manifest.get('review_schema_version')!=3:raise ValueError('Research release v3 required')
    limits=limits_checked(limits or manifest.get('verification_limits',DEFAULT_LIMITS));check=guarded([root],limits);verify(root)
    if digest(metadata(root/'research-policy.json'))!=manifest['research_policy_sha256']:raise ValueError('Research policy binding differs')
    with tempfile.TemporaryDirectory(prefix='slm-research-check-') as temp:
        index=Index(Path(temp)/'index.sqlite',limits)
        try:
            populate(root,index);index.shard_rows(root,'released');check();yield index
        finally:index.db.close()


def release(origin,population,audit,extraction,review,policy_file,output):
    output=Path(output)
    if output.exists():raise FileExistsError(output)
    policy=metadata(policy_file);policy_checked(policy)
    output.parent.mkdir(parents=True,exist_ok=True);temp=Path(tempfile.mkdtemp(prefix='.research-release-',dir=output.parent));index=None
    try:
        for prefix,source in [('origin-',origin),('population-',population),('audit-',audit)]:
            verify(source)
            for p in Path(source).iterdir():
                if not p.is_file() or p.is_symlink():raise ValueError('Flat research source required')
                shutil.copyfile(p,temp/(prefix+p.name))
        for name,path in [('extraction.json',extraction),('development-review.json',review),('research-policy.json',policy_file)]:shutil.copyfile(path,temp/name)
        shutil.copyfile(temp/'population-sources.json',temp/'sources.json')
        limits=DEFAULT_LIMITS;check=guarded([temp],limits)
        index=Index(temp/'work.sqlite',limits);report=populate(temp,index);index.db.close();index=None
        # Export deterministically from the computed database, not from caller-supplied shards.
        import sqlite3
        db=sqlite3.connect(temp/'work.sqlite')
        try:
            for split in PRIORITY:
                with (temp/(split+'-00000.jsonl')).open('w') as stream:
                    for data, in db.execute('SELECT data FROM approved WHERE split=? ORDER BY eid',(split,)):stream.write(data+'\n')
        finally:db.close()
        (temp/'work.sqlite').unlink();check()
        report.update(release='research_training',review_schema_version=3,human_attestation=False,scope=policy['scope'])
        (temp/'report.json').write_text(canonical(report)+'\n')
        manifest=dict(version=1,release='research_training',review_schema_version=3,research_policy_sha256=digest(policy),verification_limits=limits,
            files={p.name:sha(p) for p in sorted(temp.iterdir())})
        (temp/'manifest.json').write_text(canonical(manifest)+'\n')
        with open_research(temp) as checked:assert len(checked)==report['counts']['admitted_train']
        os.rename(temp,output);return report
    except BaseException:
        if index is not None:index.db.close()
        shutil.rmtree(temp,ignore_errors=True);raise

"""Checked bounded foundation research over a trusted frozen canonical population."""
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
from slm.data.schema import Source,digest
from slm.data.staging import metadata,canonical
from slm.data.tokenized import sha
from slm.data.review_stream import Index,DEFAULT_LIMITS,limits_checked,guarded,lines
from slm.data.research_admission import bundle,rows,PRIORITY
from slm.data.dialogue_screen import SCOPE,IDENTITY,PLACEHOLDER
from slm.data.dialogue_language import assess,RULE as LANGUAGE_RULE
from slm.data.quality_audit import signals

SOURCES={'OpenAssistant/oasst2':'apache-2.0','databricks/databricks-dolly-15k':'cc-by-sa-3.0'}
CLINICAL=re.compile(r'(?i)\b(?:blood pressure|heart disease|cancer|chronic pain|medical advice)\b')
RULE=dict(kind='foundation-research-eligibility-v1',scope_pattern=SCOPE.pattern,identity_pattern=IDENTITY.pattern,
          placeholder_pattern=PLACEHOLDER.pattern,clinical_pattern=CLINICAL.pattern,language_rule_sha256=digest(LANGUAGE_RULE),
          whole_group_quarantine=True,exclude_prior_graded_nonapprovals=True,exclude_known_privacy_markers=True,
          exclude_code_fences=True,foundation_only=True)
FIELDS={'version','kind','status','scope','authorized_by','authorization_instruction','review_mode','human_attestation',
        'population_manifest_sha256','audit_manifest_sha256','development_review_sha256','legacy_review_sha256',
        'recent_review_sha256','recent_sample_sha256','eligibility_rule_sha256','source_bindings','source_decisions',
        'research_assumptions','risk_acceptance','limits'}


def checked(policy):
    if (set(policy)!=FIELDS or type(policy['version']) is not int or policy['version']!=1
        or policy['kind']!='two-source-foundation-research-v1' or policy['status']!='accepted_for_bounded_research'
        or policy['scope']!='local_foundation_pilot' or policy['authorized_by']!='Navneet Prabhakar'
        or policy['review_mode']!='delegated_expert' or policy['human_attestation'] is not False
        or policy['eligibility_rule_sha256']!=digest(RULE)
        or any(not re.fullmatch('[a-f0-9]{64}',policy[k]) for k in FIELDS if k.endswith('sha256'))
        or not set(policy['source_bindings']) or not set(policy['source_bindings'])<=set(SOURCES)
        or set(policy['source_decisions'])!=set(policy['source_bindings'])
        or any(not re.fullmatch('[a-f0-9]{64}',v) for v in policy['source_bindings'].values())
        or any(not isinstance(v,str) or not v.strip() for v in policy['source_decisions'].values())
        or any(not isinstance(policy[k],str) or not policy[k].strip() for k in ('authorization_instruction','research_assumptions','risk_acceptance'))):
        raise ValueError('Exact bounded delegated foundation policy required')
    caps=dict(processed_positions=10485760,updates=12288,max_passes=2,max_parameters=100000000)
    if set(policy['limits'])!=set(caps) or any(type(v) is not int or not 1<=v<=caps[k] for k,v in policy['limits'].items()):
        raise ValueError('Foundation research limits exceed the experiment contract')


def eligible(record,audit):
    if audit['record_sha256']!=digest(record) or audit['split_group']!=record['validation_results']['split_group']:
        raise ValueError('Foundation signal binding differs')
    s=audit['signals'];base=signals(record)
    if any(s.get(k)!=v for k,v in base.items()):raise ValueError('Foundation structural/privacy signals differ')
    proof=record['validation_results'];source=record['source']
    if source=='OpenAssistant/oasst2':
        if not proof.get('dialogue_candidate'):return {'not_candidate'}
        from slm.data.dialogue_language import reasons
        flags=reasons(record,audit,.8)
    elif source=='databricks/databricks-dolly-15k':
        p=proof.get('foundation_dialogue_candidate')
        if not p:return {'not_candidate'}
        if (p.get('method')!='complete-dolly-instruction-foundation-candidate-v1' or p.get('training_eligible') is not False
            or not all(re.fullmatch('[a-f0-9]{64}',p.get(k,'')) for k in ('parent_manifest_sha256','parent_record_sha256'))
            or p.get('parent_split') not in PRIORITY or PRIORITY[record['split']]<PRIORITY[p['parent_split']]):
            raise ValueError('Dolly canonical candidate receipt differs')
        flags=set()
        if assess(record['messages'],s['language_windows'])['hard_attention']:flags.add('strong_non_english_attention')
    else:return {'not_candidate'}
    if s['privacy_findings'] or s['structural_or_cleaner_attention']:flags.add('privacy_or_structural_attention')
    text='\n'.join(m['content'] for m in record['messages'])
    if '[EMAIL]' in text or '[PHONE]' in text:flags.add('redacted_privacy_marker')
    if SCOPE.search(text) or CLINICAL.search(text):flags.add('bounded_scope_attention')
    if IDENTITY.search(text):flags.add('source_identity_or_role_artifact')
    if PLACEHOLDER.search(text):flags.add('template_attention')
    if '```' in text or re.search(r'(?m)^\s*(?:import \w|from \w.* import |def \w+\()',text):flags.add('unverified_code_attention')
    return flags


def populate(root,index):
    policy=metadata(root/'research-policy.json');checked(policy)
    population=bundle(root,'population-',policy['population_manifest_sha256']);audit=bundle(root,'audit-',policy['audit_manifest_sha256'])
    if audit.get('parent_dataset_manifest_sha256')!=policy['population_manifest_sha256']:raise ValueError('Foundation audit population differs')
    sources=metadata(root/'sources.json');evidence=metadata(root/'population-evidence.json')
    if sources!=metadata(root/'population-sources.json'):raise ValueError('Foundation source registry differs')
    for name,want in policy['source_bindings'].items():
        source=Source(**sources[name])
        if (digest(sources[name])!=want or source.license_id!=SOURCES[name]
            or sha(root/('population-'+evidence[name]['card']))!=source.card_sha256
            or sha(root/('population-'+evidence[name]['license']))!=source.license_text_sha256):raise ValueError('Foundation source evidence differs')
    for file,key in [('development-review.json','development_review_sha256'),('legacy-review.json','legacy_review_sha256'),
                     ('recent-review.json','recent_review_sha256'),('recent-sample.jsonl','recent_sample_sha256')]:
        if sha(root/file)!=policy[key]:raise ValueError('Foundation review evidence differs')
    review=metadata(root/'development-review.json');legacy=metadata(root/'legacy-review.json');recent=metadata(root/'recent-review.json')
    if (review.get('population_manifest_sha256')!=policy['population_manifest_sha256'] or review.get('audit_manifest_sha256')!=policy['audit_manifest_sha256']
        or review.get('sample_sha256')!=sha(root/'audit-sample.jsonl') or review.get('human_attestation') is not False
        or review.get('review_mode')!='delegated_expert' or legacy.get('human_attestation') is not False
        or recent.get('human_attestation') is not False or recent.get('sample_sha256')!=policy['recent_sample_sha256']):raise ValueError('Foundation review authority/selection differs')
    db=index.db;db.executescript('''CREATE TABLE population(eid TEXT PRIMARY KEY,data TEXT,gid TEXT) WITHOUT ROWID;
 CREATE TABLE signals(eid TEXT PRIMARY KEY,data TEXT) WITHOUT ROWID;
 CREATE TABLE prior(eid TEXT,message_hash TEXT,PRIMARY KEY(eid,message_hash)) WITHOUT ROWID;
 CREATE TABLE blocked(gid TEXT PRIMARY KEY) WITHOUT ROWID;
 CREATE TABLE sample(eid TEXT PRIMARY KEY,hash TEXT) WITHOUT ROWID;
 CREATE TABLE graded(eid TEXT PRIMARY KEY) WITHOUT ROWID;''')
    counts=Counter();reasons=Counter()
    for r in rows(root,'population-',population,index.limits):
        source=sources.get(r['source']);gid=r['validation_results']['split_group']
        if (source is None or r['source_revision']!=source['revision'] or r['license_record']!=digest(source)
            or not re.fullmatch('[a-f0-9]{64}',gid) or r['official_split'] not in (None,*PRIORITY)
            or r['official_split'] is not None and PRIORITY[r['split']]<PRIORITY[r['official_split']]):raise ValueError('Foundation provenance/group/partition differs')
        db.execute('INSERT INTO population VALUES(?,?,?)',(r['example_id'],canonical(r),gid));counts['population']+=1;index.tick()
        if counts['population']>index.limits['max_records']:raise ValueError('Foundation population row cap exceeded')
    for r in lines(root/'audit-signals.jsonl',index.limits):
        db.execute('INSERT INTO signals VALUES(?,?)',(r['example_id'],canonical(r)));counts['signals']+=1;index.tick()
    if counts['signals']!=counts['population']:raise ValueError('Foundation audit coverage differs')
    for eid,item in legacy['examples'].items():
        if digest(item['record'])!=item['record_sha256']:raise ValueError('Legacy review record differs')
        if item['decision'].get('quality_verified') is False:db.execute('INSERT OR IGNORE INTO prior VALUES(?,?)',(eid,digest(item['record']['messages'])))
    recent_rows={r['record']['example_id']:r for r in lines(root/'recent-sample.jsonl',index.limits)}
    for d in recent['decisions']:
        r=recent_rows[d['example_id']]['record']
        if digest(r)!=d['record_sha256'] or d['full_text_read'] is not True:raise ValueError('Recent review binding differs')
        if d['decision'] in ('exclude','unresolved'):db.execute('INSERT OR IGNORE INTO prior VALUES(?,?)',(d['example_id'],digest(r['messages'])))
    for r in lines(root/'audit-sample.jsonl',index.limits):
        if digest(r['record'])!=r['record_sha256']:raise ValueError('Development sample record differs')
        if r['record']['split']=='train':db.execute('INSERT INTO sample VALUES(?,?)',(r['record']['example_id'],r['record_sha256']))
    for d in review['decisions']:
        row=db.execute('SELECT data,gid FROM population WHERE eid=?',(d['example_id'],)).fetchone();wanted=db.execute('SELECT hash FROM sample WHERE eid=?',(d['example_id'],)).fetchone()
        if (row is None or wanted is None or wanted[0]!=d['record_sha256'] or digest(json.loads(row[0]))!=d['record_sha256']
            or d['split_group']!=row[1] or d['full_text_read'] is not True or d['foundation_decision'] not in ('consider','exclude')
            or d['conversation_sft_certified'] is not False or d['training_approved'] is not False):raise ValueError('Development reading differs')
        db.execute('INSERT INTO graded VALUES(?)',(d['example_id'],))
        if d['foundation_decision']=='exclude':db.execute('INSERT OR IGNORE INTO blocked VALUES(?)',(row[1],))
    if db.execute('SELECT count(*) FROM sample').fetchone()!=db.execute('SELECT count(*) FROM graded').fetchone():raise ValueError('Incomplete selected-train review')
    for eid,data,gid in db.execute('SELECT eid,data,gid FROM population ORDER BY eid'):
        r=json.loads(data);a=db.execute('SELECT data FROM signals WHERE eid=?',(eid,)).fetchone()
        if a is None:raise ValueError('Missing foundation audit row')
        flags=eligible(r,json.loads(a[0])) if r['source'] in policy['source_bindings'] else {'not_candidate'}
        priors=db.execute('SELECT message_hash FROM prior WHERE eid=?',(eid,)).fetchall()
        if priors:
            if any(p[0]!=digest(r['messages']) for p in priors):raise ValueError('Prior review message changed')
            flags.add('prior_graded_nonapproval')
        reasons.update(flags)
        if flags and flags!={'not_candidate'}:db.execute('INSERT OR IGNORE INTO blocked VALUES(?)',(gid,))
    for eid,data,gid in db.execute('SELECT eid,data,gid FROM population ORDER BY eid'):
        r=json.loads(data)
        marker='dialogue_candidate' if r['source']=='OpenAssistant/oasst2' else 'foundation_dialogue_candidate'
        if r['source'] not in policy['source_bindings'] or not r['validation_results'].get(marker):continue
        if db.execute('SELECT 1 FROM blocked WHERE gid=?',(gid,)).fetchone():counts['quarantined']+=1;continue
        item=deepcopy(r);item['language']='en';item['content_category']='sfw'
        item['validation_results'].update(language_review='research_policy_assumed_en',content_review='research_scope_sfw_proxy',
            quality_review='research_language_only_not_factual_or_sft',privacy_review='research_screened_not_individually_verified',
            research_admission=dict(review_schema_version=4,policy_sha256=digest(policy),population_record_sha256=digest(r),
                                    scope=policy['scope'],human_attestation=False,review_mode='delegated_expert'))
        if item['split']=='train':
            from slm.data.holdout import check_training_context
            check_training_context(item['messages'],(eid,item['parent_group_id'],gid))
        db.execute('INSERT INTO approved(eid,data,gid,split) VALUES(?,?,?,?)',(eid,canonical(item),gid,item['split']));counts['admitted_'+item['split']]+=1;index.tick()
    if not counts['admitted_train']:raise ValueError('No admitted foundation train records')
    db.commit();index.research_limits=policy['limits'];index.research_scope=policy['scope']
    return dict(counts=dict(counts),exclusion_reasons=dict(reasons),limits=policy['limits'],policy_sha256=digest(policy))


@contextmanager
def open_research(root,limits=None):
    root=Path(root);m=metadata(root/'manifest.json')
    if m.get('release')!='research_training' or m.get('review_schema_version')!=4:raise ValueError('Foundation research v4 required')
    limits=limits_checked(limits or m.get('verification_limits',DEFAULT_LIMITS));check=guarded([root],limits);verify(root)
    if digest(metadata(root/'research-policy.json'))!=m['research_policy_sha256']:raise ValueError('Foundation policy manifest differs')
    with tempfile.TemporaryDirectory(prefix='foundation-research-check-') as temp:
        index=Index(Path(temp)/'index.sqlite',limits)
        try:populate(root,index);index.shard_rows(root,'released');check();yield index
        finally:index.db.close()


def release(population,audit,review,legacy,recent,recent_sample,policy_file,output):
    output=Path(output)
    if output.exists():raise FileExistsError(output)
    checked(metadata(policy_file));output.parent.mkdir(parents=True,exist_ok=True)
    temp=Path(tempfile.mkdtemp(prefix='.foundation-release-',dir=output.parent));index=None
    try:
        for prefix,path in [('population-',population),('audit-',audit)]:
            verify(path)
            for p in Path(path).iterdir():
                if not p.is_file() or p.is_symlink():raise ValueError('Flat regular foundation inputs required')
                shutil.copyfile(p,temp/(prefix+p.name))
        for name,path in [('development-review.json',review),('legacy-review.json',legacy),('recent-review.json',recent),('recent-sample.jsonl',recent_sample),('research-policy.json',policy_file)]:shutil.copyfile(path,temp/name)
        shutil.copyfile(temp/'population-sources.json',temp/'sources.json');check=guarded([temp],DEFAULT_LIMITS)
        index=Index(temp/'work.sqlite',DEFAULT_LIMITS);report=populate(temp,index)
        for split in PRIORITY:
            with (temp/(split+'-00000.jsonl')).open('w') as out:
                for data, in index.db.execute('SELECT data FROM approved WHERE split=? ORDER BY eid',(split,)):out.write(data+'\n')
        index.db.close();index=None;(temp/'work.sqlite').unlink();check()
        report.update(creator='Navneet Prabhakar',review_schema_version=4,release='research_training',human_attestation=False,scope='local_foundation_pilot')
        (temp/'report.json').write_text(canonical(report)+'\n')
        manifest=dict(version=1,review_schema_version=4,release='research_training',research_policy_sha256=digest(metadata(policy_file)),
                      verification_limits=DEFAULT_LIMITS,files={p.name:sha(p) for p in temp.iterdir()})
        (temp/'manifest.json').write_text(canonical(manifest)+'\n')
        with open_research(temp) as checked_index:assert len(checked_index)==report['counts']['admitted_train']
        os.rename(temp,output);return report
    except BaseException:
        if index is not None:index.db.close()
        shutil.rmtree(temp,ignore_errors=True);raise

"""Offline signals and whole-group samples; never admit or rewrite training data."""
# Creator: Navneet Prabhakar
from collections import Counter
from dataclasses import asdict
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import tempfile
import time
import unicodedata
from slm.data.build import verify
from slm.data.curation import EMAIL,PHONE,SECRET,clean
from slm.data.schema import Example,Source,digest
from slm.data.staging import metadata,parse,canonical
from slm.data.tokenized import sha,stamp

LIMITS=dict(max_input_bytes=64*1024*1024,max_records=20000,max_record_bytes=1024*1024,max_windows=50000,
            max_db_bytes=512*1024*1024,max_sample_records=2000,max_strata=1024,max_detector_output_bytes=16*1024*1024,detector_seconds=30)
PATTERNS={'email':EMAIL,'contextual_phone':PHONE,'credential_pattern':SECRET,
          'international_phone_candidate':re.compile(r'(?<!\w)\+[1-9][\d ()-]{8,18}\d(?!\w)'),
          'bearer_token_candidate':re.compile(r'(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{12,}'),
          'private_key_header':re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
          'identity_or_address_context':re.compile(r'(?i)\b(?:passport|social security|ssn|account number|home address|date of birth)\s*[:=]')}


def signals(record):
    texts=[m['content'] for m in record['messages']]
    text='\n'.join(texts);words=re.findall(r'\w+',text.casefold());lines=[s.strip() for s in text.splitlines() if s.strip()]
    findings={}
    for name,pattern in PATTERNS.items():
        count=0;locations=[]
        for i,value in enumerate(texts):
            for match in pattern.finditer(value):
                count+=1
                if len(locations)<20:locations.append([i,match.start(),match.end()])
        if count:findings[name]=dict(count=count,first_locations=locations)
    locations=[];count=0
    for i,value in enumerate(texts):
        for match in re.finditer(r'(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])',value):
            try:ipaddress.IPv4Address(match.group())
            except ipaddress.AddressValueError:continue
            count+=1
            if len(locations)<20:locations.append([i,match.start(),match.end()])
    if count:findings['ipv4_literal_candidate']=dict(count=count,first_locations=locations)
    structural=None
    try:clean(Example(**record))
    except (ValueError,KeyError,TypeError) as exc:structural=str(exc)
    return dict(characters=len(text),utf8_bytes=len(text.encode()),messages=len(texts),word_tokens=len(words),
                unique_word_tokens=len(set(words)),most_common_word_count=max(Counter(words).values(),default=0),
                nonempty_lines=len(lines),duplicate_nonempty_lines=len(lines)-len(set(lines)),
                alphabetic_characters=sum(c.isalpha() for c in text),
                control_characters=sum(unicodedata.category(c)=='Cc' and c not in '\n\t' for c in text),
                replacement_characters=text.count('\ufffd'),url_occurrences=len(re.findall(r'https?://',text)),
                markup_tag_candidates=len(re.findall(r'</?[A-Za-z][^>]{0,200}>',text)),code_fences=text.count('```'),
                structural_or_cleaner_attention=structural,privacy_findings=findings,
                privacy_assessment='unverified',quality_assessment='unverified',content_assessment='unverified',
                interpretation='Counts and candidates only; no PII certainty, quality/content grade or text rewrite.')


def predict(binary,model,input_path,output,limits):
    """Official CLI only. Kill and reap on timeout/output overflow; no shell/fallback."""
    with output.open('wb') as out,(output.parent/'detector.stderr').open('wb') as err:
        child=subprocess.Popen([str(binary),'predict-prob',str(model),str(input_path),'2','0'],stdout=out,stderr=err)
        started=time.monotonic()
        try:
            while child.poll() is None:
                if time.monotonic()-started>limits['detector_seconds']:raise ValueError('Detector time budget exceeded')
                if output.stat().st_size>limits['max_detector_output_bytes'] or (output.parent/'detector.stderr').stat().st_size>65536:
                    raise ValueError('Detector output byte budget exceeded')
                time.sleep(.02)
            if child.returncode:raise ValueError('Detector process failed; no fallback')
            if output.stat().st_size>limits['max_detector_output_bytes']:raise ValueError('Detector output byte budget exceeded')
        finally:
            if child.poll() is None:child.kill()
            child.wait()


def top_scores(line):
    parts=line.split()
    if len(parts) not in (0,2,4):raise ValueError('Expected up to two language scores per window')
    result=[]
    for label,score in zip(parts[::2],parts[1::2]):
        if not re.fullmatch(r'__label__[a-z_\-]{2,24}',label):raise ValueError('Unexpected language label')
        value=float(score)
        # Upstream approximate probabilities may slightly exceed one. Preserve
        # the raw score, do not clamp or interpret it as calibrated confidence.
        if not math.isfinite(value) or not 0<=value<=1.001:raise ValueError('Invalid detector score')
        result.append(dict(language=label.removeprefix('__label__'),score=value))
    if len(result)==2 and (result[0]['language']==result[1]['language'] or result[0]['score']<result[1]['score']):raise ValueError('Unordered or duplicate language predictions')
    return result


def audit(dataset,descriptor,output,*,limits,seed,groups_per_stratum=3,window_characters=2048):
    dataset,descriptor,output=map(Path,(dataset,descriptor,output));limits=dict(limits)
    if set(limits)!=set(LIMITS) or any(type(v) is not int or v<1 for v in limits.values()) or limits['max_db_bytes']<1024*1024:raise ValueError('Complete positive audit limits required')
    if not isinstance(seed,str) or not seed or type(groups_per_stratum) is not int or groups_per_stratum<1 or type(window_characters) is not int or not 32<=window_characters<=8192:raise ValueError('Explicit seed, positive group count and bounded window size required')
    if output.exists():raise FileExistsError(output)
    metadata(dataset/'manifest.json');model_spec=metadata(descriptor)
    if model_spec.get('version')!=1 or model_spec.get('kind')!='offline-fasttext-lid-v1':raise ValueError('Pinned offline detector descriptor required')
    binary=descriptor.parent/model_spec['binary'];model=descriptor.parent/model_spec['model']
    guards={}
    for path in [descriptor,binary,model,*dataset.iterdir(),Path(__file__),Path(__file__).with_name('build.py'),Path(__file__).with_name('curation.py')]:
        if not path.is_file() or path.is_symlink():raise ValueError('Regular pinned audit inputs required')
        guards[path.resolve()]=stamp(path)
    if sum(p.stat().st_size for p in dataset.iterdir())>limits['max_input_bytes']:raise ValueError('Audit input byte budget exceeded')
    if sha(binary)!=model_spec['binary_sha256'] or sha(model)!=model_spec['model_sha256']:raise ValueError('Detector artifact checksum differs')
    def unchanged():
        for path,before in guards.items():
            if stamp(path)!=before:raise ValueError('Audit input, detector or implementation changed')
    verify(dataset);sources={k:Source(**v) for k,v in metadata(dataset/'sources.json').items()};unchanged()
    output.parent.mkdir(parents=True,exist_ok=True);temp=Path(tempfile.mkdtemp(prefix='.quality-audit-',dir=output.parent));db=None
    try:
        db=sqlite3.connect(temp/'work.sqlite');db.executescript('''PRAGMA page_size=4096; PRAGMA cache_size=-8192; PRAGMA temp_store=FILE;
 CREATE TABLE records(eid TEXT PRIMARY KEY,data TEXT,signals TEXT,gid TEXT,source TEXT,task TEXT,category TEXT,split TEXT,nchar INTEGER) WITHOUT ROWID;
 CREATE INDEX record_group ON records(gid,eid);
 CREATE TABLE windows(id INTEGER PRIMARY KEY,eid TEXT,message INTEGER,start INTEGER,end INTEGER,scored INTEGER,result TEXT);
 CREATE INDEX record_windows ON windows(eid,id);
 CREATE TABLE groups(gid TEXT PRIMARY KEY,stratum TEXT,priority TEXT,nrows INTEGER,selected INTEGER DEFAULT 0,population INTEGER,sample_size INTEGER) WITHOUT ROWID;''')
        db.execute('PRAGMA max_page_count='+str(limits['max_db_bytes']//4096));count=windows=0;peak=0
        with (temp/'detector-input.txt').open('w') as detector_in:
            for split in ('train','validation','test'):
                for path in sorted(dataset.glob(split+'-*.jsonl')):
                    with path.open('rb') as f:
                        while line:=f.readline(limits['max_record_bytes']+1):
                            if len(line)>limits['max_record_bytes']:raise ValueError('Audit row byte budget exceeded')
                            if not line.strip():continue
                            row=parse(line);count+=1
                            if count>limits['max_records']:raise ValueError('Audit record budget exceeded')
                            src=sources.get(row['source']);gid=row['validation_results']['split_group']
                            if src is None or row['source_revision']!=src.revision or row['license_record']!=digest(asdict(src)):raise ValueError('Audit provenance differs')
                            if row['split']!=split or not re.fullmatch('[a-f0-9]{64}',gid):raise ValueError('Audit split/group differs')
                            if any(not isinstance(row[k],str) or len(row[k].encode())>128 for k in ('task','content_category')):raise ValueError('Bounded audit stratum labels required')
                            if row['source']=='OpenAssistant/oasst2':
                                from slm.data.review import oasst_mapping
                                oasst_mapping(row)
                            stats=signals(row)
                            try:db.execute('INSERT INTO records VALUES(?,?,?,?,?,?,?,?,?)',(row['example_id'],canonical(row),canonical(stats),gid,row['source'],row['task'],row['content_category'],split,stats['characters']))
                            except sqlite3.IntegrityError as exc:raise ValueError('Duplicate audit identity') from exc
                            for i,message in enumerate(row['messages']):
                                text=message['content']
                                for start in range(0,len(text),window_characters):
                                    windows+=1
                                    if windows>limits['max_windows']:raise ValueError('Detector window budget exceeded; no truncation')
                                    part=text[start:start+window_characters];scored=any(c.isalpha() for c in part)
                                    db.execute('INSERT INTO windows VALUES(?,?,?,?,?,?,NULL)',(windows,row['example_id'],i,start,start+len(part),int(scored)))
                                    if scored:detector_in.write(part.replace('\r',' ').replace('\n',' ')+'\n')
                            if count%256==0:db.commit()
                            peak=max(peak,db.execute('PRAGMA page_count').fetchone()[0]*4096)
        if not count:raise ValueError('Nonempty audit population required')
        db.commit();unchanged();predict(binary,model,temp/'detector-input.txt',temp/'predictions.txt',limits);unchanged()
        with (temp/'predictions.txt').open() as predictions:
            for id, in db.execute('SELECT id FROM windows WHERE scored=1 ORDER BY id'):
                line=predictions.readline(513)
                if len(line)>512 or not line:raise ValueError('Detector prediction coverage differs')
                db.execute('UPDATE windows SET result=? WHERE id=?',(canonical(top_scores(line)),id))
            if predictions.read(1):raise ValueError('Extra detector predictions')
        for group in db.execute('SELECT gid,min(source),max(source),min(task),max(task),min(category),max(category),min(split),max(split),max(nchar),count(*) FROM records GROUP BY gid ORDER BY gid'):
            gid,s0,s1,t0,t1,c0,c1,p0,p1,length,n=group
            if p0!=p1:raise ValueError('Related records cross partitions')
            bucket='short_0_255' if length<256 else 'medium_256_2047' if length<2048 else 'long_2048_plus'
            stratum=canonical([['single',s0] if s0==s1 else ['mixed'],['single',t0] if t0==t1 else ['mixed'],['single',c0] if c0==c1 else ['mixed'],p0,bucket])
            db.execute('INSERT INTO groups(gid,stratum,priority,nrows) VALUES(?,?,?,?)',(gid,stratum,digest([seed,gid]),n))
        if db.execute('SELECT count(DISTINCT stratum) FROM groups').fetchone()[0]>limits['max_strata']:raise ValueError('Audit stratum budget exceeded')
        strata=[]
        for stratum,n in db.execute('SELECT stratum,count(*) FROM groups GROUP BY stratum ORDER BY stratum'):
            k=min(n,groups_per_stratum);strata.append(dict(stratum=parse(stratum),groups=n,sampled_groups=k,inclusion_probability=k/n))
            db.execute('UPDATE groups SET population=?,sample_size=? WHERE stratum=?',(n,k,stratum))
            db.execute('UPDATE groups SET selected=1 WHERE gid IN (SELECT gid FROM groups WHERE stratum=? ORDER BY priority,gid LIMIT ?)',(stratum,k))
        sampled=db.execute('SELECT coalesce(sum(nrows),0) FROM groups WHERE selected=1').fetchone()[0]
        if sampled>limits['max_sample_records']:raise ValueError('Whole-group sample exceeds record budget; no partial family output')
        labels=Counter();attention=Counter();privacy=Counter();sample_count=0;source_attention={k:Counter() for k in sources}
        with (temp/'signals.jsonl').open('w') as signal_out,(temp/'sample.jsonl').open('w') as sample_out:
            for eid,data,stats,gid,selected,n,k,stratum in db.execute('SELECT r.eid,r.data,r.signals,r.gid,g.selected,g.population,g.sample_size,g.stratum FROM records r JOIN groups g ON g.gid=r.gid ORDER BY r.eid'):
                row=parse(data);stats=parse(stats);language=[]
                for id,message,start,end,scored,result in db.execute('SELECT id,message,start,end,scored,result FROM windows WHERE eid=? ORDER BY id',(eid,)):
                    scores=parse(result) if scored else None
                    language.append(dict(message=message,start=start,end=end,top_scores=scores,status='scored' if scores else 'no_prediction' if scored else 'no_alphabetic_content'))
                    if scores:labels[scores[0]['language']]+=1
                stats['language_windows']=language;stats['language_assessment']='unverified'
                flags=[]
                if stats['privacy_findings']:flags.append('privacy_candidate')
                if stats['structural_or_cleaner_attention']:flags.append('structural_or_cleaner_attention')
                if any(w['top_scores'] and w['top_scores'][0]['language']!='en' for w in language):flags.append('non_english_top_window')
                if not language or any(w['status']!='scored' for w in language):flags.append('unscored_window')
                if any(w['top_scores'] is not None and len(w['top_scores'])<2 for w in language):flags.append('incomplete_top_k')
                stats['attention']=flags;attention.update(flags);source_attention[row['source']].update(flags);privacy.update({p:v['count'] for p,v in stats['privacy_findings'].items()})
                item=dict(example_id=eid,record_sha256=digest(row),split_group=gid,signals=stats,training_eligible=False)
                signal_out.write(canonical(item)+'\n')
                if selected:
                    sample_count+=1
                    sample_out.write(canonical(dict(record=row,record_sha256=digest(row),signals=stats,
                        selection=dict(unit='split_group',seed=seed,stratum=parse(stratum),population_groups=n,sampled_groups=k,inclusion_probability=k/n,whole_group=True),
                        judgments=dict(english=None,privacy=None,quality=None,content_category=None),approved=None))+'\n')
        db.commit();peak=max(peak,db.execute('PRAGMA page_count').fetchone()[0]*4096)
        source_summary={}
        for source,total,groups in db.execute('SELECT source,count(*),count(DISTINCT gid) FROM records GROUP BY source'):
            selected_rows=db.execute('SELECT count(*) FROM records r JOIN groups g ON g.gid=r.gid WHERE r.source=? AND g.selected=1',(source,)).fetchone()[0]
            source_summary[source]=dict(records=total,groups=groups,sampled_records=selected_rows,attention_records=dict(source_attention[source]))
        report=dict(release='sample_only',kind='non-admitting-quality-audit-v1',records=count,groups=db.execute('SELECT count(*) FROM groups').fetchone()[0],
                    windows=windows,sources=source_summary,top_language_window_counts=dict(labels),attention_records=dict(attention),privacy_candidate_occurrences=dict(privacy),
                    sampled_records=sample_count,sampled_groups=db.execute('SELECT count(*) FROM groups WHERE selected=1').fetchone()[0],strata=strata,
                    sampling='Seeded bottom-k split groups per group-level stratum; full selected groups, clustered rows, conditional on this frozen input only.',
                    seed=seed,groups_per_stratum=groups_per_stratum,window_characters=window_characters,limits=limits,peak_database_allocated_bytes=peak,
                    training_eligible=False,source_rights_approved=False,human_approvals=0,
                    scope='Signals and sampling only. No calibrated language/PII/content/quality acceptance; no corpus admission or upstream representativeness claim.')
        db.close();db=None
        for name in ('work.sqlite','detector-input.txt','predictions.txt','detector.stderr'):(temp/name).unlink()
        (temp/'report.json').write_text(canonical(report)+'\n')
        (temp/'detector.json').write_text(canonical(model_spec)+'\n');shutil.copyfile(dataset/'sources.json',temp/'sources.json')
        unchanged();manifest=dict(version=1,release='sample_only',kind=report['kind'],parent_dataset_manifest_sha256=sha(dataset/'manifest.json'),
                                 detector_descriptor_sha256=sha(descriptor),implementation_sha256=sha(__file__),files={p.name:sha(p) for p in sorted(temp.iterdir())})
        (temp/'manifest.json').write_text(canonical(manifest)+'\n');verify(temp);os.rename(temp,output);return report
    except BaseException:
        if db is not None:db.close()
        shutil.rmtree(temp,ignore_errors=True);raise


def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--spec',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    spec=metadata(a.spec);base=Path(a.spec).resolve().parent
    for name in ('dataset','descriptor'):spec[name]=str(base/spec[name])
    print(json.dumps(audit(output=a.output,**spec),sort_keys=True))


if __name__=='__main__':main()

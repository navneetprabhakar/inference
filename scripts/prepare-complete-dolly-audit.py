#!/usr/bin/env python3
"""Complete a small pinned instruction-source audit, preserving all prior holdouts."""
# Creator: Navneet Prabhakar
import argparse
from collections import Counter,defaultdict
import json
from pathlib import Path
import resource
import shutil
import sqlite3
import time
from slm.data.adapters import rows
from slm.data.build import read_source,verify
from slm.data.curation import clean
from slm.data.schema import digest
from slm.data.staging import stage,canonical,metadata
from slm.data.quality_audit import audit,LIMITS
from slm.data.tokenized import sha,stamp
from slm.data.review import training_examples

DOLLY='databricks/databricks-dolly-15k'


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--acquired',required=True);p.add_argument('--detector',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    acquired=Path(a.acquired).resolve();old=Path('data/official-split-audit-v1/curated').resolve();verify(old)
    source=read_source(acquired/'source.json');receipt=metadata(acquired/'acquisition.json');raw=acquired/'rows.jsonl'
    if source.source_id!=DOLLY or source.revision!='bdd27f4d94b9c1f951818a7da7fd7aeea5dbff1a' or receipt['published_sha256']!=sha(raw):raise ValueError('Expected verified pinned complete Dolly source')
    if shutil.disk_usage(acquired).free<3*1024**3:raise ValueError('At least 3 GiB free scratch disk required')
    root=Path(a.output);root.mkdir(parents=True,exist_ok=False);before=stamp(raw);packet=Path('data/official-split-audit-v1/pending-review.json');packet_sha=sha(packet)
    index=sqlite3.connect(root/'raw-index.sqlite');index.executescript('PRAGMA cache_size=-8192; CREATE TABLE raw(eid TEXT PRIMARY KEY,data TEXT,category TEXT,occurrences INTEGER,first_row INTEGER) WITHOUT ROWID;')
    input_rows=0;category_raw=Counter();max_raw_bytes=0
    try:
        with raw.open('rb') as f:
            while line:=f.readline(1024*1024+1):
                if len(line)>1024*1024:raise ValueError('Source row budget exceeded')
                if not line.strip():continue
                item=json.loads(line);input_rows+=1
                if input_rows>20000:raise ValueError('Small-source row budget exceeded')
                if set(item)!={'instruction','context','response','category'} or any(not isinstance(v,str) for v in item.values()) or not item['category'] or len(item['category'])>128:raise ValueError('Complete source row schema differs')
                max_raw_bytes=max(max_raw_bytes,len(line));eid=DOLLY+':'+digest(item);data=canonical(item);category_raw[item['category']]+=1
                previous=index.execute('SELECT data FROM raw WHERE eid=?',(eid,)).fetchone()
                if previous and previous[0]!=data:raise ValueError('Raw identity collision')
                index.execute('INSERT INTO raw VALUES(?,?,?,1,?) ON CONFLICT(eid) DO UPDATE SET occurrences=occurrences+1',(eid,data,item['category'],input_rows-1))
                if input_rows%256==0:index.commit()
        index.commit();unique_rows=index.execute('SELECT count(*) FROM raw').fetchone()[0]
        if input_rows!=15011:raise ValueError('Pinned source record count differs')
        inputs=root/'inputs';inputs.mkdir();unique=inputs/'dolly-unique-raw.jsonl';rejected=Counter();rejected_ids=[]
        with unique.open('w') as out:
            for eid,data in index.execute('SELECT eid,data FROM raw ORDER BY eid'):
                out.write(data+'\n')
                try:clean(rows(source,[json.loads(data)],'dolly','train')[0])
                except ValueError as exc:rejected[str(exc)]+=1;rejected_ids.append(dict(example_id=eid,reason=str(exc)))
        specs=[dict(path=str(unique.resolve()),sha256=sha(unique),source_record=str(acquired/'source.json'),adapter='dolly',official_split='train')]
        by_source=defaultdict(list);old_records={}
        for path in sorted(old.glob('*.jsonl')):
            for line in path.open():
                row=json.loads(line);old_records[row['example_id']]=row
                if row['source']==DOLLY:
                    if index.execute('SELECT 1 FROM raw WHERE eid=?',(row['example_id'],)).fetchone() is None:raise ValueError('Prior Dolly identity absent from complete source')
                else:by_source[row['source']].append(row)
        descriptors={read_source(p).source_id:p.resolve() for p in Path('data/audit-v1').glob('*/source/source.json')}
        for n,(name,records) in enumerate(sorted(by_source.items())):
            path=inputs/f'prior-canonical-{n}.jsonl';path.write_text(''.join(canonical(r)+'\n' for r in records))
            specs.append(dict(path=str(path.resolve()),sha256=sha(path),source_record=str(descriptors[name]),adapter='canonical'))
        limits=dict(max_input_bytes=64*1024*1024,max_records=20000,max_record_bytes=1024*1024,max_shingles=100000,max_pair_checks=2000000,max_db_bytes=1024*1024*1024)
        spec=dict(inputs=specs,limits=limits,frozen_dataset=str(old));(root/'staging-spec.json').write_text(canonical(spec)+'\n')
        start=time.monotonic();staging=stage(specs,root/'staged',limits=limits,frozen_dataset=old);stage_seconds=time.monotonic()-start
        retained_categories=Counter();present=set();old_heldout={k:r for k,r in old_records.items() if r['split']!='train'}
        for path in (root/'staged').glob('*.jsonl'):
            for line in path.open():
                row=json.loads(line);present.add(row['example_id'])
                if row['example_id'] in old_heldout:
                    prior=old_heldout[row['example_id']]
                    if row['messages']!=prior['messages'] or row['official_split']!=prior['official_split'] or row['split']=='train':raise ValueError('Prior held-out content or partition changed')
                if row['source']==DOLLY:
                    category=index.execute('SELECT category FROM raw WHERE eid=?',(row['example_id'],)).fetchone()
                    if category is None:raise ValueError('Retained Dolly lineage absent from pinned raw source')
                    retained_categories[category[0]]+=1
        if not set(old_heldout)<=present:raise ValueError('Prior held-out identity lost')
        qspec=dict(dataset=str((root/'staged').resolve()),descriptor=str(Path(a.detector).resolve()),limits=LIMITS,
                   seed='complete-small-source-audit-20261019-v1',groups_per_stratum=10,window_characters=2048)
        (root/'quality-spec.json').write_text(canonical(qspec)+'\n');start=time.monotonic();quality=audit(output=root/'quality',**qspec);quality_seconds=time.monotonic()-start
        sampled_categories=Counter()
        for line in (root/'quality/sample.jsonl').open():
            row=json.loads(line)['record']
            if row['source']==DOLLY:sampled_categories[index.execute('SELECT category FROM raw WHERE eid=?',(row['example_id'],)).fetchone()[0]]+=1
        try:list(training_examples(root/'staged'))
        except ValueError as exc:refusal=str(exc)
        else:raise AssertionError('Unreviewed source accepted as training release')
        if stamp(raw)!=before or sha(packet)!=packet_sha:raise ValueError('Original source or pending review packet changed')
        result=dict(scope='Complete pinned small source, combined with prior other-source records and frozen holdouts; sample-only, no corpus approval.',
                    acquisition=receipt,raw_records=input_rows,unique_raw_objects=unique_rows,exact_raw_duplicate_occurrences=input_rows-unique_rows,
                    max_raw_row_bytes=max_raw_bytes,raw_categories=dict(category_raw),retained_dolly_categories=dict(retained_categories),sampled_dolly_categories=dict(sampled_categories),
                    raw_cleaner_rejections=dict(rejected),raw_cleaner_rejected_identities=rejected_ids,staging=staging,quality=quality,
                    staging_seconds=stage_seconds,quality_seconds=quality_seconds,prior_heldout_records_preserved=len(old_heldout),prior_dolly_ids_covered=200,
                    original_review_packet_unchanged_sha256=packet_sha,training_refusal=refusal,process_peak_rss_platform_units=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                    rss_unit='bytes on macOS; KiB on Linux',staged_manifest_sha256=sha(root/'staged/manifest.json'),quality_manifest_sha256=sha(root/'quality/manifest.json'),
                    actual_source_or_row_approvals=0,neural_updates=0,teacher_launches=0,platform_teacher_api_calls=0,cloud_jobs=0,implementation_sha256=sha(__file__))
        (root/'preparation.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
        print(json.dumps({k:result[k] for k in ('raw_records','unique_raw_objects','exact_raw_duplicate_occurrences','staging_seconds','quality_seconds','prior_heldout_records_preserved','actual_source_or_row_approvals')}))
    finally:index.close()


if __name__=='__main__':main()

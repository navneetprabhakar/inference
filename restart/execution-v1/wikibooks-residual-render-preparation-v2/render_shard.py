"""One fixed canonical ordinal shard; preparation only until parent launches."""
import argparse,json,os,sqlite3
from pathlib import Path
import reader_core as rc
import profile as effective_profile
from shared_clock import shared_clock

CANONICAL_SHA='7ff5023543d3f69ce1963ee0b0f7e15fc60eaad6e28896aa7556251dd379a6bd'
CANONICAL=Path(__file__).resolve().parents[1]/'m2-intake/wikibooks-canonical-candidates-v1/canonical.sqlite3'
RANGES={i:None for i in range(1,9)}
BATCH_RECORDS=100
BATCH_BYTES=2_000_000

def open_output(path):
    os.environ['SQLITE_TMPDIR']=str(path.parent)
    d=sqlite3.connect(path);d.execute('pragma journal_mode=DELETE');d.execute('pragma synchronous=FULL');d.execute('pragma cache_size=-4096');d.execute('pragma temp_store=FILE');d.execute('pragma max_page_count='+str(rc.CAPS['output_bytes']//4096))
    d.execute('create table rendered (source_ordinal integer primary key,page_id integer unique,revision_id integer,family text,data text)')
    d.execute('create table blocks (source_ordinal integer,ordinal integer,kind text,hash text,characters integer,start integer,end integer,primary key(source_ordinal,ordinal))');d.commit();return d

def load_candidates(path,shard,expected_sha,job):
    if shard not in RANGES:raise ValueError('unknown_fixed_shard')
    if rc.file_sha(path)!=expected_sha:raise ValueError('canonical_manifest_hash_mismatch')
    lo,hi=min(job['ordinals']),job['end_source_ordinal'];d=sqlite3.connect('file:'+str(path.resolve())+'?mode=ro',uri=True)
    candidates={o:json.loads(s) for o,s in d.execute('select source_ordinal,data from candidates where source_ordinal between ? and ? order by source_ordinal',(lo,hi))};d.close();targets=set(job['ordinals']);candidates={o:r for o,r in candidates.items() if o in targets}
    if set(candidates)!=set(job['ordinals']):raise ValueError('residual_targets_missing_in_effective_canonical')
    for r in job['rows']:
        if candidates[r['source_ordinal']]['record_sha256']!=r['record_sha256']:raise ValueError('residual_record_hash_mismatch')
    return candidates

def render(archive,output,shard,start,canonical=CANONICAL,expected_canonical=CANONICAL_SHA,production=True):
    limits=rc.CAPS;guards=rc.Guards(output,start);db=None
    profile=effective_profile.load();job=profile['jobs_loaded'][shard-1];canonical=profile['canonical_path'];expected_canonical=profile['canonical_sha256']
    stats={'timings':{'extraction_total_seconds':0.0,'SQLite_insert_seconds':0.0,'source_iteration_and_guard_seconds':0.0,'SQLite_commit_seconds':0.0},'slowest_records':[],'members':[],'actual_decoded_bytes':0,'tar_end_blocks_verified':False,'gzip_eof_crc_verified':False,'encountered_source_records':0,'render_attempts':0,'committed_rendered':0}
    rc.terminal_write(output/'worker-result.json',{'status':'RUNNING_NOT_COMPLETE'},limits['output_bytes'])
    try:
        if production:rc.check_pins();rc.check_processed_reservation(output,limits['output_bytes'])
        guards.check()
        if rc.file_sha(archive)!=rc.ARCHIVE_SHA256:raise ValueError('archive_hash_mismatch')
        expected=load_candidates(canonical,shard,expected_canonical,job);lo,hi=min(job['ordinals']),job['end_source_ordinal']
        baseline_path=Path(__file__).with_name('baseline-v3-holds.json')
        if rc.file_sha(baseline_path)!=rc.core.BASELINE_HOLDS_SHA256:raise ValueError('prior_holds_hash_mismatch')
        baseline={(r['page_id'],r['revision_id'],r['html_sha256']):r['holds'] for r in json.loads(baseline_path.read_text())['records']}
        db=open_output(output/'rendered.sqlite3');batch=0;batch_bytes=0
        stream=rc.tar_records(archive,guards,stats);iteration_end=shared_clock()
        for ordinal,loc in enumerate(stream,1):
            stats['timings']['source_iteration_and_guard_seconds']+=shared_clock()-iteration_end
            guards.check();stats['encountered_source_records']=ordinal
            if ordinal in expected:
                candidate=expected[ordinal]
                if loc['raw'] is None or loc['record_sha256']!=candidate['record_sha256'] or loc['line']!=candidate['line'] or loc['member_ordinal']!=candidate['member_ordinal']:raise ValueError('source_occurrence_manifest_mismatch')
                raw=json.loads(loc['raw']);extract_start=shared_clock();c=rc.core.extract_record(raw);extract_elapsed=shared_clock()-extract_start
                stats['timings']['extraction_total_seconds']+=extract_elapsed
                stats['slowest_records'].append({'source_ordinal':ordinal,'extraction_seconds':extract_elapsed,'record_bytes':loc['record_bytes'],'page_id':c['page_id']});stats['slowest_records']=sorted(stats['slowest_records'],key=lambda r:(-r['extraction_seconds'],r['source_ordinal']))[:16]
                if (c['page_id'],c['revision_id'],c['title'],c['url'],c['html_sha256'],raw['license'])!=(candidate['page_id'],candidate['revision_id'],candidate['title'],candidate['url'],candidate['html_sha256'],candidate['license_original_metadata']):raise ValueError('canonical_identity_changed')
                if c['wikitext_sha256']!=candidate['wikitext_sha256']:raise ValueError('canonical_wikitext_hash_changed')
                row=rc.compact(raw,c,loc,baseline);row['family_id']=candidate['family_id'];row['canonical_source_ordinal']=ordinal;row['canonical_manifest_sha256']=expected_canonical;row['text']=c['text'];row['training_admitted']=False;row['cross_shard_overlap_status']='pending_joint_global_family_block_finalization'
                payload=json.dumps(row,sort_keys=True,ensure_ascii=False);encoded=len(payload.encode());guards.check(8*encoded+len(c['blocks'])*512+65536)
                insert_start=shared_clock();db.execute('insert into rendered values (?,?,?,?,?)',(ordinal,c['page_id'],c['revision_id'],candidate['family_id'],payload));offset=0
                for i,b in enumerate(c['blocks']):
                    end=offset+len(b['text']);db.execute('insert into blocks values (?,?,?,?,?,?,?)',(ordinal,i,b['kind'],b['sha256'],len(b['text']),offset,end));offset=end+2
                stats['timings']['SQLite_insert_seconds']+=shared_clock()-insert_start
                stats['render_attempts']+=1;batch+=1;batch_bytes+=encoded
                if batch>=BATCH_RECORDS or batch_bytes>=BATCH_BYTES:
                    commit_start=shared_clock();db.commit();stats['timings']['SQLite_commit_seconds']+=shared_clock()-commit_start;guards.check();stats['committed_rendered']+=batch;batch=0;batch_bytes=0
                del raw,c,row
            if ordinal==hi and shard!=8:
                stream.close();break
            if ordinal>hi:raise ValueError('source_records_exceed_frozen_range')
            iteration_end=shared_clock()
        db.commit();stats['committed_rendered']+=batch;guards.check()
        if stats['encountered_source_records']!=hi:raise ValueError('incomplete_source_ordinal_range')
        if shard==8 and not (stats['tar_end_blocks_verified'] and stats['gzip_eof_crc_verified']):raise ValueError('last_shard_full_archive_EOF_not_verified')
        actual={r[0] for r in db.execute('select source_ordinal from rendered')}
        if actual!=set(expected):raise ValueError('missing_or_extra_canonical_candidates')
        if db.execute('pragma integrity_check').fetchone()[0]!='ok':raise ValueError('SQLite_integrity_failure')
        db.close();db=None;guards.check()
        result={'status':'COMPLETE_CANONICAL_RENDER_SHARD_NO_ADMISSION','shard':shard,'fixed_source_ordinal_range':[lo,hi],'expected_candidates':len(expected),'stats':stats,'canonical_manifest_sha256':expected_canonical,'archive_sha256':rc.ARCHIVE_SHA256,'inventory_sha256':rc.file_sha(output/'rendered.sqlite3'),'elapsed_seconds':shared_clock()-start,'limits':limits,'batch_records':BATCH_RECORDS,'batch_payload_bytes':BATCH_BYTES,'full_texts_stored':True,'original_HTML_or_wikitext_rewritten':False,'joint_family_overlap_finalization':'not_performed_across_shards_yet','new_admitted_documents':0,'new_admitted_tokens':0}
        return rc.terminal_write(output/'worker-result.json',result,limits['output_bytes'])
    except Exception as exc:
        if db is not None:
            try:db.rollback();stats['committed_rendered']=db.execute('select count(*) from rendered').fetchone()[0];db.close()
            except Exception:pass
        result={'status':'PARTIAL_CANONICAL_RENDER_SHARD_NO_ADMISSION','shard':shard,'reason':str(exc)[:2000],'stats':stats,'elapsed_seconds':shared_clock()-start,'limits':limits,'new_admitted_documents':0,'new_admitted_tokens':0}
        rc.terminal_write(output/'worker-result.json',result,limits['output_bytes']);raise

def main():
    p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--shard',type=int,choices=RANGES,required=True);p.add_argument('--supervisor-pid',type=int,required=True);p.add_argument('--start-monotonic',type=float,required=True);p.add_argument('--code-pins-sha256',required=True);a=p.parse_args();os.environ['WIKIBOOKS_CODE_PINS_SHA256']=a.code_pins_sha256;rc.check_pins();rc.validate_supervisor_start(a.supervisor_pid,a.start_monotonic);render(a.archive,a.output,a.shard,a.start_monotonic)
if __name__=='__main__':main()

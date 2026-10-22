import hashlib,io,json,sqlite3,tarfile,tempfile,time,sys
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote
import render_shard as rs
import reader_core as rc
import supervisor,aggregate

HERE=Path(__file__).resolve().parent
def fixture(page):
    title='Fixture Book/Chapter '+str(page)
    return {'name':title,'identifier':page,'url':'https://en.wikibooks.org/wiki/'+quote(title.replace(' ','_'),safe='/'),'namespace':{'identifier':0},'is_part_of':{'identifier':'enwikibooks'},'version':{'identifier':page+100},'license':[{'identifier':'CC-BY-SA-4.0','url':'https://creativecommons.org/licenses/by-sa/4.0/'}],'article_body':{'html':'<nav class="navbox"><span class="toc">Remove</span></nav><p>'+('Onl<span>in</span>e is a useful source of information. '*8)+'</p><pre><span>let</span> x = 1;\nprint(x)</pre>','wikitext':'Fixture source'}}
def refuse(f):
    try:f()
    except Exception:return
    raise AssertionError('expected refusal')
def main():
    checks=[]
    assert rs.RANGES=={1:(1,22488),2:(22489,44976),3:(44977,67464),4:(67465,89951)}
    covered=[n for lo,hi in rs.RANGES.values() for n in range(lo,hi+1)];assert covered==list(range(1,89952));checks.append('four_fixed_ranges_cover89951_once')
    with tempfile.TemporaryDirectory(dir=HERE) as td:
        p=Path(td);records=[fixture(i) for i in [1,2,3]];payloads=[(json.dumps(r)+'\n').encode() for r in records];archive=p/'fixture.tar.gz'
        with tarfile.open(archive,'w:gz',format=tarfile.USTAR_FORMAT) as t:
            b=b''.join(payloads);m=tarfile.TarInfo('fixture.ndjson');m.size=len(b);t.addfile(m,io.BytesIO(b))
        sourcehash=rc.file_sha(archive);manifest=p/'canonical.sqlite3';d=sqlite3.connect(manifest);d.execute('create table candidates(source_ordinal integer primary key,data text)')
        for n,r in enumerate(records,1):
            c=rc.core.extract_record(r);candidate={'source_ordinal':n,'page_id':r['identifier'],'revision_id':r['version']['identifier'],'title':r['name'],'url':r['url'],'html_sha256':c['html_sha256'],'wikitext_sha256':c['wikitext_sha256'],'family_id':'canonical:joined-family','license_original_metadata':r['license'],'record_sha256':rc.digest(payloads[n-1]),'member_ordinal':1,'line':n}
            d.execute('insert into candidates values (?,?)',(n,json.dumps(candidate)))
        d.commit();d.close();mh=rc.file_sha(manifest)
        with patch.object(rc,'ARCHIVE_SHA256',sourcehash),patch.object(rs,'RANGES',{1:(1,3),4:(1,3)}):
            out=p/'render';out.mkdir();result=rs.render(archive,out,1,rc.shared_clock(),manifest,mh,production=False)
            assert result['status']=='COMPLETE_CANONICAL_RENDER_SHARD_NO_ADMISSION' and result['stats']['committed_rendered']==3;checks.append('bounded_synthetic_shard_renders_exact_candidate_set')
            db=sqlite3.connect(out/'rendered.sqlite3');rows=[json.loads(x) for (x,) in db.execute('select data from rendered')]
            assert all(x['family_id']=='canonical:joined-family' for x in rows);checks.append('canonical_connected_family_preserved')
            assert all('Online' in x['text'] and 'Onl in e' not in x['text'] and 'let x = 1;\nprint(x)' in x['text'] for x in rows);checks.append('fixed_inline_code_renderer_and_nested_cleanup')
            for n,text in db.execute('select source_ordinal,json_extract(data,"$.text") from rendered'):
                for start,end,h in db.execute('select start,end,hash from blocks where source_ordinal=?',(n,)):
                    assert rc.digest(text[start:end].encode())==h
            checks.append('stored_block_offsets_reconstruct_exact_text_hashes')
            assert all(not x['training_admitted'] and x['cross_shard_overlap_status'].startswith('pending') for x in rows);checks.append('no_admission_or_cross_shard_overlap_claim')
            assert not result['stats']['gzip_eof_crc_verified'];checks.append('early_shard_prefix_not_claimed_full_archive_EOF')
            db.close()
            last=p/'last';last.mkdir();r4=rs.render(archive,last,4,rc.shared_clock(),manifest,mh,production=False)
            assert r4['stats']['gzip_eof_crc_verified'] and r4['stats']['tar_end_blocks_verified'];checks.append('last_shard_requires_full_verified_EOF')
            refuse(lambda:rs.load_candidates(manifest,1,'0'*64));checks.append('canonical_artifact_hash_mismatch_refused')
        ledger=p/'aggregate';ledger.mkdir()
        with patch('aggregate.rc.output_size',return_value=0),patch('aggregate.shutil.disk_usage',return_value=type('Disk',(),{'free':100_000_000_000})()):
            for shard in range(1,5):aggregate.reserve(shard,ledger/('shard-'+str(shard)),rc.shared_clock(),root=ledger)
            state=json.loads((ledger/'aggregate-ledger.json').read_text());assert sum(x['reserved_seconds'] for x in state['attempts'].values())==3600;checks.append('four_writeahead_reservations_total3600seconds')
            refuse(lambda:aggregate.reserve(1,ledger/'shard-1',rc.shared_clock(),root=ledger));checks.append('no_retry_of_reserved_shard')
            aggregate.finish(1,1,'SYNTHETIC_COMPLETE',root=ledger);state=json.loads((ledger/'aggregate-ledger.json').read_text());assert state['attempts']['1']['reserved_seconds']==900;checks.append('completed_attempt_not_refunded_for_extra_retry')
    result={'status':'PASS_OFFLINE_SHARD_AND_LEDGER_CHECKS_NO_REAL_SHARD_RUN','checks':checks,'check_count':len(checks),'new_admitted_documents':0,'new_admitted_tokens':0};(HERE/'offline-check-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()

"""Bounded synthetic tar/JATS-free Wikibooks fixture checks; no real run."""
import gzip
import hashlib
import io
import json
import sqlite3
import tarfile
import tempfile
import time
from pathlib import Path
from urllib.parse import quote
from unittest.mock import patch

import inventory as inv
import supervisor

HERE=Path(__file__).resolve().parent

def fixture(page=1,title=None,html=None):
    title=title or 'Synthetic Book/Chapter '+str(page)
    return {'name':title,'identifier':page,'url':'https://en.wikibooks.org/wiki/'+quote(title.replace(' ','_'),safe='/'),
            'namespace':{'identifier':0},'is_part_of':{'identifier':'enwikibooks'},'in_language':{'identifier':'en'},
            'version':{'identifier':page+100},'date_modified':'2025-03-01T00:00:00Z',
            'license':[{'identifier':'CC-BY-SA-4.0','url':'https://creativecommons.org/licenses/by-sa/4.0/'}],
            'article_body':{'html':html or '<p>'+('A complete synthetic explanatory paragraph. '*8)+'</p>','wikitext':'Fixture source wikitext'}}

def archive(path,records,member='fixture.ndjson',mutate=None):
    payload=b''.join((json.dumps(x)+'\n').encode() if isinstance(x,dict) else x for x in records)
    with tarfile.open(path,'w:gz',format=tarfile.USTAR_FORMAT) as t:
        m=tarfile.TarInfo(member);m.size=len(payload);t.addfile(m,io.BytesIO(payload))
    return path

def limits(**kw):
    d=dict(inv.CAPS);d.update({'decoded_bytes':2_000_000,'output_bytes':8_000_000,'seconds':15,'records':100,'parsed_record_bytes':4096,'oversize_chunk_bytes':256});d.update(kw);return d

def fail(f):
    try:f()
    except Exception:return
    raise AssertionError('expected failure')

def build(path,out,lim=None):
    out.mkdir();return inv.build(path,out,inv.file_sha(path),time.monotonic(),limits() if lim is None else lim,reserve=0,enforce_pins=False)

def main():
    cases=[]
    with tempfile.TemporaryDirectory(dir=HERE) as td:
        p=Path(td)
        a=archive(p/'complete.tar.gz',[fixture(),fixture(2)])
        out=p/'complete';r=build(a,out)
        assert r['status']=='COMPLETE_SOURCE_INVENTORY_NO_ADMISSION' and r['stats']['encountered_records']==2 and r['stats']['gzip_eof_crc_verified'] and r['stats']['tar_end_blocks_verified']
        cases.append('complete_tar_EOF_and_gzip_CRC_required')
        db=sqlite3.connect(out/'inventory.sqlite3');rows=[json.loads(x) for (x,) in db.execute('select data from records order by ordinal')]
        assert all(x['wikitext_present'] and x['wikitext_sha256']==inv.digest(b'Fixture source wikitext') and x['page_id'] and x['revision_id'] and x['license_original_metadata'] and x['record_sha256'] and x['html_sha256'] for x in rows)
        assert all('original_html' not in x and 'text' not in x for x in rows)
        assert {x['family_id'] for x in rows}.__len__()==1
        cases.append('compact_exact_identity_wikitext_license_and_family_without_fulltext_rewrite')
        finals=[json.loads(x) for (x,) in db.execute('select holds from final_holds')]
        assert sum('substantive_block_duplicates_canonical_chapter' in x for x in finals)==1
        db.close();cases.append('final_whole_book_block_overlap_computed')
        large=(json.dumps({'not_parsed':'x'*20000})+'\n').encode()
        a2=archive(p/'oversize.tar.gz',[fixture(),large,fixture(2)])
        r=build(a2,p/'oversize')
        assert r['stats']['encountered_records']==3 and r['stats']['oversize_records']==1
        db=sqlite3.connect(p/'oversize/inventory.sqlite3');h=json.loads(db.execute('select data from records where page_id is null').fetchone()[0]);db.close()
        assert h['record_sha256']==inv.digest(large) and h['record_bytes']==len(large) and h['record_complete'] and h['license_original_metadata'] is None
        cases.append('oversize_whole_record_hash_no_parsing_or_invented_identity')
        fail(lambda:build(a2,p/'count-stop',limits(records=2)))
        partial=json.loads((p/'count-stop/worker-result.json').read_text());assert partial['status']=='PARTIAL_INVENTORY_NO_ADMISSION' and partial['stats']['encountered_records']==2
        cases.append('encountered_cap_includes_oversize_and_forbids_complete_claim')
        fail(lambda:build(a2,p/'decoded-stop',limits(decoded_bytes=10000)))
        partial=json.loads((p/'decoded-stop/worker-result.json').read_text());assert partial['stats']['actual_decoded_bytes']<=10000 and partial['incomplete_record_diagnostic']['record_complete'] is False
        cases.append('actual_decoded_cap_midrecord_retains_partial_hash')
        corrupt=p/'badCRC.tar.gz';b=bytearray(a.read_bytes());b[-8]^=1;corrupt.write_bytes(b)
        fail(lambda:build(corrupt,p/'badCRC'))
        assert json.loads((p/'badCRC/worker-result.json').read_text())['status']=='PARTIAL_INVENTORY_NO_ADMISSION'
        cases.append('CRC_failure_never_complete')
        noend=p/'noend.tar.gz';payload=(json.dumps(fixture())+'\n').encode();m=tarfile.TarInfo('f.ndjson');m.size=len(payload)
        with gzip.open(noend,'wb') as f:f.write(m.tobuf()+payload+b'\0'*((-len(payload))%512))
        fail(lambda:build(noend,p/'noend'))
        cases.append('missing_tar_end_blocks_refused')
        trailing=p/'trailing.tar.gz'
        with gzip.open(trailing,'wb') as f:f.write(gzip.decompress(a.read_bytes())+b'not tar padding')
        fail(lambda:build(trailing,p/'trailing'))
        cases.append('nonzero_trailing_tar_data_refused')
        fail(lambda:build(archive(p/'unsafe.tar.gz',[fixture()],member='../escape.ndjson'),p/'unsafe'))
        assert not (p.parent/'escape.ndjson').exists();cases.append('tar_paths_never_extracted_and_unsafe_path_refused')
        sym=p/'symlink.tar.gz'
        with tarfile.open(sym,'w:gz') as t:
            m=tarfile.TarInfo('symlink');m.type=tarfile.SYMTYPE;m.linkname='/tmp/unused';t.addfile(m)
        fail(lambda:build(sym,p/'symlink'));cases.append('tar_link_member_refused')
        fail(lambda:build(archive(p/'unknown.tar.gz',[{'unknown':'schema'}]),p/'unknown'))
        cases.append('unknown_record_schema_terminal_diagnostic')
        fail(lambda:build(archive(p/'duplicate.tar.gz',[fixture(),fixture()]),p/'duplicate'))
        cases.append('duplicate_page_identity_terminal')
        fail(lambda:build(a,p/'output-stop',limits(output_bytes=100000)))
        assert inv.output_size(p/'output-stop')<=100000
        cases.append('output_guard_stops_before_oversize_write')
        expired=p/'expired';expired.mkdir()
        fail(lambda:inv.build(a,expired,inv.file_sha(a),time.monotonic()-20,limits(),reserve=0,enforce_pins=False))
        cases.append('worker_elapsed_guard_partial')
        wrong=p/'wronghash';wrong.mkdir();fail(lambda:inv.build(a,wrong,'0'*64,time.monotonic(),limits(),reserve=0,enforce_pins=False))
        cases.append('exact_archive_hash_required')
        notice=inv.notice_flags('Beginning. Copyright 2020 Contributors. Redistribution and use are permitted. End.')
        assert notice and all(inv.digest(x['exact_span'].encode())==x['span_sha256'] for x in notice)
        cases.append('thirdparty_notice_exact_span_hash_review_flag')
        sourcefixture=fixture();sourcefixture['article_body']['wikitext']='<!-- Copyright 1995 Motorola Inc. All Rights Reserved. -->'
        c=inv.core.extract_record(sourcefixture);loc={'member':'s.ndjson','member_ordinal':1,'line':1,'record_bytes':1,'record_sha256':'0'*64,'raw':b'x'}
        source_row=inv.compact(sourcefixture,c,loc,{})
        assert any(x['source_kind']=='original_wikitext' and 'Motorola' in x['exact_span'] for x in source_row['potential_third_party_notice_flags'])
        cases.append('original_wikitext_notices_survive_rendered_comment_removal')
        slots=p/'slots';slots.mkdir();cap=8_000_000
        inv.terminal_write(slots/'worker-result.json',{'status':'RUNNING'},cap)
        size=inv.output_size(slots);(slots/'filler').write_bytes(b'x'*(cap-size))
        inv.terminal_write(slots/'worker-result.json',{'status':'PARTIAL_INVENTORY_NO_ADMISSION','reason':'output cap'},cap)
        assert inv.output_size(slots)==cap
        cases.append('preallocated_terminal_slot_writes_at_full_output_cap_without_growth')
        inv.terminal_write(slots/'worker-result.json',{'status':'COMPLETE_SOURCE_INVENTORY_NO_ADMISSION','large':'x'*1_000_000},cap)
        assert json.loads((slots/'worker-result.json').read_text())['status']=='PARTIAL_INVENTORY_NO_ADMISSION'
        cases.append('oversized_terminal_metadata_falls_back_to_bounded_partial_receipt')
        many=p/'members.tar.gz'
        with tarfile.open(many,'w:gz') as t:
            for n in range(65):t.addfile(tarfile.TarInfo(str(n)+'.ndjson'))
        fail(lambda:build(many,p/'members'))
        assert len(json.loads((p/'members/worker-result.json').read_text())['stats']['members'])==64
        cases.append('64_member_cap_bounds_terminal_metadata')
        with patch('inventory.output_size',return_value=63_500_000_000):
            fail(lambda:inv.check_processed_reservation(inv.INTAKE_ROOT/'future-test',1_000_000_000))
        cases.append('combined_intake64GB_reservation_ceiling_before_launch')
        zero=p/'disk';zero.mkdir()
        with patch('inventory.shutil.disk_usage',return_value=type('Disk',(),{'free':0})()):fail(lambda:inv.Guards(zero,time.monotonic(),limits(),reserve=1).check())
        cases.append('weights_and_free_floor_guard')
    rss,pids=supervisor.tree_rss_from_ps('10 1 100\n11 10 200\n12 11 300\n99 1 500',10)
    assert rss==600*1024 and pids==[10,11,12];cases.append('RSS_counts_all_descendants_excludes_other_processes')
    assert supervisor.decision(900,0,0,inv.FREE_RESERVE)=='elapsed_time_cap';cases.append('supervisor900s_hard_stop')
    assert supervisor.decision(0,1_000_000_001,0,inv.FREE_RESERVE)=='process_tree_RSS_hard_cap';cases.append('supervisor_observed1GB_RSS_stop')
    assert supervisor.decision(0,600_000_000,0,inv.FREE_RESERVE) is None;cases.append('512MB_target_is_not_silently_claimed_hard_cap')
    assert supervisor.decision(0,0,1_000_000_001,inv.FREE_RESERVE)=='aggregate_output_byte_cap';cases.append('supervisor_aggregate_output_guard')
    assert supervisor.decision(0,0,0,inv.FREE_RESERVE-1)=='disk_weights_free_floor';cases.append('supervisor_free_floor_plus_weights')
    captured=HERE.parent/'m2-intake/wikibooks-discovery-v3/source-records.jsonl'
    if captured.exists():
        motorola=next(json.loads(l) for l in captured.read_text().splitlines() if json.loads(l)['identifier']==251051)
        c=inv.core.extract_record(motorola);row=inv.compact(motorola,c,loc,{})
        assert any('Motorola' in n['exact_span'] for n in row['potential_third_party_notice_flags'])
        cases.append('known_captured_page251051_Motorola_notice_flagged_no_rights_decision')
    result={'status':'PASS_SYNTHETIC_ONLY_NO_REAL_ARCHIVE_RUN','cases':cases,'case_count':len(cases),'new_admitted_documents':0,'new_admitted_tokens':0}
    (HERE/'synthetic-check-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':main()

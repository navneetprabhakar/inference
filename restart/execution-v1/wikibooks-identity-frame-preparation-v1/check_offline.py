import gzip,hashlib,io,json,sqlite3,tarfile,tempfile
from pathlib import Path
from unittest.mock import patch
import inventory as inv
import supervisor
from shared_clock import shared_clock
HERE=Path(__file__).resolve().parent
cases=[]
def fail(f):
    try:f()
    except Exception:return
    raise AssertionError('expected failure')
def fixture(n=1):return {'identifier':n,'name':'Book/Chapter','url':'https://en.wikibooks.org/wiki/Book/Chapter','version':{'identifier':n+100},'license':[{'url':'https://creativecommons.org/licenses/by-sa/4.0/'}],'article_body':{'html':'<p>π Original</p>','wikitext':'Original π'}}
def arc(p,rows,name='a.ndjson'):
    payload=b''.join((json.dumps(r,ensure_ascii=False)+'\n').encode() if isinstance(r,dict) else r for r in rows)
    with tarfile.open(p,'w:gz',format=tarfile.USTAR_FORMAT) as t:
        m=tarfile.TarInfo(name);m.size=len(payload);t.addfile(m,io.BytesIO(payload))
    return p
def limits(**kw):
    d=dict(inv.CAPS);d.update(decoded_bytes=2_000_000,output_bytes=8_000_000,seconds=15,records=100,parsed_record_bytes=4096,oversize_chunk_bytes=256);d.update(kw);return d
def build(a,o,lim=None,start=None,sha=None):
    o.mkdir();return inv.build(a,o,sha or inv.file_sha(a),shared_clock() if start is None else start,lim or limits(),reserve=0,enforce_pins=False)
with tempfile.TemporaryDirectory(dir=HERE) as td:
    p=Path(td);rows=[fixture(),b'\n',b'{invalid}\n',{'identifier':False},fixture()];a=arc(p/'a.gz',rows);r=build(a,p/'out')
    assert r['status']=='COMPLETE_IDENTITY_FRAME_NO_ADMISSION' and r['stats']['encountered_records']==4 and r['stats']['identity_held_records']==2
    db=sqlite3.connect(p/'out/inventory.sqlite3');saved=[json.loads(x[0]) for x in db.execute('select data from records order by ordinal')];db.close()
    assert saved[0]['record_sha256']==inv.digest((json.dumps(rows[0],ensure_ascii=False)+'\n').encode())
    assert saved[0]['html_sha256']==inv.digest(rows[0]['article_body']['html'].encode()) and saved[0]['wikitext_sha256']==inv.digest('Original π'.encode())
    assert saved[1]['line']==3 and saved[1]['member_uncompressed_byte_offset']==saved[0]['record_bytes']+1
    assert saved[3]['page_id']==saved[0]['page_id'] and all('eligibility' not in x and 'text' not in x for x in saved)
    cases+=['complete_gzip_tar_EOF_integrity_counts','exact_UTF8_line_HTML_wikitext_hashes','blank_lines_locations_and_offsets','invalid_JSON_and_schema_retained_as_held','duplicate_identity_preserved_without_dedup_claim','no_DOM_text_eligibility_or_quality_fields']
    invalid=fixture();invalid['article_body']['html']='\ud800';invalid['identifier']=2**64
    row=inv.identity(json.dumps(invalid).encode(),{'raw':b'x'},'0'*64)
    assert 'invalid_Unicode_html' in row['identity_holds'] and 'invalid_page_id' in row['identity_holds']
    cases.append('surrogate_body_and_out_of_SQLite_integer_identity_held')
    big=b'{"big":"'+b'x'*20000+b'"}\n';b=arc(p/'big.gz',[fixture(),big,fixture(2)]);r=build(b,p/'big')
    db=sqlite3.connect(p/'big/inventory.sqlite3');row=json.loads(db.execute('select data from records where ordinal=2').fetchone()[0]);db.close()
    assert row['record_sha256']==inv.digest(big) and row['record_bytes']==len(big) and row['record_complete'] and row['identity_holds']==['oversize_record_not_parsed'] and row['html_sha256'] is None
    cases.append('oversize_whole_line_hash_and_explicit_hold')
    for name,lim in [('count',limits(records=2)),('decoded',limits(decoded_bytes=10000)),('output',limits(output_bytes=100000)),('members',limits(tar_members=0))]:
        fail(lambda:build(b,p/name,lim));assert 'COMPLETE' not in json.loads((p/name/'worker-result.json').read_text())['status'];cases.append(name+'_cap_no_complete_claim')
    assert inv.output_size(p/'output')<=100000
    partial=json.loads((p/'decoded/worker-result.json').read_text());assert partial['incomplete_record_diagnostic']['record_complete'] is False;cases.append('midoversize_partial_hash_diagnostic')
    bad=p/'CRC.gz';content=bytearray(a.read_bytes());content[-8]^=1;bad.write_bytes(content);fail(lambda:build(bad,p/'CRC'));cases.append('gzip_CRC_failure_refused')
    raw=gzip.decompress(a.read_bytes());trailing=p/'tail.gz';trailing.write_bytes(gzip.compress(raw+b'bad'));fail(lambda:build(trailing,p/'tail'));cases.append('nonzero_tar_tail_refused')
    missing=p/'missing.gz';m=tarfile.TarInfo('a.ndjson');m.size=2;missing.write_bytes(gzip.compress(m.tobuf()+b'{}'+b'\0'*510));fail(lambda:build(missing,p/'missing'));cases.append('missing_tar_EOF_refused')
    fail(lambda:build(arc(p/'unsafe.gz',[fixture()],'../x.ndjson'),p/'unsafe'));cases.append('unsafe_path_refused_no_extraction')
    fail(lambda:build(a,p/'clock',start=shared_clock()-20));cases.append('shared_worker_clock_deadline')
    fail(lambda:build(a,p/'sha',sha='0'*64));cases.append('archive_pin_required')
    with patch('inventory.shutil.disk_usage',return_value=type('D',(),{'free':0})()):fail(lambda:inv.Guards(p,shared_clock(),reserve=1).check())
    cases.append('weights_disk_free_floor')
    with patch('inventory.output_size',return_value=63_500_000_000):fail(lambda:inv.check_processed_reservation(inv.INTAKE_ROOT/'future-test',1_000_000_000))
    cases.append('aggregate_processed64GB_preflight')
    assert supervisor.decision(900,0,0,inv.FREE_RESERVE)=='elapsed_time_cap';assert supervisor.decision(0,1_000_000_001,0,inv.FREE_RESERVE)=='process_tree_RSS_hard_cap'
    cases+=['supervisor900second_bound','supervisor1GB_observed_tree_RSS_bound']
    rss,pids=supervisor.tree_rss_from_ps('1 0 10\n2 1 20\n3 2 30\n4 0 99',1);assert rss==60*1024 and pids==[1,2,3];cases.append('RSS_descendants_only')
result={'status':'PASS_OFFLINE_FIXTURES_ONLY','case_count':len(cases),'cases':cases,'new_admitted_documents':0,'new_admitted_tokens':0}
(HERE/'offline-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

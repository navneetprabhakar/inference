import gzip,io,json,pathlib,tarfile,tempfile
import inventory as a
checks=[]
assert a.CAPS['parsed_record_bytes']==32000000 and a.CAPS['decoded_bytes']==6000000000 and a.CAPS['output_bytes']==10000000 and a.CAPS['seconds']==180 and a.CAPS['rss_hard_bytes']==1000000000;checks.append('exact_parent_caps_32MB_6GB_10MB_180s_1GB_RSS')
assert (a.HERE/'supervisor.py').read_bytes()==(a.UP/'supervisor.py').read_bytes();checks.append('external_supervisor_exact_frozen_copy')
assert a.FREE_RESERVE==20*1024**3+32000000000;checks.append('weights16GB_scratch16GB_and20GiB_floor')
row={'identifier':1,'name':'Test','url':'https://en.wikibooks.org/wiki/Test','version':{'identifier':2},'license':[{'identifier':'CC-BY-SA-4.0','url':'https://creativecommons.org/licenses/by-sa/4.0/'}],'article_body':{'html':'x'*4500000,'wikitext':'source'}};raw=(json.dumps(row)+'\n').encode()
with tempfile.TemporaryDirectory() as td:
 d=pathlib.Path(td);archive=d/'fixture.tar.gz';data=raw+b'{"identifier":3}\n';stream=io.BytesIO()
 with tarfile.open(fileobj=stream,mode='w') as t:
  m=tarfile.TarInfo('fixture.ndjson');m.size=len(data);t.addfile(m,io.BytesIO(data))
 archive.write_bytes(gzip.compress(stream.getvalue()))
 def run(cap):
  stats={'members':[]};g=a.u.Guards(d,a.shared_clock(),dict(a.CAPS,parsed_record_bytes=cap),0);records=list(a.u.tar_records(archive,g,stats));return records,stats
 old,os=run(4194304);new,ns=run(32000000);assert old[0]['raw'] is None and new[0]['raw']==raw;a.reconcile(new[0],old[0]);assert ns['gzip_eof_crc_verified'] and ns['tar_end_blocks_verified'];checks.append('same_reader_oversize_to_metadata_exact_line_binding_and_full_EOF')
 assert old[1]['record_sha256']==new[1]['record_sha256'];checks.append('nonselected_record_hashloc_unchanged')
 changed=dict(old[0],record_sha256='0'*64)
 try:a.reconcile(new[0],changed)
 except AssertionError:pass
 else:raise AssertionError('hash substitution accepted')
 checks.append('original_record_hash_substitution_refused')
 r=a.u.identity(new[0]['raw'],new[0],a.ARCHIVE_SHA256);assert r['page_id']==1 and r['revision_id']==2 and r['html_UTF8_bytes']==4500000 and r['wikitext_UTF8_bytes']==6;checks.append('metadata_only_identifiers_and_body_hashes')
 corrupted=bytearray(archive.read_bytes());corrupted[-8]^=1;archive.write_bytes(corrupted)
 try:run(32000000)
 except gzip.BadGzipFile:pass
 else:raise AssertionError('CRC corruption accepted')
 checks.append('gzip_CRC_corruption_refused')
original={'source_ordinal':1,'revision_id':2,'identity_holds':[],'license_original_metadata':[{'identifier':'CC-BY-SA-4.0','url':'https://creativecommons.org/licenses/by-sa/4.0/'}],'url':'https://en.wikibooks.org/wiki/Test','title':'Test','html_sha256':'a','wikitext_sha256':'b'}
new=dict(original,source_ordinal=2,revision_id=3,identity_holds=['original_oversize_record_render_hold']);chosen,_=a.c.resolve_group([original,new]);assert chosen is None;checks.append('supplement_higher_revision_shadow_blocks_older_canonical_fallback')
chosen,_=a.c.resolve_group([original,dict(new,revision_id=1)]);assert chosen==1;checks.append('supplement_older_revision_preserves_existing_maximum')
result={'status':'PASS_OFFLINE_ONLY','checks':checks,'case_count':len(checks),'source_archive_opened':False,'network_requests':0};(a.HERE/'offline-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

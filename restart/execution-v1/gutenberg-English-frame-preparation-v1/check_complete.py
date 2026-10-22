"""Synthetic tiny archive only; no real catalog pass."""
import bz2,gzip,io,json,tempfile,tarfile
from pathlib import Path
import complete_frame as f
c=f.compact;checks=[]
def test(name,ok):assert ok,name;checks.append(name)
def refused(fn):
 try:fn()
 except Exception:return True
 return False
with tempfile.TemporaryDirectory() as temporary:
 root=Path(temporary);source=root/'source';source.mkdir();raw=(c.ROOT/'gutenberg-discovery-pilot-v2/metadata.raw').read_bytes();buffer=io.BytesIO()
 with tarfile.open(fileobj=buffer,mode='w',format=tarfile.USTAR_FORMAT) as tar:
  for name in ['pg1342.rdf','copy/pg1342.rdf']:
   member=tarfile.TarInfo(name);member.size=len(raw);tar.addfile(member,io.BytesIO(raw))
 archive=root/'synthetic.bz2';archive.write_bytes(bz2.compress(buffer.getvalue()));stats=c.inventory(archive,c.Guards(source,c.clock()))
 worker={'status':'COMPLETE_LOSSLESS_COMPACT_CATALOG_METADATA_ONLY_NO_ADMISSION','stats':stats,'database_shards':stats['database_shards'],'source_archive_SHA256':c.ARCHIVE_SHA};(source/'worker-result.json').write_text(json.dumps(worker));wh=c.file_sha(source/'worker-result.json');supervisor={'status':'COMPLETE','worker_result_SHA256':wh};(source/'supervisor-result.json').write_text(json.dumps(supervisor));sh=c.file_sha(source/'supervisor-result.json')
 dest=root/'derived';result=f.run(source,dest,wh,sh)
 with gzip.open(dest/'metadata-frame.jsonl.gz','rt') as stream:rows=[json.loads(line) for line in stream]
 test('full_EOF_source_fixture_rows_exactly_once',len(rows)==2 and result['rows']==2)
 test('duplicate_family_all_held',len({r['provisional_family_component'] for r in rows})==1 and all(r['discovery_status']=='HELD_METADATA_REPAIR_OR_REVIEW' for r in rows))
 test('all_source_roles_formats_and_rights_preserved',all(r['contributors_and_all_roles'] and r['all_formats'] and r['rights_fields'] for r in rows))
 test('no_body_rights_or_training_claim',result['usable_documents']==0 and result['usable_tokens']==0 and result['original_English_and_edition_rights_unverified_rows']==2)
 test('mismatched_source_receipt_refused_before_output',refused(lambda:f.run(source,root/'bad','0'*64,sh)) and not (root/'bad').exists())
 p=source/'catalog-0.sqlite3';p.write_bytes(p.read_bytes()+b'change');test('source_shard_hash_tamper_refused',refused(lambda:f.run(source,root/'bad2',wh,sh)) and not (root/'bad2').exists())
Path(__file__).with_name('complete-function-checks.json').write_text(json.dumps({'status':'PASS','cases':checks,'count':len(checks),'actual_catalog_executed':False,'network_requests':0},indent=2)+'\n');print(len(checks),'PASS')

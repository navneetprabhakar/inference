"""Offline function only. Parent must pin code/policy and dispatch under external supervisor.
Never call on running/partial source. No network, source mutation, book fetch or admission.
"""
import collections,gzip,hashlib,json,os,sys,time
from pathlib import Path
import derive
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'gutenberg-catalog-compact-preparation-v2'))
import compact
MAX_ROWS=150000;OUTPUT_CAP=600000000;SECONDS=540
class Capped:
 def __init__(self,file,guard):self.file=file;self.guard=guard
 def write(self,b):self.guard(len(b));return self.file.write(b)
 def flush(self):return self.file.flush()
 def tell(self):return self.file.tell()
 def close(self):return self.file.close()
def run(source,dest,expected_worker_SHA256,expected_supervisor_SHA256):
 source=Path(source).resolve();dest=Path(dest).resolve();start=time.monotonic()
 assert not dest.exists(),'Fresh isolated output only'
 worker_path=source/'worker-result.json';supervisor_path=source/'supervisor-result.json'
 assert compact.file_sha(worker_path)==expected_worker_SHA256 and compact.file_sha(supervisor_path)==expected_supervisor_SHA256
 worker=json.loads(worker_path.read_text());supervisor=json.loads(supervisor_path.read_text());stats=worker['stats']
 assert worker['status']=='COMPLETE_LOSSLESS_COMPACT_CATALOG_METADATA_ONLY_NO_ADMISSION' and supervisor['status']=='COMPLETE'
 assert supervisor['worker_result_SHA256']==expected_worker_SHA256 and worker['source_archive_SHA256']==compact.ARCHIVE_SHA
 assert all(stats[k] for k in ['full_tar_EOF_verified','full_bzip2_CRC_EOF_verified','archive_identity_inventory_complete']) and stats['SQLite_integrity']=='ok'
 assert stats['members']<=MAX_ROWS and stats['parsed_ebook_records']<=MAX_ROWS
 shards=worker['database_shards'];assert [r['file'] for r in shards]==['catalog-0.sqlite3','catalog-1.sqlite3']
 for r in shards:
  p=source/r['file'];assert not p.is_symlink() and p.stat().st_size==r['bytes'] and compact.file_sha(p)==r['SHA256']
 dest.mkdir();used=0
 def guard(add=0):
  nonlocal used
  assert 0<=time.monotonic()-start<SECONDS,'540second worker deadline'
  assert sum(p.stat().st_size for p in dest.iterdir() if p.is_file())+add<=OUTPUT_CAP-1048576,'Output prewrite cap+terminal headroom'
  assert compact.shutil.disk_usage(dest).free>=sum(json.loads((compact.EXEC/'disk-budget.json').read_text())[k] for k in ['weights_checkpoints_reserved_bytes','scratch_cap_bytes','free_disk_floor_bytes'])+add+32000000,'Protected disk reserves'
 def stream():
  db=compact.readonly_union([source/r['file'] for r in shards])
  db.set_progress_handler(lambda:1 if time.monotonic()-start>=SECONDS else 0,10000)
  try:
   for values in db.execute('select r.shard,r.member,r.raw_bytes,r.raw_hash,r.packed_hash,r.codec,r.payload,m.raw_bytes,m.raw_hash,m.packed_hash,m.codec,m.payload from records r join members m on r.shard=m.shard and r.member=m.ordinal order by r.member,r.shard'):
    guard();slot,ordinal=values[:2];row=compact.unpack(*values[2:7]);member=compact.unpack(*values[7:]);binding={'archive_SHA256':compact.ARCHIVE_SHA,'source_worker_SHA256':expected_worker_SHA256,'source_shard':shards[slot],'ordinal':ordinal,'member_identity':member,'record_raw_JSON_SHA256':values[3]}
    yield derive.classify(row,binding)
  finally:db.close()
 try:
  minimal=[]
  for row in stream():
   minimal.append({k:row[k] for k in ['ebook_ID','provisional_family','explicit_related_ebook_IDs']});assert len(minimal)<=MAX_ROWS
  assert len(minimal)==stats['parsed_ebook_records']
  derive.families(minimal);components={r['ebook_ID']:r['provisional_family_component'] for r in minimal};del minimal
  statuses=collections.Counter();holds=collections.Counter();exclusions=collections.Counter();genres=collections.Counter();eras=collections.Counter();roles=collections.Counter();missing=collections.Counter();n=0;historical_narrative=0
  with (dest/'metadata-frame.jsonl.gz').open('xb') as raw:
   with gzip.GzipFile(fileobj=Capped(raw,guard),mode='wb',filename='',mtime=0) as out:
    for row in stream():
     row['provisional_family_component']=components[row['ebook_ID']];row['priority_key']=derive.sha((derive.POLICY_VERSION+'\n'+row['provisional_family_component']).encode());data=derive.canonical(row)+b'\n';out.write(data)
     n+=1;statuses[row['discovery_status']]+=1;holds.update(row['metadata_hold_reasons']);exclusions.update(row['exclusion_reasons']);genres.update(row['observed_genre_strata']);eras[row['creator_era_stratum']]+=1;roles.update(a['role_qualified_name'] for a in row['contributors_and_all_roles'])
     missing.update({k:int(v) for k,v in row['missingness'].items()});historical_narrative+=int(row['discovery_status']=='ELIGIBLE_FOR_BODY_REVIEW_METADATA_ONLY' and 'narrative' in row['observed_genre_strata'] and row['creator_era_stratum']=='creator_deaths_all_exact_le1900_priority_only')
   raw.flush();os.fsync(raw.fileno())
  assert n==stats['parsed_ebook_records'];guard()
  result={'status':'COMPLETE_METADATA_FRAME_ONLY_NO_BODY_RIGHTS_CLEARANCE','rows':n,'status_counts':dict(statuses),'hold_counts_nonexclusive':dict(holds),'exclusion_counts_nonexclusive':dict(exclusions),'genre_counts_nonexclusive':dict(genres),'era_counts':dict(eras),'role_counts':dict(roles),'missingness_counts':dict(missing),'historical_narrative_metadata_review_rows':historical_narrative,'provisional_family_components':len(set(components.values())),'source_stats':stats,'source_worker_SHA256':expected_worker_SHA256,'source_supervisor_SHA256':expected_supervisor_SHA256,'frame_SHA256':compact.file_sha(dest/'metadata-frame.jsonl.gz'),'frame_bytes':(dest/'metadata-frame.jsonl.gz').stat().st_size,'elapsed_seconds':time.monotonic()-start,'original_English_and_edition_rights_unverified_rows':n,'usable_documents':0,'usable_tokens':0,'network_requests':0,'admitted_documents':0}
  compact.terminal_write(dest/'result.json',result,OUTPUT_CAP);return result
 except BaseException as error:
  compact.terminal_write(dest/'result.json',{'status':'TERMINAL_METADATA_FRAME_FAILED_NO_RETRY','error':str(error),'elapsed_seconds':time.monotonic()-start,'admitted_documents':0},OUTPUT_CAP);raise

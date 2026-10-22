"""Offline exact300 metadata/span inventory; no source transforms or ledger access."""
import collections,hashlib,json,os,stat
from pathlib import Path
import boundaries

def require(v,m):
 if not v:raise ValueError(m)
def identity(s):return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
def read_source(root,entry,check):
 path=Path(root)/entry['path'];require(path.is_relative_to(root),'source_relative_path')
 for p in [path,*path.parents]:
  require(not p.is_symlink(),'source_path_symlink')
  if p==Path(root):break
 s=path.stat(follow_symlinks=False);require(stat.S_ISREG(s.st_mode) and identity(s)==entry['dev_ino_size_mtime_ns_ctime_ns'] and 0<s.st_size<=2400000,'exact_frozen_source_stat')
 fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW);chunks=[];h=hashlib.sha256();n=0
 try:
  require(identity(os.fstat(fd))==identity(s),'source_FD_custody')
  while True:
   check();b=os.read(fd,min(1048576,s.st_size-n+1))
   if not b:break
   n+=len(b);require(n<=s.st_size,'source_growth');chunks.append(b);h.update(b)
  require(n==entry['bytes'] and h.hexdigest()==entry['SHA256'] and identity(os.fstat(fd))==identity(s) and identity(path.stat(follow_symlinks=False))==identity(s),'source_exact_hash_EOF_final_stat')
 finally:os.close(fd)
 return b''.join(chunks)
def preflight(profile):
 require(len(profile['records'])==len(profile['source_files'])==300 and profile['expected_plaintext_bytes']==153222386,'fixed300_source_frame')
 require(len({r['ebook_ID'] for r in profile['records']})==300,'300_unique_frozen_source_IDs')
 require(sum(e['bytes'] for e in profile['source_files'])==153222386,'fixed_raw_byte_total')
 for i,(r,e) in enumerate(zip(profile['records'],profile['source_files'])):
  require(r['ordinal']==i and e['path']==f"attempt-{i:03}/raw/pg{r['ebook_ID']}.txt" and len(e['dev_ino_size_mtime_ns_ctime_ns'])==5 and e['dev_ino_size_mtime_ns_ctime_ns'][2]==e['bytes'] and 0<e['bytes']<=2400000,'exact_ordered_source_frame')
 return True

def run(profile,out,check):
 out=Path(out);summary=collections.Counter();reasons=collections.Counter();events=0;total=0;records_sha=hashlib.sha256();written=0
 with (out/'records.jsonl').open('xb') as f:
  for plan,entry in zip(profile['records'],profile['source_files']):
   check();raw=read_source(profile['source_output'],entry,check);total+=len(raw);require(total<=160000000,'aggregate_raw_input_cap')
   x=boundaries.inspect(raw,plan['ebook_ID']);events+=len(x['structural_hints']);require(events<=50000,'aggregate_annotation_cap')
   # Current source cannot be called same catalog edition just from title/death/size.
   extent=plan['catalog_extent_bytes_not_expected_current_size'];drift=len(raw)!=extent
   record={'ordinal':plan['ordinal'],'ebook_ID':plan['ebook_ID'],'source_file':entry,'catalog_plan_preserved':plan,'catalog_current_version_equivalence':'UNVERIFIED','catalog_extent_differs':drift,'catalog_extent_difference_is_edition_drift_proof':False,'source_family_custody':'Whole frozen conservative family reserved; no preferred version selected','structural_inventory':x,'source_quality_rights_originalEnglish_family_near_protected_holds':['not_reviewed_or_cleared'],'new_admitted_documents':0}
   b=(json.dumps(record,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode();require(len(b)<=524288 and written+len(b)<=28000000,'bounded_record_and_stream_output')
   check(len(b));f.write(b);f.flush();os.fsync(f.fileno());records_sha.update(b);written+=len(b)
   summary['raw_files']+=1;summary['raw_bytes']+=len(raw);summary['raw_characters']+=x['raw_characters'];summary['raw_whitespace_words']+=x['raw_whitespace_words'];summary['catalog_extent_differences_diagnostic_only']+=drift
   summary['boundary_held_files']+=bool(x['boundary_holds']);summary['unique_unheld_PG_envelopes']+=not bool(x['boundary_holds'])
   if x['payload']:
    summary['all_discovered_payload_envelope_bytes']+=x['payload']['bytes'];summary['all_discovered_payload_envelope_characters']+=x['payload_characters'];summary['all_discovered_payload_envelope_whitespace_words']+=x['payload_whitespace_words']
   reasons.update(x['boundary_holds'])
 require(summary['raw_files']==300 and total==profile['expected_plaintext_bytes'] and len(profile['source_files'])==300,'complete_exact300_input_reconciliation')
 for e in profile['source_files']:
  check();require(identity((Path(profile['source_output'])/e['path']).stat(follow_symlinks=False))==e['dev_ino_size_mtime_ns_ctime_ns'],'all_sources_final_stat_custody')
 summary['distinct_raw_SHA256']=len({e['SHA256'] for e in profile['source_files']});summary['frozen_conservative_catalog_family_components']=len({r['family_component_ID'] for r in profile['records']})
 return {'status':'COMPLETE_EXACT300_LOSSLESS_BOUNDARY_DISCOVERY_NO_ADMISSION','summary':dict(summary),'boundary_hold_counts':dict(reasons),'records_file':'records.jsonl','records_bytes':written,'records_SHA256':records_sha.hexdigest(),'structural_hint_events':events,'raw_files_unchanged':True,'raw_partitions_inverse_exact':True,'full_original_header_footer_and_components_preserved_as_source_bound_spans':True,'payload_envelope_is_not_approved_continuous_authored_prose':True,'original_acquisition_producer_remains_failed':True,'all_version_rights_quality_leakage_language_tokenizer_gates_uncleared':True,'new_admitted_documents':0,'new_admitted_tokens':0}

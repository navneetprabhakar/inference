"""Metadata-only gate API; UNBOUND templates refuse before any file/SQL access.
A separately reviewed parent-created binding is required after actual producer
and independent verifier completion/reaping. No implicit source/DB hash replay.
"""
import hashlib,re
STATUS='PARENT_BOUND_VERIFIED_RETAINED_PREFIX_V3_FOR_POSTINVENTORY'
PROF='dd697043d80eef1e49178d76b2ad527655f6e9449815cf502eb11fe010f89d91'
PINS='db0ac3c36a72384459b15d9645f8c0494645795408a47057e4f7085b40cce9ac'
VPROF='2a212906eebd41551e6b10793d813ba07a78097df39f0a9d9a0894df499f542d'
VPINS='0ea3b73f9923e1d3f8a4a2b025adc333e0943d40e03e3018d2b49bd9f0aa7078'
def need(v,m):
 if not v:raise ValueError(m)
def validate(binding,load_verified_json,stat_identity,pid_absent):
 need(binding.get('status')==STATUS and binding.get('producer_reaped') is True and binding.get('verifier_reaped') is True and binding.get('producer_exit_code')==0 and binding.get('verifier_exit_code')==0,'actual_COMPLETE_verified_reaped_binding_required')
 # Callback validates path and SHA before parsing each small metadata object.
 pp=load_verified_json(binding['producer_profile']);need(binding['producer_profile']['SHA256']==PROF,'exact_producer_profile_digest');p=load_verified_json(binding['producer_result']);s=load_verified_json(binding['producer_supervisor']);owner=load_verified_json(binding['producer_ownership']);v=load_verified_json(binding['verifier_result']);vs=load_verified_json(binding['verifier_supervisor']);vo=load_verified_json(binding['verifier_ownership']);original=load_verified_json(binding['producer_terminal_binding'])
 need(p['status']=='COMPLETE_RETAINED_PREFIX_FRAGMENT_FRAME_NO_ADMISSION' and s['status']=='COMPLETE_RETAINED_PREFIX_FRAGMENT_NO_ADMISSION' and s['worker_exit_code']==0,'producer_complete_scope')
 need(p['profile_SHA256']==PROF and p['codepins_SHA256']==PINS and p['whole_publisher_archive_verified'] is False and s['result_SHA256']==binding['producer_result']['SHA256'],'producer_exact_frozen_policy')
 need(v['status']=='COMPLETE_INDEPENDENT_STORED_FRAGMENT_METADATA_VERIFICATION_NO_ADMISSION' and vs['status']=='COMPLETE_STORED_METADATA_VERIFICATION' and vs['worker_exit_code']==0 and vs['result_SHA256']==binding['verifier_result']['SHA256'] and v['publisher_whole_archive_verified'] is False,'independent_complete_verification')
 need(v['producer_binding_SHA256']==binding['producer_terminal_binding']['SHA256'] and original['status']=='PARENT_REVIEWED_COMPLETE_TERMINAL_METADATA_BINDING' and original['producer_reaped'] is True and original['producer_exec_exit_code']==0 and original['producer_owned_PIDs_absent'] is True,'exact_independent_producer_binding_chain')
 need(p['counts']['pages']==v['pages']==15840694 and p['counts']['groups']==v['groups']==158433 and p['counts']['revision_occurrences']==v['revisions']['observed']==v['revisions']['expected'] and p['counts']['ns0_nonredirect']==v['ns0_nonredirect_pending_only'],'verified_frame_denominators')
 need(owner['profile_SHA256']==PROF and owner['codepins_SHA256']==PINS and vo['profile_SHA256']==VPROF and vo['codepins_SHA256']==VPINS,'producer_verifier_owned_exact_policy')
 for who in [owner,vo]:
  for k in ['worker_PID','supervisor_PID']:need(type(who[k]) is int and who[k]>1 and pid_absent(who[k]),'owned_process_absence')
 for name,key in [('frame.sqlite','frame'),('original-header.xml','header'),('codec.json','codec'),('group-receipts.jsonl','group_receipts')]:
  b=binding[key];need(re.fullmatch('[0-9a-f]{64}',b['SHA256']) is not None and b['stat']==original['files'][name]['stat'] and b['SHA256']==original['files'][name]['SHA256']==v['output_hashes'][name] and stat_identity(b['path'])==b['stat'],'frozen_verified_artifact_stat_hash_binding')
 need(binding['index']==pp['index'] and {k:binding['prefix'][k] for k in ['path','bytes','SHA256','stat']}=={k:pp['source'][k] for k in ['path','bytes','SHA256','stat']} and pp['selection']['compressed_prefix_end_exclusive']==17988779480,'exact_frozen_index_prefix_context')
 need(stat_identity(binding['index']['path'])==binding['index']['stat'] and stat_identity(binding['prefix']['path'])==binding['prefix']['stat'],'inherited_index_prefix_stat_only')
 need(binding['frame']['stat'][2]<=2000000000 and binding['header']['stat'][2]<=65536 and binding['codec']['stat'][2]<=1000000 and binding['group_receipts']['stat'][2]<=256000000,'source_metadata_bounds')
 return {'status':'VERIFIED_TERMINAL_CONTEXT_NO_SOURCE_BODY_OPENED','binding':binding,'expected':{'pages':15840694,'groups':158433},'inherited_global_native_page_ID_uniqueness':True,'source_producer_result':p,'independent_verifier_result':v,'whole_publisher_archive_verified':False}

def load_metadata(entry):
 """Default small hash-bound metadata loader for a future frozen wrapper."""
 import os,stat,json
 from pathlib import Path
 path=Path(entry['path']);need(not path.is_symlink() and str(path.resolve())==str(path),'metadata_path_no_symlink');fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
 try:
  s=os.fstat(fd);ident=lambda x:[x.st_dev,x.st_ino,x.st_size,x.st_mtime_ns,x.st_ctime_ns];need(stat.S_ISREG(s.st_mode) and s.st_size<=8000000,'small_metadata_regular_bound');b=os.read(fd,s.st_size+1);need(len(b)==s.st_size and ident(os.fstat(fd))==ident(s) and ident(path.stat(follow_symlinks=False))==ident(s) and hashlib.sha256(b).hexdigest()==entry['SHA256'],'metadata_exact_SHA_FD_custody');return json.loads(b)
 finally:os.close(fd)

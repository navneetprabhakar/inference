"""Receipt/stat custody only. No archive body reads, sockets or decompression."""
import pathlib,json,hashlib,os,stat
HERE=pathlib.Path(__file__).resolve().parent;BASE=HERE.parent;ROOT=BASE/'m2-intake'
SOURCE=ROOT/'enwiki-native-full-XML-20260801-v2/archive.partial';V2=SOURCE.parent;V3=ROOT/'enwiki-native-full-XML-20260801-v3'
OLDPREP=BASE/'enwiki-native-full-acquisition-preparation-v2';COPYPREP=BASE/'enwiki-native-full-acquisition-preparation-v3'
URL='https://dumps.wikimedia.org/enwiki/20260801/enwiki-20260801-pages-articles-multistream.xml.bz2';PUBLISHER_BYTES=26668484995;PREFIX_BYTES=16927669898
PREFIX_HASHES={'bytes':PREFIX_BYTES,'MD5':'a3faaeff7f3696eb71f0fcea55c9c415','SHA1':'655c90c458e48d1899c8f040b38ae6d3bdb7862a','SHA256':'1fe6566d328a9c8b790df414dc89a4922a8fa6f209b5f7e0120ad7ce6951400e'}
ETAG='"6a738a16-63590c983"';FIELDS=['st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns']
def chain_paths():
 return {V2/n for n in ['worker-result.json','supervisor-result.json','response-headers.json','preflight.json','ownership.json']}|{V3/'prefix-copy.json',V3/'ownership.json'}|{p/n for p in [OLDPREP,COPYPREP] for n in ['archive.py','profile.json','code-pins.json']}
def small_bytes(path,cap=1048576):
 p=pathlib.Path(path)
 if p.is_symlink() or not p.is_file() or p.stat().st_size>cap:raise ValueError('bounded_regular_metadata_required')
 with p.open('rb') as f:b=f.read(cap+1)
 if len(b)>cap:raise ValueError('metadata_grew_over_cap')
 return b
def digest(p):return hashlib.sha256(small_bytes(p)).hexdigest()
def load(p):return json.loads(small_bytes(p))
def no_old_owners(ownership):
 for k in ['supervisor_pid','worker_pid']:
  pid=ownership.get(k)
  if type(pid)!=int or pid<=1:raise ValueError('valid_old_owned_PID_required')
  try:os.kill(pid,0)
  except ProcessLookupError:continue
  except PermissionError:raise ValueError('old_owned_PID_absence_unproven')
  raise ValueError('old_owned_PID_present_refuse_no_write_custody')
def verify(path,expected,profile):
 if path is None or expected is None:raise ValueError('SEPARATE_PARENT_REVIEWED_TERMINAL_PREFIX_BINDING_REQUIRED')
 raw=small_bytes(path,65536)
 if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('external_source_binding_digest')
 b=json.loads(raw)
 if b.get('status')!='PARENT_REVIEWED_TERMINAL_PREFIX_FRAME_PILOT_READY' or b.get('profile_SHA256')!=profile or b.get('source_path')!=str(SOURCE) or b.get('source_prefix_bytes')!=PREFIX_BYTES or b.get('source_prefix_SHA256')!=PREFIX_HASHES['SHA256'] or b.get('whole_publisher_archive_verified') is not False or b.get('additional_whole_prefix_rehash_bytes')!=0:raise ValueError('separate_terminal_prefix_policy')
 wanted={str(p) for p in chain_paths()}
 if set(b.get('chain_SHA256',{}))!=wanted:raise ValueError('exact_receipt_copycode_chain_inventory')
 for p,d in b['chain_SHA256'].items():
  if digest(p)!=d:raise ValueError('receipt_or_copycode_chain_changed')
 w=load(V2/'worker-result.json');s=load(V2/'supervisor-result.json');pre=load(V2/'preflight.json');head=load(V2/'response-headers.json');owner=load(V2/'ownership.json');cp=load(V3/'prefix-copy.json');copyowner=load(V3/'ownership.json')
 if w.get('status')!='TERMINAL_PARTIAL_XML_NO_RETRY' or w.get('partial_bytes')!=PREFIX_BYTES or w.get('complete_recorded_prefix')!=PREFIX_HASHES or w.get('prefix_hash_covers_entire_partial') is not True or w.get('published_final_exists') is not False:raise ValueError('terminal_whole_prefix_hash_evidence_required')
 if s.get('status')!='PARTIAL_XML_NO_RETRY' or s.get('worker_exit_code')!=1 or s.get('worker_receipt_SHA256')!=digest(V2/'worker-result.json') or s.get('independent_final_file_verification') is not None or s.get('owned_ledger',{}).get('state')!='failed' or s['owned_ledger']['key']!=owner['ledger_key']:raise ValueError('terminal_failed_old_acquisition_no_fullverification')
 if pre.get('URL')!=URL or pre.get('CERT_REQUIRED_hostname') is not True or pre.get('publisher_size')!=PUBLISHER_BYTES:raise ValueError('original_official_TLS_source_required')
 hraw=bytes.fromhex(head['prefix_hex'])
 if head.get('status')!=200 or head.get('effective_URL')!=URL or head.get('prefix_only') is not False or len(hraw)>65536 or len(hraw)!=head['parsed_header_bytes'] or hashlib.sha256(hraw).hexdigest()!=head['headers_SHA256']:raise ValueError('original_complete_200_header_evidence')
 headers={}
 for line in hraw.decode('latin1').splitlines():
  if ':' not in line:raise ValueError('retained_header_line')
  k,v=line.split(':',1);headers.setdefault(k.casefold(),[]).append(v.strip())
 if headers.get('content-length')!=[str(PUBLISHER_BYTES)] or headers.get('etag')!=[ETAG] or headers.get('content-encoding',[]) not in [[],['identity']] or headers.get('transfer-encoding') or headers.get('content-range'):raise ValueError('exact_source_ETag_identity_zero_origin')
 for prep,o in [(OLDPREP,owner),(COPYPREP,copyowner)]:
  registry=load(prep/'code-pins.json')
  if digest(prep/'code-pins.json')!=o['code_pins_sha256'] or digest(prep/'profile.json')!=o['profile_sha256'] or registry.get('sha256',{}).get(str(prep/'archive.py'))!=digest(prep/'archive.py'):raise ValueError('actual_owned_acquisition_copy_code_profile_pins')
 if pre.get('CA_SHA256') not in load(OLDPREP/'code-pins.json')['sha256'].values():raise ValueError('retained_TLS_CA_registry_binding')
 if cp.get('old_prefix')!={'path':str(SOURCE),'bytes':PREFIX_BYTES,'SHA256':PREFIX_HASHES['SHA256']} or cp.get('new_copy_bytes')!=PREFIX_BYTES or cp.get('new_copy_prefix_SHA256')!=PREFIX_HASHES['SHA256'] or cp.get('no_HTTP_before_verified_copy') is not True:raise ValueError('actual_v3_full_prefix_copy_reverification_required')
 expected_stat=b.get('source_stat',{})
 if set(expected_stat)!=set(FIELDS) or any(type(expected_stat[k])!=int for k in FIELDS) or [expected_stat[k] for k in FIELDS]!=cp.get('old_file_identity'):raise ValueError('exact_verified_copy_stat_custody_required')
 no_old_owners(owner)
 if SOURCE.is_symlink() or SOURCE.resolve()!=SOURCE:raise ValueError('no_symlink_source_or_parent')
 now=SOURCE.stat()
 if not stat.S_ISREG(now.st_mode) or {k:getattr(now,k) for k in FIELDS}!=expected_stat:raise ValueError('terminal_prefix_stat_changed')
 return b

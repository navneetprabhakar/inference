"""Actual source guard synthetic metadata/stat fixtures. Never retained archive IO."""
import pathlib,tempfile,json,hashlib,copy,types
from contextlib import ExitStack
from unittest.mock import patch
import source_guard as g
checks=[]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):p.write_text(json.dumps(x))
def reject(name,fn,errors=(ValueError,OSError)):
 try:fn()
 except errors:checks.append(name)
 else:raise AssertionError(name)
with tempfile.TemporaryDirectory() as td,ExitStack() as stack:
 root=pathlib.Path(td).resolve();v2=root/'v2';v3=root/'v3';old=root/'oldprep';new=root/'copyprep'
 for p in [v2,v3,old,new]:p.mkdir()
 source=v2/'archive.partial';source.write_bytes(b'SYNTHETIC prefix only');n=source.stat().st_size;hashes={'bytes':n,'MD5':hashlib.md5(source.read_bytes()).hexdigest(),'SHA1':hashlib.sha1(source.read_bytes()).hexdigest(),'SHA256':digest(source)}
 for k,v in {'SOURCE':source,'V2':v2,'V3':v3,'OLDPREP':old,'COPYPREP':new,'PREFIX_BYTES':n,'PREFIX_HASHES':hashes,'PUBLISHER_BYTES':100}.items():stack.enter_context(patch.object(g,k,v))
 stack.enter_context(patch.object(g.os,'kill',side_effect=ProcessLookupError()))
 ca='0'*64
 for p in [old,new]:
  (p/'archive.py').write_text('# synthetic code only');write(p/'profile.json',{'synthetic':True});write(p/'code-pins.json',{'sha256':{str(p/'archive.py'):digest(p/'archive.py'),'synthetic_CA':ca}})
 owner={'supervisor_pid':987654321,'worker_pid':987654322,'code_pins_sha256':digest(old/'code-pins.json'),'profile_sha256':digest(old/'profile.json'),'ledger_key':'failed-synthetic'}
 write(v2/'ownership.json',owner);write(v3/'ownership.json',{'code_pins_sha256':digest(new/'code-pins.json'),'profile_sha256':digest(new/'profile.json')})
 write(v2/'worker-result.json',{'status':'TERMINAL_PARTIAL_XML_NO_RETRY','partial_bytes':n,'complete_recorded_prefix':hashes,'prefix_hash_covers_entire_partial':True,'published_final_exists':False})
 write(v2/'supervisor-result.json',{'status':'PARTIAL_XML_NO_RETRY','worker_exit_code':1,'worker_receipt_SHA256':digest(v2/'worker-result.json'),'independent_final_file_verification':None,'owned_ledger':{'state':'failed','key':'failed-synthetic'}})
 write(v2/'preflight.json',{'URL':g.URL,'CERT_REQUIRED_hostname':True,'publisher_size':100,'CA_SHA256':ca})
 hraw=('Content-Length: 100\r\nETag: '+g.ETAG+'\r\n').encode();write(v2/'response-headers.json',{'status':200,'effective_URL':g.URL,'prefix_only':False,'parsed_header_bytes':len(hraw),'prefix_hex':hraw.hex(),'headers_SHA256':hashlib.sha256(hraw).hexdigest()})
 st=source.stat();sid={k:getattr(st,k) for k in g.FIELDS};write(v3/'prefix-copy.json',{'old_prefix':{'path':str(source),'bytes':n,'SHA256':hashes['SHA256']},'new_copy_bytes':n,'new_copy_prefix_SHA256':hashes['SHA256'],'no_HTTP_before_verified_copy':True,'old_file_identity':list(sid.values())})
 bind=root/'binding.json';base={'status':'PARENT_REVIEWED_TERMINAL_PREFIX_FRAME_PILOT_READY','profile_SHA256':'PROFILE','source_path':str(source),'source_prefix_bytes':n,'source_prefix_SHA256':hashes['SHA256'],'whole_publisher_archive_verified':False,'additional_whole_prefix_rehash_bytes':0,'source_stat':sid}
 def call(b=None):
  x=copy.deepcopy(base if b is None else b);x['chain_SHA256']={str(p):digest(p) for p in g.chain_paths()};write(bind,x);return g.verify(str(bind),digest(bind),'PROFILE')
 call();checks.append('actual_guard_complete_synthetic_terminal_prefix_code_receipt_stat_chain')
 for key,value in [('status','PENDING'),('source_path',str(v3/'assembled.partial')),('whole_publisher_archive_verified',True),('source_prefix_SHA256','f'*64),('additional_whole_prefix_rehash_bytes',n)]:
  b=copy.deepcopy(base);b[key]=value;reject('refuse_binding_'+key,lambda b=b:call(b))
 originals={p:p.read_bytes() for p in g.chain_paths()}
 for name,path,key,value in [
  ('live_worker',v2/'worker-result.json','status','TRANSFER_PREFIX_ONLY_NOT_FINAL'),
  ('uncovered_prefixhash',v2/'worker-result.json','prefix_hash_covers_entire_partial',False),
  ('unverified_TLS',v2/'preflight.json','CERT_REQUIRED_hostname',False),
  ('fullverified_claim',v2/'supervisor-result.json','independent_final_file_verification',{'SHA256':'f'*64}),
  ('wrong_copied_hash',v3/'prefix-copy.json','new_copy_prefix_SHA256','f'*64),
  ('wrong_copied_length',v3/'prefix-copy.json','new_copy_bytes',n-1),
  ('not_terminal_ledger',v2/'supervisor-result.json','owned_ledger',{'state':'pending','key':'failed-synthetic'})]:
  x=json.loads(path.read_text());x[key]=value;write(path,x);reject('refuse_'+name,call);path.write_bytes(originals[path])
 x=json.loads((v2/'response-headers.json').read_text());bad=hraw.replace(b'ETag: "',b'ETag: W/"');x.update(prefix_hex=bad.hex(),parsed_header_bytes=len(bad),headers_SHA256=hashlib.sha256(bad).hexdigest());write(v2/'response-headers.json',x);reject('weak_ETag_is_not_same_identity',call);(v2/'response-headers.json').write_bytes(originals[v2/'response-headers.json'])
 (new/'archive.py').write_text('# changed copy verifier');reject('copy_code_changed_even_when_outer_chain_repinned',call);(new/'archive.py').write_bytes(originals[new/'archive.py'])
 with patch.object(g.os,'kill',return_value=None):reject('old_owned_PID_present_refuses',call)
 b=copy.deepcopy(base);b['source_stat']['st_ino']+=1;reject('wrong_prefix_source_stat_refuses',lambda:call(b))
 # Stable metadata without sourcebody verification must never silently permit changed source.
 source.write_bytes(b'changed synthetic prefix');reject('source_mutation_refuses',call)
 reject('no_binding_no_reads',lambda:g.verify(None,None,'PROFILE'))
print(json.dumps({'status':'PASS_SYNTHETIC_BINDING_ONLY','count':len(checks),'checks':checks,'retained_source_bytes':0,'network':0,'ledger_writes':0},indent=2))

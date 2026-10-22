"""Exact20 native NDJSON source records from existing bounded gzip/tar reader."""
import argparse,hashlib,importlib.util,json,os,pathlib,platform,signal,sys,time
import supervisor_core as supervisor
HERE=pathlib.Path(__file__).resolve().parent;BASE=HERE.parent
READER=BASE/'wikibooks-identity-frame-preparation-v1/inventory.py'
IDS=[26016,71952,33975,22041,8455,39918,48092,14562,26258,60306,72203,61485,42685,72377,54034,85584,76753,40765,15744,77079]
LIMITS={'worker_seconds':110,'external_seconds':120,'output_bytes':8000000,'tree_RSS_bytes':1000000000,'decoded_bytes':6000000000,'exact_source_records':20,'selected_record_bytes':65536,'source_records':89951,'decoded_bytes_expected':5333783552,'tar_members':64,'member_name_bytes':4096}
def sha(p):
 h=hashlib.sha256()
 with pathlib.Path(p).open('rb') as f:
  for b in iter(lambda:f.read(65536),b''):h.update(b)
 return h.hexdigest()
def digest(b):return hashlib.sha256(b).hexdigest()
def runtime():return {'python':sys.version,'executable':str(pathlib.Path(sys.executable).resolve()),'platform':platform.platform()}
def load_reader():
 # Original pinned module only; no extraction_core/DOM renderer imported.
 sys.path.insert(0,str(READER.parent));spec=importlib.util.spec_from_file_location('pinned_WB_identity_reader',READER);reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader);return reader
def inventory(profile):
 paths={HERE/x for x in ['capture.py','supervisor_core.py','checks.py','profile.json','runtime.json']}
 paths|={READER,READER.with_name('shared_clock.py'),pathlib.Path(profile['archive']['path']),pathlib.Path(profile['selection_path']),pathlib.Path(profile['identity_terminal_path']),pathlib.Path(sys.executable).resolve()}
 for e in profile['selected']:paths|={pathlib.Path(e['native_metadata_path']),pathlib.Path(e['capture_receipt_path'])}
 # Pin the imported stdlib parser/compression stack and extension origins too.
 reader=load_reader()
 for mod in [argparse,hashlib,importlib.util,json,os,pathlib,platform,signal,supervisor.shutil,supervisor.subprocess,reader.gzip,reader.tarfile,reader.unicodedata,reader.gzip.zlib]:
  if getattr(mod,'__file__',None):paths.add(pathlib.Path(mod.__file__).resolve())
 return {str(p.resolve()) for p in paths}
def verify(args):
 if sha(HERE/'code-pins.json')!=args.code_pins_sha256 or sha(HERE/'profile.json')!=args.profile_sha256:raise ValueError('external_pins')
 p=json.loads((HERE/'profile.json').read_text());pins=json.loads((HERE/'code-pins.json').read_text())
 if set(pins['SHA256'])!=inventory(p) or p['limits']!=LIMITS or json.loads((HERE/'runtime.json').read_text())!=runtime():raise ValueError('inventory_limits_runtime')
 for path,h in pins['SHA256'].items():
  q=pathlib.Path(path)
  if q.is_symlink() or sha(q)!=h:raise ValueError('input_hash:'+path)
 if [e['source_ordinal'] for e in p['selected']]!=IDS or sum(e['record_bytes'] for e in p['selected'])!=253245 or max(e['record_bytes'] for e in p['selected'])!=42673:raise ValueError('frozen_exact20')
 if p['archive']['SHA256']!='361fb441fe35d13be56c4eca22a09df6868a663e5d7f3b1ed2a665e332a4d263' or pathlib.Path(p['archive']['path']).stat().st_size!=798092108:raise ValueError('exact_archive')
 return p
def bind_source(raw,loc,e):
 if raw is None or len(raw)>65536 or len(raw)!=e['record_bytes'] or digest(raw)!=e['record_sha256']:raise ValueError('selected_raw_record_binding')
 for k in ['member','member_ordinal','line','record_bytes','record_sha256']:
  if loc[k]!=e[k]:raise ValueError('selected_location:'+k)
 obj=json.loads(raw.decode('utf8'))
 if not isinstance(obj,dict) or obj.get('identifier')!=e['page_id'] or obj.get('version',{}).get('identifier')!=e['revision_id'] or obj.get('name')!=e['title'] or obj.get('url')!=e['url'] or obj.get('license')!=e['license_original_metadata']:raise ValueError('native_identity_license_metadata')
 body=obj.get('article_body');html=body.get('html') if isinstance(body,dict) else None;wikitext=body.get('wikitext') if isinstance(body,dict) else None
 if not isinstance(html,str) or digest(html.encode())!=e['html_sha256'] or not isinstance(wikitext,str) or digest(wikitext.encode())!=e['wikitext_sha256']:raise ValueError('HTML_wikitext_hash_binding')
 return {'HTML_UTF8_bytes':len(html.encode()),'HTML_SHA256':digest(html.encode()),'wikitext_UTF8_bytes':len(wikitext.encode()),'wikitext_SHA256':digest(wikitext.encode())}
def process(archive,out,start,selected,reader_limits,expected_records,expected_decoded):
 reader=load_reader();guards=reader.Guards(out,start,reader_limits,reserve=53474836480);stats={'members':[],'actual_decoded_bytes':0,'tar_end_blocks_verified':False,'gzip_eof_crc_verified':False};found={};lookup={e['source_ordinal']:e for e in selected};count=0
 for count,loc in enumerate(reader.tar_records(archive,guards,stats),1):
  guards.check()
  if count>expected_records:raise ValueError('record_count_excess')
  if count not in lookup:continue
  e=lookup[count];raw=loc['raw'];detail=bind_source(raw,loc,e);name=str(count)+'.source.json';supervisor.write(out,name,raw)
  receipt={'source_ordinal':count,'selection':e,'source_file':name,'source_record_SHA256':digest(raw),'source_record_UTF8_bytes':len(raw),'native_body':detail,'status':'WHOLE_NATIVE_JSON_CAPTURED_PENDING_ANCESTRY_ROLE_REVIEW','original_rendered_and_global_holds_preserved':True,'no_rendering_or_filtering':True,'new_admitted_documents':0}
  supervisor.write(out,str(count)+'.receipt.json',supervisor.data(receipt));found[count]=receipt
 if count!=expected_records or stats['actual_decoded_bytes']!=expected_decoded or not stats['tar_end_blocks_verified'] or not stats['gzip_eof_crc_verified'] or set(found)!=set(lookup):raise ValueError('full_EOF_count_or_selection_reconciliation')
 return stats,found
def worker(args):
 supervisor.arm(110-(time.clock_gettime(time.CLOCK_MONOTONIC)-args.start));out=pathlib.Path(args.output)
 try:
  p=verify(args)
  if str(out)!=p['output'] or os.getppid()!=args.supervisor_pid:raise ValueError('owned_output_parent')
  rl={'decoded_bytes':6000000000,'output_bytes':8000000,'seconds':110,'records':89951,'parsed_record_bytes':4194304,'oversize_chunk_bytes':65536,'tar_members':64,'member_name_bytes':4096}
  stats,found=process(pathlib.Path(p['archive']['path']),out,args.start,p['selected'],rl,89951,5333783552)
  verify(args)
  supervisor.slot(out,'result.json',{'status':'COMPLETE_EXACT20_NATIVE_SOURCE_CAPTURE','stats':stats,'source_ordinals_in_selection_order':IDS,'whole_native_source_bytes':sum(r['source_record_UTF8_bytes'] for r in found.values()),'source_records':89951,'all_inputs_rehashed_unchanged':True,'new_admitted_documents':0,'no_rendering_filtering_network_models_training':True})
 except BaseException as e:
  supervisor.slot(out,'result.json',{'status':'PARTIAL_NO_RETRY','error':type(e).__name__+':'+str(e),'new_admitted_documents':0});raise
 finally:signal.setitimer(signal.ITIMER_REAL,0)
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--code-pins-sha256',required=True);parser.add_argument('--profile-sha256',required=True);parser.add_argument('--execute',action='store_true');parser.add_argument('--worker',action='store_true');parser.add_argument('--start',type=float);parser.add_argument('--supervisor-pid',type=int);parser.add_argument('--output');a=parser.parse_args()
 if a.worker:worker(a)
 elif a.execute:
  start=time.clock_gettime(time.CLOCK_MONOTONIC);supervisor.arm(120);out=pathlib.Path(json.loads((HERE/'profile.json').read_text())['output'])
  supervisor.supervise(out,lambda start:[sys.executable,'-B',str(HERE/'capture.py'),'--worker','--code-pins-sha256',a.code_pins_sha256,'--profile-sha256',a.profile_sha256,'--start',str(start),'--supervisor-pid',str(os.getpid()),'--output',str(out)],lambda:verify(a),started=start)
 else:
  supervisor.arm(110)
  try:verify(a);print('READY_NO_ARCHIVE_CAPTURE')
  finally:signal.setitimer(signal.ITIMER_REAL,0)
if __name__=='__main__':main()

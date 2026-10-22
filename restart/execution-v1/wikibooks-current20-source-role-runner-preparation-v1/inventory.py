"""Fixed20 native source DOM roles; original extractor/renderer text stays unchanged."""
import argparse,hashlib,importlib.util,json,os,pathlib,platform,signal,sys,time
import supervisor_core as supervisor
HERE=pathlib.Path(__file__).resolve().parent;BASE=HERE.parent;ROOT=BASE/'m2-intake'
POLICY=BASE/'wikibooks-source-role-core-preparation-v2';PIPELINE=BASE/'wikibooks-sharded-render-preparation-v2'
BS4_SITE=pathlib.Path('/Users/navneetprabhakar/.local/share/uv/tools/aider-chat/lib/python3.12/site-packages')
LXML_SITE=pathlib.Path('/Users/navneetprabhakar/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages')
LIMITS={'worker_seconds':55,'external_seconds':60,'output_bytes':16000000,'tree_RSS_bytes':1000000000,'exact_sources':20,'native_record_max_bytes':65536,'rendered_text_max_bytes':2000000,'max_blocks':10000}
IDS=[26016,71952,33975,22041,8455,39918,48092,14562,26258,60306,72203,61485,42685,72377,54034,85584,76753,40765,15744,77079]
POLICY_CODEPINS_SHA256='567b8b829b195685ff580ee3e1b92a23cf5284cb1f4e0a44fd4af3f19b397ce3'
def sha(p):
 h=hashlib.sha256()
 with pathlib.Path(p).open('rb') as f:
  for b in iter(lambda:f.read(65536),b''):h.update(b)
 return h.hexdigest()
def digest(b):return hashlib.sha256(b).hexdigest()
def load(name,p):
 spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def dependencies():
 for path in [BS4_SITE,LXML_SITE,PIPELINE]:sys.path.insert(0,str(path))
 import bs4,lxml.etree,extraction_core,dom_renderer
 if pathlib.Path(bs4.__file__).resolve()!=BS4_SITE/'bs4/__init__.py' or pathlib.Path(lxml.etree.__file__).resolve()!=LXML_SITE/'lxml/etree.cpython-312-darwin.so' or pathlib.Path(extraction_core.__file__).resolve()!=PIPELINE/'extraction_core.py' or pathlib.Path(dom_renderer.__file__).resolve()!=PIPELINE/'dom_renderer.py' or bs4.__version__!='4.14.3' or tuple(lxml.etree.LXML_VERSION)!=(6,1,1,0):raise ValueError('exact_bs4_lxml_pipeline_origins_versions')
 if extraction_core.dom_renderer is not dom_renderer:raise ValueError('single_original_renderer_namespace')
 return extraction_core,dom_renderer,load('WB_policy_v2',POLICY/'role_core.py'),{'bs4_origin':str(pathlib.Path(bs4.__file__).resolve()),'bs4_version':bs4.__version__,'lxml_origin':str(pathlib.Path(lxml.etree.__file__).resolve()),'lxml_version':list(lxml.etree.LXML_VERSION)}
def runtime():
 _,_,_,deps=dependencies();return {'python':sys.version,'executable':str(pathlib.Path(sys.executable).resolve()),'platform':platform.platform(),**deps}
def expected_inventory(profile):
 policy_pins=json.loads((POLICY/'code-pins.json').read_text())['files'];paths=set(policy_pins)|{str((POLICY/'code-pins.json').resolve())}
 paths|={str((HERE/n).resolve()) for n in ['inventory.py','supervisor_core.py','checks.py','profile.json','runtime.json']}
 paths|={str((PIPELINE/'extraction_core.py').resolve()),str(pathlib.Path(sys.executable).resolve()),profile['native_capture_profile'],profile['native_capture_verification'],profile['known_hold_overlay']}
 for e in profile['selected']:
  paths|={e['native_source_path'],e['native_source_receipt_path'],e['original_text_path'],e['original_native_metadata_path'],e['original_capture_receipt_path']}
  if e.get('manual_component_sidecar'):paths.add(e['manual_component_sidecar'])
 for m in [argparse,hashlib,importlib.util,json,os,pathlib,platform,signal,supervisor.shutil,supervisor.subprocess]:
  if getattr(m,'__file__',None):paths.add(str(pathlib.Path(m.__file__).resolve()))
 return paths
def verify(args):
 if sha(HERE/'code-pins.json')!=args.code_pins_sha256 or sha(HERE/'profile.json')!=args.profile_sha256 or sha(POLICY/'code-pins.json')!=POLICY_CODEPINS_SHA256:raise ValueError('external_policy_runner_profile_pins')
 p=json.loads((HERE/'profile.json').read_text());pins=json.loads((HERE/'code-pins.json').read_text())['SHA256']
 if p['limits']!=LIMITS or [e['source_ordinal'] for e in p['selected']]!=IDS or set(pins)!=expected_inventory(p):raise ValueError('exact20_limits_input_inventory')
 for path,h in pins.items():
  q=pathlib.Path(path)
  if q.is_symlink() or not q.is_file() or sha(q)!=h:raise ValueError('frozen_input_changed:'+path)
 if runtime()!=json.loads((HERE/'runtime.json').read_text()):raise ValueError('frozen_runtime')
 return p
def blocks_for(rendered):
 cursor=0;blocks=[]
 for ordinal,b in enumerate(rendered['blocks']):
  n=len(b['text']);blocks.append({'ordinal':ordinal,'kind':b['kind'],'hash':b['sha256'],'characters':n,'start':cursor,'end':cursor+n});cursor+=n+2
 return blocks
def instrument(native,expected_text,expected_blocks,extractor,renderer,policy,approved):
 """Call original function once; inspect its exact cleaned DOM without edits."""
 original=renderer.render_blocks;observed=[]
 def wrapped(content):
  original_DOM=str(content);result=original(content)
  roles=policy.inventory(content,expected_text,expected_blocks,renderer,approved)
  if str(content)!=original_DOM:raise ValueError('role_inventory_mutated_original_cleaned_DOM')
  observed.append(roles);return result
 renderer.render_blocks=wrapped
 try:result=extractor.extract_record(native)
 finally:renderer.render_blocks=original
 if len(observed)!=1 or result['text']!=expected_text or blocks_for(result)!=[{k:b[k] for k in ['ordinal','kind','hash','characters','start','end']} for b in expected_blocks]:raise ValueError('original_pipeline_single_call_whole_block_parity')
 return result,observed[0]
def manual_annotations(text,blocks,sidecar,ordinal):
 raw=text.encode()
 if digest(raw)!=sidecar['source_SHA256'] or sidecar['source_ordinal']!=ordinal:raise ValueError('manual_exact_parent_identity')
 spans=[]
 for s in sidecar['partition']:
  if s['role']!='presentation':continue
  a,b=s['source_UTF8_range'];piece=raw[a:b]
  if digest(piece)!=s['SHA256'] or piece.decode()!=s['text']:raise ValueError('manual_presentation_span_identity')
  lo,hi=len(raw[:a].decode()),len(raw[:b].decode());bound=[v['ordinal'] for v in blocks if lo<=v['start'] and v['end']<=hi]
  spans.append({'source_UTF8_range':[a,b],'source_Unicode_range':[lo,hi],'exact_preserved_text_SHA256':s['SHA256'],'wholly_contained_block_ordinals':bound,'manual_identity_specific_annotation_only':True})
 return spans
def worker(args):
 supervisor.arm(55-(time.clock_gettime(time.CLOCK_MONOTONIC)-args.start));out=pathlib.Path(args.output)
 try:
  p=verify(args)
  if str(out)!=p['output'] or os.getppid()!=args.supervisor_pid:raise ValueError('owned_parent_output')
  extractor,renderer,policy,deps=dependencies();approved=json.loads((POLICY/'approved-atoms.json').read_text())
  approved_hashes=p['approved_disclaimer_hashes'];outcomes=[]
  if approved_hashes!=approved['hashes']:raise ValueError('exact_reviewed_four_disclaimer_atoms')
  for e in p['selected']:
   ordinal=e['source_ordinal'];raw=pathlib.Path(e['native_source_path']).read_bytes();body=pathlib.Path(e['original_text_path']).read_bytes();receipt=json.loads(pathlib.Path(e['original_capture_receipt_path']).read_text());meta=json.loads(pathlib.Path(e['original_native_metadata_path']).read_text())
   if len(raw)>65536 or len(body)>2000000 or digest(raw)!=e['record_SHA256'] or digest(body)!=e['rendered_text_SHA256'] or len(receipt['metadata']['blocks'])>10000 or meta['renderer_sha256']!=sha(PIPELINE/'dom_renderer.py'):raise ValueError('source_body_renderer_identity_bound')
   native=json.loads(raw.decode());text=body.decode();blocks=receipt['metadata']['blocks'];record={'source_ordinal':ordinal,'page_id':e['page_id'],'revision_id':e['revision_id'],'source_record_SHA256':digest(raw),'HTML_SHA256':e['HTML_SHA256'],'original_text_SHA256':digest(body),'original_holds':e['original_holds'],'known_manual_hold_overlay_preserved':e['known_manual_hold'],'source_nodes_removed':0,'text_changed':False,'new_admitted_documents':0}
   if native['identifier']!=e['page_id'] or native['version']['identifier']!=e['revision_id'] or digest(native['article_body']['html'].encode())!=e['HTML_SHA256']:raise ValueError('native_HTML_ID_revision_binding')
   try:
    result,roles=instrument(native,text,blocks,extractor,renderer,policy,approved_hashes);record.update(status='EXACT_WHOLE_AND_EVERY_BLOCK_PARITY_SOURCE_ROLE_INVENTORY',role_inventory=roles,new_parser_pipeline_holds=result['holds'],original_structural_holds_unchanged=result['holds']==meta['structural_holds'])
    if result['holds']!=meta['structural_holds']:record['status']='HELD_NEW_PARSER_PIPELINE_HOLD_DIFFERENCE_WITH_EXACT_TEXT_BLOCKS'
    if e.get('manual_component_sidecar'):
     sidecar=json.loads(pathlib.Path(e['manual_component_sidecar']).read_text());record['manual_exact_source_presentation_annotations']=manual_annotations(text,blocks,sidecar,ordinal);record['manual_sidecar_SHA256']=sha(e['manual_component_sidecar']);record['no_generalized_firstparagraph_or_linklist_removal']=True
   except (ValueError,TypeError,KeyError,IndexError,RuntimeError) as err:record.update(status='HELD_ROLE_INVENTORY_NOT_RECONCILED_NO_SUBSTITUTE',reason=type(err).__name__+':'+str(err))
   supervisor.write(out,str(ordinal)+'.roles.json',supervisor.data(record));outcomes.append({'source_ordinal':ordinal,'status':record['status'],'role_receipt_SHA256':sha(out/(str(ordinal)+'.roles.json'))})
  verify(args)
  supervisor.slot(out,'result.json',{'status':'COMPLETE_FIXED20_ROLE_INVENTORY_OUTCOMES_NOT_QUALITY_OR_ADMISSION','outcomes':outcomes,'exact_parity_outcomes':sum(r['status']=='EXACT_WHOLE_AND_EVERY_BLOCK_PARITY_SOURCE_ROLE_INVENTORY' for r in outcomes),'held_outcomes':sum(r['status']!='EXACT_WHOLE_AND_EVERY_BLOCK_PARITY_SOURCE_ROLE_INVENTORY' for r in outcomes),'source_nodes_removed':0,'text_changed':False,'all_inputs_rehashed_unchanged':True,'no_tokenization_network_model_training':True,'new_admitted_documents':0,'new_admitted_tokens':0})
 except BaseException as err:
  supervisor.slot(out,'result.json',{'status':'PARTIAL_NO_RETRY_NO_SOURCE_ROLE_CLEARANCE','reason':type(err).__name__+':'+str(err),'new_admitted_documents':0});raise
 finally:signal.setitimer(signal.ITIMER_REAL,0)
def main():
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--worker',action='store_true');p.add_argument('--code-pins-sha256',required=True);p.add_argument('--profile-sha256',required=True);p.add_argument('--start',type=float);p.add_argument('--supervisor-pid',type=int);p.add_argument('--output');a=p.parse_args()
 if a.worker:worker(a)
 elif a.execute:
  start=time.clock_gettime(time.CLOCK_MONOTONIC);supervisor.arm(60);out=pathlib.Path(json.loads((HERE/'profile.json').read_text())['output'])
  supervisor.supervise(out,lambda start:[sys.executable,'-B',str(HERE/'inventory.py'),'--worker','--code-pins-sha256',a.code_pins_sha256,'--profile-sha256',a.profile_sha256,'--start',str(start),'--supervisor-pid',str(os.getpid()),'--output',str(out)],lambda:verify(a),started=start)
 else:
  supervisor.arm(55)
  try:verify(a);print('READY_NO_RETAINED_SOURCE_DOM_APPLICATION')
  finally:signal.setitimer(signal.ITIMER_REAL,0)
if __name__=='__main__':main()

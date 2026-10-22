"""Fixed current WB metadata triage, no source text/native HTML/tokenizer/model operations."""
import argparse,collections,hashlib,json,os,pathlib,platform,signal,sqlite3,sys,time
import feature_core as core,supervisor_core as supervisor
HERE=pathlib.Path(__file__).resolve().parent;BASE=HERE.parent;OUT=BASE/'m2-intake/wikibooks-current-candidate-heading-metadata-v1'
LIMITS={'worker_seconds':110,'external_seconds':120,'tree_RSS_bytes':1000000000,'output_bytes':32000000,'max_blocks':4008512,'record_bytes':1024,'candidate_documents':18680,'anchor_documents':10,'distinct_union_documents':18685,'stores':12}
def sha(p):
 with pathlib.Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def runtime():return {'python':sys.version,'launcher':sys.executable,'binary':str(pathlib.Path(sys.executable).resolve()),'prefix':sys.prefix,'platform':platform.platform(),'SQLite_version':sqlite3.sqlite_version}
def inventory(p):
 paths={str((HERE/n).resolve()) for n in ['triage.py','feature_core.py','supervisor_core.py','checks.py','profile.json','runtime.json']}
 paths|={p[k] for k in ['screening','finalizer','manual_overlay','counts_v22','prior_proposal','canonical_stores_manifest','extra_61485_factual_hold']}
 paths|={e['path'] for e in p['stores']};paths.add(str(pathlib.Path(sys.executable).resolve()))
 paths.add(str((BASE/'wikibooks-current20-native-source-capture-preparation-v2/supervisor_core.py').resolve()))
 paths.add(str((BASE/'wikibooks-rendered-heading-triage-preparation-v1/triage_core.py').resolve()))
 for m in [argparse,collections,hashlib,json,os,pathlib,platform,signal,sqlite3,sys,time,supervisor.shutil,supervisor.subprocess]:
  if getattr(m,'__file__',None):paths.add(str(pathlib.Path(m.__file__).resolve()))
 import _sqlite3
 if getattr(_sqlite3,'__file__',None):paths.add(str(pathlib.Path(_sqlite3.__file__).resolve()))
 elif _sqlite3.__spec__.origin!='built-in':raise ValueError('SQLite_origin_unbound')
 return paths
def verify(a):
 if sha(HERE/'code-pins.json')!=a.code_pins_sha256 or sha(HERE/'profile.json')!=a.profile_sha256:raise ValueError('external_code_profile_pins')
 p=json.loads((HERE/'profile.json').read_text());pins=json.loads((HERE/'code-pins.json').read_text())['SHA256']
 if p['limits']!=LIMITS or p['output']!=str(OUT) or len(p['stores'])!=12 or set(pins)!=inventory(p):raise ValueError('exact_inventory_limits_output')
 for f,h in pins.items():
  q=pathlib.Path(f)
  if q.is_symlink() or not q.is_file() or sha(q)!=h:raise ValueError('input_pin_changed:'+f)
 if runtime()!=json.loads((HERE/'runtime.json').read_text()):raise ValueError('runtime')
 if p['stores']!=json.loads(pathlib.Path(p['canonical_stores_manifest']).read_text()):raise ValueError('canonical12_inventory')
 return p
def connect(p):
 d=sqlite3.connect(pathlib.Path(p).as_uri()+'?mode=ro',uri=True);d.execute('pragma query_only=ON');d.execute('pragma cache_size=-4096');return d
def frame(p):
 d=connect(p['screening']);d.row_factory=sqlite3.Row
 try:rows=[dict(r) for r in d.execute('select source_ordinal,page_id,revision_id,family,text_sha256,characters,utf8_bytes,content_tokens,tokens_plus_one_EOS,language_pass,known_discovery_hold,holds from docs where language_pass=1 and known_discovery_hold=0 order by source_ordinal')]
 finally:d.close()
 overlay=json.loads(pathlib.Path(p['manual_overlay']).read_text())['known_hold_overlay'];by,candidates,held=core.select_frame(rows,overlay,p['frame'])
 ids=sorted(candidates);identity=[[i,by[i]['page_id'],by[i]['revision_id'],by[i]['family'],by[i]['text_sha256'],by[i]['content_tokens']] for i in ids]
 if hashlib.sha256(json.dumps(identity,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()!=p['candidate_identity_SHA256']:raise ValueError('candidate_frame_identity_digest')
 anchors={a['source_ordinal']:a for a in p['anchors']}
 if len(anchors)!=10 or set(anchors)&set(candidates)!=set(p['anchor_candidate_overlap']) or set(anchors)&held!=set(p['anchor_excluded']):raise ValueError('anchor_roles')
 for i,a in anchors.items():
  if (by[i]['page_id'],by[i]['revision_id'],by[i]['family'],by[i]['text_sha256'])!=(a['page_id'],a['revision_id'],a['family'],a['text_sha256']):raise ValueError('anchor_identity')
 union=set(candidates)|set(anchors)
 if len(union)!=18685:raise ValueError('exact_union18685')
 return by,candidates,held,anchors,union

def worker(a):
 start=a.start;supervisor.arm(110-(time.clock_gettime(time.CLOCK_MONOTONIC)-start));out=pathlib.Path(a.output)
 try:
  p=verify(a)
  if out!=OUT or os.getppid()!=a.supervisor_pid:raise ValueError('parent_output')
  by,candidates,held,anchors,union=frame(p);counts=json.loads(pathlib.Path(p['counts_v22']).read_text())
  if counts['new_source_pilot']['language_pass_after_known_holds_documents']!=18680 or counts['new_source_pilot']['language_pass_after_known_holds_provisional_content_tokens']!=19904934:raise ValueError('counts_v22_frame_binding')
  final=connect(p['finalizer']);seen=set();stats=collections.Counter();owner_rows=[];feature_hash=hashlib.sha256();anchor_results={}
  def guard(check_output=True):
   if time.clock_gettime(time.CLOCK_MONOTONIC)-start>=110:raise TimeoutError('shared_worker110')
   if check_output and supervisor.outsize(out)>32000000-1048576:raise ValueError('output_headroom')
  def block_guard():
   guard(False);stats['block_metadata_rows']+=1
   if stats['block_metadata_rows']>4008512:raise ValueError('block_metadata_cap')
  with (out/'features.metadata').open('xb') as sink:
   for e in p['stores']:
    guard();d=connect(e['path']);store_rows=0
    try:
     cols=d.execute('pragma table_info(blocks)').fetchall()
     if [r[1] for r in cols]!=['source_ordinal','ordinal','kind','hash','characters','start','end'] or [r[5] for r in cols][:2]!=[1,2]:raise ValueError('indexed_blocks_schema')
     ids=sorted(union)
     for off in range(0,len(ids),500):
      group=ids[off:off+500];sql='select source_ordinal,page_id,revision_id,family from rendered where source_ordinal in ('+','.join('?' for _ in group)+') order by source_ordinal'
      for i,page,revision,family in d.execute(sql,group):
       guard()
       if i in seen:raise ValueError('duplicate_owner_for_union_identity')
       r=by[i]
       if (page,revision,family)!=(r['page_id'],r['revision_id'],r['family']):raise ValueError('canonical_owner_identity')
       native=final.execute('select p.page_id,p.revision_id,p.family,p.text_sha256,p.characters,p.utf8_bytes,p.holds,p.active,f.holds from pages p join final_pages f on p.source_ordinal=f.source_ordinal where p.source_ordinal=?',(i,)).fetchone()
       if native is None or native[:6]!=(page,revision,family,r['text_sha256'],r['characters'],r['utf8_bytes']) or json.loads(native[6])!=[] or native[7]!=1 or json.loads(native[8])!=[]:raise ValueError('global_finalizer_identity_original_holds')
       result=core.summarize(d.execute('select ordinal,kind,hash,characters,start,end from blocks where source_ordinal=? order by ordinal',(i,)),r['characters'],block_guard)
       identity={'source_ordinal':i,'page_id':page,'revision_id':revision,'family':family,'text_sha256':r['text_sha256'],'M1_tokens_stored':r['content_tokens'],'candidate':i in candidates,'development_anchor':i in anchors,'known_manual_hold':i in held}
       line=core.bounded_record(identity,result);guard()
       if supervisor.outsize(out)+len(line)>32000000-1048576:raise ValueError('prewrite_feature_output')
       sink.write(line);sink.flush();feature_hash.update(line);seen.add(i);store_rows+=1
       if i in candidates:
        stats['candidate_documents']+=1;stats['candidate_tokens_stored_unchanged']+=r['content_tokens'];stats['candidate_documents_with_empty_subtree']+=bool(result['empty_subtrees']);stats['candidate_empty_subtrees']+=result['empty_subtrees'];stats['candidate_empty_leaf_subtrees']+=result['empty_leaf_subtrees'];stats['candidate_unknown_kind_documents']+=bool(result['unknown_kinds'])
       else:stats['excluded_development_anchor_documents']+=1
       if i in anchors:
        expected=anchors[i]
        if (result['empty_subtrees'],result['empty_leaf_subtrees'])!=(expected['expected_empty_subtrees'],expected['expected_empty_leaves']):raise ValueError('known_anchor_feature_count_mismatch')
        anchor_results[str(i)]={'empty_subtrees':result['empty_subtrees'],'empty_leaf_subtrees':result['empty_leaf_subtrees'],'candidate':i in candidates,'known_manual_hold':i in held}
     owner_rows.append({'path':e['path'],'selected_union_rows':store_rows})
    finally:d.close()
   os.fsync(sink.fileno())
  final.close()
  if seen!=union or stats['candidate_documents']!=18680 or stats['excluded_development_anchor_documents']!=5 or stats['candidate_tokens_stored_unchanged']!=19904934 or len(anchor_results)!=10:raise ValueError('exact_all_owner_frame_reconciliation')
  guard();verify(a)
  supervisor.slot(out,'result.json',{'status':'COMPLETE_METADATA_FEATURE_INVENTORY_NOT_FILTER_OR_ADMISSION','stats':dict(stats),'exact_union_identities':len(seen),'candidate_identity_SHA256':p['candidate_identity_SHA256'],'feature_file_SHA256':feature_hash.hexdigest(),'store_owner_coverage':owner_rows,'known_anchor_results':anchor_results,'all_input_pins_rechecked_unchanged':True,'source_bodies_or_native_HTML_read':0,'semantic_failure_inferred':False,'candidate_exclusions_performed':0,'counts_or_source_registry_mutated':False,'new_admitted_documents':0,'new_admitted_tokens':0,'no_network_tokenization_model_training':True,'elapsed_seconds':time.clock_gettime(time.CLOCK_MONOTONIC)-start})
 except BaseException as e:
  supervisor.slot(out,'result.json',{'status':'PARTIAL_NO_RETRY_NO_SOURCE_QUALITY_OR_COVERAGE_CLAIM','error':type(e).__name__+':'+str(e),'new_admitted_documents':0});raise
 finally:signal.setitimer(signal.ITIMER_REAL,0)
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true');parser.add_argument('--worker',action='store_true');parser.add_argument('--code-pins-sha256',required=True);parser.add_argument('--profile-sha256',required=True);parser.add_argument('--start',type=float);parser.add_argument('--supervisor-pid',type=int);parser.add_argument('--output');a=parser.parse_args()
 if a.worker:worker(a)
 elif a.execute:
  started=time.clock_gettime(time.CLOCK_MONOTONIC);supervisor.arm(120);supervisor.supervise(OUT,lambda t:[sys.executable,'-B',str(HERE/'triage.py'),'--worker','--code-pins-sha256',a.code_pins_sha256,'--profile-sha256',a.profile_sha256,'--start',str(t),'--supervisor-pid',str(os.getpid()),'--output',str(OUT)],lambda:verify(a),started=started)
 else:
  supervisor.arm(110)
  try:verify(a);print('READY_NO_CANDIDATE_FEATURE_PASS')
  finally:signal.setitimer(signal.ITIMER_REAL,0)
if __name__=='__main__':main()

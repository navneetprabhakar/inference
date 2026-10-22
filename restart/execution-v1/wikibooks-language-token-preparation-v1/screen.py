"""One bounded offline pass: pinned classifier inference and M1 token counts only."""
import argparse,hashlib,json,os,pathlib,resource,sqlite3,subprocess,sys,time,shutil
import rules
HERE=pathlib.Path(__file__).resolve().parent
BASE=HERE.parent
CAPS={'seconds':600,'work_seconds':570,'output_bytes':100_000_000,'rss_bytes':1_000_000_000,'documents':27585,'source_UTF8_bytes':111989353,'max_document_UTF8_bytes':1048576,'max_scored_lines':150471,'max_all_windows':150471,'batch_documents':64,'batch_projection_bytes':4194304,'detector_batch_seconds':30,'detector_stdout_bytes':1048576}
os.environ['TOKENIZERS_PARALLELISM']='false'
SLOT=262144
FREE=20*1024**3+16_000_000_000

def clk():return time.clock_gettime(time.CLOCK_MONOTONIC)
def size(p):return sum(x.stat().st_size for x in p.rglob('*') if x.is_file())
def ro(p):return sqlite3.connect('file:'+str(pathlib.Path(p).resolve())+'?mode=ro',uri=True)
def terminal(out,r):
 p=out/'result.json';b=(json.dumps(r,indent=2,sort_keys=True)+'\n').encode()
 if len(b)>SLOT:raise RuntimeError('terminal_metadata_cap')
 if not p.exists():
  with p.open('xb') as f:f.write(b' '*SLOT)
 with p.open('r+b') as f:f.write(b+b' '*(SLOT-len(b)));f.flush();os.fsync(f.fileno())
def runtime():
 from importlib.metadata import version
 return {'executable':str(pathlib.Path(sys.executable).resolve()),'python':sys.version,'sqlite':sqlite3.sqlite_version,'tokenizers':version('tokenizers')}
def infer(profile,data,remaining):
 cmd=[profile['fasttext']['path'],'predict-prob',profile['language_model']['path'],'-','1']
 p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 try:
  stdout,stderr=p.communicate(data,timeout=min(CAPS['detector_batch_seconds'],remaining))
  if p.returncode or len(stdout)>CAPS['detector_stdout_bytes'] or len(stderr)>65536:raise RuntimeError('classifier_exit_or_output_cap')
  return stdout.decode('utf8').splitlines()
 finally:
  if p.poll() is None:p.kill()
  p.wait(timeout=5)
def run(profile_path,profile_sha,out,start):
 raw=profile_path.read_bytes()
 if len(raw)>1048576 or hashlib.sha256(raw).hexdigest()!=profile_sha:raise RuntimeError('approved_profile_digest_mismatch')
 profile=json.loads(raw);stats={'documents':0,'source_UTF8_bytes':0,'content_tokens':0,'scored_lines':0,'skipped_chunks':0,'all_windows':0,'batches':0};db=None
 terminal(out,{'status':'RUNNING_NOT_COMPLETE_NO_ADMISSION'})
 def guard(extra=0):
  import shutil
  if clk()-start>=CAPS['work_seconds']:raise RuntimeError('570second_work_cap')
  rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
  if rss>CAPS['rss_bytes'] or size(out)+extra>CAPS['output_bytes']-1048576:raise RuntimeError('memory_or_output_cap')
  if shutil.disk_usage(out).free<FREE+extra:raise RuntimeError('disk_weights_reserve')
 try:
  if profile['status']!='PARENT_REVIEW_PREPARED_LANGUAGE_TOKEN_PROFILE_NO_ADMISSION' or profile['limits']!=CAPS or profile['runtime']!=runtime():raise RuntimeError('profile_policy_or_runtime_mismatch')
  for item in profile['inputs']:
   if rules.sha(pathlib.Path(item['path']))!=item['sha256']:raise RuntimeError('input_pin_mismatch')
   guard()
  final=ro(profile['finalizer']['path']);targets={o:(p,r,f,t,h,n,b) for o,p,r,f,t,h,n,b in final.execute("select p.source_ordinal,p.page_id,p.revision_id,p.family,p.title,p.text_sha256,p.characters,p.utf8_bytes from pages p join final_pages f on f.source_ordinal=p.source_ordinal where f.holds='[]'")}
  if len(targets)!=27585 or sum(r[-1] for r in targets.values())!=111989353 or final.execute('select count(*) from cross_family_block_groups').fetchone()[0]!=15720:raise RuntimeError('frozen_cohort_or_overlap_frame_mismatch')
  reviews=json.loads(pathlib.Path(profile['discovery_holds']['path']).read_text())['records'];known={r['source_ordinal']:r for r in reviews}
  if len(known)!=20:raise RuntimeError('all20_discovery_reviews_required')
  for ordinal,r in known.items():
   if final.execute('select text_sha256 from pages where source_ordinal=?',(ordinal,)).fetchone()[0]!=r['text_sha256']:raise RuntimeError('discovery_identity_mismatch')
  tokenizer=rules.load_tokenizer(profile);db=sqlite3.connect(out/'screening.sqlite3');db.executescript('''pragma journal_mode=DELETE;pragma synchronous=FULL;pragma cache_size=-4096;pragma temp_store=MEMORY;pragma max_page_count=15000;
 create table docs(source_ordinal integer primary key,page_id integer,revision_id integer,family text,title text,text_sha256 text,characters integer,utf8_bytes integer,content_tokens integer,tokens_plus_one_EOS integer,scored_lines integer,skipped_chunks integer,language_pass integer,minimum_english_probability real,known_discovery_hold integer,holds text);
 create table windows(id integer primary key,source_ordinal integer,ordinal integer,kind text,start integer,end integer,alphabetics integer,raw_sha256 blob,projection_sha256 blob,scored integer,skip_reason text,label text,raw_probability text,top_probability real,english_probability real,policy_pass integer,unique(source_ordinal,ordinal));
 create table discovery_reviews(source_ordinal integer primary key,post_finalizer_candidate integer,disposition text,metadata text);
 ''')
  for r in reviews:db.execute('insert into discovery_reviews values (?,?,?,?)',(r['source_ordinal'],int(r['post_finalizer_candidate']),r['disposition'],json.dumps(r,sort_keys=True)))
  db.commit();seen=set();batch=[];projection_bytes=0;window_id=0
  def flush():
   nonlocal batch,projection_bytes
   if not batch:return
   guard(1048576);lines=[projected for doc in batch for meta,projected in doc['windows'] if meta['scored']];preds=infer(profile,b'\n'.join(lines)+b'\n',CAPS['work_seconds']-(clk()-start))
   if len(preds)!=len(lines):raise RuntimeError('classifier_window_line_count_mismatch')
   pi=0
   for doc in batch:
    english=[];skipped=0
    for j,(meta,projected) in enumerate(doc['windows']):
     if meta['scored']:
      label,praw,p,en,ok=rules.prediction(preds[pi]);pi+=1;english.append(en);pred=(label,praw,p,en,ok)
     else:pred=(None,None,None,None,None);skipped+=1
     db.execute('insert into windows(source_ordinal,ordinal,kind,start,end,alphabetics,raw_sha256,projection_sha256,scored,skip_reason,label,raw_probability,top_probability,english_probability,policy_pass) values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(doc['ordinal'],j,meta['kind'],meta['start'],meta['end'],meta['alphabetics'],meta['raw_sha256'],meta['projection_sha256'],int(meta['scored']),meta['skip_reason'],*pred))
    if not english or len(english)!=doc['expected_scored']:raise RuntimeError('per_document_whole_chunk_count_mismatch')
    passed=min(english)>=.8;holds=[]
    if not passed:holds.append('whole_document_or_1024character_window_language')
    if doc['ordinal'] in known:holds.append('known_discovery_review_hold_or_exclusion')
    p,r,f,t,h,n,b=doc['identity'];tok=doc['tokens'];db.execute('insert into docs values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(doc['ordinal'],p,r,f,t,h,n,b,tok,tok+1,len(english),skipped,int(passed),min(english),int(doc['ordinal'] in known),json.dumps(holds)))
    stats['documents']+=1;stats['source_UTF8_bytes']+=b;stats['content_tokens']+=tok;stats['scored_lines']+=len(english);stats['skipped_chunks']+=skipped;stats['all_windows']+=len(doc['windows'])
   if pi!=len(preds) or stats['scored_lines']>150471 or stats['all_windows']>150471:raise RuntimeError('score_or_window_denominator_cap')
   db.commit();stats['batches']+=1;batch=[];projection_bytes=0;guard()
  for item in profile['shards']:
   source=ro(item['path'])
   for ordinal,page,rev,family,payload in source.execute('select source_ordinal,page_id,revision_id,family,data from rendered order by source_ordinal'):
    if ordinal not in targets:continue
    guard();row=json.loads(payload);identity=targets[ordinal];text=row['text'];rawtext=text.encode()
    if ordinal in seen or (page,rev,family,row['title'],row['extracted_text_sha256'],len(text),len(rawtext))!=identity or hashlib.sha256(rawtext).hexdigest()!=identity[4] or len(rawtext)>1048576 or row['structural_holds'] or row['prior_v3_holds']:raise RuntimeError('source_identity_or_existing_hold_changed')
    seen.add(ordinal);prepared=[];nbytes=0
    for meta,chunk in rules.windows(text):
     projected=rules.projection(chunk).encode();meta.update({'raw_sha256':hashlib.sha256(chunk.encode()).digest(),'projection_sha256':hashlib.sha256(projected).digest()});prepared.append((meta,projected));nbytes+=len(projected)+1 if meta['scored'] else 0
    if nbytes>CAPS['batch_projection_bytes']:raise RuntimeError('single_document_projection_bound')
    if batch and (len(batch)>=64 or projection_bytes+nbytes>CAPS['batch_projection_bytes']):flush()
    batch.append({'ordinal':ordinal,'identity':identity,'tokens':len(tokenizer.encode(text,add_special_tokens=False).ids),'windows':prepared,'expected_scored':sum(m['scored'] for m,_ in prepared)});projection_bytes+=nbytes
   source.close()
  flush()
  if seen!=set(targets) or stats['documents']!=27585 or stats['source_UTF8_bytes']!=111989353:raise RuntimeError('missing_or_extra_document_denominator')
  if db.execute('select count(*) from windows where scored=1').fetchone()[0]!=stats['scored_lines'] or db.execute('select count(*) from windows where scored=1 and (label is null or policy_pass is null)').fetchone()[0]:raise RuntimeError('missing_window_prediction')
  summary={}
  for name,where in [('all_post_finalizer','1'),('raw_language_pass','language_pass=1'),('language_pass_after_known_discovery_holds','language_pass=1 and known_discovery_hold=0')]:
   n,t,e,b=db.execute('select count(*),sum(content_tokens),sum(tokens_plus_one_EOS),sum(utf8_bytes) from docs where '+where).fetchone();summary[name]={'documents':n,'provisional_M1_content_tokens':t or 0,'provisional_content_plus_one_EOS_each':e or 0,'source_UTF8_bytes':b or 0}
  db.commit()
  if db.execute('pragma integrity_check').fetchone()[0]!='ok':raise RuntimeError('SQLite_integrity')
  db.close();db=None;final.close()
  for item in profile['inputs']:
   guard()
   if rules.sha(pathlib.Path(item['path']))!=item['sha256']:raise RuntimeError('immutable_input_changed')
  if rules.sha(profile_path)!=profile_sha:raise RuntimeError('profile_changed_during_run')
  terminal(out,{'status':'COMPLETE_LANGUAGE_DIAGNOSTICS_PROVISIONAL_M1_COUNTS_NO_ADMISSION','stats':stats,'summary':summary,'limits':CAPS,'profile_sha256':profile_sha,'M1_manifest_sha256':profile['tokenizer_manifest']['sha256'],'M1_core_sha256':profile['tokenizer_core']['sha256'],'database_sha256':rules.sha(out/'screening.sqlite3'),'all20_known_discovery_holds_preserved':True,'all_original_holds_and_cross_family_groups_immutable':True,'remaining_gates':['sourcequality/readability/factual review and filter repair','rights/captured-text exceptions','cross-source duplicate/leakage and family merging','fresh representative acceptance review'],'not_usable_or_admitted_counts':True,'elapsed_seconds':clk()-start,'new_admitted_documents':0,'new_admitted_tokens':0})
 except BaseException as exc:
  committed=None
  if db is not None:
   try:
    db.rollback();committed={'documents':db.execute('select count(*) from docs').fetchone()[0],'windows':db.execute('select count(*) from windows').fetchone()[0],'scored_lines':db.execute('select count(*) from windows where scored=1').fetchone()[0]};db.close()
   except Exception:pass
  terminal(out,{'committed_database_counts':committed,'processed_stats_may_include_uncommitted_batch':True,'status':'PARTIAL_LANGUAGE_DIAGNOSTICS_NO_ADMISSION','reason':str(exc)[:2000],'stats':stats,'elapsed_seconds':clk()-start,'new_admitted_documents':0,'new_admitted_tokens':0});raise

def main():
 p=argparse.ArgumentParser();p.add_argument('--profile',type=pathlib.Path,required=True);p.add_argument('--profile-sha256',required=True);p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--start-shared-monotonic',type=float,required=True);p.add_argument('--supervisor-pid',type=int,required=True);p.add_argument('--code-pins-sha256',required=True);a=p.parse_args();import code_guard;code_guard.verify(a.code_pins_sha256)
 if os.getppid()!=a.supervisor_pid or not 0<=clk()-a.start_shared_monotonic<600:raise RuntimeError('live_supervisor_shared_clock_required')
 run(a.profile,a.profile_sha256,a.output,a.start_shared_monotonic)
if __name__=='__main__':main()

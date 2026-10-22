"""Stored PG diagnostic proof only. No source plaintext/tokenizer/detector access."""
import hashlib,json,math,os,re,sqlite3,stat
from pathlib import Path
P='cd2e53d06ecaae370ce91b340e4631635ca9d715c025cd064515e2c40f6a45ca'
C='1b961a1c5f6862d9e260bc80e028927acf2407a5312feb85f22f33a3a797d595'
def need(v,m):
 if not v:raise ValueError(m)
def ident(p):
 s=Path(p).stat(follow_symlinks=False);need(stat.S_ISREG(s.st_mode),'regular_stored_metadata');return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
def small(p,cap=1048576):
 need(ident(p)[2]<=cap,'metadata_cap');b=Path(p).read_bytes();need(len(b)<=cap,'metadata_cap');return b
def load(p):return json.loads(small(p))
def hash_file(p,check):
 before=ident(p);fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW);h=hashlib.sha256();n=0
 try:
  need([os.fstat(fd).st_dev,os.fstat(fd).st_ino,os.fstat(fd).st_size,os.fstat(fd).st_mtime_ns,os.fstat(fd).st_ctime_ns]==before,'FD_stat_before')
  while True:
   check();b=os.read(fd,1048576)
   if not b:break
   n+=len(b);need(n<=before[2],'stored_file_grew');h.update(b)
  s=os.fstat(fd);need([s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]==before==ident(p) and n==before[2],'FD_path_post_stat')
 finally:os.close(fd)
 return n,h.hexdigest()
def absent(pid):
 need(type(pid) is int and pid>1,'positive_PID')
 try:os.kill(pid,0)
 except ProcessLookupError:return
 raise ValueError('producer_PID_live_or_reused')
def gate(p,path,digest):
 raw=small(path,64000);need(hashlib.sha256(raw).hexdigest()==digest,'external_binding_pin');b=json.loads(raw)
 need(b['producer_reaped'] is True and b['exec_exit_code']==0 and b['exec_session']==22400 and b['owned_PIDs_absent'] is True,'terminal_gate')
 need(b['profile_SHA256']==p['producer_profile_SHA256']==P and b['codepins_SHA256']==p['producer_codepins_SHA256']==C,'exact_current_producer')
 need(b['supervisor_PID']==p['expected_supervisor_PID'] and b['worker_PID']==p['expected_worker_PID'],'exact_producer_PIDs');absent(b['supervisor_PID']);absent(b['worker_PID'])
 b['files']={}
 for name,x in b['artifacts'].items():
  need(x['path']==str(Path(p['source_output'])/name) and x['bytes']==x['dev_ino_size_mtime_ns_ctime_ns'][2],'binding_exact_artifact_path_size')
  b['files'][name]={'stat':x['dev_ino_size_mtime_ns_ctime_ns'],'SHA256':x['SHA256']}
 return b
def prediction(line):
 need(type(line) is str and len(line)<=160 and '\n' not in line and '\r' not in line,'prediction_width_line')
 parts=line.split();need(len(parts)==2 and re.fullmatch(r'__label__[a-z_\-]{2,24}',parts[0]) is not None,'top1_prediction_syntax');v=float(parts[1]);need(math.isfinite(v) and 0<=v<=1.001,'finite_probability');en=v if parts[0]=='__label__en' else 0.;return parts[0],parts[1],v,en,int(en>=.8)
def verify_sql(dbpath,producer,check):
 before=ident(dbpath);fd=os.open(dbpath,os.O_RDONLY|os.O_NOFOLLOW);db=sqlite3.connect(Path(dbpath).as_uri()+'?mode=ro&immutable=1',uri=True)
 try:
  db.execute('PRAGMA query_only=ON');db.execute('PRAGMA cache_size=-8192');db.execute('PRAGMA temp_store=MEMORY');db.execute('PRAGMA mmap_size=0');db.set_progress_handler(lambda:(check() or 0),10000)
  need(db.execute('PRAGMA integrity_check').fetchone()==('ok',) and not db.execute('PRAGMA foreign_key_check').fetchall(),'SQL_integrity_FK')
  fk=db.execute('PRAGMA foreign_key_list(windows)').fetchall();need(len(fk)==1 and fk[0][2:5]==('docs','doc','ordinal'),'exact_windows_FK')
  stats={'documents':0,'raw_source_bytes_read':0,'UTF8_bytes':0,'characters':0,'M1_content_tokens':0,'all_windows':0,'scored':0,'skipped':0,'language_pass':0};distinct={};language_tokens=0;language_bytes=0
  rows=db.execute('SELECT ordinal,ebook_ID,raw_SHA256,source_start,source_end,text_SHA256,characters,UTF8_bytes,content_tokens,EOS_separate,scored,skipped,language_pass,min_english,input_SHA256,prediction_logical_lines_SHA256 FROM docs ORDER BY ordinal')
  for expected,row in enumerate(rows):
   check();doc,eid,rawhash,start,end,tx,chars,nb,tok,eos,scored,skipped,passed,min_en,inp,predhash=row
   need(expected<len(producer['records']),'extra_doc');rec=producer['records'][expected];src=producer['source_files'][expected];e=producer['envelopes'][expected]
   need((doc,eid,rawhash,start,end,tx,chars,nb)==(rec['ordinal'],rec['ebook_ID'],bytes.fromhex(src['SHA256']),e['start_byte'],e['end_byte'],bytes.fromhex(e['SHA256']),e['characters'],e['bytes']),'exact_boundary_source_identity')
   need(type(tok) is int and 0<=tok<=nb*4 and eos==1 and len(inp)==len(predhash)==32,'content_token_EOS_hash_domains')
   count=0;score=0;skip=0;english=[];logical=hashlib.sha256()
   for w in db.execute('SELECT ordinal,kind,start,end,alphabetics,raw_SHA256,projection_SHA256,scored,skip_reason,label,raw_probability,top_probability,english_probability,policy_pass,prediction_logical_line FROM windows WHERE doc=? ORDER BY ordinal',(doc,)):
    if count%256==0:check()
    no,kind,a,z,alpha,rh,ph,is_scored,why,label,rawp,top,en,policy,line=w
    aa=0 if count==0 else (count-1)*1024;zz=chars if count==0 else min(chars,aa+1024)
    need((no,kind,a,z)==(count,0 if count==0 else 1,aa,zz) and 0<=aa<=zz<=chars,'exact_window_identity_coverage')
    need(type(alpha) is int and 0<=alpha<=zz-aa and len(rh)==len(ph)==32,'window_hash_alpha_domains')
    want=count==0 or alpha>=40;need(is_scored==int(want),'whole_or_40alpha_policy')
    if want:
     need(why is None and prediction(line)==(label,rawp,top,en,policy),'stored_top1_policy_recomputed');score+=1;english.append(en);logical.update((line+'\n').encode())
    else:
     need(why=='fewer_than_40_alphabetic_characters' and all(v is None for v in [label,rawp,top,en,policy,line]),'explicit_skip_all_null_prediction');skip+=1
    count+=1
   need(count==1+(chars+1023)//1024 and (score,skip,passed,min_en)==(scored,skipped,int(min(english)>=.8),min(english)) and logical.digest()==predhash,'doc_window_probability_logical_transcript')
   signature=(chars,nb,tok,passed);need(tx not in distinct or distinct[tx]==signature,'exact_text_alias_diagnostic_agreement');distinct[tx]=signature
   stats['documents']+=1;stats['raw_source_bytes_read']+=src['bytes'];stats['UTF8_bytes']+=nb;stats['characters']+=chars;stats['M1_content_tokens']+=tok;stats['all_windows']+=count;stats['scored']+=score;stats['skipped']+=skip;stats['language_pass']+=passed
   if passed:language_tokens+=tok;language_bytes+=nb
  need(stats['documents']==len(producer['records']) and db.execute('SELECT count(*) FROM windows').fetchone()[0]==stats['all_windows'],'all_docs_windows_no_orphans')
  need(all(stats[k]==v for k,v in producer['expected'].items()),'frozen_denominators')
  d={'count':len(distinct),'M1_content_tokens':sum(v[2] for v in distinct.values()),'UTF8_bytes':sum(v[1] for v in distinct.values()),'language_pass':sum(v[3] for v in distinct.values()),'arbitrary_representative_chosen':False}
  s=os.fstat(fd);need([s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]==before==ident(dbpath),'SQL_post_stat')
  return {'stats':stats,'one_EOS_per_raw_envelope_separate':stats['documents'],'raw_content_plus_EOS':stats['M1_content_tokens']+stats['documents'],'distinct_envelope_SHA_diagnostic':d,'language_pass_raw_M1_content_tokens':language_tokens,'language_pass_raw_UTF8_bytes':language_bytes,'distinct_language_pass_M1_content_tokens':sum(v[2] for v in distinct.values() if v[3]),'distinct_language_pass_EOS_separate':sum(v[3] for v in distinct.values())}
 finally:db.close();os.close(fd)
def run(p,out,check):
 b=gate(p,p['terminal_binding_path'],p['terminal_binding_SHA256']);folder=Path(p['source_output']);names=set(b['files']);required={'result.json','supervisor.json','ownership.json','screening.sqlite','screening.sqlite-journal'}
 need(names==required and {q.name for q in folder.iterdir()}==required,'exact_terminal_inventory')
 for n,x in b['files'].items():need(ident(folder/n)==x['stat'],'external_artifact_stat')
 r=load(folder/'result.json');s=load(folder/'supervisor.json');o=load(folder/'ownership.json')
 need(r['status']=='COMPLETE_PG300_ENVELOPE_M1_LANGUAGE_PROVISIONAL_NO_ADMISSION' and s['status']=='COMPLETE_PG300_ENVELOPE_DIAGNOSTICS_NO_ADMISSION' and s['worker_exit_code']==0,'complete_result_supervisor')
 need((r['profile_SHA256'],r['codepins_SHA256'])==(P,C) and (o['profile_SHA256'],o['codepins_SHA256'])==(P,C) and (o['supervisor_PID'],o['worker_PID'])==(b['supervisor_PID'],b['worker_PID']),'result_ownership_exactbinding')
 need(s['result_SHA256']==hashlib.sha256(small(folder/'result.json')).hexdigest() and s['elapsed_seconds']<=660 and s['peak_observed_RSS_bytes']<=1000000000,'producer_resource_result_link')
 hashes={}
 for name,x in b['files'].items():
  n,h=hash_file(folder/name,check);need((n,h)==(x['stat'][2],x['SHA256']),'all_output_file_SHA');hashes[name]=h
 need(set(r['artifacts'])==names-{'result.json','supervisor.json'},'producer_artifact_inventory_complete')
 for name,x in r['artifacts'].items():need(name in hashes and hashes[name]==x['SHA256'] and ident(folder/name)[2]==x['bytes'],'producer_artifact_hashes')
 need(sum(x['stat'][2] for x in b['files'].values())==s['all_output_bytes']<=192000000 and ident(folder/'screening.sqlite')[2]<=128000000 and ident(folder/'screening.sqlite-journal')[2]<=16000000,'producer_output_caps')
 producer=json.loads(small(p['producer_profile'],8000000));result=verify_sql(folder/'screening.sqlite',producer,check)
 for k in ['stats','one_EOS_per_raw_envelope_separate','raw_content_plus_EOS','distinct_envelope_SHA_diagnostic']:need(result[k]==r[k],'independent_stored_summary_matches_producer')
 for n,x in b['files'].items():need(ident(folder/n)==x['stat'],'terminal_sources_unchanged')
 absent(b['worker_PID']);absent(b['supervisor_PID'])
 return {'status':'COMPLETE_INDEPENDENT_PG300_M1_LANGUAGE_METADATA_VERIFICATION_NO_ADMISSION',**result,'output_SHA256':hashes,'source_body_reads':0,'source_UTF8_alpha_window_raw_and_projection_preimages_independently_recomputed':False,'source_token_values_independently_recomputed':False,'proof_limit':'Raw source/envelope/projection/token/alphabetic preimages inherit pinned completed reviewed producer; independently verify every stored identity/window geometry/scoring decision/top1 probability/logical transcript and all aggregate counts. No detector/tokenizer rerun.','source_rewriting_or_quality_rights_family_admission_clearance':False,'new_admitted_documents':0,'new_admitted_tokens':0}

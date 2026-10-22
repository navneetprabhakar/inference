"""Once finite preparation from closed VERIFIED metadata only; no source-body reads."""
import hashlib,json,sqlite3,subprocess
from pathlib import Path
import adapter
HERE=Path(__file__).resolve().parent;BASE=HERE.parent

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ident(p):
 s=Path(p).stat();return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
def main():
 proof=BASE/'pressbooks-full-raw-filter-terminal-parent-verification-v3/verification.json'
 if sha(proof)!='e0b28b8a4c9d751affe424343d800311912acdc39b5deeca25cb80c7e933f517':raise ValueError('independent_terminal_parent_proof_SHA')
 vp=json.loads(proof.read_text())
 if vp['status']!='PASS_ALL_COMPLETED_STORED_PB_FILTER_COUNTS_RECEIPTS_AND400_DRAWS_VERIFIED_NO_ADMISSION' or vp['exec_exit_code']!=0 or vp['all_owner_PIDs_absent'] is not True:raise ValueError('independent_complete_reaped')
 bp=BASE/'pressbooks-full-raw-filter-terminal-parent-binding-v1/binding.json';binding=json.loads(bp.read_text())
 if binding['status']!='PARENT_REVIEWED_COMPLETE_PB_FULL_FILTER_TERMINAL_BINDING' or binding['producer_exec_exit']!=0 or binding['producer_reaped'] is not True or binding['producer_owner_PIDs_absent'] is not True:raise ValueError('producer_complete_reaped')
 root=BASE/'m2-intake/pressbooks-full-raw-filter-fresh400-v1';owner=json.loads((root/'ownership.json').read_text())
 for pid in [owner['worker_PID'],owner['supervisor_PID'],31298,31300]:
  p=subprocess.run(['/bin/ps','-p',str(pid),'-o','pid='],capture_output=True,text=True,timeout=1)
  if p.returncode not in [0,1] or p.stdout.strip():raise ValueError('owner_PID_not_absent')
 for name in ['result.json','supervisor.json','ownership.json','fresh-review-selection.json']:
  if ident(root/name)!=binding['files'][name]['stat'] or sha(root/name)!=binding['files'][name]['SHA256']:raise ValueError('producer_terminal_metadata_binding')
 dbp=root/'candidate.sqlite'
 if dbp.is_symlink() or ident(dbp)!=binding['files']['candidate.sqlite']['stat']:raise ValueError('closed_candidate_DB_stat')
 db=sqlite3.connect(dbp.as_uri()+'?mode=ro&immutable=1',uri=True);db.execute('PRAGMA query_only=ON');db.execute('PRAGMA cache_size=-4096');db.execute('PRAGMA mmap_size=0')
 sourceprofile=json.loads((BASE/'pressbooks-development30-capture-preparation-v1/profile.json').read_text());frames={}
 try:
  for s in sourceprofile['sources']:
   f=s['frame'];q=Path(f['path'])
   if q.is_symlink() or ident(q)!=f['stat']:raise ValueError('closed_original_frame_stat')
   x=sqlite3.connect(q.as_uri()+'?mode=ro&immutable=1',uri=True);x.execute('PRAGMA query_only=ON');x.execute('PRAGMA cache_size=-4096');frames[s['source_id']]=x
  selection=json.loads((root/'fresh-review-selection.json').read_text())
  def lookup(sid,ordinal):
   t=db.execute('SELECT t.text_SHA256,t.UTF8_bytes,t.M1_content_tokens,t.candidate,t.fresh_population,t.first_source,t.first_ordinal,o.line_offset,o.line_bytes,o.line_SHA256,o.source_flags,o.identity_holds,o.lead_status FROM texts t JOIN occurrences o ON o.text_SHA256=t.text_SHA256 AND o.source_id=t.first_source AND o.ordinal=t.first_ordinal WHERE t.first_source=? AND t.first_ordinal=?',(sid,ordinal)).fetchall()
   if len(t)!=1 or t[0][3:7]!=(1,1,sid,ordinal):raise ValueError('selected_closed_fresh_candidate')
   t=t[0];r=frames[sid].execute('SELECT ordinal,line_offset,line_bytes,ends_LF,line_SHA256,flags,text_SHA256,text_UTF8_bytes FROM records WHERE ordinal=?',(ordinal,)).fetchone()
   if r is None or (r[1],r[2],r[4],r[5],r[6],r[7])!=(t[7],t[8],t[9],t[10],t[0],t[1]):raise ValueError('original_frame_candidate_locator_hash_metadata')
   return {'source_id':sid,'ordinal':ordinal,'line_offset':r[1],'line_bytes':r[2],'ends_LF':r[3],'line_SHA256':r[4].hex(),'text_SHA256':r[6].hex(),'text_UTF8_bytes':r[7],'existing_flags':r[5],'identity_holds':t[11],'lead_status':t[12]}
  derived=adapter.adapt(selection,lookup)
  if derived['stats']['unique_raw_SHA']!=398 or derived['stats']['text_UTF8_bytes']!=10563953 or derived['stats']['max_text_UTF8_bytes']!=958137:raise ValueError('actual_terminal_expected_capture_cost')
  if ident(dbp)!=binding['files']['candidate.sqlite']['stat']:raise ValueError('candidate_DB_changed')
  for s in sourceprofile['sources']:
   if ident(s['frame']['path'])!=s['frame']['stat']:raise ValueError('original_frame_changed')
 finally:
  db.close()
  for x in frames.values():x.close()
 data=(json.dumps(derived,ensure_ascii=False,indent=2)+'\n').encode()
 if len(data)>8000000:raise ValueError('derived_capture_selection_metadata_cap')
 target=HERE/'selection.json'
 with target.open('xb') as f:f.write(data)
 evidence={'status':'COMPLETE_FINITE_CLOSED_METADATA_BINDING_NO_SOURCE_BODY_READ','parent_independent_proof':{'path':str(proof),'SHA256':sha(proof)},'producer_binding':{'path':str(bp),'SHA256':sha(bp)},'candidate_DB':{'path':str(dbp),'stat':binding['files']['candidate.sqlite']['stat'],'inherited_verified_SHA256':binding['files']['candidate.sqlite']['SHA256']},'source_selection':{'path':str(root/'fresh-review-selection.json'),'SHA256':sha(root/'fresh-review-selection.json')},'derived_selection_SHA256':sha(target),'derived_selection_bytes':len(data),'stats':derived['stats'],'source_body_reads':0,'all_draw_roles_preserved':True}
 with (HERE/'metadata-binding.json').open('x') as f:f.write(json.dumps(evidence,indent=2)+'\n')
 print(json.dumps(evidence))
if __name__=='__main__':main()

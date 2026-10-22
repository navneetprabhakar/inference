"""Terminal-only read-only union verification; copies journaled DBs before recovery."""
import pathlib,sqlite3,json,hashlib,shutil,sys,time,resource,os
BASE=pathlib.Path(__file__).resolve().parents[1]
PREP=BASE/'wikibooks-residual-render-preparation-v2'
ROOT=BASE/'m2-intake/wikibooks-residual-render-v1'
OUT=BASE/'m2-intake/wikibooks-residual-render-v1-verification-v1'
PROFILE_SHA='11f603b8a75fa422b17d2b64a0e4848129e75bb9a9ec519ce5a7dc18f1893ee1'
CODE_SHA='e080aba6067325530745bf06610dec8d5e5c64c40d711b220a7aaa41762a2e66'
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def ro(p):return sqlite3.connect('file:'+str(p.resolve())+'?mode=ro',uri=True)
def size(p):return sum(f.stat().st_size for f in p.rglob('*') if f.is_file())
def clk():return time.clock_gettime(time.CLOCK_MONOTONIC)
def main():
 start=clk()
 if not (ROOT/'joint-result.json').exists():raise RuntimeError('joint_profile_not_terminal')
 sys.path.insert(0,str(PREP));import profile,code_guard
 code_guard.verify(CODE_SHA);os.environ['WIKIBOOKS_EFFECTIVE_PROFILE']=str(PREP/'effective-inputs.json');os.environ['WIKIBOOKS_EFFECTIVE_PROFILE_SHA256']=PROFILE_SHA;p=profile.load()
 OUT.mkdir(exist_ok=False)
 def guard(add=0):
  if clk()-start>=900:raise RuntimeError('verification900sec')
  rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
  if rss>1_000_000_000:raise RuntimeError('verificationRSS1GB')
  if size(OUT)+add>1_000_000_000:raise RuntimeError('verification_output1GB')
  if shutil.disk_usage(OUT).free<20*1024**3+16_000_000_000+add:raise RuntimeError('verification_free_weights_reserve')
 original={str(f.relative_to(ROOT)):{'bytes':f.stat().st_size,'sha256':sha(f)} for f in ROOT.rglob('*') if f.is_file()};(OUT/'original-file-hashes.json').write_text(json.dumps(original,indent=2,sort_keys=True)+'\n')
 c=ro(p['canonical_path']);expected={o for o, in c.execute('select source_ordinal from candidates')};seen=set();inputs=[]
 for item in p['prior_shards']:
  source=pathlib.Path(item['path']);d=ro(source);ids={o for o, in d.execute('select source_ordinal from rendered')};d.close()
  if ids&seen or sha(source)!=item['sha256']:raise RuntimeError('prior_evidence_changed')
  seen|=ids;inputs.append({'path':str(source),'sha256':item['sha256'],'rows':len(ids),'type':'prior_verified_immutable_recovered_copy'})
 prior=set(seen);new=set();results=[];totalblocks=0;new_characters=0;new_UTF8_bytes=0
 for job in p['jobs_loaded']:
  n=job['job'];targets=set(job['ordinals']);folder=ROOT/('shard-'+str(n));source=folder/'rendered.sqlite3'
  if not source.exists():results.append({'job':n,'status':'NOT_STARTED','rows':0,'missing':len(job['ordinals'])});continue
  before=sha(source);journal=pathlib.Path(str(source)+'-journal');dbpath=source
  if journal.exists():
   guard(source.stat().st_size+journal.stat().st_size+1_048_576);q=OUT/('job-'+str(n));q.mkdir();dbpath=q/'recovered.sqlite3';shutil.copy2(source,dbpath);shutil.copy2(journal,pathlib.Path(str(dbpath)+'-journal'));recovery=sqlite3.connect(dbpath);recovery.execute('pragma integrity_check').fetchone();recovery.close()
  d=ro(dbpath)
  if d.execute('pragma integrity_check').fetchone()[0]!='ok':raise RuntimeError('source_integrity')
  w=json.loads((folder/'worker-result.json').read_text());s=json.loads((folder/'supervisor-result.json').read_text());count=0;blocks=0;ids=[]
  if sha(folder/'worker-result.json')!=s.get('worker_result_sha256'):raise RuntimeError('worker_receipt_binding')
  bc=iter(d.execute('select source_ordinal,ordinal,kind,hash,characters,start,end from blocks order by source_ordinal,ordinal'));b=next(bc,None)
  for ordinal,page,rev,family,payload in d.execute('select source_ordinal,page_id,revision_id,family,data from rendered order by source_ordinal'):
   guard()
   if ordinal in seen or ordinal not in targets:raise RuntimeError('rerender_extra_or_duplicate')
   e=json.loads(c.execute('select data from candidates where source_ordinal=?',(ordinal,)).fetchone()[0]);r=json.loads(payload);text=r['text']
   if (page,rev,family)!=(e['page_id'],e['revision_id'],e['family_id']):raise RuntimeError('identity_family_mismatch')
   for k in ['record_sha256','html_sha256','wikitext_sha256','title','url','license_original_metadata','archive_sha256','line','member_ordinal']:
    if r[k]!=e[k]:raise RuntimeError('source_provenance_changed:'+k)
   if hashlib.sha256(text.encode()).hexdigest()!=r['extracted_text_sha256'] or len(text)!=r['text_unicode_characters'] or len(text.encode())!=r['text_UTF8_bytes'] or r['training_admitted'] is not False:raise RuntimeError('text_hash_or_admission_mismatch')
   index=0;end=0
   while b is not None and b[0]==ordinal:
    _,i,kind,h,chars,a,z=b
    if i!=index or a!=(0 if index==0 else end+2) or z<a or chars!=z-a or z>len(text) or hashlib.sha256(text[a:z].encode()).hexdigest()!=h:raise RuntimeError('block_offset_or_hash_mismatch')
    if index and text[end:a]!='\n\n':raise RuntimeError('separator_mismatch')
    end=z;index+=1;blocks+=1;b=next(bc,None)
   if end!=len(text) or (b is not None and b[0]<ordinal):raise RuntimeError('block_coverage_mismatch')
   ids.append(ordinal);seen.add(ordinal);new.add(ordinal);count+=1;new_characters+=len(text);new_UTF8_bytes+=len(text.encode())
  if b is not None:raise RuntimeError('orphan_blocks')
  if ids!=job['ordinals'][:len(ids)]:raise RuntimeError('not_exact_job_candidate_prefix')
  d.close();verifiedsha=sha(dbpath)
  if sha(source)!=before:raise RuntimeError('original_DB_mutated')
  complete=w['status']=='COMPLETE_CANONICAL_RENDER_SHARD_NO_ADMISSION' and s['status']=='COMPLETE_CANONICAL_RENDER_SHARD_NO_ADMISSION'
  if complete and (count!=len(job['ordinals']) or w['inventory_sha256']!=before or w['stats']['committed_rendered']!=count):raise RuntimeError('false_worker_completion')
  if n==8 and complete and not (w['stats']['gzip_eof_crc_verified'] and w['stats']['tar_end_blocks_verified']):raise RuntimeError('last_job_source_EOF_missing')
  inputs.append({'path':str(dbpath.resolve()),'sha256':verifiedsha,'rows':count,'type':'new_verified_residual','job':n});results.append({'job':n,'rows':count,'blocks_verified':blocks,'complete':complete,'worker':w,'supervisor':s,'missing':len(job['ordinals'])-count,'original_DB_sha256':before,'verified_DB_sha256':verifiedsha});totalblocks+=blocks
 for rel,meta in original.items():
  f=ROOT/rel
  if f.stat().st_size!=meta['bytes'] or sha(f)!=meta['sha256']:raise RuntimeError('original_terminal_evidence_changed')
 joint=json.loads((ROOT/'joint-result.json').read_text())
 for wave in joint.get('waves',[]):
  wp=ROOT/('wave-'+str(wave['wave'])+'-result.json')
  if sha(wp)!=wave['receipt_sha256']:raise RuntimeError('joint_wave_receipt_binding')
  wr=json.loads(wp.read_text())
  if sha(ROOT/'aggregate-ledger.json')!=wr['aggregate_ledger_sha256'] and wave['wave']==joint['waves'][-1]['wave']:raise RuntimeError('final_wave_ledger_binding')
  for jobid,jr in wr.get('shards',{}).items():
   if sha(ROOT/('shard-'+jobid)/'supervisor-result.json')!=jr['receipt_sha256']:raise RuntimeError('wave_supervisor_receipt_binding')
 ledger=json.loads((ROOT/'aggregate-ledger.json').read_text())
 if sum(r['reserved_seconds'] for r in ledger['attempts'].values())>7200 or len(ledger['attempts'])>8:raise RuntimeError('reserved_budget_exceeded')
 oldroot=BASE/'m2-intake/wikibooks-sharded-render-v2';oldhashes=json.loads((BASE/'m2-intake/wikibooks-sharded-render-v2-verification-v1/original-file-hashes.json').read_text())
 for rel,meta in oldhashes.items():
  f=oldroot/rel
  if f.stat().st_size!=meta['bytes'] or sha(f)!=meta['sha256']:raise RuntimeError('original50457source_evidence_mutated')
 full=seen==expected and all(r.get('complete') for r in results) and joint['status']=='COMPLETE_EIGHT_RESIDUAL_JOBS_PROVISIONAL_NO_ADMISSION'
 receipt={'status':'COMPLETE_VERIFIED_CANONICAL_RENDER_UNION_PROVISIONAL_NO_ADMISSION' if full else 'PARTIAL_VERIFIED_CANONICAL_RENDER_UNION_NO_ADMISSION','prior_rows':len(prior),'new_rows':len(new),'combined_rows':len(seen),'expected_rows':len(expected),'missing':len(expected-seen),'extra':len(seen-expected),'disjoint_union_verified':True,'all_new_source_provenance_and_text_hashes_verified':True,'new_block_offsets_hashes_verified':totalblocks,'new_rendered_characters':new_characters,'new_rendered_UTF8_bytes':new_UTF8_bytes,'lengths_are_not_tokens':True,'original_terminal_evidence_unchanged':True,'canonical_sha256':p['canonical_sha256'],'profile_sha256':PROFILE_SHA,'code_pins_sha256':CODE_SHA,'verified_input_databases':inputs,'jobs':results,'elapsed_seconds':clk()-start,'new_admitted_documents':0,'new_admitted_tokens':0}
 guard(1_048_576);(OUT/'verification.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n');(OUT/'remaining-ordinals.json').write_text(json.dumps(sorted(expected-seen))+'\n');print(json.dumps({k:v for k,v in receipt.items() if k not in ['verified_input_databases','jobs']}))
if __name__=='__main__':main()

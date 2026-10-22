"""Read-only terminal verification; accepts partial evidence without completion claim."""
import collections,hashlib,json,pathlib,sqlite3,time,shutil,os
BASE=pathlib.Path(__file__).resolve().parents[1]
ROOT=BASE/'m2-intake/wikibooks-sharded-render-v2'
CANONICAL=BASE/'m2-intake/wikibooks-canonical-candidates-v1/canonical.sqlite3'
OUT=BASE/'m2-intake/wikibooks-sharded-render-v2-verification-v1'
SHA='7ff5023543d3f69ce1963ee0b0f7e15fc60eaad6e28896aa7556251dd379a6bd'
RANGES={1:(1,22488),2:(22489,44976),3:(44977,67464),4:(67465,89951)}
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def ro(p):return sqlite3.connect('file:'+str(p.resolve())+'?mode=ro',uri=True)
def main():
 started=time.clock_gettime(time.CLOCK_MONOTONIC)
 if not (ROOT/'joint-result.json').exists():raise RuntimeError('joint_not_terminal')
 if sha(CANONICAL)!=SHA:raise RuntimeError('canonical_hash_changed')
 OUT.mkdir(exist_ok=False)
 if shutil.disk_usage(OUT).free < 20*1024**3+16_000_000_000+1_000_000_000:raise RuntimeError('free_space_weights_reservation')
 preserved={}
 for f in ROOT.rglob('*'):
  if f.is_file():preserved[str(f.relative_to(ROOT))]={'bytes':f.stat().st_size,'sha256':sha(f)}
 (OUT/'original-file-hashes.json').write_text(json.dumps(preserved,sort_keys=True,indent=2)+'\n')
 joint=json.loads((ROOT/'joint-result.json').read_text());ledger=json.loads((ROOT/'aggregate-ledger.json').read_text())
 c=ro(CANONICAL);expected={r[0] for r in c.execute('select source_ordinal from candidates')}
 seen=set();results=[];block_total=0
 for n in range(1,5):
  p=ROOT/('shard-'+str(n));original=p/'rendered.sqlite3';before=sha(original);q=OUT/('shard-'+str(n));q.mkdir();dbpath=q/'recovered.sqlite3'
  if sum(f.stat().st_size for f in OUT.rglob('*') if f.is_file())+original.stat().st_size+2_000_000>1_000_000_000:raise RuntimeError('verification_output_cap')
  shutil.copy2(original,dbpath)
  journal=pathlib.Path(str(original)+'-journal')
  if journal.exists():shutil.copy2(journal,pathlib.Path(str(dbpath)+'-journal'))
  recovered=sqlite3.connect(dbpath);recovered.execute('pragma integrity_check').fetchone();recovered.close();d=ro(dbpath)
  if d.execute('pragma integrity_check').fetchone()[0]!='ok':raise RuntimeError('sqlite_integrity')
  worker=json.loads((p/'worker-result.json').read_text());supervisor=json.loads((p/'supervisor-result.json').read_text());count=0;blocks=0
  bc=iter(d.execute('select source_ordinal,ordinal,kind,hash,characters,start,end from blocks order by source_ordinal,ordinal'));b=next(bc,None)
  for ordinal,page,rev,family,payload in d.execute('select source_ordinal,page_id,revision_id,family,data from rendered order by source_ordinal'):
   if time.clock_gettime(time.CLOCK_MONOTONIC)-started>900:raise RuntimeError('verification_900sec_bound')
   lo,hi=RANGES[n]
   if not lo<=ordinal<=hi or ordinal in seen or ordinal not in expected:raise RuntimeError('union_or_range_mismatch')
   r=json.loads(payload);e=json.loads(c.execute('select data from candidates where source_ordinal=?',(ordinal,)).fetchone()[0]);text=r['text']
   if (page,rev,family)!=(e['page_id'],e['revision_id'],e['family_id']):raise RuntimeError('identity_family_mismatch')
   for k in ['record_sha256','html_sha256','wikitext_sha256','title','url','license_original_metadata','archive_sha256','line','member_ordinal']:
    if r[k]!=e[k]:raise RuntimeError('source_provenance_changed:'+k)
   if hashlib.sha256(text.encode()).hexdigest()!=r['extracted_text_sha256'] or len(text)!=r['text_unicode_characters'] or len(text.encode())!=r['text_UTF8_bytes']:raise RuntimeError('text_hash_length_mismatch')
   if r['training_admitted'] is not False:raise RuntimeError('unexpected_admission')
   end=0;index=0
   while b is not None and b[0]==ordinal:
    _,i,kind,h,chars,start,stop=b
    if i!=index or start!=(0 if index==0 else end+2) or stop<start or chars!=stop-start or stop>len(text):raise RuntimeError('block_offset_mismatch')
    if index and text[end:start]!='\n\n':raise RuntimeError('block_separator_mismatch')
    if hashlib.sha256(text[start:stop].encode()).hexdigest()!=h:raise RuntimeError('block_hash_mismatch')
    end=stop;index+=1;blocks+=1;b=next(bc,None)
   if end!=len(text):raise RuntimeError('block_coverage_mismatch')
   if b is not None and b[0]<ordinal:raise RuntimeError('orphan_block')
   seen.add(ordinal);count+=1
  if b is not None:raise RuntimeError('orphan_block_at_EOF')
  d.close()
  recovered_sha=sha(dbpath)
  if sha(original)!=before:raise RuntimeError('input_mutated')
  complete=worker['status']=='COMPLETE_CANONICAL_RENDER_SHARD_NO_ADMISSION'
  if complete and worker.get('inventory_sha256')!=before:raise RuntimeError('worker_hash_mismatch')
  if worker.get('stats',{}).get('committed_rendered') is not None and worker['stats']['committed_rendered']!=count:raise RuntimeError('worker_count_mismatch')
  if supervisor.get('worker_result_sha256') and sha(p/'worker-result.json')!=supervisor['worker_result_sha256']:raise RuntimeError('supervisor_worker_receipt_hash_mismatch')
  subset={o for o in expected if RANGES[n][0]<=o<=RANGES[n][1]}
  if complete and count!=len(subset):raise RuntimeError('false_complete_shard')
  results.append({'shard':n,'rows':count,'blocks':blocks,'original_sqlite_sha256':before,'recovered_sqlite_sha256':recovered_sha,'recovered_path':str(dbpath.resolve()),'worker':worker,'supervisor':supervisor,'complete':complete,'missing_candidates':len(subset)-count});block_total+=blocks
 full=seen==set(expected) and all(r['complete'] and r['supervisor']['status']=='COMPLETE_CANONICAL_RENDER_SHARD_NO_ADMISSION' for r in results) and joint['status']=='COMPLETE_FOUR_RENDER_SHARDS_PROVISIONAL_NO_ADMISSION'
 out={'status':'INDEPENDENT_COMPLETE_PROVISIONAL_RENDER_UNION' if full else 'INDEPENDENT_PARTIAL_RENDER_UNION','canonical_sha256':SHA,'expected_candidates':len(expected),'actual_union_rows':len(seen),'missing_candidates':len(set(expected)-seen),'extra_candidates':len(seen-set(expected)),'block_offset_hash_checks':block_total,'exact_disjoint_union':True,'all_source_provenance_fields_match':True,'input_shards_unchanged':True,'joint':joint,'aggregate_ledger':ledger,'shards':results,'elapsed_seconds':time.clock_gettime(time.CLOCK_MONOTONIC)-started,'admitted_documents':0,'admitted_tokens':0}
 for relative,meta in preserved.items():
  f=ROOT/relative
  if f.stat().st_size!=meta['bytes'] or sha(f)!=meta['sha256']:raise RuntimeError('original_evidence_mutated:'+relative)
 out['original_file_hashes_sha256']=sha(OUT/'original-file-hashes.json')
 missing=sorted(set(expected)-seen)
 with open(OUT/'missing-canonical-ordinals.jsonl','x') as f:
  for ordinal in missing:
   e=json.loads(c.execute('select data from candidates where source_ordinal=?',(ordinal,)).fetchone()[0]);f.write(json.dumps({'source_ordinal':ordinal,'page_id':e['page_id'],'revision_id':e['revision_id'],'record_sha256':e['record_sha256'],'member_ordinal':e['member_ordinal'],'line':e['line'],'member_uncompressed_byte_offset':e['member_uncompressed_byte_offset']},sort_keys=True)+'\n')
 out['missing_manifest_sha256']=sha(OUT/'missing-canonical-ordinals.jsonl')
 outpath=OUT/'independent-union-block-verification.json'
 with open(outpath,'x') as f:json.dump(out,f,sort_keys=True,indent=2);f.write('\n')
 print(json.dumps({k:v for k,v in out.items() if k not in ['joint','aggregate_ledger','shards']}))
if __name__=='__main__':main()

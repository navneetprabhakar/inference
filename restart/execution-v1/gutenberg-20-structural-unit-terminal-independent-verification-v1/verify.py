"""One bounded20-book stored-span verification; no parser/segmentation rerun."""
import os,stat,signal,time,resource,json,hashlib,re,collections
from pathlib import Path
START=time.monotonic()
def alarm(*a):raise TimeoutError('independent120sec')
signal.signal(signal.SIGALRM,alarm);signal.setitimer(signal.ITIMER_REAL,115)
BASE=Path(__file__).resolve().parents[1];OUT=Path(__file__).resolve().parent
P='343b86e3f450ad1a912bd2dbe9cebd8d7b8d5058d97d44e4ea80483c94e58840';C='58ddf45df9cfd5e34338485185cc982298eda95dbaa1d0b75a3773adffc627e3'
sha=lambda b:hashlib.sha256(b).hexdigest()
def need(v,m):
 if not v:raise ValueError(m)
def check():need(time.monotonic()-START<115,'clock');need(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss<=1000000000,'processRSS')
def ident(p):
 s=p.stat(follow_symlinks=False);need(stat.S_ISREG(s.st_mode),'regular_source');return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
def read(p,cap,expected=None):
 check();before=ident(p);need(before[2]<=cap and not p.is_symlink() and p.resolve()==p,'bounded_canonical_regular');need(expected is None or before==expected,'source_pinned_stat');fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
 try:
  s=os.fstat(fd);need([s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]==before,'FDstat');chunks=[];n=0
  while True:
   check();v=os.read(fd,min(1048576,cap-n+1))
   if not v:break
   n+=len(v);need(n<=cap,'read_cap');chunks.append(v)
  s=os.fstat(fd);need([s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]==before==ident(p),'poststat')
 finally:os.close(fd)
 return b''.join(chunks),before
def verify_span(raw,s):
 a,z=s['start_byte'],s['end_byte'];need(type(a) is int and type(z) is int and 0<=a<=z<=len(raw) and s['bytes']==z-a and s['SHA256']==sha(raw[a:z]),'span_hash_bounds')
 if 'start_character' in s:need(raw[:a].decode('utf8').__len__()==s['start_character'] and raw[:z].decode('utf8').__len__()==s['end_character'],'char_byte_span')
 return a,z
def controls():
 raw='éabc'.encode();good={'start_byte':2,'end_byte':5,'bytes':3,'SHA256':sha(b'abc'),'start_character':1,'end_character':4};verify_span(raw,good);n=1
 for key,v in [('SHA256','0'*64),('bytes',99),('start_character',2),('end_byte',6)]:
  bad={**good,key:v}
  try:verify_span(raw,bad)
  except (ValueError,UnicodeError):n+=1
  else:raise AssertionError('span_mutation_accepted')
 return n
def main():
 controls_count=controls();prep=BASE/'gutenberg-20-structural-unit-preparation-v1';profilepath=prep/'profile.json';praw,_=read(profilepath,8000000);need(sha(praw)==P,'profile_pin');p=json.loads(praw);registryraw,_=read(prep/'code-pins.json',8000000);need(sha(registryraw)==C,'registry_pin');registry=json.loads(registryraw)['SHA256']
 for f,h in registry.items():v,_=read(Path(f),8000000);need(sha(v)==h,'input_code_pin')
 folder=Path(p['output']);rraw,rstat=read(folder/'result.json',1048576);need(sha(rraw)=='707e193aab282a9b0dfccad66da962785e6f02899d956ad00b393d857df3fce7','parent_external_result_pin');r=json.loads(rraw);sraw,sstat=read(folder/'supervisor.json',1048576);sup=json.loads(sraw);oraw,ostat=read(folder/'ownership.json',10000);owner=json.loads(oraw)
 need(r['status']==sup['status']=='COMPLETE_PG20_STRUCTURAL_UNIT_DISCOVERY_NO_ADMISSION' and sup['worker_exit_code']==0 and sup['result_SHA256']==sha(rraw),'terminal_receipts');need((owner['supervisor_PID'],owner['worker_PID'])==(45265,45266) and (owner['profile_SHA256'],owner['codepins_SHA256'])==(P,C) and (r['profile_SHA256'],r['codepins_SHA256'])==(P,C),'ownership_policy')
 for pid in [45265,45266]:
  try:os.kill(pid,0)
  except ProcessLookupError:pass
  else:raise ValueError('owner_live_or_reused')
 metadata,mstat=read(folder/'records.jsonl',12000000);need(len(metadata)==454468 and sha(metadata)==r['records_SHA256']=='a93a34fe28a113226c93b267d1655c53c02d153e863132ef156963f9654a997f','metadata_exact_pin');lines=metadata.splitlines(keepends=True);need(len(lines)==20 and all(v.endswith(b'\n') for v in lines),'complete20JSONL')
 stats=collections.Counter();structured=[];books=[];sources=[]
 for line,rec,src,e in zip(lines,p['records'],p['source_files'],p['envelopes']):
  check();x=json.loads(line);need((x['ordinal'],x['ebook_ID'],x['catalog_record_all_roles_preserved'],x['source_file'])==(rec['ordinal'],rec['ebook_ID'],rec,src),'exact20selection_source');d=x['structural_discovery'];rawpath=Path(p['source_output'])/src['path'];raw,st=read(rawpath,2400000,src['dev_ino_size_mtime_ns_ctime_ns']);need(len(raw)==src['bytes']==d['raw_bytes'] and sha(raw)==src['SHA256']==d['source_raw_SHA256'],'whole_source_SHA');raw.decode('utf8');need(d['envelope']==e and sha(raw[e['start_byte']:e['end_byte']])==e['SHA256'] and e['end_byte']-e['start_byte']==e['bytes'],'exact_envelope');sources.append((rawpath,st))
  parts=d['parts'];need(parts and parts[0]['start_byte']==0 and parts[-1]['end_byte']==len(raw),'source_full_partition_endpoints');pos=0;reconstruction=hashlib.sha256()
  for part in parts:
   a,z=verify_span(raw,part);need(a==pos,'source_partition_contiguous');pos=z;reconstruction.update(raw[a:z])
  need(reconstruction.hexdigest()==sha(raw) and sum(q['bytes'] for q in parts)==len(raw),'independent_full_inverse')
  unitids=set()
  for u in d['units']:
   a,z=verify_span(raw,u);need(any((q['start_byte'],q['end_byte'],q['SHA256'])==(a,z,u['SHA256']) for q in parts),'unit_is_whole_partition_part');need(u['unit_ID']==f"pg{x['ebook_ID']}:{sha(raw)}:{a}-{z}" and u['unit_ID'] not in unitids,'unit_identity');unitids.add(u['unit_ID']);need(u['semantic_completeness']=='UNASSESSED' and u['whole_book_family_lineage_required'] is True,'no_semantic_family_clearance')
  for key in ['chapter_heading_candidates','unsupported_chapter_like_lines','structure_heading_hints','literal_ending_hints','note_dependency_hints']:
   for hint in d[key]:verify_span(raw,hint)
  for note in d['note_dependency_hints']:
   a,z=note['start_byte'],note['end_byte'];need(note['overlapping_unit_IDs']==[u['unit_ID'] for u in d['units'] if u['start_byte']<z and a<u['end_byte']] and note['definition_extent_or_reference_resolution_proven'] is False,'exact_note_overlap_unresolved')
  fallback=bool(d['chapter_sequence_holds']);need(d['whole_envelope_fallback']==fallback and d['full_inverse_verified'] and d['notes_front_endmatter_or_editorial_removed']==d['source_bytes_rewritten']==0,'fallback_immutable')
  if fallback:need(len(d['units'])==1 and (d['units'][0]['start_byte'],d['units'][0]['end_byte'])==(e['start_byte'],e['end_byte']) and d['units'][0]['structural_status']=='WHOLE_ENVELOPE_FALLBACK_NOT_CHAPTER_AUDIT_UNIT','whole_fallback_preserved')
  else:
   heads=d['chapter_heading_candidates'];need(len(heads)>=2 and [q['number'] for q in heads]==list(range(1,len(heads)+1)) and len({q['number_style'] for q in heads})==1 and len(heads)==len(d['units']),'consecutive_chapter_candidates')
   for h,u in zip(heads,d['units']):need(u['heading_span']==h and u['start_byte']==h['start_byte'] and u['chapter_number']==h['number'],'unit_heading_binding')
   structured.append({'ebook_ID':x['ebook_ID'],'frozen_ordinal':x['ordinal'],'source_raw_SHA256':sha(raw),'source_path':str(rawpath),'chapter_candidate_count':len(d['units']),'first_unit':d['units'][0],'last_unit':d['units'][-1]})
  stats['books']+=1;stats['whole_envelope_fallbacks']+=fallback;stats['chapter_candidate_units']+=0 if fallback else len(d['units']);stats['envelope_bytes']+=e['bytes'];stats['raw_source_bytes']+=len(raw);stats['units_including_fallbacks']+=len(d['units']);stats['events']+=sum(len(d[k]) for k in ['chapter_heading_candidates','unsupported_chapter_like_lines','structure_heading_hints','literal_ending_hints','note_dependency_hints']);books.append({'ordinal':rec['ordinal'],'ebook_ID':rec['ebook_ID'],'raw_SHA256':sha(raw),'parts_verified':len(parts),'units_verified':len(d['units']),'fallback':fallback,'holds':d['chapter_sequence_holds']})
 need(dict(stats)==r['stats'] and len(structured)==7 and stats['units_including_fallbacks']==233,'independent_exact_totals')
 for name,x in r['artifacts'].items():v,_=read(folder/name,12000000);need((len(v),sha(v))==(x['bytes'],x['SHA256']),'producer_artifact_pin')
 need(sum(q.stat().st_size for q in folder.iterdir())==sup['all_output_bytes']<=16000000 and sup['elapsed_seconds']<=120 and sup['peak_observed_RSS_bytes']<=1000000000,'producer_caps')
 for q,st in sources:need(ident(q)==st,'source_final_stat')
 for name,st in [('result.json',rstat),('supervisor.json',sstat),('ownership.json',ostat),('records.jsonl',mstat)]:need(ident(folder/name)==st,'metadata_final_stat')
 check();proof={'status':'COMPLETE_INDEPENDENT_PG20_STORED_SPAN_AND_SOURCE_INVERSE_VERIFICATION_NO_ADMISSION','profile_SHA256':P,'codepins_SHA256':C,'result_SHA256':sha(rraw),'supervisor_SHA256':sha(sraw),'records_SHA256':sha(metadata),'synthetic_span_mutation_controls':controls_count,'stats':dict(stats),'structured_books':structured,'all20_books':books,'source_bytes_independently_hashed':stats['raw_source_bytes'],'source_body_segmentation_reexecuted':False,'semantic_whole_read_or_quality_certification':False,'all20_raw_fullbyte_and_character_inverse':True,'notes_front_endmatter_retained':True,'elapsed_seconds':time.monotonic()-START,'process_peak_RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'new_admitted_documents':0}
 data=(json.dumps(proof,ensure_ascii=False,indent=2)+'\n').encode();need(len(data)<=16000000,'proof_output_cap');(OUT/'verification.json').write_bytes(data);print(json.dumps({'status':proof['status'],'stats':dict(stats),'structured_books':[(x['ebook_ID'],x['chapter_candidate_count']) for x in structured],'proof_SHA256':sha(data),'elapsed_seconds':proof['elapsed_seconds']}))
if __name__=='__main__':main()

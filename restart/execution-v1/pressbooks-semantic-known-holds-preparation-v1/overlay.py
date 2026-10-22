"""Exact SHA additive diagnostic overlay. Metadata only; never admits or edits text."""
import collections,hashlib,json,sqlite3,os
from pathlib import Path

def require(ok,why):
 if not ok:raise ValueError(why)
def build_reviews(uniform,byte):
 require(uniform['status']=='COMPLETE_20_WHOLE_UNIFORM_DEVELOPMENT_UNITS_READ','uniform_whole_status')
 require(byte['status']=='COMPLETE_FINITE_TEN_UNIT_TEAM_WHOLE_REVIEW_NO_ADMISSION','byte_whole_status')
 rows=[]
 for mode,reviews in [('uniform',uniform['reviews']),('UTF8_BYTE_weighted',byte['units'])]:
  for r in reviews:
   whole=r.get('whole_text_read') if mode=='uniform' else r.get('whole_review_completed_by_team')
   require(whole is True and not r.get('tool_output_truncated',False),'review_incomplete')
   h=r['text_SHA256'];require(len(h)==64 and bytes.fromhex(h).hex()==h,'review_textSHA')
   verdict=r.get('development_verdict',r.get('verdict'))
   require(isinstance(verdict,str) and (verdict.startswith('HOLD') or verdict.startswith(('PASS_RESEARCH_QUALITY_PROXY','READABLE_COHERENT_'))),'unrecognized_verdict')
   rows.append({'source_id':r['source_id'],'ordinal':r['ordinal'],'text_SHA256':h,'text_UTF8_bytes':r.get('UTF8_bytes',r.get('text_UTF8_bytes')),'review_mode':mode,'draw':r.get('uniform_draw',r.get('byte_weighted_draws',[{}])[0].get('draw')),'verdict':verdict,'semantic_hold':verdict.startswith('HOLD'),'evidence':r.get('evidence',r.get('assessment'))})
 require(len(rows)==30 and len({(r['review_mode'],r['draw']) for r in rows})==30,'exact30_draw_roles')
 require(sum(r['review_mode']=='uniform' for r in rows)==20,'exact20_uniform')
 require(len({r['text_SHA256'] for r in rows})==30,'actual30_unique_no_silent_dedup')
 return rows

def aggregate(rows,reviews,emit,check,expected,measurements=None):
 """Rows sid,ordinal,lineSHA,textSHA,UTF8bytes,oldflags,identityholds,leadstatus."""
 seen={};old=set();new={bytes.fromhex(r['text_SHA256']):r for r in reviews if r['semantic_hold']}
 targets={(r['source_id'],r['ordinal']):r for r in reviews};observed=set();raw=0;rawold=0;rawnew=0;both=0
 sourcecounts=collections.Counter();copycounts=collections.Counter();prior_id=None
 for sid,ordinal,line,h,n,flags,holds,lead in rows:
  check();key=(sid,ordinal)
  require(prior_id is None or key>prior_id,'ordered_unique_occurrence');prior_id=key
  require(type(sid)==int and sid>0 and type(ordinal)==int and ordinal>0,'identity')
  require(isinstance(line,bytes) and len(line)==32 and isinstance(h,bytes) and len(h)==32,'native_hash_lengths')
  require(type(n)==int and n>=0 and type(holds)==int and holds>=0,'nonnegative_metadata')
  if key in targets:
   r=targets[key];require(h.hex()==r['text_SHA256'] and n==r['text_UTF8_bytes'],'review_occurrence_exactSHA_bytes');observed.add(key)
  if h in seen:require(seen[h]['UTF8_bytes']==n,'sameSHA_length_contradiction')
  else:seen[h]={'UTF8_bytes':n,'raw_occurrences':0,'prior_identity_hold_bits':0,'source_flags':0}
  v=seen[h];v['raw_occurrences']+=1;v['prior_identity_hold_bits']|=holds;v['source_flags']|=flags
  raw+=1;sourcecounts[sid]+=1;copycounts[h]+=1
  rawold+=bool(holds);rawnew+=h in new;both+=bool(holds) and h in new
  if holds:old.add(h)
  require(raw<=expected['raw_rows'],'raw_row_cap')
 require(raw==expected['raw_rows'] and len(seen)==expected['distinct_textSHA'] and len(old)==expected['prior_held_distinct_textSHA'],'full_metadata_count_reconciliation')
 require(observed==set(targets) and set(new)<=set(seen),'all30_review_source_bindings')
 diagnostics={}
 if measurements is not None:
  measured=set();normalized={};diag=collections.defaultdict(lambda:{'distinct_textSHA':0,'M1_content_tokens':0,'UTF8_bytes':0,'raw_occurrences':0})
  for h,n,tokens,passed,occurrences,holds,flags,norm,words in measurements:
   check();require(h in seen and h not in measured,'measurement_SHA_bijection');measured.add(h);v=seen[h]
   require(n==v['UTF8_bytes'] and occurrences==v['raw_occurrences'] and holds==v['prior_identity_hold_bits'] and flags==v['source_flags'],'measurement_family_metadata_exact')
   require(type(tokens)==int and tokens>=0 and passed in [0,1],'measurement_values')
   v['M1_content_tokens']=tokens;v['stored_language_pass']=passed
   require(isinstance(norm,bytes) and len(norm)==32 and type(words)==int and words>=0,'normalized_metadata')
   if passed and h not in old and h not in new:
    if norm not in normalized:normalized[norm]={'raw_textSHA_members':0,'raw_occurrences':0,'M1_content_tokens_min':tokens,'M1_content_tokens_max':tokens,'normalized_words_min':words,'normalized_words_max':words}
    g=normalized[norm];g['raw_textSHA_members']+=1;g['raw_occurrences']+=occurrences
    for name,value in [('M1_content_tokens',tokens),('normalized_words',words)]:g[name+'_min']=min(g[name+'_min'],value);g[name+'_max']=max(g[name+'_max'],value)
   names=['all_distinct']
   if passed:names.append('language_pass_before_quality')
   if passed and h not in old:names.append('language_pass_after_prior_holds')
   if passed and h not in old and h not in new:names.append('language_pass_after_all_exact_known_holds_NOT_usable')
   if h in new:names.append('new_quality_holds_all_language')
   if passed and h in new:names.append('new_quality_holds_language_pass')
   for name in names:
    d=diag[name];d['distinct_textSHA']+=1;d['M1_content_tokens']+=tokens;d['UTF8_bytes']+=n;d['raw_occurrences']+=occurrences
  require(measured==set(seen),'all_measurements_exact_coverage')
  diagnostics=dict(diag)
  groups=[(norm,g) for norm,g in normalized.items() if g['raw_textSHA_members']>1]
  diagnostics['normalized_exact_candidate_equivalence_NOT_selected']={'scope':'Stored case/punctuation-losing exact normalization, after language and all exact known holds. No near/protected clearance or arbitrary representative.','remaining_normalized_groups':len(normalized),'groups_with_multiple_raw_textSHA':len(groups),'raw_textSHA_in_multimember_groups':sum(g['raw_textSHA_members'] for _,g in groups),'raw_textSHA_excess':sum(g['raw_textSHA_members']-1 for _,g in groups),'max_raw_textSHA_group':max((g['raw_textSHA_members'] for _,g in groups),default=1 if normalized else 0),'ambiguous_token_count_groups':sum(g['M1_content_tokens_min']!=g['M1_content_tokens_max'] for _,g in groups),'hypothetical_one_per_group_content_tokens_min':sum(g['M1_content_tokens_min'] for g in normalized.values()),'hypothetical_one_per_group_content_tokens_max':sum(g['M1_content_tokens_max'] for g in normalized.values()),'usable_or_admitted':False}
  for norm,g in sorted(groups):emit({'record_type':'NORMALIZED_EXACT_CANDIDATE_GROUP_NOT_SELECTION','normalized_SHA256':norm.hex(),**g})
 # Prior holds propagate to every exact content copy, even if a particular occurrence lacks the prior bit.
 for h,v in sorted(seen.items()):
  prior=h in old;semantic=h in new
  if prior or semantic:emit({'record_type':'EXACT_RAW_TEXT_SHA_HOLD','text_SHA256':h.hex(),**v,'prior_exact_text_hold':prior,'new_semantic_hold':semantic,'hold_all_raw_copies':True,'review':new.get(h),'admitted':False})
 held=old|set(new)
 return {'status':'COMPLETE_EXACT_SHA_SEMANTIC_HOLD_OVERLAY_NO_ADMISSION','raw_rows':raw,'distinct_textSHA':len(seen),'prior_held_distinct_textSHA':len(old),'new_semantic_hold_distinct_textSHA':len(new),'overlap_prior_new_distinct_textSHA':len(old&set(new)),'union_held_distinct_textSHA':len(held),'not_exact_known_held_distinct_textSHA_NOT_usable':len(seen)-len(held),'raw_occurrences_prior_bits':rawold,'raw_occurrences_new_semantic_holds':rawnew,'raw_occurrences_both_direct_flags':both,'raw_occurrences_union_exact_text_holds':sum(copycounts[h] for h in held),'source_rows':dict(sourcecounts),'whole_development_draws':30,'review_research_proxy_not_admitted':sum(not r['semantic_hold'] for r in reviews),'prior_hold_bits_preserved':True,'ancestry_split_rights_family_uncertainty_unchanged':True,'all_unheld_still_uncleared':True,'new_admitted_documents':0,'new_admitted_tokens':0,'existing_M1_token_diagnostics':diagnostics,'token_counts':'Exact stored M1 content-token metadata only; no retokenization. One EOS per distinct SHA separate, no mixture-usable/admission inference.'}

def run(profile,out,check):
 binding=profile['family_frame'];p=Path(binding['path'])
 def ident(s):return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
 require(not p.is_symlink() and ident(p.stat())==binding['stat'],'input_stat')
 token=Path(profile['token_frame']['path']);tb=profile['token_frame']
 require(not token.is_symlink() and ident(token.stat())==tb['stat'],'token_input_stat')
 fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW);tfd=None;db=None
 try:
  require(ident(os.fstat(fd))==binding['stat'],'input_fd_stat')
  tfd=os.open(token,os.O_RDONLY|os.O_NOFOLLOW);require(ident(os.fstat(tfd))==tb['stat'],'token_fd_stat')
  db=sqlite3.connect(p.as_uri()+'?mode=ro&immutable=1',uri=True)
  for pragma in ['query_only=ON','cache_size=-4096','temp_store=MEMORY','mmap_size=0']:db.execute('PRAGMA '+pragma)
  db.set_progress_handler(lambda:(check() or 0),10000)
  require(db.execute('pragma quick_check').fetchone()==('ok',),'input_quickcheck')
  reviews=build_reviews(json.loads(Path(profile['uniform_review']).read_text()),json.loads(Path(profile['byte_review']).read_text()))
  written=0
  with (Path(out)/'exact-text-held-overlay.jsonl').open('xb') as f:
   def emit(row):
    nonlocal written
    b=(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n').encode();require(len(b)<=65536,'one_overlay_record_cap');check(len(b));require(written+len(b)<=profile['limits']['overlay_bytes'],'overlay_cap_before_write');f.write(b);written+=len(b)
   db.execute('ATTACH DATABASE ? AS measured',(Path(profile['token_frame']['path']).as_uri()+'?mode=ro&immutable=1',))
   require(db.execute('SELECT count(*) FROM measured.docs').fetchone()[0]==profile['expected']['raw_rows'],'token_docs_count')
   bad=db.execute('SELECT count(*) FROM rows r LEFT JOIN measured.docs d ON d.source=r.source_id AND d.source_ordinal=r.ordinal WHERE d.doc IS NULL OR d.text_SHA256!=r.text_SHA256 OR d.line_SHA256!=r.line_SHA256 OR d.UTF8_bytes!=r.text_UTF8_bytes OR d.source_flags!=r.existing_flags OR d.explicit_hold_flags!=r.identity_holds').fetchone()[0]
   require(bad==0,'all_raw_metadata_doc_bijection')
   rows=db.execute('SELECT source_id,ordinal,line_SHA256,text_SHA256,text_UTF8_bytes,existing_flags,identity_holds,lead_status FROM rows ORDER BY source_id,ordinal')
   measurements=db.execute('SELECT text_SHA256,UTF8_bytes,content_tokens,language_pass,occurrences,explicit_hold_flags,source_flags,normalized_SHA256,normalized_words FROM measured.texts ORDER BY text_SHA256')
   result=aggregate(rows,reviews,emit,check,profile['expected'],measurements);f.flush();os.fsync(f.fileno())
  require(ident(p.stat())==binding['stat'] and ident(os.fstat(fd))==binding['stat'] and ident(token.stat())==tb['stat'] and ident(os.fstat(tfd))==tb['stat'],'inputs_unchanged')
  result['overlay_bytes']=written;return result
 finally:
  if db is not None:db.close()
  os.close(fd)
  if tfd is not None:os.close(tfd)

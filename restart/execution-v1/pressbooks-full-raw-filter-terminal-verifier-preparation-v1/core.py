"""Independent terminal metadata consistency; never source bytes or filter policy."""
import hashlib,json,sqlite3,zlib,collections,heapq
from pathlib import Path
RULES=['REPEATED_RESOURCE_CATALOG_FIELDS','LINKED_SOURCE_INDEX_WITH_NO_MAIN_EXPOSITION','LINE_COMMENT_CONTAINS_FLATTENED_PROGRAM','EMPTY_PAIRED_LABELS','UNBOUND_MATH_EXERCISE_INTRO','INTRODUCED_VALUE_ABSENT_AT_DISCOURSE_BOUNDARY','DANGLING_MEASURED_VALUE_CLAUSE','EMPTY_MATH_ELEMENT']
CONTEXT={'AMBIGUOUS_CONJUNCTION_OR_LABEL_TOKEN','FIGURE_REFERENCE_CONTEXT','SOURCE_MATH_MARKUP_PRESERVED','POSSIBLE_COMPONENT_HEADING'}
def require(v,n):
 if not v:raise ValueError(n)
def sha(path,check=lambda:None):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b);check()
 return h.hexdigest()
def dbopen(path):
 d=sqlite3.connect(Path(path).as_uri()+'?mode=ro&immutable=1',uri=True)
 for p in ['query_only=ON','cache_size=-4096','temp_store=MEMORY','mmap_size=0']:d.execute('pragma '+p)
 return d
def unique(pairs):
 d={}
 for k,v in pairs:require(k not in d,'duplicate_JSON_key');d[k]=v
 return d
def receipt(row,h,bytecount,chars,stored):
 rh,jsha,packed,psha,codec=row;require(rh==h and codec=='zlib6-jsonUTF8-v1' and type(packed)is bytes and len(packed)<=2000000,'receipt_identity_codec_cap');require(hashlib.sha256(packed).digest()==psha,'receipt_compressed_SHA')
 d=zlib.decompressobj();raw=d.decompress(packed,2000001);require(len(raw)<=2000000 and d.eof and not d.unused_data and not d.unconsumed_tail,'bounded_single_zlib_complete_no_trailing');require(hashlib.sha256(raw).digest()==jsha,'receipt_JSON_SHA')
 j=json.loads(raw.decode(),object_pairs_hook=unique,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('nonfinite_JSON')))
 require(j['source_SHA256']==h.hex()==j['derivative_SHA256'] and j['source_UTF8_bytes']==bytecount and j['source_characters']==chars and j['raw_unchanged']is True and j['omitted_source_bytes']==0,'receipt_source_metadata_binding')
 require(j['policy_status']=='DEVELOPMENT_GENERIC_RAW_UNIT_FILTER_NOT_ACCEPTANCE' and j['English_quality_or_factual_truth_proven']is False and j['rights_family_leakage_cleared']is False,'receipt_no_clearance')
 reasons=j['reasons'];contexts=j['context_only_diagnostics'];require(type(reasons)is list and type(contexts)is list and len(reasons)+len(contexts)<=5000,'receipt_events_cap')
 counts=collections.Counter();mask=0
 for isreason,items in [(True,reasons),(False,contexts)]:
  for e in items:
   code=e['reason'];require(code in (RULES if isreason else CONTEXT),'finite_reason_code');a,b=e['char_start'],e['char_end'];c,f=e['byte_start'],e['byte_end'];require(all(type(x)is int for x in [a,b,c,f]) and 0<=a<=b<=chars and 0<=c<=f<=bytecount,'event_source_bounds');v=e['source_span_SHA256'];require(type(v)is str and len(v)==64 and bytes.fromhex(v).hex()==v,'event_source_span_SHA_shape')
   if isreason:counts[code]+=1;mask|=1<<RULES.index(code)
 require(j['decision']==('HOLD_STRUCTURAL_REPRESENTATION_REVIEW' if reasons else 'RAW_CANDIDATE_UNCHANGED_PENDING_ALL_OTHER_GATES'),'receipt_decision')
 events=len(reasons)+len(contexts);require(stored==(mask,events,stored[2],len(raw)) and events<=stored[2]<=5000,'stored_mask_event_upper_and_JSON_bytes');return mask,events,counts,len(raw)
def transcript(v):return (json.dumps(v,ensure_ascii=False,separators=(',',':'))+'\n').encode()
def position(seed,i,total):
 require(total>0,'positive_weight_sum');ceiling=2**256-(2**256%total)
 for retry in range(100):
  n=int.from_bytes(hashlib.sha256(f'{seed}\nTOKEN_WEIGHTED\n{i}\n{retry}\n'.encode()).digest(),'big')
  if n<ceiling:return n%total
 raise ValueError('finite_integer_draw')
def verify_draws(db,selection,seed,context,check):
 n,total=db.execute('select count(*),sum(tokens) from agg where fresh=1').fetchone();require(n>=200 and total>0,'sampling_population');ordered=hashlib.sha256()
 def ranks():
  for h,t,b,s,o in db.execute('select h,tokens,bytes,firstsource,firstordinal from agg where fresh=1 order by h'):
   check();ordered.update(transcript([h.hex(),t,b,s,o]));yield (hashlib.sha256(seed.encode()+b'\nUNIFORM\n'+h).digest(),h,t,b,s,o)
 uniform=heapq.nsmallest(200,ranks());want={}
 def add(mode,i,h,t,b,s,o,extra):want[(mode,i)]={'mode':mode,'draw':i,'text_SHA256':h.hex(),'M1_content_tokens':t,'UTF8_bytes':b,'capture_source_id':s,'capture_ordinal':o,'capture_occurrence_not_preferred_corpus_version':True,'context':context(s,o),**extra}
 for i,(priority,h,t,b,s,o) in enumerate(uniform,1):add('UNIFORM_DISTINCT_RAW_SHA_WITHOUT_REPLACEMENT',i,h,t,b,s,o,{'priority_SHA256':priority.hex()})
 ps=sorted((position(seed,i,total),i) for i in range(1,201));ix=0;running=0
 for h,t,b,s,o in db.execute('select h,tokens,bytes,firstsource,firstordinal from agg where fresh=1 order by h'):
  while ix<len(ps) and ps[ix][0]<running+t:
   pos,i=ps[ix];add('TOKEN_WEIGHTED_WITH_REPLACEMENT_NOT_BYTES',i,h,t,b,s,o,{'token_position_zero_based':pos});ix+=1
  running+=t
 require(ix==200 and running==total,'complete_weighted_CDF');require(selection['seed']==seed and selection['fresh_population_distinct_raw_SHA']==n and selection['fresh_population_M1_content_tokens']==total and selection['ordered_fresh_frame_SHA256']==ordered.hexdigest(),'fresh_frame_and_seed')
 actual=selection['draws'];require(len(actual)==400 and len({(d['mode'],d['draw']) for d in actual})==400,'400_exact_draw_identities')
 for d in actual:require(d==want[(d['mode'],d['draw'])],'independent_exact_draw_and_context')
 us={d['text_SHA256'] for d in actual if d['mode'].startswith('UNIFORM')};ws=[d['text_SHA256'] for d in actual if d['mode'].startswith('TOKEN')]
 for key,val in {'uniform_without_replacement':200,'tokenweighted_with_replacement':200,'unique_drawn_raw_SHA':len(us|set(ws)),'weighted_unique_raw_SHA':len(set(ws)),'weighted_repeat_draws':200-len(set(ws)),'cross_draw_mode_overlap_raw_SHA':len(us&set(ws)),'all_draw_multiplicity_and_overlaps_preserved':True,'source_rights_family_near_protected_uncleared':True,'new_admitted_documents':0,'new_admitted_tokens':0}.items():require(selection[key]==val,'selection_summary_'+key)
 require(selection['status']=='FROZEN_PRE_REVIEW_CANDIDATE_QUALITY_AUDIT_SELECTION_NOT_M2_ACCEPTANCE','selection_scope');return {'draws':400,'uniform':200,'weighted':200,'fresh_population':n,'token_weight':total,'ordered_frame_SHA256':ordered.hexdigest()}
def verify(candidate,frames,family,tokens,result,profile,selection,check):
 for d in [candidate,*frames.values(),family,tokens]:require(d.execute('pragma integrity_check').fetchone()==('ok',),'metadata_SQL_integrity')
 require(candidate.execute('pragma foreign_key_check').fetchone()is None,'candidate_FK')
 agg=sqlite3.connect(':memory:');agg.execute('pragma cache_size=-8192');agg.execute('pragma temp_store=MEMORY');agg.execute('create table agg(h blob primary key,norm blob,words integer,bytes integer,tokens integer,lang integer,held integer,mask integer,candidate integer,fresh integer,reviewed integer,firstsource integer,firstordinal integer,occ integer,flags integer,uncertain integer,events integer,upper integer,jsonbytes integer,chars integer) without rowid')
 known={bytes.fromhex(x) for x in profile['known_hold_SHA256']};exclude={bytes.fromhex(x) for x in profile['fresh_exclusion_SHA256']};seen={};cursors={s:iter(d.execute('select * from records order by ordinal')) for s,d in frames.items()};counts=collections.Counter();linehashes={s:hashlib.sha256() for s in frames};total=0
 try:
  for occ in candidate.execute('select * from occurrences order by source_id,ordinal'):
   s,o,offset,n,line,h,flags,identity,lead,root=occ;require(s in cursors,'unexpected_source');m=next(cursors[s],None);require(m is not None and (o,offset,n,line,h,flags)==(m[0],m[1],m[2],m[4],m[17],m[5]),'all_source_locator_textSHA_flags')
   f=family.execute('select line_offset,line_bytes,ends_LF,line_SHA256,text_SHA256,text_UTF8_bytes,existing_flags,identity_holds,lead_status,lead_root_id from rows where source_id=? and ordinal=?',(s,o)).fetchone();require(f==(m[1],m[2],m[3],m[4],m[17],m[18],m[5],identity,lead,root),'full_family_metadata_join')
   t=tokens.execute('select ID_SHA256,text_SHA256,line_SHA256,characters,UTF8_bytes,content_tokens,language_pass,source_flags,explicit_hold_flags,normalized_SHA256,normalized_words from docs where source=? and source_ordinal=?',(s,o)).fetchone()
   require(t is not None and t[:5]==(hashlib.sha256(m[6].encode()).digest(),h,line,m[19],m[18]) and t[7:9]==(flags,identity),'full_verified_M1_record_join')
   chars,b,tok,lang,norm,words=t[3],t[4],t[5],t[6],t[9],t[10];require(type(tok)is int and 0<=tok<=b and lang in [0,1] and type(norm)is bytes and len(norm)==32,'token_diagnostic_bounds')
   held=int(h in known);reviewed=int(h in exclude);uncertain=int(lead!=1 or bool(flags&64));prior=agg.execute('select bytes,tokens,lang,norm,words,chars from agg where h=?',(h,)).fetchone()
   if prior is None:agg.execute('insert into agg values('+','.join('?'*20)+')',(h,norm,words,b,tok,lang,held,0,0,0,reviewed,s,o,1,flags,uncertain,0,0,0,chars))
   else:require(prior==(b,tok,lang,norm,words,chars),'rawSHA_alias_diagnostics_equal');agg.execute('update agg set occ=occ+1,flags=flags|?,uncertain=uncertain|? where h=?',(flags,uncertain,h))
   counts[s]+=1;total+=1;linehashes[s].update(transcript([o,offset,n,m[3],line.hex()]));check()
  require(all(next(c,None)is None for c in cursors.values()) and total==profile['expected']['raw_rows'],'complete_occurrence_and_source_coverage')
  require(agg.execute('select count(*) from agg').fetchone()==(profile['expected']['distinct_textSHA'],),'complete_distinct_coverage')
  for s in profile['sources']:require(counts[s['source_id']]==s['frame']['rows'] and linehashes[s['source_id']].hexdigest()==s['frame']['ordered_line_locator_SHA256'],'source_line_transcript')
  for h in known|exclude:require(agg.execute('select 1 from agg where h=?',(h,)).fetchone()is not None,'every_known_or_reviewed_SHA_present')
  observed=iter(candidate.execute('select * from texts order by text_SHA256'));receipts=iter(candidate.execute('select * from receipts order by text_SHA256'));events=0;maxevents=0;maxupper=0;maxjson=0;eventcounts=collections.Counter({k:0 for k in RULES});docincidence=collections.Counter({k:0 for k in RULES})
  for row in agg.execute('select * from agg order by h'):
   h,norm,words,b,tok,lang,held,_,_,_,reviewed,s,o,occ,flags,uncertain,_,_,_,chars=row;stored=next(observed,None);rec=next(receipts,None);require(stored is not None and rec is not None and stored[0]==h,'all_text_receipt_identities')
   mask,ne,rc,nj=receipt(rec,h,b,chars,(stored[7],stored[16],stored[17],stored[18]));cand=int(bool(lang) and not held and mask==0);fresh=int(bool(cand) and not reviewed)
   expected=(h,norm,words,b,tok,lang,held,mask,cand,fresh,reviewed,s,o,occ,flags,uncertain,ne,stored[17],nj);require(stored==expected,'all_distinct_fields_candidate_and_fresh_predicates')
   agg.execute('update agg set mask=?,candidate=?,fresh=?,events=?,upper=?,jsonbytes=? where h=?',(mask,cand,fresh,ne,stored[17],nj,h));events+=ne;maxevents=max(maxevents,ne);maxupper=max(maxupper,stored[17]);maxjson=max(maxjson,nj);eventcounts.update(rc)
   for i,k in enumerate(RULES):docincidence[k]+=bool(mask&(1<<i))
   check()
  require(next(observed,None)is None and next(receipts,None)is None,'no_extra_texts_or_receipts');require(events<=5000000,'aggregate_event_cap')
  populations={}
  for name,w in [('all_distinct','1'),('language_pass','lang=1'),('language_after_known32','lang=1 and held=0'),('full_filtered_candidate','candidate=1'),('fresh_review_population','fresh=1'),('previously_reviewed_surviving_candidate','candidate=1 and fresh=0')]:
   n,t,b,o=agg.execute('select count(*),coalesce(sum(tokens),0),coalesce(sum(bytes),0),coalesce(sum(occ),0) from agg where '+w).fetchone();populations[name]={'distinct_raw_textSHA':n,'M1_content_tokens':t,'one_EOS_each_separate':n,'UTF8_bytes':b,'raw_occurrences':o,'usable_or_admitted':False}
  require(populations==result['populations'],'exact_all_population_counts_and_EOS')
  for name,base in profile.get('expected_baselines',{}).items():require(all(populations[name][k]==v for k,v in base.items()),'prior_verified_count_baseline')
  normalized={'scope':'Candidate exact stored case/punctuation-losing normalization, no representative selected or near/protected clearance.','groups':0,'multiple_raw_SHA_groups':0,'excess_raw_SHA':0,'max_group':0,'one_per_group_tokens_min':0,'one_per_group_tokens_max':0,'ambiguous_tokens_groups':0}
  for _,n,lo,hi in agg.execute('select norm,count(*),min(tokens),max(tokens) from agg where candidate=1 group by norm'):
   normalized['groups']+=1;normalized['multiple_raw_SHA_groups']+=n>1;normalized['excess_raw_SHA']+=n-1;normalized['max_group']=max(normalized['max_group'],n);normalized['one_per_group_tokens_min']+=lo;normalized['one_per_group_tokens_max']+=hi;normalized['ambiguous_tokens_groups']+=lo!=hi
  require(normalized==result['normalized_exact_candidate_diagnostics'],'normalized_equivalence_not_representative')
  def context(s,o):
   f=family.execute('select r.lead_status,r.existing_flags,r.identity_holds,a.value,b.value,c.value,d.value from rows r left join strings a on a.string_id=r.id_id left join strings b on b.string_id=r.url_id left join strings c on c.string_id=r.book_url_id left join strings d on d.string_id=r.lead_root_id where r.source_id=? and r.ordinal=?',(s,o)).fetchone();require(f is not None,'draw_context');return dict(zip(['lead_status','source_flags','prior_identity_hold_bits','source_id_URL','source_url','book_url','derived_book_root_LEAD_NOT_verified_family'],f))
  sampled=verify_draws(agg,selection,profile['sampling_seed'],context,check);require({k:v for k,v in selection.items() if k!='draws'}==result['sampling'],'selection_terminal_summary')
  require(result['raw_rows']==total and result['distinct_raw_SHA']==populations['all_distinct']['distinct_raw_textSHA'] and result['known_exact_hold_SHA']==len(known) and result['fresh_exclusion_SHA']==len(exclude),'terminal_denominators')
  require(result['all_policy_events']==events and result['max_events_per_text']==maxevents and result['max_event_upper_bound_per_text']==maxupper and result['max_lossless_policy_JSON_bytes']==maxjson and result['reason_counts_distinct_raw_SHA']==dict(eventcounts),'policy_EVENT_count_summary_not_document_incidence')
  return {'raw_rows':total,'distinct_textSHA':populations['all_distinct']['distinct_raw_textSHA'],'populations':populations,'normalized_exact_candidate_diagnostics':normalized,'all_policy_events':events,'reason_EVENT_counts':dict(eventcounts),'independent_per_reason_distinct_document_incidence':dict(docincidence),'sampling':sampled,'original_source_policy_or_preimage_recomputed':False,'source_CRC_SHA_inherited_from_bound_reviewed_producer':True,'new_admitted_documents':0,'new_admitted_tokens':0}
 finally:agg.close()

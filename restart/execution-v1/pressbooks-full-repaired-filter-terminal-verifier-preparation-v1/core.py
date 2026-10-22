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
V2H={'UNBALANCED_LATEX_WRAPPER','EMPTY_INTRODUCED_MATH_ENDPOINT','EMPTY_INTRODUCED_EQUATION_SLOT','EMPTY_REQUIRED_ASSESSMENT_SLOT'}
V2Q={'NAMED_VISUAL_DEPENDENCY_REVIEW','ASSESSMENT_DEPENDENCY_REVIEW','AMBIGUOUS_LITERAL_LATEX_TOKEN'}
V3H={'EXACT_ACCESS_WALL_WITHOUT_CAPTURED_BODY','RESOURCE_ACCESS_ONLY_NO_SUBSTANTIVE_CAPTURED_BODY','EXPLICIT_EMPTY_ASSESSMENT_BLOCK','PRACTICE_OPTIONS_AND_ANSWER_WITHOUT_CAPTURED_PROMPT'}
V3Q={'ACCESS_WALL_MENTION_CONTEXT_UNRESOLVED','ASSESSMENT_BLOCK_CONTENT_ROLE_UNRESOLVED','PRACTICE_PROMPT_RELATION_UNRESOLVED','NAMED_MEDIA_COMPARISON_OR_REQUIRED_CONTEXT_REVIEW'}
def hexsha(s):require(type(s)is str and len(s)==64 and bytes.fromhex(s).hex()==s,'SHA_shape')
def span(e,chars,bytecount):
 a,b,c,d=e['char_start'],e['char_end'],e['byte_start'],e['byte_end'];require(all(type(x)is int for x in [a,b,c,d]) and 0<=a<=b<=chars and 0<=c<=d<=bytecount,'event_source_bounds');hexsha(e['source_span_SHA256'])
def receipt(row,h,bytecount,chars,firstsource,firstordinal,firstline,stored):
 rh,jsha,packed,psha,codec=row;require(rh==h and codec=='zlib6-jsonUTF8-repaired-v1' and type(packed)is bytes and len(packed)<=3000000,'receipt_identity_codec_cap');require(hashlib.sha256(packed).digest()==psha,'compressed_SHA')
 d=zlib.decompressobj();raw=d.decompress(packed,3000001);require(len(raw)<=3000000 and d.eof and not d.unused_data and not d.unconsumed_tail,'bounded_zlib_complete_single_member');require(hashlib.sha256(raw).digest()==jsha,'JSON_SHA')
 j=json.loads(raw.decode(),object_pairs_hook=unique,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('nonfinite_JSON')));s=j['structural'];v2=s['prior_v2'];v1=v2['prior_v1'];c=j['component_ancestry_review']
 for stage in [s,v2,v1]:require(stage['source_SHA256']==h.hex() and stage['source_UTF8_bytes']==bytecount and stage['raw_unchanged'] is True,'all_structural_stages_source_binding')
 require(v2['source_characters']==v1['source_characters']==c['characters']==chars and v2['omitted_source_bytes']==v1['omitted_source_bytes']==s['source_bytes_removed']==0,'all_stages_no_source_removal');require(v1['derivative_SHA256']==v2['derivative_SHA256']==h.hex(),'same_raw_derivative')
 require(j['all_source_unchanged'] is True and j['no_quality_or_admission_verdict'] is True and s['new_admissions']==0,'no_quality_clearance')
 require(c['identity']=={'source_id':firstsource,'ordinal':firstordinal,'text_SHA256':h.hex(),'source_JSON_SHA256':firstline.hex()} and c['UTF8_bytes']==bytecount and c['source_text_unchanged'] is True and c['automatic_candidate_exclusion'] is False and c['new_admission'] is False and c['unmarked_rights_and_human_authorship']=='UNASSESSED_NOT_CLEARED','component_first_occurrence_identity_and_scope')
 groups=[v1['reasons'],v1['context_only_diagnostics'],v2['delta_representation_review_holds'],v2['delta_review_only_signals'],s['delta_representation_review_holds'],s['pending_dependency_queue'],c['flags']];require(all(type(g)is list for g in groups) and sum(map(len,groups))<=5000 and len(groups[6])<=256,'combined_event_cap')
 counts=collections.Counter();incidence=set()
 for group,allowed,prefix in [(groups[0],set(RULES),''),(groups[1],CONTEXT,'QUEUE:'),(groups[2],V2H,''),(groups[3],V2Q,'QUEUE:'),(groups[4],V3H,''),(groups[5],V3Q,'QUEUE:')]:
  for e in group:
   require(e['reason'] in allowed,'finite_structural_reason');span(e,chars,bytecount);name=prefix+e['reason'];counts[name]+=1;incidence.add(name)
 for e in groups[6]:
  require(e['kind'] in {'COMPONENT_GRANT_NOTICE','LICENSE_MENTION','EXPLICIT_GENERATION_ATTRIBUTION','GENERATION_LANGUAGE_MENTION','AI_ASSISTANCE_DISCLOSURE_NOT_FULL_AUTHORSHIP','TRANSLATION_ANCESTRY_NOTICE','REPUBLICATION_OR_ADAPTATION_ANCESTRY_LEAD','EXPLICIT_SOURCE_URL_LEAD'},'finite_component_kind')
  a,b=e['char_span'];aa,bb=e['UTF8_span'];ca,cb=e['context_char_span'];cca,ccb=e['context_UTF8_span'];require(all(type(v)is int for v in [a,b,aa,bb,ca,cb,cca,ccb]) and 0<=ca<=a<=b<=cb<=chars and 0<=cca<=aa<=bb<=ccb<=bytecount,'component_notice_context_bounds')
  require(len(e['raw'])==b-a and len(e['raw'].encode())==bb-aa and hashlib.sha256(e['raw'].encode()).hexdigest()==e['raw_SHA256'] and len(e['context_raw'])==cb-ca and len(e['context_raw'].encode())==ccb-cca and hashlib.sha256(e['context_raw'].encode()).hexdigest()==e['context_SHA256'],'component_raw_context_internal_hashes')
  require(e['disposition']=='SCOPED_REVIEW_FLAG_ONLY' and e['component_extent']=='UNKNOWN_NOT_THE_NOTICE_SPAN' and e['automatic_candidate_exclusion'] is False and e['confirms_generated_retained_body'] is False,'component_scope_not_grant_or_generation_proof');name='COMPONENT:'+e['kind'];counts[name]+=1;incidence.add(name)
 mask=int(bool(groups[0]))|int(bool(groups[2]))*2|int(bool(groups[4]))*4;queue=int(bool(groups[1] or groups[3] or groups[5]))|int(bool(groups[6]))*2;events=sum(map(len,groups));require(stored==(mask,events,None,len(raw)),'stored_mask_events_upperNone_JSONbytes')
 return mask,queue,events,counts,len(raw),incidence

def transcript(v):return (json.dumps(v,ensure_ascii=False,separators=(',',':'))+'\n').encode()
def verify(candidate,frames,family,tokens,result,profile,check):
 for d in [candidate,*frames.values(),family,tokens]:require(d.execute('pragma integrity_check').fetchone()==('ok',),'metadata_SQL_integrity')
 require(candidate.execute('pragma foreign_key_check').fetchone()is None,'candidate_FK')
 agg=sqlite3.connect(':memory:');agg.execute('pragma cache_size=-8192');agg.execute('pragma temp_store=MEMORY');agg.execute('create table agg(h blob primary key,norm blob,words integer,bytes integer,tokens integer,lang integer,held integer,mask integer,queue integer,candidate integer,fresh integer,reviewed integer,firstsource integer,firstordinal integer,occ integer,flags integer,uncertain integer,events integer,upper integer,jsonbytes integer,chars integer,firstline blob) without rowid')
 expected_sources=[(s['source_id'],s['raw']['path'],bytes.fromhex(s['raw']['SHA256']),s['raw']['stat'],s['frame']['rows']) for s in profile['sources']];stored_sources=[(sid,path,h,json.loads(st),n) for sid,path,h,st,n in candidate.execute('select * from sources order by source_id')];require(stored_sources==expected_sources,'source_provenance')
 known={bytes.fromhex(x) for x in profile['known_hold_SHA256']};excluded={bytes.fromhex(x) for x in profile['fresh_exclusion_SHA256']};targets={bytes.fromhex(x['text_SHA256']):x for x in profile['overlay_targets']};expectedroles={}
 for h,target in targets.items():
  for kind in ['hold_roles','pending_roles']:
   for role in target[kind]:expectedroles[(h,role,kind)]=target['evidence']
 gotroles={}
 for h,role,kind,evidence in candidate.execute('select * from known_roles'):require((h,role,kind) not in gotroles,'duplicate_knownrole');gotroles[(h,role,kind)]=json.loads(evidence,object_pairs_hook=unique)
 require(gotroles==expectedroles,'exact_all_known_pending_roles_and_evidence')
 cursors={s:iter(d.execute('select * from records order by ordinal')) for s,d in frames.items()};counts=collections.Counter();decoded=collections.Counter();lines={s:hashlib.sha256() for s in frames};total=0
 try:
  for occ in candidate.execute('select * from occurrences order by source_id,ordinal'):
   s,o,offset,n,line,h,flags,identity,lead,root=occ;require(s in cursors,'unexpected_source');m=next(cursors[s],None);require(m is not None and (o,offset,n,line,h,flags)==(m[0],m[1],m[2],m[4],m[17],m[5]),'every_source_locator_textSHA_flag_join')
   f=family.execute('select line_offset,line_bytes,ends_LF,line_SHA256,text_SHA256,text_UTF8_bytes,existing_flags,identity_holds,lead_status,lead_root_id from rows where source_id=? and ordinal=?',(s,o)).fetchone();require(f==(m[1],m[2],m[3],m[4],m[17],m[18],m[5],identity,lead,root),'family_exact_join')
   t=tokens.execute('select ID_SHA256,text_SHA256,line_SHA256,characters,UTF8_bytes,content_tokens,language_pass,source_flags,explicit_hold_flags,normalized_SHA256,normalized_words from docs where source=? and source_ordinal=?',(s,o)).fetchone();require(t is not None and t[:5]==(hashlib.sha256(m[6].encode()).digest(),h,line,m[19],m[18]) and t[7:9]==(flags,identity),'verified_M1_allrow_join')
   chars,b,tok,lang,norm,words=t[3],t[4],t[5],t[6],t[9],t[10];require(type(tok)is int and 0<=tok<=b and lang in [0,1] and type(norm)is bytes and len(norm)==32,'measured_domains')
   held=int(h in known);reviewed=int(h in excluded);uncertain=int(lead!=1 or bool(flags&64));prior=agg.execute('select bytes,tokens,lang,norm,words,chars from agg where h=?',(h,)).fetchone()
   if prior is None:agg.execute('insert into agg values('+','.join('?'*22)+')',(h,norm,words,b,tok,lang,held,0,0,0,0,reviewed,s,o,1,flags,uncertain,0,None,0,chars,line))
   else:require(prior==(b,tok,lang,norm,words,chars),'same_raw_SHA_measurement_agreement');agg.execute('update agg set occ=occ+1,flags=flags|?,uncertain=uncertain|? where h=?',(flags,uncertain,h))
   counts[s]+=1;decoded[s]+=n;total+=1;lines[s].update(transcript([o,offset,n,m[3],line.hex()]));check()
  require(all(next(c,None)is None for c in cursors.values()) and total==profile['expected']['raw_rows'],'all_source_occurrences_complete');require(agg.execute('select count(*) from agg').fetchone()==(profile['expected']['distinct_textSHA'],),'distinct_coverage')
  for s in profile['sources']:require(counts[s['source_id']]==s['frame']['rows'] and lines[s['source_id']].hexdigest()==s['frame']['ordered_line_locator_SHA256'],'ordered_source_line_transcript')
  for source,proof in zip(profile['sources'],result['sources'],strict=True):require(proof['source_id']==source['source_id'] and proof['counts']['decoded_bytes']==decoded[source['source_id']],'decoded_line_byte_sum')
  for h in known|excluded|set(targets):require(agg.execute('select 1 from agg where h=?',(h,)).fetchone()is not None,'every_known_seen_overlay_SHA_covered')
  observed=iter(candidate.execute('select * from texts order by text_SHA256'));receipts=iter(candidate.execute('select * from receipts order by text_SHA256'));events=0;maxevents=0;maxjson=0;eventcounts=collections.Counter();docincidence=collections.Counter()
  for row in agg.execute('select * from agg order by h'):
   h,norm,words,b,tok,lang,held,_,_,_,_,reviewed,s,o,occ,flags,uncertain,_,_,_,chars,firstline=row;stored=next(observed,None);rec=next(receipts,None);require(stored is not None and rec is not None and stored[0]==h,'all_receipt_texts_bijection')
   mask,queue,ne,rc,nj,inc=receipt(rec,h,b,chars,s,o,firstline,(stored[7],stored[17],stored[18],stored[19]))
   for role in targets.get(h,{}).get('pending_roles',[]):queue|=4 if role.startswith('SOURCE_SPECIFIC_SUSPECTED') else 8
   cand=int(bool(lang) and not held and mask==0 and queue==0);fresh=int(bool(cand) and not reviewed);want=(h,norm,words,b,tok,lang,held,mask,queue,cand,fresh,reviewed,s,o,occ,flags,uncertain,ne,None,nj);require(stored==want,'all_distinct_fields_masks_queue_candidate_fresh')
   agg.execute('update agg set mask=?,queue=?,candidate=?,fresh=?,events=?,jsonbytes=? where h=?',(mask,queue,cand,fresh,ne,nj,h));events+=ne;maxevents=max(maxevents,ne);maxjson=max(maxjson,nj);eventcounts.update(rc);docincidence.update(inc);check()
  require(next(observed,None)is None and next(receipts,None)is None and events<=5000000,'receipt_terminal_coverage_and_events')
  axes={};conditions=[('all_distinct','1'),('language_pass','lang=1'),('known_exact_holds','held=1'),('representation_holds','mask!=0'),('dependency_queue','(queue&1)!=0'),('component_queue','(queue&10)!=0'),('specific_factual_pending_queue','(queue&4)!=0'),('clear_diagnostic_candidate','candidate=1'),('clear_seen_not_fresh','candidate=1 and fresh=0'),('clear_unreviewed_frame','fresh=1')]
  for name,w in conditions:
   n,t,b,o=agg.execute('select count(*),coalesce(sum(tokens),0),coalesce(sum(bytes),0),coalesce(sum(occ),0) from agg where '+w).fetchone();axes[name]={'distinct_raw_textSHA':n,'M1_content_tokens':t,'one_EOS_each_separate':n,'UTF8_bytes':b,'raw_occurrences':o,'usable_or_admitted':False}
  require(axes==result['populations_overlapping_axes'],'all_overlapping_axis_totals')
  prefix='lang=1 and held=0 and mask=0';disjoint=[('LANGUAGE_FAIL','lang=0'),('KNOWN_EXACT_HOLD','lang=1 and held=1'),('REPRESENTATION_HOLD','lang=1 and held=0 and mask!=0'),('DEPENDENCY_QUEUE',prefix+' and (queue&1)!=0'),('COMPONENT_QUEUE',prefix+' and (queue&1)=0 and (queue&10)!=0'),('SPECIFIC_FACTUAL_PENDING_QUEUE',prefix+' and (queue&11)=0 and (queue&4)!=0'),('CLEAR_ALREADY_SEEN','candidate=1 and fresh=0'),('CLEAR_UNREVIEWED','fresh=1')];buckets={}
  for name,w in disjoint:
   n,t,b,o=agg.execute('select count(*),coalesce(sum(tokens),0),coalesce(sum(bytes),0),coalesce(sum(occ),0) from agg where '+w).fetchone();buckets[name]={'distinct_raw_textSHA':n,'M1_content_tokens':t,'one_EOS_each_separate':n,'UTF8_bytes':b,'raw_occurrences':o,'admitted':False}
  require(buckets==result['disjoint_buckets'] and sum(v['distinct_raw_textSHA'] for v in buckets.values())==axes['all_distinct']['distinct_raw_textSHA'] and sum(v['M1_content_tokens'] for v in buckets.values())==axes['all_distinct']['M1_content_tokens'] and sum(v['raw_occurrences'] for v in buckets.values())==total,'disjoint_buckets_sum_and_precedence')
  require((result['raw_rows'],result['distinct_raw_SHA'],result['known_exact_hold_SHA'],result['overlay_target_SHA'],result['freshness_exclusion_SHA'])==(total,axes['all_distinct']['distinct_raw_textSHA'],len(known),len(targets),len(excluded)),'exact_terminal_denominators')
  require(result['all_policy_events']==events and result['max_events_per_text']==maxevents and result['max_lossless_policy_JSON_bytes']==maxjson and result['reason_counts_distinct_raw_SHA']==dict(eventcounts),'EVENT_multiplicity_summary_not_doc_incidence')
  return {'raw_rows':total,'distinct_textSHA':axes['all_distinct']['distinct_raw_textSHA'],'populations_overlapping_axes':axes,'disjoint_buckets':buckets,'all_policy_events':events,'reason_EVENT_counts':dict(eventcounts),'independent_per_reason_distinct_document_incidence':dict(docincidence),'known_hold_SHA':len(known),'overlay_target_SHA':len(targets),'fresh_quality_exclusion_SHA':len(excluded),'sampling_performed':False,'source_policy_semantics_and_source_preimage_recomputed':False,'source_CRC_SHA_inherited_from_bound_reviewed_producer':True,'new_admitted_documents':0,'new_admitted_tokens':0}
 finally:agg.close()

"""Pure bounded post-terminal group capture/core integration, supplied readers only."""
import hashlib,collections
import old_capture_core,maintext_core
LIMITS={'compressed_bytes':84000000,'decoded_bytes':512000000,'group_decoded_bytes':32000000,'group_compressed_bytes':4078038,'page_bytes':1000000,'output_bytes':64000000,'worker_seconds':90,'external_seconds':120,'RSS_bytes':1000000000}
def need(v,m):
 if not v:raise ValueError(m)
def plan(selection,limits=LIMITS):
 rows=selection['selected'];need(len(rows)==20 and len({r['row_ordinal'] for r in rows})==20,'fixed20_no_replacement');by={}
 for entry in selection['selected_group_receipts']:
  g=entry['receipt'];need(g['group_ordinal'] not in by,'group_receipt_duplicates');by[g['group_ordinal']]=g
 decisions=[];groups={}
 for rank,r in enumerate(rows):
  holds=[]
  if r['raw_XML_bytes']>limits['page_bytes']:holds.append('PAGE_RAW_XML_OVER_CAPTURE_CAP_NO_REPLACEMENT')
  gid=r['group']['group_ordinal'];need(gid in by,'selected_group_receipt_missing');g=by[gid]
  decisions.append({'rank':rank,'selection':r,'precontent_capture_holds':holds});groups.setdefault(gid,{'receipt':g,'first_rank':rank,'ranks':[]})['ranks'].append(rank)
 compressed=decoded=0;reads=[]
 for gid,g in sorted(groups.items(),key=lambda kv:(kv[1]['first_rank'],kv[0])):
  eligible=[i for i in g['ranks'] if not decisions[i]['precontent_capture_holds']]
  if not eligible:continue
  receipt=g['receipt'];n=receipt['compressed_end_exclusive']-receipt['compressed_start'];d=receipt['decoded_bytes'];need(receipt['compressed_bytes']==n and receipt['trailing_absent'] is True and receipt['CRC_EOF_members']>=1,'group_receipt_structure');why=[]
  if not 0<n<=limits['group_compressed_bytes']:why.append('GROUP_COMPRESSED_RANGE_OVER_CAPTURE_CAP_NO_REPLACEMENT')
  if not 0<d<=limits['group_decoded_bytes']:why.append('GROUP_DECODED_SIZE_OVER_CAPTURE_CAP_NO_REPLACEMENT')
  if compressed+n>limits['compressed_bytes'] or decoded+d>limits['decoded_bytes']:why.append('AGGREGATE_CAPTURE_BUDGET_HOLD_NO_REPLACEMENT')
  if why:
   for i in eligible:decisions[i]['precontent_capture_holds'].extend(why)
  else:compressed+=n;decoded+=d;reads.append(receipt)
 return {'decisions':decisions,'groups_read_order':reads,'planned_compressed_bytes':compressed,'planned_decoded_bytes':decoded,'all20_outcomes_preserved':True,'limits':limits}
def capture(selection,capture_plan,header,read_group,write,check,semantic_path,limits=LIMITS,extract=maintext_core.extract):
 need(capture_plan==plan(selection,limits),'precontent_plan_exact_reproduction');need(type(header) is bytes and 0<len(header)<=65536,'original_header_bound');write('original-header.xml',header)
 records=[{'selection':d['selection'],'precontent_capture_holds':d['precontent_capture_holds'],'outcome':'HELD_PRECONTENT_BOUNDS_NO_REPLACEMENT'} if d['precontent_capture_holds'] else None for d in capture_plan['decisions']];compressed=decoded=0;seen=set()
 for g in capture_plan['groups_read_order']:
  check();gid=g['group_ordinal'];need(gid not in seen,'group_read_once');seen.add(gid);raw=read_group(g);compressed+=len(raw);need(compressed<=limits['compressed_bytes'],'compressed_global_bound');native=old_capture_core.decode(raw,g,limits['decoded_bytes']-decoded,check);decoded+=len(native);need(len(native)<=limits['group_decoded_bytes'],'group_decoded_cap')
  for d in capture_plan['decisions']:
   r=d['selection'];rank=d['rank']
   if d['precontent_capture_holds'] or r['group']['group_ordinal']!=gid:continue
   a,n=r['group_decoded_start'],r['raw_XML_bytes'];need(type(a) is int and type(n) is int and 0<=a and 0<n<=limits['page_bytes'] and a+n<=len(native),'exact_wholepage_locator')
   page=bytes(native[a:a+n]);need(hashlib.sha256(page).hexdigest()==r['raw_SHA256'],'exact_native_page_SHA');name=f'page-{r["row_ordinal"]}-{r["page_id"]}.xml';write(name,page)
   expected={'selection':r,'raw_XML_bytes':n,'raw_XML_SHA256':r['raw_SHA256'],'expected_model':r['expected_model'],'expected_format':r['expected_format']}
   record,text=extract(header,page,expected,semantic_path,check)
   need(record['source_title']==r['expected_semantic_title'] and record['native_page_ID']==r['page_id'] and record['native_revision_IDs']==r['all_revision_ID_occurrences'],'all_selected_title_page_revision_occurrence_identity')
   textfile=None
   if text is not None:
    need(len(text)<=limits['page_bytes'],'whole_wikitext_output_bound');textfile=f'page-{r["row_ordinal"]}-{r["page_id"]}.source-text.utf8';write(textfile,text)
   records[rank]={'selection':r,'raw_XML_file':name,'raw_XML_SHA256':r['raw_SHA256'],'maintext_file':textfile,'maintext_SHA256':hashlib.sha256(text).hexdigest() if text is not None else None,'maintext_UTF8_bytes':len(text) if text is not None else None,'native_extraction':record,'group_receipt':g,'CRC_EOF_verified_for_group':True,'outcome':record['outcome'],'new_admitted_documents':0}
  del raw,native
 need(all(r is not None for r in records) and len(records)==20 and compressed==capture_plan['planned_compressed_bytes'] and decoded==capture_plan['planned_decoded_bytes'],'all20_exact_outcomes_counts')
 return {'status':'COMPLETE_POSTINVENTORY20_FULLPAGE_WIKITEXT_DEVELOPMENT_CAPTURE_NO_ADMISSION','records':records,'groups_read_once':sorted(seen),'compressed_bytes_read':compressed,'decoded_bytes':decoded,'no_replacements':True,'whole_publisher_archive_verified':False,'source_scope':'Verified retained-prefix fragment only','rendered_or_language_quality_cleared':False,'new_admitted_documents':0}

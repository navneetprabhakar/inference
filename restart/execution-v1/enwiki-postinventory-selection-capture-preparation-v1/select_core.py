"""Post-terminal constant-memory article-frame counts and uniform20 priorities.
No file/SQLite opener: caller must first verify terminal custody and readonly DBs.
"""
import hashlib,heapq,json,collections,re
import title_decode
from native_codec import FLAGS
SEED='enwiki-retained-prefix-v3-development20-20261021'
FIELDS=('row_ordinal','page_id','first_revision_id','namespace','flags','model_code','revision_count','main_text_bytes','group_decoded_start','raw_XML_bytes','raw_SHA256')
def need(v,m):
 if not v:raise ValueError(m)
def priority(row):
 pre=(SEED+'\0'+str(row['row_ordinal'])+'\0'+str(row['page_id'])+'\0'+row['raw_SHA256']).encode('utf8');return hashlib.sha256(pre).hexdigest()
def scan_pages(rows,groups,expected,check):
 """Rows andgroups orderedexactly; pageIDs uniqueness inherited terminal proof."""
 groups=iter(groups);group=None;group_count=0;count=0;ns=collections.Counter();flag_counts=collections.Counter();article_flags=collections.Counter();heap=[];stats=collections.Counter()
 for r0 in rows:
  count+=1
  if count%1024==0:check()
  r=dict(r0);need(set(r)==set(FIELDS),'exact_page_schema');need(r['row_ordinal']==count and type(r['page_id']) is int and r['page_id']>0,'exact_ordered_occurrence_frame')
  if isinstance(r['raw_SHA256'],bytes):need(len(r['raw_SHA256'])==32,'raw_SHA_width');r['raw_SHA256']=r['raw_SHA256'].hex()
  need(type(r['raw_SHA256']) is str and re.fullmatch('[0-9a-f]{64}',r['raw_SHA256']) is not None,'raw_SHA_string_width')
  if group is None or count>group['last_page_ordinal']:
   group=next(groups,None);group_count+=1;need(group is not None and group['group_ordinal']==group_count and group['first_page_ordinal']==count and group['last_page_ordinal']-count+1==group['page_count'],'exact_group_row_range')
  need(group['first_page_ordinal']<=count<=group['last_page_ordinal'],'page_group_binding')
  need(r['revision_count']>=0 and r['raw_XML_bytes']>0 and r['group_decoded_start']>=0 and r['group_decoded_start']+r['raw_XML_bytes']<=group['decoded_bytes'],'native_locator_bounds')
  ns[r['namespace']]+=1;flag_counts[r['flags']]+=1;need(len(ns)<=1024 and len(flag_counts)<=4096,'summary_cardinality_caps')
  if r['namespace']==0 and not r['flags']&FLAGS['redirect']:
   stats['article_frame_records']+=1;stats['article_raw_XML_bytes']+=r['raw_XML_bytes'];stats['article_pages_raw_XML_over1MB']+=r['raw_XML_bytes']>1000000
   if r['main_text_bytes']>=0:stats['article_known_maintext_UTF8_bytes']+=r['main_text_bytes'];stats['article_known_maintext_records']+=1;stats['article_known_maintext_over_existing120KB_renderer_cap']+=r['main_text_bytes']>120000
   else:stats['article_unknown_maintext_records']+=1
   for name,bit in FLAGS.items():article_flags[name]+=bool(r['flags']&bit)
   r['group']={k:(v.hex() if isinstance(v,bytes) else v) for k,v in dict(group).items()};r['priority_SHA256']=priority(r);key=(-int(r['priority_SHA256'],16),-count,r)
   if len(heap)<20:heapq.heappush(heap,key)
   elif key[:2]>heap[0][:2]:heapq.heapreplace(heap,key)
 need(count==expected['pages'] and group is not None and group['last_page_ordinal']==count and group_count==expected['groups'] and next(groups,None) is None,'complete_terminal_pages_groups_coverage')
 need(len(heap)==20,'article_frame_smaller_than20_no_replacement');check()
 selected=sorted((v[2] for v in heap),key=lambda r:(r['priority_SHA256'],r['row_ordinal']))
 return {'scope':'VERIFIED_RETAINED_PREFIX_NAMESPACE0_NONREDIRECT_FRAME_NOT_ENGLISH_OR_PROSE_CLEARANCE','all_native_rows':count,'all_native_groups':group_count,'namespace_counts':dict(ns),'exact_flag_combination_counts':dict(flag_counts),'article_flag_bit_counts':dict(article_flags),'counts':dict(stats),'selected':selected,'seed':SEED,'selection_formula':'SHA256 UTF8(seed+literalNUL+decimalrowordinal+literalNUL+decimalpageID+literalNUL+lowercase rawXMLSHA), lowest20 distinct occurrences, no newline','uniform_distinct_without_replacement_development_only':True,'held_or_oversized_not_excluded_from_population':True,'new_admitted_documents':0}
def enrich_selected(db,index,selection,models,check):
 """Only20index lookups; ONE revisions scan, preserving repeatedID occurrences."""
 selected=selection['selected'];by={r['row_ordinal']:r for r in selected};need(len(by)==20,'exact20selected_rows');modelmap={r['code']:(r['model'],r['format']) for r in models};modelmap[0]=(None,None)
 for r in selected:
  check();row=index.execute('SELECT * FROM rows WHERE row_ordinal=?',(r['row_ordinal'],)).fetchone();need(row is not None,'selected_index_row_missing');q=dict(row);need(q['page_id']==r['page_id'] and q['group_ordinal']==r['group']['group_ordinal'],'selected_index_ID_group');decoded=title_decode.decode_once(q['title']);r['index_row_metadata']={k:(v.hex() if isinstance(v,bytes) else v) for k,v in q.items()};r['expected_semantic_title']=decoded['semantic_expected_title'];r['title_decode_once_receipt']=decoded;need(r['model_code'] in modelmap,'selected_unknown_model_code');r['expected_model'],r['expected_format']=modelmap[r['model_code']];r['all_revision_ID_occurrences']=[]
 ids=sorted(by);placeholders=','.join('?' for _ in ids)
 cursor=db.execute('SELECT page_ordinal,revision_ordinal,revision_id FROM revisions WHERE page_ordinal IN ('+placeholders+') ORDER BY page_ordinal,revision_ordinal LIMIT 200001',ids)
 for page,o,rid in cursor:
  check();r=by[page];need(o==len(r['all_revision_ID_occurrences'])+1 and o<=10000 and type(rid) is int and rid>0,'selected_exact_revision_order_cap');r['all_revision_ID_occurrences'].append(rid)
 for r in selected:
  vals=r['all_revision_ID_occurrences'];need(len(vals)==r['revision_count'] and (vals[0] if vals else None)==r['first_revision_id'],'selected_all_revision_ID_coverage')
 return selection

def attach_groups(lines,selection,expected_sha,expected_count,check):
 """Consume whole verified metadata transcript once; no native bytes."""
 selected=selection['selected'];wanted={r['group']['group_ordinal']:r['group'] for r in selected};got={};h=hashlib.sha256();n=0
 for raw in lines:
  check();need(type(raw) is bytes and raw.endswith(b'\n') and len(raw)<=65536,'group_receipt_line_bound');h.update(raw);n+=1;x=json.loads(raw);need(x['group_ordinal']==n,'group_receipt_order')
  if n in wanted:
   g=wanted[n];need(x['compressed_start']==g['compressed_start'] and x['compressed_end_exclusive']==g['compressed_end_exclusive'] and x['decoded_bytes']==g['decoded_bytes'] and x['decoded_SHA256']==g['raw_SHA256'] and x['compressed_bytes']==g['compressed_end_exclusive']-g['compressed_start'] and x['trailing_absent'] is True and x['CRC_EOF_members']>=1,'receipt_SQL_group_identity');need(x['actual_native_identity_SHA256']==x['frozen_index_identity_SHA256'],'group_native_index_identity_transcript');got[n]={'receipt':x,'receipt_line_SHA256':hashlib.sha256(raw).hexdigest()}
 need(n==expected_count and h.hexdigest()==expected_sha and set(got)==set(wanted),'full_group_transcript_SHA_and_selected_coverage')
 selection['selected_group_receipts']=[got[k] for k in sorted(got)];return selection

"""Stored metadata only. Never opens native XML or compressed archive."""
import array,hashlib,json,sqlite3,collections,os
from pathlib import Path

def require(ok,label):
 if not ok:raise ValueError(label)
def transcript(v):return (json.dumps(v,ensure_ascii=False,separators=(',',':'))+'\n').encode()
def unique(pairs):
 out={}
 for k,v in pairs:
  require(k not in out,'duplicate_JSON_key');out[k]=v
 return out
def loads(raw):return json.loads(raw,object_pairs_hook=unique,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('nonstandard_constant')))
def stream_hash(path,check):
 h=hashlib.sha256();n=0
 with Path(path).open('rb') as f:
  while True:
   b=f.read(1048576)
   if not b:break
   n+=len(b);h.update(b);check()
 return n,h.hexdigest()
def json_lines(path,cap,check):
 with Path(path).open('rb') as f:
  while True:
   raw=f.readline(cap+1)
   if not raw:break
   require(len(raw)<=cap and raw.endswith(b'\n'),'bounded_complete_JSONL_line');check();yield raw,loads(raw)
class RevisionProof:
 def __init__(self,page_cap,revision_cap):
  self.page_cap=page_cap;self.revision_cap=revision_cap;self.count=array.array('H',[0]);self.first=array.array('q',[-1]);self.offset=array.array('I',[0]);self.total=0;self.seen=None;self.observed=0;self.last=None
 def page(self,ordinal,count,first):
  require(self.seen is None and ordinal==len(self.count) and ordinal<=self.page_cap,'revision_page_order_or_cap')
  require(type(count) is int and 0<=count<=10000,'revision_perpage_bound')
  require((count==0 and first is None) or (count>0 and type(first) is int and 0<first<2**63),'first_revision_binding')
  require(self.total+count<=self.revision_cap,'revision_total_bound')
  self.count.append(count);self.first.append(-1 if first is None else first);self.offset.append(self.total);self.total+=count
 def seal(self):
  require(self.seen is None,'revision_already_sealed');self.seen=bytearray((self.total+7)//8)
 def revision(self,rid,page,ordinal):
  require(self.seen is not None,'revision_not_sealed')
  require(type(rid) is int and 0<rid<2**63 and type(page) is int and 0<page<len(self.count) and type(ordinal) is int and 0<ordinal<=self.count[page],'revision_occurrence_outside_expected')
  key=(rid,page,ordinal);require(self.last is None or key>self.last,'revision_PK_order_or_duplicate');self.last=key
  if ordinal==1:require(rid==self.first[page],'revision_first_ID_mismatch')
  bit=self.offset[page]+ordinal-1;byte,shift=divmod(bit,8);mask=1<<shift;require(not self.seen[byte]&mask,'duplicate_page_revision_ordinal');self.seen[byte]|=mask;self.observed+=1
 def finish(self):
  require(self.observed==self.total,'revision_missing_occurrences')
  return {'pages':len(self.count)-1,'expected':self.total,'observed':self.observed,'array_and_bitset_bytes':sum(x.itemsize*len(x) for x in [self.count,self.first,self.offset])+len(self.seen)}
def connect(path,check):
 db=sqlite3.connect(Path(path).as_uri()+'?mode=ro&immutable=1',uri=True)
 for p in ['query_only=ON','cache_size=-8192','temp_store=MEMORY','mmap_size=0']:db.execute('pragma '+p)
 db.set_progress_handler(lambda:(check() or 0),10000);return db

def verify_frame(profile,producer,selection,index_path,folder,decode,decoder_SHA,bridge,check):
 folder=Path(folder);db=connect(folder/'frame.sqlite',check);idx=connect(index_path,check)
 try:
  require(db.execute('pragma integrity_check').fetchall()==[('ok',)] and db.execute('pragma foreign_key_check').fetchone() is None,'SQL_integrity_FK')
  proof=RevisionProof(selection['rows'],30000000);namespace=collections.Counter();flagcounts=collections.Counter();ns0=0;references=0;groups=0;pages=0
  codec=loads((folder/'codec.json').read_bytes());modelcodes={0}|{x['code'] for x in codec['models']};require(len(modelcodes)<=129,'model_dictionary_bound')
  header=loads((folder/'header-receipt.json').read_bytes());decoded=header['decoded_bytes'];compressed=selection['header_bytes'];groupdigest=hashlib.sha256();groupbytes=0
  require(header['compressed_bytes']==compressed and header['CRC_EOF_members']>=1 and header['trailing_absent'],'header_CRC_receipt')
  require(stream_hash(folder/'original-header.xml',check)==(decoded,header['decoded_SHA256']),'original_header_hash')
  groupsSQL=iter(db.execute('select group_ordinal,compressed_start,compressed_end_exclusive,decoded_bytes,first_page_ordinal,last_page_ordinal,page_count,raw_SHA256 from groups order by group_ordinal'))
  pagesSQL=iter(db.execute('select row_ordinal,page_id,first_revision_id,namespace,flags,model_code,revision_count,main_text_bytes,group_decoded_start,raw_XML_bytes,raw_SHA256 from pages order by row_ordinal'))
  indexgroups=idx.execute('select group_ordinal,block_start,block_end_exclusive,first_row,last_row,row_count from groups where group_ordinal<=? order by group_ordinal',(selection['groups'],))
  receiptlines=iter(json_lines(folder/'group-receipts.jsonl',16384,check))
  for ig in indexgroups:
   check();g,begin,end,first,last,n=ig;sg=next(groupsSQL,None);packet=next(receiptlines,None);require(sg is not None and packet is not None,'missing_SQL_group_or_receipt');raw,t=packet;groups+=1;groupdigest.update(raw);groupbytes+=len(raw)
   require(g==groups and begin==compressed and first==pages+1 and last-first+1==n and 1<=n<=100 and end-begin<=profile['max_group_compressed_bytes'],'index_subset_partition')
   require(sg[:3]==(g,begin,end) and sg[4:7]==(first,last,n) and len(sg[7])==32,'SQLgroup_index_binding')
   require(t['group_ordinal']==g and t['compressed_start']==begin and t['compressed_end_exclusive']==end and t['compressed_bytes']==end-begin and t['decoded_global_start']==decoded and t['decoded_bytes']==sg[3] and t['decoded_SHA256']==sg[7].hex() and t['native_pages']==n and t['CRC_EOF_members']>=1 and t['trailing_absent'],'receipt_SQLgroup_CRC_span_binding')
   require(len(bytes.fromhex(t['compressed_SHA256']))==32,'compressed_receipt_SHA_shape')
   rawidentity=hashlib.sha256();semantic=hashlib.sha256();rawlines=hashlib.sha256();refs=0;lastend=0;got=0
   rows=idx.execute('select row_ordinal,page_id,title,raw_line_sha256,raw_line_bytes,line_ends_LF,noncanonical_offset_ascii,noncanonical_page_ascii,group_ordinal from rows where row_ordinal between ? and ? order by row_ordinal',(first,last))
   for ir in rows:
    ordinal,pid,title,lineSHA,linebytes,LF,offlex,idlex,rowgroup=ir;got+=1;require(ordinal==pages+1 and rowgroup==g,'index_row_order')
    off=str(begin) if offlex is None else offlex;ident=str(pid) if idlex is None else idlex
    require(off.isascii() and off.isdigit() and ident.isascii() and ident.isdigit() and int(off)==begin and int(ident)==pid and LF in (0,1),'index_numeric_or_LF')
    line=(off+':'+ident+':'+title).encode()+b'\n'*LF;require(len(line)<=131072 and len(line)==linebytes and hashlib.sha256(line).digest()==lineSHA,'index_rawline_hash')
    rawlines.update(line);rawidentity.update(transcript([ordinal,pid,title]));projected=decode(title);semantic.update(transcript([ordinal,pid,projected['semantic_expected_title']]));refs+=projected['references_decoded_once']
    v=next(pagesSQL,None);require(v is not None,'missing_SQLpage');o,ID,rev,ns,fl,model,revc,textbytes,span,length,sha=v
    require(o==ordinal and ID==pid and type(revc) is int and 0<=revc<=10000 and span>=lastend and length>0 and span+length<=sg[3] and len(sha)==32,'SQLpage_identity_span')
    require(type(fl) is int and 0<=fl<2**25 and model in modelcodes and textbytes>=-1,'SQLpage_finite_metadata');require(bool(fl&2)==(ns!=0) and bool(fl&8)==(revc==0) and bool(fl&16)==(revc>1) and bool(fl&32)==(textbytes==-1),'SQLpage_count_and_sentinel_flags');lastend=span+length;pages+=1;proof.page(o,revc,rev);namespace[str(ns)]+=1;flagcounts[str(fl)]+=1;ns0+=int(ns==0 and not fl&1)
    require(len(namespace)<=1024 and len(flagcounts)<=4096,'finite_counter_cardinality')
    if o<=1600:
     x=bridge['expected_SQL_fields'][o-1];require((ID,rev,ns,revc,textbytes,span,length,sha.hex())==(x['page_ID'],x['first_revision_ID'],x['namespace'],x['revision_count'],x['main_text_UTF8_bytes'],x['group_decoded_start'],x['raw_XML_bytes'],x['raw_SHA256']),'first1600_old_algorithm_bridge');require(bool(fl&1)==x.get('redirect_present',bool(fl&1)),'first1600_redirect_role_bridge')
   require(got==n and t['raw_index_lines_SHA256']==rawlines.hexdigest() and t['raw_index_identity_SHA256']==rawidentity.hexdigest(),'raw_index_transcripts')
   require(t['actual_native_identity_SHA256']==t['frozen_index_identity_SHA256']==semantic.hexdigest() and t['title_decoder_SHA256']==decoder_SHA and t['references_decoded_once']==refs,'semantic_native_transcript')
   require(t['durable']=={'durable_groups':groups,'durable_pages':pages,'durable_revision_occurrences':proof.total},'durable_group_counters')
   if g<=16 and len(bridge.get('expected_groups',[]))>=g:
    old=bridge['expected_groups'][g-1];require((begin,end,sg[3],n,t['compressed_SHA256'])==(old['compressed_start'],old['compressed_end_exclusive'],old['decoded_bytes'],old['page_count'],old['raw_compressed_SHA256']),'first16_prior_group_bridge')
   references+=refs;decoded+=sg[3];compressed=end
  require(next(groupsSQL,None) is None and next(pagesSQL,None) is None and next(receiptlines,None) is None,'extra_SQL_or_receipt_rows')
  require(groups==selection['groups'] and pages==selection['rows'] and compressed==selection['compressed_prefix_end_exclusive'],'exact_selected_coverage')
  nxt=idx.execute('select block_start,block_end_exclusive,first_row from groups where group_ordinal=?',(groups+1,)).fetchone();require(nxt is not None and nxt[0]==compressed and nxt[1]>profile['source_prefix_bytes'] and nxt[2]==pages+1,'next_group_incomplete_cutoff')
  summary=loads((folder/'header-summary.json').read_bytes());require(summary['scope']=='PREFIX_ONLY_EXTERNAL_GROUP_INDEX_PROOF_REQUIRED' and not summary['root_holds'] and summary['siteinfo_base_status']=='VERIFIED_HTTPS_ENWIKI_BASE' and summary['pages']==pages and summary['raw']['actual_root_closed'] is False and summary['raw']['global_XML_validity'] is False and summary['raw']['decoded_bytes']==decoded,'actual_open_root_prefix_scope')
  proof.seal()
  for rid,page,ordinal in db.execute('select revision_id,page_ordinal,revision_ordinal from revisions order by revision_id,page_ordinal,revision_ordinal'):
   proof.revision(rid,page,ordinal)
   if proof.observed%65536==0:check()
  revisions=proof.finish();counts=producer['counts'];require(counts['pages']==pages and counts['groups']==groups and counts['revision_occurrences']==proof.total and counts['ns0_nonredirect']==ns0,'terminal_counts')
  require(dict((str(k),v) for k,v in counts['namespace_counts'])==dict(namespace) and dict((str(k),v) for k,v in counts['flag_counts'])==dict(flagcounts),'terminal_metadata_counters')
  require(producer['decoded_prefix_bytes']==decoded and producer['compressed_prefix_bytes_read']==compressed,'terminal_byte_coverage')
  ex=producer['exceptions']
  if 'metadata_total_bytes' in ex:require(sum((folder/n).stat().st_size for n in ['original-header.xml','header-receipt.json','codec.json','header-summary.json','exceptions.jsonl','group-receipts.jsonl'])==ex['metadata_total_bytes']<=256000000,'combined_metadata_actual_bytes')
  require(ex['group_receipt_count']==groups and ex['group_receipt_bytes']==groupbytes and ex['ordered_group_receipts_SHA256']==groupdigest.hexdigest(),'terminal_group_stream_hash_count')
  eh=hashlib.sha256();eb=0;en=0
  for raw,event in json_lines(folder/'exceptions.jsonl',4000000,check):
   require(type(event) is dict and event.get('kind') in ('revision','page') and 1<=event['page_ordinal']<=pages,'exception_locator_scope');eh.update(raw);eb+=len(raw);en+=1
  require((en,eb,eh.hexdigest())==(ex['events'],ex['bytes'],ex['ordered_exception_SHA256']),'terminal_exception_stream_hash_count')
  return {'pages':pages,'groups':groups,'revisions':revisions,'compressed_bytes':compressed,'decoded_bytes':decoded,'references_decoded_once':references,'namespace_counts':dict(namespace),'flag_counts':dict(flagcounts),'ns0_nonredirect_pending_only':ns0,'exceptions':en,'group_receipt_bytes':groupbytes,'first1600_rawpage_bridge':True,'scope':'Complete selected closed-frame fragment only; no wholearchive/sourcequality/admission claim.'}
 finally:db.close();idx.close()

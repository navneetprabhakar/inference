"""One full compressed stream; complete-index ROW sampling, no article/ID claim."""
import bz2,hashlib,heapq,io,time
CAPS={'decoded_bytes':3000000000,'rows':40000000,'line_bytes':65536,'group_rows':10000,'group_raw_bytes':16000000,'evidence_bytes':16000000,'worker_seconds':570,'external_seconds':600,'observed_RSS_bytes':1000000000,'sample_rows':20}
def sha(b):return hashlib.sha256(b).hexdigest()
def parse(raw,ordinal,xmlsize):
 line=raw[:-1] if raw.endswith(b'\n') else raw
 fields=line.split(b':',2)
 if len(fields)!=3 or not fields[0].isdigit() or not fields[1].isdigit() or len(fields[0])>20 or len(fields[1])>20:raise ValueError('invalid_offset_pageID_title_row')
 offset=int(fields[0]);page=int(fields[1])
 if not 0<=offset<xmlsize or not 0<page<2**63:raise ValueError('offset_or_pageID_bounds')
 title=fields[2].decode('utf8',errors='strict')
 return {'row_ordinal':ordinal,'compressed_XML_block_start':offset,'page_ID_observed':page,'title_observed':title,'exact_offset_field_ascii':fields[0].decode(),'exact_page_ID_field_ascii':fields[1].decode(),'raw_line_sha256':sha(raw),'raw_line_bytes':len(raw),'raw_line_including_delimiter_hex':raw.hex(),'line_ends_LF':raw.endswith(b'\n')}

def assess(source,expected_sha256,expected_md5,expected_sha1,expected_bytes,xmlsize,seed,caps=None,check=lambda:None,progress=None):
 c=dict(CAPS if caps is None else caps);stats={'compressed_bytes':0,'decoded_bytes':0,'rows':0,'offset_groups':0,'bzip2_members':0,'unterminated_final_rows':0,'empty_titles':0,'maximum_group_rows':0,'maximum_group_raw_bytes':0,'maximum_line_bytes':0};
 if progress is not None:progress.update(stats);stats=progress
 digests=[hashlib.sha256(),hashlib.md5(),hashlib.sha1()];heap=[];group=[];groupoffset=None;groupbytes=0;linebuf=bytearray();decoder=None;needheader=bytearray();previous=None
 def finish_group(end):
  nonlocal group,groupbytes
  if not group:return
  stats['offset_groups']+=1
  for r in group:
   r['compressed_XML_block_end_exclusive']=end;r['compressed_XML_block_bytes']=end-r['compressed_XML_block_start'];r['compressed_range_HTTP_header']='bytes='+str(r['compressed_XML_block_start'])+'-'+str(end-1)
   priority=sha(('enwiki-native-index-row-discovery-v1\n'+seed+'\n'+expected_sha256+'\n'+str(r['row_ordinal'])).encode());r['sampling_priority_sha256']=priority
   entry=(-int(priority,16),-r['row_ordinal'],r)
   if len(heap)<c['sample_rows']:heapq.heappush(heap,entry)
   elif entry>heap[0]:heapq.heapreplace(heap,entry)
  group=[];groupbytes=0
 def row(raw):
  nonlocal groupoffset,groupbytes,previous
  check()
  if len(raw)>c['line_bytes']:raise ValueError('line_byte_cap')
  stats['rows']+=1
  if stats['rows']>c['rows']:raise ValueError('row_cap')
  r=parse(raw,stats['rows'],xmlsize);offset=r['compressed_XML_block_start']
  if previous is not None and offset<previous:raise ValueError('nonmonotonic_offsets')
  if groupoffset is None:groupoffset=offset
  elif offset!=groupoffset:finish_group(offset);groupoffset=offset
  previous=offset;groupbytes+=len(raw);group.append(r)
  if len(group)>c['group_rows'] or groupbytes>c['group_raw_bytes']:raise ValueError('one_offset_group_cap')
  stats['maximum_group_rows']=max(stats['maximum_group_rows'],len(group));stats['maximum_group_raw_bytes']=max(stats['maximum_group_raw_bytes'],groupbytes);stats['maximum_line_bytes']=max(stats['maximum_line_bytes'],len(raw));stats['unterminated_final_rows']+=not raw.endswith(b'\n');stats['empty_titles']+=not bool(r['title_observed'])
 def decoded(b):
  stats['decoded_bytes']+=len(b)
  if stats['decoded_bytes']>c['decoded_bytes']:raise ValueError('decoded_byte_cap')
  # At most64KiB pending raw line; never split/reconstruct a title field.
  parts=b.split(b'\n')
  for i,p in enumerate(parts):
   linebuf.extend(p)
   if i<len(parts)-1:linebuf.extend(b'\n')
   if len(linebuf)>c['line_bytes']:raise ValueError('line_byte_cap')
   if i<len(parts)-1:row(bytes(linebuf));linebuf.clear()
 while True:
  check();incoming=source.read(1048576)
  if not incoming:break
  stats['compressed_bytes']+=len(incoming)
  if stats['compressed_bytes']>expected_bytes:raise ValueError('compressed_size_exceeded')
  for h in digests:h.update(incoming)
  data=incoming
  while data or (decoder is not None and not decoder.needs_input and not decoder.eof):
   check()
   if decoder is None:
    take=min(4-len(needheader),len(data));needheader.extend(data[:take]);data=data[take:]
    if len(needheader)<4:break
    if needheader[:3]!=b'BZh' or needheader[3] not in b'123456789':raise ValueError('trailing_data_or_invalid_BZh_header')
    decoder=bz2.BZ2Decompressor();stats['bzip2_members']+=1;data=bytes(needheader)+data;needheader.clear()
   allowed=min(65536,c['decoded_bytes']-stats['decoded_bytes']+1)
   output=decoder.decompress(data,max_length=allowed);decoded(output);data=b''
   if decoder.eof:data=decoder.unused_data;decoder=None
 if decoder is not None or needheader:raise ValueError('truncated_bzip2_member_or_header')
 if stats['bzip2_members']==0:raise ValueError('empty_compressed_source')
 if linebuf:row(bytes(linebuf));linebuf.clear()
 if not stats['rows']:raise ValueError('empty_decoded_index')
 finish_group(xmlsize)
 actual=[d.hexdigest() for d in digests]
 if stats['compressed_bytes']!=expected_bytes or actual!=[expected_sha256,expected_md5,expected_sha1]:raise ValueError('whole_compressed_source_hash_size_mismatch')
 samples=[entry[2] for entry in sorted(heap,key=lambda e:(-e[0],-e[1]))]
 return {'stats':stats,'samples':samples,'source_SHA256':actual[0],'source_MD5':actual[1],'source_SHA1':actual[2],'all_bzip2_members_EOF_and_CRC_verified':True,'trailing_compressed_data_absent':True,'offsets_nondecreasing_verified':True,'global_page_ID_uniqueness_proven':False,'article_or_document_count_claimed':False,'XML_fullfile_checksums_verified':False,'sample_basis':'Uniform-priority row sample from COMPLETE observed index, not unique pages/namespace0/English articles. Every selected range is next distinct observedoffset or final publisherXMLsize. No XML/text availability conditioning.'}

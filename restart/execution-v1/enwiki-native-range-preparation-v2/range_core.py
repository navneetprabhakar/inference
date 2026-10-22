"""Exact native XML range transport. No XML parsing or decompression."""
import hashlib,json,time
URL='https://dumps.wikimedia.org/enwiki/20260801/enwiki-20260801-pages-articles-multistream.xml.bz2'
XML_BYTES=26668484995
PER_RANGE_CAP=2400000
BODY_CAP=50000000
LIMITS={'body_bytes':BODY_CAP,'output_bytes':56000000,'worker_seconds':570,'external_seconds':600,'observed_RSS_bytes':1000000000,'maximum_distinct_ranges':20,'maximum_range_bytes':PER_RANGE_CAP,'requests_per_second':1,'retries':0,'decompressed_bytes':0}
def freeze(selection):
 if selection['status']!='FROZEN20_LOWEST_HASH_COMPLETE_INDEX_ROW_DISCOVERY_NOT_ARTICLES' or selection['sample_rows']!=20 or len(selection['records'])!=20:raise ValueError('complete_frozen20_required')
 if not selection['metadata_only_no_XML_access'] or selection['XML_file_checksums_verified']:raise ValueError('selection_scope')
 rows=selection['records'];ordinals=set();priorities=[];ranges={}
 for r in rows:
  ordinal=r['row_ordinal'];start=r['compressed_XML_block_start'];end=r['compressed_XML_block_end_exclusive']
  if type(ordinal)is not int or ordinal<=0 or ordinal in ordinals:raise ValueError('ordinal_identity')
  ordinals.add(ordinal)
  if type(start)is not int or type(end)is not int or not 0<=start<end<=XML_BYTES:raise ValueError('range_bounds')
  n=end-start
  if n!=r['compressed_XML_block_bytes'] or r['compressed_range_HTTP_header']!=f'bytes={start}-{end-1}':raise ValueError('range_binding')
  raw=bytes.fromhex(r['raw_line_including_delimiter_hex']);fields=raw.removesuffix(b'\n').split(b':',2)
  if len(fields)!=3 or hashlib.sha256(raw).hexdigest()!=r['raw_line_sha256'] or len(raw)!=r['raw_line_bytes']:raise ValueError('native_line_hash')
  if fields[0].decode()!=r['exact_offset_field_ascii'] or fields[1].decode()!=r['exact_page_ID_field_ascii'] or int(fields[0])!=start or int(fields[1])!=r['page_ID_observed'] or fields[2].decode()!=r['title_observed'] or raw.endswith(b'\n')!=r['line_ends_LF']:raise ValueError('native_line_identity')
  expected=hashlib.sha256(('enwiki-native-index-row-discovery-v1\n'+selection['seed_hex']+'\n'+selection['source_SHA256']+'\n'+str(ordinal)).encode()).hexdigest()
  if r['sampling_priority_sha256']!=expected:raise ValueError('priority_binding')
  priorities.append((expected,ordinal))
  key=(start,end)
  if key not in ranges:
   ranges[key]={'start':start,'end_exclusive':end,'bytes':n,'Range':f'bytes={start}-{end-1}','URL':URL,'selected_row_ordinals':[],'status':'HELD_OVERSIZE_NO_REPLACEMENT' if n>PER_RANGE_CAP else 'PLANNED_EXACT_RANGE_NO_REQUEST','reservation_bytes':0 if n>PER_RANGE_CAP else n+1}
  ranges[key]['selected_row_ordinals'].append(ordinal)
 if priorities!=sorted(priorities):raise ValueError('frozen_selection_order')
 blocks=list(ranges.values())
 if len(blocks)>20 or sum(b['reservation_bytes'] for b in blocks)>BODY_CAP:raise ValueError('aggregate_range_reservation')
 return {'status':'FROZEN_NATIVE_RANGE_DISCOVERY_NOT_ACQUIRED','source_index_SHA256':selection['source_SHA256'],'publisher_XML_bytes':XML_BYTES,'URL':URL,'selected_rows':rows,'distinct_ranges':blocks,'selected_row_count':20,'reserved_body_bytes':sum(b['reservation_bytes'] for b in blocks),'requests':sum(b['reservation_bytes']>0 for b in blocks),'no_replacement':True,'publisher_XML_checksum_verified':False,'namespace_or_revision_known':False,'scope':'Index ROW discovery. Shared ranges fetched once. Oversize selections remain held. No article, unique-page, language, rights, quality or eligibility claim.'}
def header(response,name,required=True):
 values=response.headers.get_all(name,[])
 if len(values)!=1:
  if not values and not required:return None
  raise ValueError('missing_or_duplicate_'+name)
 return values[0]
def validate_response(response,block):
 if response.code!=206 or response.geturl()!=URL or block['URL']!=URL:raise ValueError('exact206_URL_required_no200_fallback')
 if header(response,'Content-Range')!=f"bytes {block['start']}-{block['end_exclusive']-1}/{XML_BYTES}":raise ValueError('exact_ContentRange_required')
 if header(response,'Content-Length')!=str(block['bytes']):raise ValueError('exact_ContentLength_required')
 if header(response,'Content-Encoding',False) not in (None,'identity'):raise ValueError('encoded_transfer')
 if header(response,'Transfer-Encoding',False) is not None:raise ValueError('transfer_encoding_not_accepted')
def stream(response,target,block,check):
 """One reserved overrun/EOF byte; exact bound including failure prefixes."""
 n=0;h=hashlib.sha256()
 with target.open('xb') as f:
  try:
   while True:
    check();b=response.read1(min(65536,block['bytes']+1-n))
    if not b:break
    if n+len(b)>block['reservation_bytes']:raise ValueError('unreserved_response_bytes')
    check(len(b));f.write(b);n+=len(b);h.update(b)
    if n>block['bytes']:raise ValueError('exact_range_body_overrun')
  finally:
   import os
   f.flush();os.fsync(f.fileno())
 if n!=block['bytes']:raise ValueError('truncated_exact_range')
 return n,h.hexdigest()

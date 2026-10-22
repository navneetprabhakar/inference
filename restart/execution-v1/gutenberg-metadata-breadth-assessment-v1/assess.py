import sqlite3,json,zlib,pathlib,hashlib,time,collections,datetime
base=pathlib.Path(__file__).resolve().parent;p=json.loads((base/'profile.json').read_text());src=pathlib.Path(p['source']);start=time.monotonic()
assert hashlib.file_digest(src.open('rb'),'sha256').hexdigest()==p['source_SHA256']
c=sqlite3.connect('file:'+str(src)+'?mode=ro',uri=True);c.execute('pragma query_only=ON');counts=collections.Counter();lcc=collections.Counter();genres=collections.Counter();extents=[];meta=[];total=0
for eid,status,era,rawbytes,blob in c.execute('select ebook_ID,discovery_status,era,raw_bytes,payload from frame order by ordinal'):
 if time.monotonic()-start>=45:raise TimeoutError('metadata45sec')
 total+=1
 if total>80000:raise ValueError('rowcap')
 if status!='ELIGIBLE_FOR_BODY_REVIEW_METADATA_ONLY' or era!='creator_deaths_all_exact_le1900_priority_only':continue
 if rawbytes>2000000:raise ValueError('decodedrecordcap')
 dec=zlib.decompressobj();raw=dec.decompress(blob,2000001)
 if len(raw)>2000000 or not dec.eof or dec.unused_data or dec.unconsumed_tail:raise ValueError('record_decodecap')
 d=json.loads(raw);counts['eligible_oldauthor_metadata']+=1
 roles=d['contributors_and_all_roles'];single=len(roles)==1 and roles[0]['role_qualified_name']=='{http://purl.org/dc/terms/}creator'
 if single:counts['single_creator_only_metadata']+=1
 codes=sorted({v for s in d['subjects'] if any(x.endswith('/LCC') for x in s['memberOf']) for v in s['values']})
 for x in codes:lcc[x]+=1
 gs=d['observed_genre_strata']
 for x in gs:genres[x]+=1
 formats=[f for f in d['all_formats'] if f.get('MIME_values')==['text/plain; charset=utf-8'] and isinstance(f.get('extent_bytes'),int) and f['extent_bytes']>0 and f.get('resolved_URL')==f'https://www.gutenberg.org/ebooks/{eid}.txt.utf-8' and not f.get('holds')]
 if len(formats)==1:
  n=formats[0]['extent_bytes'];counts['single_exact_UTF8_extent_metadata']+=1;extents.append(n)
  if single:meta.append({'ebook_ID':eid,'catalog_extent_bytes_not_body_verified':n,'LCC_metadata':codes,'genre_metadata':gs})
assert total==79652
result={'status':'COMPLETE_METADATA_ONLY_BREADTH_ASSESSMENT_NO_ACQUISITION_OR_ADMISSION','records_inspected':total,'counts':dict(counts),'LCC_metadata_nonexclusive':dict(lcc),'genre_metadata_nonexclusive':dict(genres),'UTF8_catalog_extents_sum_bytes_not_downloaded':sum(extents),'UTF8_catalog_extents_max_bytes':max(extents),'singlecreator_catalogued_body_records':len(meta),'singlecreator_catalogued_body_extent_sum_bytes':sum(x['catalog_extent_bytes_not_body_verified'] for x in meta),'scope':'Catalog file extents include packaging and may be stale. Metadata author dates/language/LCC are not body provenance, original-English evidence, quality, India rights or usable counts. Nonexclusive strata overlap; do not sum as disjoint genres. No tokens estimated.','source_SHA256':p['source_SHA256'],'elapsed_seconds':time.monotonic()-start,'new_admitted_documents':0,'new_admitted_tokens':0}
for name,obj in [('result.json',result),('singlecreator-metadata-capacity.json',meta)]:
 data=(json.dumps(obj,indent=2)+'\n').encode()
 if len(data)>4000000:raise ValueError('outputcap')
 (base/name).write_bytes(data)
print(json.dumps({k:v for k,v in result.items() if k not in ['LCC_metadata_nonexclusive','genre_metadata_nonexclusive']},indent=2))

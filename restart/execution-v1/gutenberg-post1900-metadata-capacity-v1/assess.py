import pathlib,sqlite3,json,hashlib,zlib,time,collections,re
base=pathlib.Path(__file__).resolve().parent;p=json.loads((base/'profile.json').read_text());src=pathlib.Path(p['source']);start=time.monotonic();assert hashlib.file_digest(src.open('rb'),'sha256').hexdigest()==p['source_SHA256']
c=sqlite3.connect('file:'+str(src)+'?mode=ro',uri=True);c.execute('pragma query_only=ON');counts=collections.Counter();rows=[]
for eid,blob in c.execute("select ebook_ID,payload from frame where discovery_status='ELIGIBLE_FOR_BODY_REVIEW_METADATA_ONLY' and era='creator_death_after1900_review' order by ordinal"):
 if time.monotonic()-start>45:raise TimeoutError('45sec')
 counts['post1900_metadata_rows_examined']+=1;dec=zlib.decompressobj();raw=dec.decompress(blob,2000001)
 if len(raw)>2000000 or not dec.eof or dec.unused_data or dec.unconsumed_tail:raise ValueError('decodecap')
 d=json.loads(raw);roles=d['contributors_and_all_roles']
 if len(roles)!=1 or roles[0]['role_qualified_name']!='{http://purl.org/dc/terms/}creator':continue
 death=roles[0]['deathdates']
 if len(death)!=1 or not re.fullmatch('[0-9]{4}',death[0]) or not 1901<=int(death[0])<=1965:continue
 counts['single_creator_exact1901_to1965_metadata']+=1
 fm=[f for f in d['all_formats'] if f.get('MIME_values')==['text/plain; charset=utf-8'] and isinstance(f.get('extent_bytes'),int) and f['extent_bytes']>0 and f.get('resolved_URL')==f'https://www.gutenberg.org/ebooks/{eid}.txt.utf-8' and not f.get('holds')]
 if len(fm)!=1:continue
 codes=sorted({v for s in d['subjects'] if any(x.endswith('/LCC') for x in s['memberOf']) for v in s['values']})
 rows.append({'ebook_ID':eid,'captured_exact_author_death':int(death[0]),'catalog_extent_bytes_not_body_verified':fm[0]['extent_bytes'],'LCC_metadata':codes,'genre_metadata':d['observed_genre_strata'],'creator_ID':roles[0]['stable_agent_ID'],'titles_metadata':d['titles']})
result={'status':'COMPLETE_METADATA_CAPACITY_ONLY_NO_POLICY_CHANGE','counts':dict(counts),'exact_UTF8_catalogued_records':len(rows),'catalog_extent_sum_bytes_not_downloaded':sum(r['catalog_extent_bytes_not_body_verified'] for r in rows),'PR_PS_metadata_records':sum(any(s in ['PR','PS'] for s in r['LCC_metadata']) for r in rows),'non_P_LCC_metadata_records':sum(bool(r['LCC_metadata']) and not any(s.startswith('P') for s in r['LCC_metadata']) for r in rows),'source_SHA256':p['source_SHA256'],'limits':p['limits'],'scope':p['scope'],'caveats':['Author dates are recorded catalog data, not independent life/publication proof.','No original-English, edition, translation, third-party component, jurisdiction rights or factual quality clearance.','File extents include packaging/may be stale. No usable or token yield inferred.'],'new_admitted_documents':0,'new_admitted_tokens':0,'elapsed_seconds':time.monotonic()-start}
for name,obj in [('result.json',result),('records.json',rows)]:
 data=(json.dumps(obj,indent=2)+'\n').encode()
 if len(data)>4000000:raise ValueError('outputcap')
 (base/name).write_bytes(data)
print(json.dumps(result,indent=2))

"""Synthetic only. Maximum-source policy and actual SQLite storage projections."""
import hashlib,json,pathlib,resource,sqlite3,tempfile,time,sys,zlib
import schema,bounded_policy
START=time.monotonic();D=pathlib.Path(__file__).resolve().parent
cases=[]
for name,unit in [('ascii_no_sentence_boundary','A coherent instructional paragraph explains a subject without guessing absent symbols '),('unicode','Une explication É; English explanation remains intact.\n')]:
 n=2195900//len(unit.encode());text=unit*n;t=time.monotonic();r=bounded_policy.evaluate(text);cases.append({'name':name,'UTF8_bytes':len(text.encode()),'characters':len(text),'seconds':time.monotonic()-t,'events':r['events'],'packed_bytes':len(r['zlib_bytes'])})
with tempfile.TemporaryDirectory() as tmp:
 p=pathlib.Path(tmp)/'capacity.sqlite';db=sqlite3.connect(p);db.execute('PRAGMA page_size=4096');db.execute('PRAGMA journal_mode=PERSIST');db.execute('PRAGMA synchronous=FULL');db.execute('PRAGMA foreign_keys=ON');db.execute('PRAGMA cache_size=-8192');db.execute('PRAGMA journal_size_limit=64000000');db.executescript(schema.SCHEMA);db.execute('INSERT INTO sources VALUES(1,?,?,?,?)',('synthetic',b'x'*32,'[]',106881));db.commit();t=time.monotonic();N=100000
 payload=bounded_policy.evaluate('This is a complete synthetic explanatory paragraph. Figure 1 is a context-only reference.\n')
 for i in range(N):
  h=hashlib.sha256(str(i).encode()).digest();row=(h,h,i%3000,20000,6000,1,0,0,1,1,0,1,i+1,1,0,0,payload['events'],payload['event_upper_bound'],payload['JSON_bytes']);db.execute('INSERT INTO texts VALUES('+','.join(['?']*19)+')',row);db.execute('INSERT INTO receipts VALUES(?,?,?,?,?)',(h,payload['JSON_SHA256'],payload['zlib_bytes'],payload['zlib_SHA256'],payload['codec']));db.execute('INSERT INTO occurrences VALUES(?,?,?,?,?,?,?,?,?,?)',(1,i+1,i*20100,20100,h,h,0,0,1,None))
  if (i+1)%100==0:db.commit()
 db.commit();require=db.execute('PRAGMA integrity_check').fetchone()==('ok',) and db.execute('PRAGMA foreign_key_check').fetchone() is None;assert require
 size=p.stat().st_size;scenarios=[]
 for count in [8,62]:
  obj={'reasons':[],'context':[]}
  for i in range(count):obj['context'].append({'reason':'FIGURE_REFERENCE_CONTEXT','char_start':i*99,'char_end':i*99+8,'byte_start':i*100,'byte_end':i*100+8,'source_span_SHA256':hashlib.sha256(f'{count}/{i}'.encode()).hexdigest(),'detail':{'automatic_hold':False,'automatic_component_boundary':False}})
  raw=json.dumps(obj,separators=(',',':')).encode();packed=zlib.compress(raw,6);extra=max(0,len(packed)-len(payload['zlib_bytes']));projected=size*(79874/100000)+extra*79874+max(0,106881-79874)*512+79874*128
  scenarios.append({'events_per_distinct_text':count,'packed_receipt_bytes':len(packed),'DB_projection_bytes':int(projected),'additional_occurrence_allowance_bytes':max(0,106881-79874)*512,'per_distinct_payload_variability_allowance_bytes':79874*128,'projection_plus25percent':int(projected*1.25),'within600MB_plus25percent':projected*1.25<600000000,'scope':'Heuristic storage projection, not a bound; DB600MB/aggregate1GB hard guards remain.'})
 result={'status':'SYNTHETIC_CAPACITY_ONLY_NO_SOURCE_BODY','SQLite_100000_texts_and_occurrences_bytes':size,'SQLite_seconds':time.monotonic()-t,'journal_bytes':p.with_name(p.name+'-journal').stat().st_size,'integrity_FK_PASS':require,'receipt_scenarios':scenarios,'max_source_policy_cases':cases,'peak_self_RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024),'total_seconds':time.monotonic()-START,'proposed_worker_seconds':1800,'proposed_external_seconds':1860,'runtime_uncertainty':'Policy timing from maximum synthetic strings, I/O and106881source/DB joins not measured here. No claim full job completion guaranteed. Hard limits and partial preservation apply.'};db.close()
(D/'capacity.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

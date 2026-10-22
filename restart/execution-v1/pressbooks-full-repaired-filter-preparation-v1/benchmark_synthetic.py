"""Synthetic capacity and max-width local resource evidence, no retained source."""
import tempfile,sqlite3,hashlib,zlib,time,json,resource
from pathlib import Path
import schema,bounded_policy
start=time.clock_gettime(time.CLOCK_MONOTONIC)
with tempfile.TemporaryDirectory() as t:
 p=Path(t)/'capacity.sqlite';db=sqlite3.connect(p);db.execute('PRAGMA journal_mode=PERSIST');db.execute('PRAGMA journal_size_limit=64000000');db.executescript(schema.SCHEMA);db.execute('INSERT INTO sources VALUES(1,?,?,?,?)',('SYNTHETIC',bytes(32),'[]',5000))
 for i in range(5000):
  h=hashlib.sha256(str(i).encode()).digest();payload=zlib.compress(b''.join(hashlib.sha256(f'{i}:{j}'.encode()).digest() for j in range(64)),6)
  db.execute('INSERT INTO texts VALUES('+','.join('?'*20)+')',(h,h,50,2000,100,1,0,0,0,1,1,0,1,i+1,1,0,0,0,None,10000));db.execute('INSERT INTO receipts VALUES(?,?,?,?,?)',(h,h,payload,hashlib.sha256(payload).digest(),'SYNTHETIC_CAPACITY_NOT_A_REAL_POLICY_RECEIPT'));db.execute('INSERT INTO occurrences VALUES(?,?,?,?,?,?,?,?,?,?)',(1,i+1,0,2000,h,h,0,0,1,None))
  if i%100==99:db.commit()
 for k in range(1691):
  h=hashlib.sha256(str(k).encode()).digest();db.execute('INSERT INTO occurrences VALUES(?,?,?,?,?,?,?,?,?,?)',(1,5001+k,0,2000,h,h,0,0,1,None));db.execute('UPDATE texts SET occurrences=occurrences+1 WHERE text_SHA256=?',(h,))
 db.commit();db.close();size=p.stat().st_size
capacity={'measured_texts_and_receipts':5000,'measured_occurrences':6691,'SQLite_bytes':size,'receipt_payload':'Each zlib-packed2048B deterministic high-entropy synthetic metadata, not source text/actualpolicyreceipt.','linear_projected_79874texts_106881occurrences_including25percent_uncertainty':int(size/5000*79874*1.25),'DB_hard_cap':600000000,'interpretation':'Finite schema stress estimate only, not guarantee of real event density. Actual output/DB/event caps remain terminal.'}
t='Intact plain explanatory prose.\n';text=(t*(2196000//len(t.encode())+1))[:2196000]
identity={'source_id':1,'ordinal':1,'text_SHA256':hashlib.sha256(text.encode()).hexdigest(),'source_JSON_SHA256':'a'*64};r=bounded_policy.evaluate(text,identity)
print(json.dumps({'status':'SYNTHETIC_RESOURCE_EVIDENCE_ONLY','storage':capacity,'max_text_UTF8_bytes':len(text.encode()),'max_text_events':r['events'],'max_text_receipt_JSON_bytes':r['JSON_bytes'],'max_observed_self_RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'elapsed_seconds':time.clock_gettime(time.CLOCK_MONOTONIC)-start,'retained_source_reads':0},indent=2))

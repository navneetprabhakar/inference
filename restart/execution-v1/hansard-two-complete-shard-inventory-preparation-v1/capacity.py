"""Synthetic SQLite footprint only. No Hansard body read."""
import json,sqlite3,tempfile,time,hashlib
from pathlib import Path
import inventory
start=time.monotonic()
with tempfile.TemporaryDirectory() as z:
 p=Path(z)/'frame.sqlite';db=sqlite3.connect(p);db.execute('PRAGMA page_size=4096');db.executescript(inventory.SCHEMA);db.execute('INSERT INTO sources VALUES(1,?,?,?)',('synthetic', '0'*64,1));db.commit()
 source='uk-hansard-lords-written-answers';license='Open Parliament Licence - https://www.parliament.uk/site-information/copyright-parliament/open-parliament-licence/'
 for i in range(1,20001):
  id='synthetic-identity-'+str(i).zfill(10)+'x'*100
  db.execute('INSERT INTO records VALUES('+','.join('?'*16)+')',(1,i,i*1000,1000,1,b'a'*32,0,id,source,'2024-06-01','2016','en',license,b'b'*32,34540,34540))
 db.commit();size=p.stat().st_size;db.close()
print(json.dumps({'status':'SYNTHETIC_CAPACITY_MEASUREMENT_NOT_OBSERVED_SOURCE_YIELD','rows':20000,'bytes':size,'bytes_per_row':size/20000,'linear_500k_projection':size/20000*500000,'SQLite_hardcap':512000000,'all_output_hardcap':600000000,'completion_guaranteed':False,'caveat':'Synthetic128-character identity and actual schema-example metadata length; longer or unknown fields can reach hard cap and stop with partial receipt. No assumption about actual shard rows/decoded size.','elapsed_seconds':time.monotonic()-start,'source_body_reads':0},indent=2))

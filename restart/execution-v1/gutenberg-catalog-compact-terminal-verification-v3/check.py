import hashlib,importlib.util,json,pathlib,sqlite3,zlib
P=pathlib.Path(__file__).resolve().parent;s=importlib.util.spec_from_file_location('terminal_verifier',P/'verify.py');v=importlib.util.module_from_spec(s);s.loader.exec_module(v);checks=[]
db=sqlite3.connect((v.c.ORIGINAL/'catalog.sqlite3').as_uri()+'?mode=ro',uri=True);payload=db.execute('select data from records order by member limit1'.replace('limit1','limit 1')).fetchone()[0];db.close();raw=payload.encode();blob=zlib.compress(raw,6);packed=[len(raw),hashlib.sha256(raw).hexdigest(),hashlib.sha256(blob).hexdigest(),v.c.CODEC,blob];assert v.independently_unpack(*packed)==json.loads(payload);checks.append('actual_retained_prefix_allfields_roundtrip')
for name,index,value in [('length',0,len(raw)-1),('rawhash',1,'0'*64),('packedhash',2,'0'*64),('codec',3,'wrong'),('oversize',0,16000001)]:
 bad=list(packed);bad[index]=value
 try:v.independently_unpack(*bad)
 except ValueError:pass
 else:raise AssertionError(name)
 checks.append(name+'_tamper_refused')
for name,badblob in [('truncated',blob[:-1]),('trailing',blob+b'extra')]:
 bad=list(packed);bad[-1]=badblob;bad[2]=hashlib.sha256(badblob).hexdigest()
 try:v.independently_unpack(*bad)
 except ValueError:pass
 else:raise AssertionError(name)
 checks.append(name+'_recomputed_packedhash_refused')
# A pragma can delete TEMP views. Explicit qualification must then fail.
import tempfile
with tempfile.TemporaryDirectory() as td:
 paths=[pathlib.Path(td)/('part'+str(i)+'.sqlite3') for i in range(2)]
 for i,path in enumerate(paths):
  db=sqlite3.connect(path);db.executescript('create table members(ordinal integer);create table records(member integer);');db.execute('insert into members values (?)',(i+1,));db.execute('insert into records values (?)',(i+1,));db.commit();db.close()
 u=v.c.readonly_union(paths);assert u.execute('select count(*) from temp.members').fetchone()[0]==2;u.execute('pragma temp_store=MEMORY')
 assert u.execute('select count(*) from members').fetchone()[0]==1
 try:u.execute('select count(*) from temp.members').fetchone()
 except sqlite3.OperationalError:pass
 else:raise AssertionError('Missing temp view did not fail closed')
 u.close();checks.append('lost_TEMP_views_explicit_temp_qualification_fails_no_attached_shard_fallback')
r={'status':'PASS_FOCUSED_STORED_PAYLOAD_VERIFIER_CONTROLS','case_count':len(checks),'checks':checks,'actual_complete_catalog_read':False,'network_requests':0};(P/'prepared-checks.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))

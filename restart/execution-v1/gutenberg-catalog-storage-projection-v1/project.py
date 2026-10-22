"""<=10MB/30sec actual-prefix SQLite capacity measurement, not source census."""
import ast,hashlib,json,sqlite3,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;EXEC=HERE.parent;PREP=EXEC/'gutenberg-catalog-compact-preparation-v1';sys.path.insert(0,str(PREP));import compact as c
CAP=10000000;SECONDS=30;started=time.monotonic();source=c.ORIGINAL/'catalog.sqlite3';output=HERE/'sample-exact-schema.sqlite3';checks=[]
def sha(b):return hashlib.sha256(b).hexdigest()
def guard():
 if time.monotonic()-started>=SECONDS:raise TimeoutError('30second projection cap')
 if sum(f.stat().st_size for f in HERE.iterdir() if f.is_file())>=CAP:raise ValueError('10MBprojection output/scratch cap')
assert not output.exists();read=sqlite3.connect('file:'+str(source.resolve())+'?mode=ro',uri=True)
try:samples=read.execute('select records.member,records.ebook_ID,records.data,members.data from records join members on members.ordinal=records.member where records.member%90=0 order by records.member limit 400').fetchall()
finally:read.close()
assert len(samples)==400
node=next(x for x in ast.parse((PREP/'compact.py').read_text()).body if isinstance(x,ast.FunctionDef) and x.name=='inventory')
ddls=[x.args[0].value for x in ast.walk(node) if isinstance(x,ast.Call) and isinstance(x.func,ast.Attribute) and x.func.attr=='execute' and x.args and isinstance(x.args[0],ast.Constant) and isinstance(x.args[0].value,str) and x.args[0].value.startswith('create ')]
assert len(ddls)==4
write=sqlite3.connect(output);write.execute('pragma page_size=4096');write.execute('pragma journal_mode=DELETE');write.execute('pragma synchronous=FULL');write.execute('pragma cache_size=-4096');write.execute('pragma temp_store=FILE');write.execute('pragma max_page_count='+str(c.DB_CAP//4096))
for sql in ddls:write.execute(sql)
write.commit();basebytes=output.stat().st_size;totals={'record_raw_JSON_bytes':0,'record_packed_bytes':0,'member_raw_JSON_bytes':0,'member_packed_bytes':0};maxrecord=0;peak=0;rows=[]
try:
 for ordinal,eid,record_json,member_json in samples:
  guard();r=json.loads(record_json);m=json.loads(member_json);pr=c.pack(r);pm=c.pack(m)
  assert c.unpack(*pr)==r and c.unpack(*pm)==m and pr[1]==sha(record_json.encode())
  write.execute('insert into members values(?,?,?,?,?,?,?,?,?,?)',(ordinal,m['name'],m['size'],m['body_SHA256'],m['hold'],*pm))
  write.execute('insert into records values(?,?,?,?,?,?,?,?,?,?,?,?,?)',(ordinal,eid,*c.indexes(r),*pr))
  totals['record_raw_JSON_bytes']+=pr[0];totals['record_packed_bytes']+=len(pr[-1]);totals['member_raw_JSON_bytes']+=pm[0];totals['member_packed_bytes']+=len(pm[-1]);maxrecord=max(maxrecord,len(pr[-1]));rows.append({'member_ordinal':ordinal,'ebook_ID':eid,'record_raw_SHA256':pr[1],'record_packed_bytes':len(pr[-1]),'member_raw_SHA256':pm[1],'member_packed_bytes':len(pm[-1])})
  if len(rows)%100==0:
   peak=max(peak,sum(f.stat().st_size for f in HERE.iterdir() if f.is_file()));write.commit();guard()
 write.commit();integrity=write.execute('pragma integrity_check').fetchone()[0];pagecount=write.execute('pragma page_count').fetchone()[0];pagesize=write.execute('pragma page_size').fetchone()[0]
 schema=[x[0] for x in write.execute("select sql from sqlite_master where sql is not null order by name")]
 try:byobject=write.execute('select name,sum(pgsize) from dbstat group by name order by name').fetchall()
 except sqlite3.OperationalError:byobject=None
finally:write.close()
finalbytes=output.stat().st_size;guard();assert integrity=='ok' and finalbytes==pagecount*pagesize
incremental=(finalbytes-basebytes)/400;withbase=finalbytes/400
projected={str(n):{'linear_actual_SQLite_bytes':round(basebytes+incremental*n),'with25percent_capacity_margin':round(basebytes+incremental*n*1.25)} for n in [80000,100000,150000]}
r={'status':'ACTUAL_PREFIX_STORAGE_PROJECTION_ONLY_NOT_CATALOG_CENSUS_OR_QUALITY_SAMPLE','selection':'Exactly400 retained parsedrecords where memberordinal%90=0, ascendingmemberordinal; members90..36000. Existingpartialprefix, systematicallyselected, notrepresentativeofthecompletecatalog.','source_original_failed_DB_SHA256':'a2100b3dbb01f43688263789b798dc978e5daf22fe5bdb544693f3bf32319400','source_path':str(source),'production_compact_code_SHA256':c.file_sha(PREP/'compact.py'),'exact_schema_DDLs':ddls,'saved_SQLite_schema':schema,'sample_count':400,'SQLite_base_bytes':basebytes,'SQLite_final_bytes':finalbytes,'SQLite_incremental_bytes_per_record_including_member_and_indexes':incremental,'SQLite_average_bytes_per_record_withbase':withbase,'actual_means':{k:v/400 for k,v in totals.items()},'maximum_sample_record_packed_bytes':maxrecord,'SQLite_object_bytes':byobject,'projection_assumptions':['Linear sampleaverage andsameSQLitepacking; actualcompletecatalogrecordcountandlaterprefixmetadatawidthunknown.','80000/100000countsarecapacityscenarios,notobservedcatalogpopulation;150000istheapprovedarchive-memberbound,notprovenebookcount.','25percentmarginisengineeringallowance,notstatisticalconfidenceinterval.','Nooriginalarchiveopened/parsed;nosupply/English/original-work/quality/rightscountsextrapolated.'],'capacity_scenarios':projected,'single400MB_assessment':'Insufficientifprojectionat80000recordsplusreasonablemarginexceeds400MB;actualsampleevidencereported,notaguarantee.','candidate_two_shard_assessment':'Two300MBdatabasesincreaseaggregatehardDBallowanceto600MB;onlyoneactivejournalwriterand32MBheadroommustbeproven. Completecatalogmaystillfailboundedifactualwidth/countoutgrowtheprofile.','elapsed_seconds':time.monotonic()-started,'peak_observed_projection_file_bytes':peak,'scratch_output_cap':CAP,'new_admitted_documents':0,'new_admitted_tokens':0,'network_requests':0,'ledger_mutations':0}
raw=(json.dumps(r,indent=2)+'\n').encode();manifest=(''.join(json.dumps(x,sort_keys=True)+'\n' for x in rows)).encode()
if sum(f.stat().st_size for f in HERE.iterdir() if f.is_file())+len(raw)+len(manifest)>CAP:raise ValueError('Projection receipt/file cap')
for name,b in [('projection.json',raw),('sample-row-hashes.jsonl',manifest)]:
 with (HERE/name).open('xb') as f:f.write(b)
print(json.dumps(r,indent=2))

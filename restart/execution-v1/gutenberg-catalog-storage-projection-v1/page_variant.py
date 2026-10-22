"""Same400actual rows/schema,64KiBpages; combinedprojectionoutputs<10MB."""
import json,sqlite3,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE.parent/'gutenberg-catalog-compact-preparation-v1'));import compact as c
start=time.monotonic();first=json.loads((HERE/'projection.json').read_text());path=HERE/'sample-page65536.sqlite3';assert not path.exists()
read=sqlite3.connect('file:'+str((c.ORIGINAL/'catalog.sqlite3').resolve())+'?mode=ro',uri=True)
try:rows=read.execute('select records.member,records.ebook_ID,records.data,members.data from records join members on members.ordinal=records.member where records.member%90=0 order by records.member limit 400').fetchall()
finally:read.close()
d=sqlite3.connect(path);d.execute('pragma page_size=65536');d.execute('pragma journal_mode=DELETE');d.execute('pragma synchronous=FULL');d.execute('pragma cache_size=-4096');d.execute('pragma temp_store=FILE')
for sql in first['exact_schema_DDLs']:d.execute(sql)
d.commit();base=path.stat().st_size
try:
 for ordinal,eid,rj,mj in rows:
  if time.monotonic()-start>20:raise TimeoutError('Remaining20sec variantbudget')
  r=json.loads(rj);m=json.loads(mj);pr=c.pack(r);pm=c.pack(m)
  d.execute('insert into members values(?,?,?,?,?,?,?,?,?,?)',(ordinal,m['name'],m['size'],m['body_SHA256'],m['hold'],*pm));d.execute('insert into records values(?,?,?,?,?,?,?,?,?,?,?,?,?)',(ordinal,eid,*c.indexes(r),*pr))
  if ordinal%9000==0:d.commit()
  if sum(f.stat().st_size for f in HERE.iterdir() if f.is_file())>=10000000:raise ValueError('Combined10MBscratchlimit')
 d.commit();assert d.execute('pragma integrity_check').fetchone()[0]=='ok';assert d.execute('pragma page_size').fetchone()[0]==65536
finally:d.close()
size=path.stat().st_size;increment=(size-base)/400
result={'status':'ACTUAL_SAME400_SCHEMA_ROWS_PAGE65536_STORAGE_ONLY','original_v1_projection_SHA256':c.file_sha(HERE/'projection.json'),'same_sample_original_records_and_all_metadata':True,'schema_identical_to_production_except_page_size':True,'page_size':65536,'sample_records':400,'base_schema_bytes':base,'final_SQLite_bytes':size,'incremental_SQLite_bytes_per_record_including_member_and_indexes':increment,'capacity_scenarios':{str(n):{'two_shard_linear_bytes':round(2*base+increment*n),'two_shard_with25percent_engineering_margin':round(2*base+increment*n*1.25)} for n in [80000,100000,150000]},'two_shard_total_hard_DB_bytes':600000000,'maximum_actual_sample_average_records_before600MB':int((600000000-2*base)//increment),'projection_sample_not_complete_catalog_count_or_quality':True,'elapsed_seconds':time.monotonic()-start,'first_projection_elapsed_seconds':first['elapsed_seconds'],'combined_projection_file_bytes_now':sum(f.stat().st_size for f in HERE.iterdir() if f.is_file()),'peak_scope_note':'Originalprojectionpeakfieldrecordedprecommitobservations;finalfilecountisalsoexplicitlyguarded. Thisvariantandallpriorprojectionfilesremaintogetherunder10MB.','network_requests':0,'ledger_mutations':0}
b=(json.dumps(result,indent=2)+'\n').encode();assert result['combined_projection_file_bytes_now']+len(b)<10000000
with (HERE/'page65536-projection.json').open('xb') as f:f.write(b)
print(json.dumps(result,indent=2))

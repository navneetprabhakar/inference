"""Full1.6M-window synthetic maximum-field measurement; no retained inputs."""
import pathlib,sqlite3,tempfile,time,hashlib,json,resource,sys
from schema import SCHEMA,DOC_INSERT,WINDOW_INSERT,TEXT_INSERT
start=time.monotonic();windows=1600000;docs=106881;CAP=768000000
with tempfile.TemporaryDirectory(prefix='PB-synthetic-capacity-') as z:
 p=pathlib.Path(z)/'sample.sqlite';db=sqlite3.connect(p);db.execute('pragma page_size=4096');db.execute('pragma journal_mode=PERSIST');db.execute('pragma synchronous=FULL');db.execute('pragma cache_size=-8192');db.execute('pragma temp_store=MEMORY');db.execute('pragma journal_size_limit=32000000');db.execute('pragma max_page_count='+str(CAP//4096));db.executescript(SCHEMA)
 for d in range(1,docs+1):
  sha=hashlib.sha256(str(d).encode()).digest();db.execute(DOC_INSERT,(d,1 if d<=73943 else 2,d if d<=73943 else d-73943,sha,sha,sha,2179415,2195961,2195961,1,15,0,0,.111111,2048,7,sha,8000000));db.execute(TEXT_INSERT,(sha,2179415,2195961,2195961,0,.111111,15,0,1,7,2048,sha,8000000))
  if d%64==0:db.commit()
 db.commit();batch=[]
 for i in range(windows):
  d=i//15+1;ordinal=i%15;sha=hashlib.sha256(i.to_bytes(8,'little')).digest();batch.append((d,ordinal,int(ordinal>0),2178391,2179415,1024,sha,sha,1,None,'__label__'+'a'*24,'0.'+'1'*62,.111111,0.,0))
  if len(batch)>=960:db.executemany(WINDOW_INSERT,batch);db.commit();batch=[]
 if batch:db.executemany(WINDOW_INSERT,batch);db.commit()
 assert db.execute('select count(*) from docs').fetchone()==(docs,) and db.execute('select count(*) from windows').fetchone()==(windows,)
 assert db.execute('pragma integrity_check').fetchone()==('ok',) and db.execute('pragma foreign_key_check').fetchone() is None
 page_count=db.execute('pragma page_count').fetchone()[0];db.close();size=p.stat().st_size;journal=pathlib.Path(str(p)+'-journal').stat().st_size
 result={'status':'MEASURED_SYNTHETIC_MAXIMUM_FIELD_PROJECTION_NOT_CORPUS_RESULT','rows':{'docs':docs,'windows':windows,'texts':docs},'schema_SHA256':hashlib.sha256(SCHEMA.encode()).hexdigest(),'SQLite_bytes':size,'page_count':page_count,'PERSIST_journal_bytes':journal,'DB_cap_proposed':CAP,'DB_with25percent_margin_bytes':size*1.25,'fits_proposed_cap_with25pct':size*1.25<CAP,'all_output_cap_proposed':1000000000,'journal_reserve_proposed':32000000,'field_shape':'Allwindows scored,33charlabel,64charprobability,3byte-largeoffsets,32Braw+projectionhashes; alldocs have unique textSHA so texts table maximal106881; practical labels/probs usually shorter. No text payloads.','elapsed_seconds':time.monotonic()-start,'peak_RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024),'temporary_DB_deleted_after_measurement':True,'retained_source_or_classifier_reads':0}
 print(json.dumps(result,indent=2))

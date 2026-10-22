"""400 existing prefix diagnostics, exact production schema, small offline projection only."""
import json,sqlite3,sys,time
from pathlib import Path
import frame
HERE=Path(__file__).resolve().parent;start=time.monotonic();path=HERE/'sample400-capacity.sqlite3';assert not path.exists();db=frame.database(path);empty=path.stat().st_size
rows=[]
original=sqlite3.connect('file:'+str((frame.EXEC/'gutenberg-catalog-storage-projection-v1/sample-page65536.sqlite3').resolve())+'?mode=ro',uri=True)
diag={json.loads(line)['ebook_ID']:json.loads(line) for line in (frame.EXEC/'gutenberg-English-frame-preparation-v1/prefix400-diagnostic-rows.jsonl').open()}
try:
 for ordinal,*packed in original.execute('select member,raw_bytes,raw_hash,packed_hash,codec,payload from records order by member'):
  native=frame.c.unpack(*packed);binding=diag[native['ebook_ID']]['source_binding'];row=frame.classified(native,binding);rows.append(row);frame.insert(db,row,ordinal,'ORIGINAL_SOURCE_PARSED')
finally:original.close()
for row in rows:db.execute('insert into families values(?,?,?,?)',(row['ebook_ID'],row['ebook_ID'],row['priority_key'],json.dumps([a['role_qualified_name'] for a in row['contributors_and_all_roles']],separators=(',',':'))))
db.commit();assert db.execute('pragma integrity_check').fetchone()[0]=='ok';db.close();size=path.stat().st_size;increment=(size-empty)/400;result={'status':'ACTUAL400_PREFIX_EXACT_FRAME_SCHEMA_CAPACITY_ONLY','rows':400,'SQLite_page_size':frame.PAGE,'empty_bytes':empty,'database_bytes':size,'incremental_bytes_per_row':increment,'scenario79652_bytes':empty+increment*79652,'scenario79652_plus10percentengineering_margin_bytes':empty+increment*79652*1.10,'source_scope':'Existing systematically selected prefix only; not full frame count/quality/probability inference.','source_diagnostic_SHA256':frame.c.file_sha(frame.EXEC/'gutenberg-English-frame-preparation-v1/prefix400-diagnostic-rows.jsonl'),'elapsed_seconds':time.monotonic()-start};(HERE/'capacity.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

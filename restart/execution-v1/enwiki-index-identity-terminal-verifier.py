"""Stored SQLite and receipt verifier, no source-index/XML stream or producer rerun."""
from pathlib import Path
import sys,json,hashlib,sqlite3,types,os,signal,time
B=Path(__file__).resolve().parent;P=B/'enwiki-index-identity-frame-preparation-v1';D=B/'m2-intake/enwiki-complete-index-identity-frame-v1';O=B/'enwiki-index-identity-terminal-independent-verification-v1'
sys.path.insert(0,str(P));import inventory as producer
SUP=B/'wikibooks-rendered-heading-triage-executor-preparation-v1/supervisor_core.py'
spec=__import__('importlib.util',fromlist=['']).spec_from_file_location('verification_supervisor',SUP);sup=__import__('importlib.util',fromlist=['']).module_from_spec(spec);spec.loader.exec_module(sup)
sup.LIMITS={'worker_seconds':290,'external_seconds':300,'output_bytes':16000000,'tree_RSS_bytes':1000000000}
h=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def worker(start):
 sup.arm(290-(time.clock_gettime(time.CLOCK_MONOTONIC)-start))
 p=producer.verify(types.SimpleNamespace(code_pins_sha256='c658f2538345e8362c91dbc5656b69bbecc7c84b4132b45633237d8a4e106277',profile_sha256='a58362e5bbfb7a3f63b3d7f7a7dceb01ba8edad690350ff373cbea722d1940d3'))
 r=json.loads((D/'result.json').read_text());s=json.loads((D/'supervisor.json').read_text());owner=json.loads((D/'ownership.json').read_text());assert r['status']=='COMPLETE_INDEX_IDENTITY_FRAME_NO_ADMISSION' and s['status']=='COMPLETE_INDEX_IDENTITY_FRAME_SUPERVISED_NO_ADMISSION' and s['worker_exit_code']==0 and s['worker_reaped'] and s['worker_receipt_SHA256']==h(D/'result.json')
 for key in ['supervisor_pid','worker_pid']:
  try:os.kill(owner[key],0)
  except ProcessLookupError:pass
  else:raise AssertionError('producerPID_present')
 dbpath=D/'index.sqlite';before=producer.stat(dbpath);assert not dbpath.is_symlink() and dbpath.stat().st_size==r['SQLite_bytes']<=3800000000;dbhash=producer.sha(dbpath);assert dbhash==r['SQLite_SHA256']==s['SQLite_SHA256'];assert r['source_stats']==p['source']['stats'] and all(r['source_'+key]==p['source'][key] for key in ['SHA256','MD5','SHA1']);assert r['all_BZ2_EOF_CRC_verified'] and r['trailing_compressed_data_absent']
 db=sqlite3.connect(dbpath.as_uri()+'?mode=ro',uri=True);db.execute('pragma query_only=ON');db.execute('pragma cache_size=-32768');db.execute('pragma temp_store=MEMORY');db.execute('pragma mmap_size=0')
 assert db.execute('pragma integrity_check').fetchall()==[('ok',)] and db.execute('pragma foreign_key_check').fetchall()==[]
 indices=db.execute('pragma index_list(rows)').fetchall();assert any(x[2]==1 and [q[2] for q in db.execute('pragma index_info('+x[1]+')')]==['page_id'] for x in indices)
 assert db.execute('select count(*),min(row_ordinal),max(row_ordinal) from rows').fetchone()==(25792234,1,25792234)
 prov={k:json.loads(v) for k,v in db.execute('select key,value from provenance')};assert prov['source_stats']==r['source_stats'] and prov['global_page_ID_uniqueness_proven'] and prov['source_SHA256']==p['source']['SHA256']
 groups=[];lastend=None;lastrow=0
 for gid,a,b,first,last,count in db.execute('select group_ordinal,block_start,block_end_exclusive,first_row,last_row,row_count from groups order by group_ordinal'):
  assert gid==len(groups)+1 and a>=0 and a<b<=p['source']['XML_bytes'] and (lastend is None or a==lastend) and first==lastrow+1 and last-first+1==count and 1<=count<=100
  groups.append((gid,first,last,a,b));lastend=b;lastrow=last
 assert len(groups)==257960 and lastend==p['source']['XML_bytes'] and lastrow==25792234
 # One bounded SQL row-order metadata pass, no title/body decode and no in-memory ID set.
 n=rawbytes=unterminated=0;gpos=0
 for ordinal,gid,length,lf in db.execute('select row_ordinal,group_ordinal,raw_line_bytes,line_ends_LF from rows order by row_ordinal'):
  n+=1;assert ordinal==n
  while ordinal>groups[gpos][2]:gpos+=1
  assert gid==groups[gpos][0] and groups[gpos][1]<=ordinal<=groups[gpos][2] and 1<=length<=288 and lf in [0,1]
  rawbytes+=length;unterminated+=1-lf
  if n%100000==0 and time.clock_gettime(time.CLOCK_MONOTONIC)-start>=290:raise TimeoutError('worker290seconds')
 assert n==25792234 and rawbytes==1226514721 and unterminated==0
 prior=json.loads((B/'m2-intake/enwiki-native-index-assessment-v1/selection.json').read_text());sample=[]
 for x in prior['records']:
  row=db.execute('select r.row_ordinal,r.page_id,r.title,r.raw_line_sha256,r.raw_line_bytes,r.line_ends_LF,r.noncanonical_offset_ascii,r.noncanonical_page_ascii,g.block_start from rows r join groups g using(group_ordinal) where row_ordinal=?',(x['row_ordinal'],)).fetchone();i,pid,title,sha,n,lf,ol,pl,offset=row
  raw=((ol if ol is not None else str(offset))+':'+(pl if pl is not None else str(pid))+':'+title).encode('utf8')+(b'\n' if lf else b'');assert raw.hex()==x['raw_line_including_delimiter_hex'] and len(raw)==n==x['raw_line_bytes'] and hashlib.sha256(raw).digest()==sha and sha.hex()==x['raw_line_sha256'] and pid==x['page_ID_observed'] and title==x['title_observed'] and offset==x['compressed_XML_block_start'];sample.append({'row_ordinal':i,'raw_line_SHA256':sha.hex()})
 db.close();assert producer.stat(dbpath)==before;assert s['elapsed_seconds']<1260 and s['peak_tree_RSS_bytes']<=1000000000 and s['output_bytes']<=4000000000
 out={'status':'COMPLETE_INDEPENDENT_INDEX_IDENTITY_METADATA_VERIFICATION_NO_ADMISSION','all32producer_pins_verified':True,'SQLite_SHA256_independently_rehashed':dbhash,'SQLite_bytes':before[2],'SQLite_integrity_and_FK_checks':'ok','all_unique_page_ID_constraint_and_exact_row_coverage_verified':True,'global_index_page_ID_uniqueness_proven':True,'all25792234row_ordinal_group_membership_and_length_LF_metadata_reconciled':True,'closed_contiguous_offset_groups':len(groups),'decoded_source_line_bytes_reconciled':rawbytes,'original_frozen20indexrawlines_reconstructed_exact':sample,'source_BZ2_CRC_EOF_and_triplechecksum_scope':'Inherited from pinned complete source/producer receipts; source compressed index not reread/decompressed. Only stored SQLite metadata traversed.','source_index_or_XML_body_stream_reads':0,'producer_reruns_network_ledger_tokenizer_training':0,'new_admitted_documents':0,'scope':'Index rows/page IDs are not article/English/prose/usable document counts. XML body identity/rights/quality remain separate.','verification_elapsed_seconds':time.clock_gettime(time.CLOCK_MONOTONIC)-start,'output_pins':{x.name:producer.sha(x) for x in D.iterdir() if x.is_file() and x.name!='index.sqlite'}}
 sup.slot(O,'result.json',out);signal.setitimer(signal.ITIMER_REAL,0)
if __name__=='__main__':
 if '--worker' in sys.argv:worker(float(sys.argv[-1]))
 else:sup.supervise(O,lambda start:[sys.executable,'-B',str(Path(__file__).resolve()),'--worker',str(start)])

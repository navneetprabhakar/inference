from pathlib import Path
import sys,json,hashlib,tempfile,sqlite3
B=Path(__file__).resolve().parent;P=B/'enwiki-compact-SQLite-sink-preparation-v2';O=B/'enwiki-compact-SQLite-sink-independent-audit-v2';sys.path.insert(0,str(P));from sink import Sink
from checks import page
h=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();assert h(P/'readiness.json')=='91412a58c9062682c2adcfa270c47d5832b67887819bbc5bcdd6917561bcb37e';ready=json.loads((P/'readiness.json').read_text());assert all(h(P/k)==v for k,v in ready['code_sha256'].items());cases=[]
with tempfile.TemporaryDirectory() as td:
 for name,a,b in [('reversed',20,0),('overlap',0,10),('identical',0,0)]:
  path=Path(td)/(name+'.sqlite');s=Sink(path);s.begin_group(1,570,670,[(1,10,'A'),(2,11,'B')]);s.revision(91,1,1);s.page(page(1,10,group_decoded_start=a,raw_XML_bytes=20),'A');s.revision(92,2,1)
  try:s.page(page(2,11,first=92,group_decoded_start=b,raw_XML_bytes=20),'B')
  except ValueError as e:assert str(e)=='page_spans_overlap_or_reordered' and s.failed and [s.db.execute('select count(*) from '+n).fetchone()[0] for n in ['groups','pages','revisions']]==[0,0,0];cases.append(name+'_rollback_entiregroup')
  else:raise AssertionError('acceptedbadspan')
  s.close()
 for gap in [0,1,17]:
  s=Sink(Path(td)/('gap'+str(gap)+'.sqlite'));s.begin_group(1,570,670,[(1,10,'A'),(2,11,'B')]);s.revision(91,1,1);s.page(page(1,10,group_decoded_start=2,raw_XML_bytes=20),'A');s.revision(92,2,1);s.page(page(2,11,first=92,group_decoded_start=22+gap,raw_XML_bytes=20),'B');s.end_group(42+gap,bytes(32));assert s.pages==2;s.begin_group(2,670,770,[(3,12,'C')]);s.revision(93,3,1);s.page(page(3,12,first=93,group_decoded_start=0,raw_XML_bytes=20),'C');s.end_group(20,bytes(32));assert s.pages==3 and s.groups==2;cases.append('valid_touch_gap'+str(gap)+'_and_group_relative_reset');s.close()
 # Prior committedgroup remains intact on a later caughtspanerror.
 s=Sink(Path(td)/'prior.sqlite');s.begin_group(1,570,670,[(1,10,'A')]);s.revision(91,1,1);s.page(page(1,10),'A');s.end_group(20,bytes(32));s.begin_group(2,670,770,[(2,11,'B')]);s.revision(92,2,1);s.page(page(2,11,first=92,group_decoded_start=1,raw_XML_bytes=20),'B')
 try:s.end_group(20,bytes(32))
 except ValueError:assert s.failed and s.pages==1 and s.db.execute('select count(*) from pages').fetchone()[0]==1;cases.append('outofgroup_end_rollback_preserves_priorcommittedgroup')
 else:raise AssertionError('spanexceedsdecodedaccepted')
 s.close()
O.mkdir(exist_ok=False);r={'status':'PASS_SINK_V2_FOCUSED_INDEPENDENT_REVIEW_SPAN_GAP_FIXED','readiness_SHA256':h(P/'readiness.json'),'sink_SHA256':h(P/'sink.py'),'original26controls_reproduced':True,'independent_controls':cases,'v1_originalcounterexamples_refused_atomically':True,'exact_measured_schema_no_new_storage_columns_or_indexes':True,'two_line_production_delta_reviewed':True,'no_additional_concrete_blockers':True,'power_semantics':'Ordinarycaughtfailuregroup atomicity only; MEMORYjournal hardcrash/powerloss recovery not promised. Futureproducer must enforce wholeoutput/time/RSS/source/index/BZ2/schema/publication independently.','native_index_or_otherbody_reads_network_globalledger_training':0,'new_admissions':0}
(O/'review.json').write_text(json.dumps(r,indent=2)+'\n');(O/'manifest.json').write_text(json.dumps({'review.json':h(O/'review.json'),'auditor_SHA256':h(__file__)},indent=2)+'\n');print(h(O/'review.json'),h(O/'manifest.json'))

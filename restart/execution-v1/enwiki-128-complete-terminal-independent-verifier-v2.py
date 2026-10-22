from pathlib import Path
import sys,json,hashlib,sqlite3,types,os,signal,time,collections,importlib.util
B=Path(__file__).resolve().parent;P=B/'enwiki-first128-calibration-preparation-v2';D=B/'m2-intake/enwiki-first128-native-calibration-v2';O=B/'enwiki-first128-complete-terminal-independent-verification-v2';sys.path.insert(0,str(P));import pilot
h=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def deadline(*a):raise TimeoutError('stored_output_verifier110seconds')
signal.signal(signal.SIGALRM,deadline);signal.setitimer(signal.ITIMER_REAL,110);start=time.monotonic()
profile,selection,rows,binding=pilot.verify(types.SimpleNamespace(code_pins_sha256='360ce4415162860d304c3300af918e9fb26ff1571e973d12656cb120abe2d146',profile_sha256='8e59ef7067ad3bfe7efb32a65206052a1280c9e57ac6174cb731a4c4f5721015'))
r=json.loads((D/'result.json').read_text());s=json.loads((D/'supervisor.json').read_text());owner=json.loads((D/'ownership.json').read_text());assert r['status']=='COMPLETE_FIRST128_TERMINAL_PREFIX_CALIBRATION_NO_ADMISSION' and s['worker_exit_code']==0 and s['result_SHA256']==h(D/'result.json')
for k,v in owner.items():
 if 'pid' in k.lower() and isinstance(v,int):
  try:os.kill(v,0)
  except ProcessLookupError:pass
  else:raise AssertionError('ownedPID_live')
for name,v in r['artifacts'].items():assert (D/name).stat().st_size==v['bytes'] and h(D/name)==v['SHA256']
path=D/'frame.sqlite';before=path.stat();dbhash=h(path);db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True);db.execute('pragma query_only=ON');assert db.execute('pragma integrity_check').fetchall()==[('ok',)] and db.execute('pragma foreign_key_check').fetchall()==[]
groups=db.execute('select group_ordinal,compressed_start,compressed_end_exclusive,decoded_bytes,first_page_ordinal,last_page_ordinal,page_count,raw_SHA256 from groups order by group_ordinal').fetchall();assert len(groups)==128
receipts=json.loads((D/'group-receipts.json').read_text());assert len(receipts['groups'])==128
spec=importlib.util.spec_from_file_location('titles',profile['title_decoder']);titles=importlib.util.module_from_spec(spec);spec.loader.exec_module(titles)
def digest(values):return hashlib.sha256(b''.join((json.dumps(v,ensure_ascii=False,separators=(',',':'))+'\n').encode() for v in values)).hexdigest()
decoded=receipts['header']['decoded_bytes'];references=0
for g,w,t in zip(groups,selection['groups'],receipts['groups']):
 assert g[0]==w['group_ordinal']==t['group_ordinal'] and g[1:3]==(w['compressed_start'],w['compressed_end_exclusive']) and g[4:7]==(w['first_row_ordinal'],w['last_row_ordinal'],100) and len(g[7])==32
 assert g[3]==t['decoded_bytes'] and g[7].hex()==t['decoded_SHA256'] and t['decoded_global_start']==decoded and t['native_pages']==100 and t['CRC_EOF_members']>=1 and t['trailing_absent']
 expected=rows[w['first_row_ordinal']-1:w['last_row_ordinal']];projected=[titles.decode_once(x[3]) for x in expected]
 assert t['raw_index_identity_SHA256']==digest([[x[0],x[2],x[3]] for x in expected])
 want=digest([[x[0],x[2],v['semantic_expected_title']] for x,v in zip(expected,projected)])
 assert t['frozen_index_identity_SHA256']==t['actual_native_identity_SHA256']==want and t['title_decoder_SHA256']==h(profile['title_decoder'])
 assert t['references_decoded_once']==sum(x['references_decoded_once'] for x in projected);references+=t['references_decoded_once'];decoded+=g[3]
assert decoded==r['decoded_prefix_bytes'] and r['compressed_prefix_bytes_read']==150857439
sqlrows=db.execute('select row_ordinal,page_id,first_revision_id,namespace,flags,model_code,revision_count,main_text_bytes,group_decoded_start,raw_XML_bytes,raw_SHA256 from pages order by row_ordinal').fetchall();assert len(sqlrows)==12800
revs=collections.defaultdict(list)
for rev,ordinal,n in db.execute('select revision_id,page_ordinal,revision_ordinal from revisions order by page_ordinal,revision_ordinal'):revs[ordinal].append((rev,n))
bridgepath=B/'enwiki-128-calibration-terminal-verifier-preparation-v1/first1600-bridge-reference.metadata.json';assert h(bridgepath)=='9d7d51ef14fbd4187aa670e80b9c2a7d1fce13fa5aaa2855187c9a41bcf98bbb';bridge=json.loads(bridgepath.read_text());assert all(h(p)==v for p,v in bridge['evidence_pins'].items());codec=json.loads((D/'codec.json').read_text());flags=codec['flag_bits'];lastend=0;previousgroup=0;namespaces=collections.Counter();flagcounts=collections.Counter();bridged=0
for v,w in zip(sqlrows,rows):
 ordinal,pid,rev,ns,fl,model,revc,textbytes,span,length,sha=v;gid=w[1];assert ordinal==w[0] and pid==w[2] and revc>=0 and length>0 and len(sha)==32 and fl>=0 and fl<2**25
 if gid!=previousgroup:lastend=0;previousgroup=gid
 assert span>=lastend and span+length<=groups[gid-1][3];lastend=span+length;namespaces[str(ns)]+=1;flagcounts[str(fl)]+=1
 actualrevs=revs[ordinal];assert len(actualrevs)==revc and [x[1] for x in actualrevs]==list(range(1,revc+1)) and rev==(actualrevs[0][0] if actualrevs else None)
 if ordinal<=1600:
  x=bridge['expected_SQL_fields'][ordinal-1];assert (pid,rev,ns,revc,textbytes,span,length,sha.hex())==(x['page_ID'],x['first_revision_ID'],x['namespace'],x['revision_count'],x['main_text_UTF8_bytes'],x['group_decoded_start'],x['raw_XML_bytes'],x['raw_SHA256']);assert bool(fl&flags['redirect'])==x['redirect_present'];bridged+=1
assert bridged==1600 and sum(v[6] for v in sqlrows)==r['counts']['revision_occurrences']
assert r['counts']['pages']==12800 and r['counts']['groups']==128
assert dict((str(k),v) for k,v in r['counts']['namespace_counts'])==dict(namespaces)
assert dict((str(k),v) for k,v in r['counts']['flag_counts'])==dict(flagcounts)
assert r['counts']['ns0_nonredirect']==sum(v[3]==0 and not(v[4]&1) for v in sqlrows)
modelcodes={x['code'] for x in codec['models']}|{0};assert all(v[5] in modelcodes for v in sqlrows)
oldsegments=json.loads((B/'m2-intake/enwiki-terminal-prefix-first16-frame-discovery-v2/segment-reconciliation.json').read_text())
for g,old in zip(groups[:16],oldsegments[1:]):assert g[3]==old['decoded_bytes'] and g[7].hex()==old['decoded_SHA256']
db.close();assert path.stat()==before
exceptions=(D/'exceptions.jsonl').read_bytes();events=[json.loads(x) for x in exceptions.splitlines()];assert len(events)==r['exceptions']['events'] and len(exceptions)==r['exceptions']['bytes'] and hashlib.sha256(exceptions).hexdigest()==r['exceptions']['ordered_exception_SHA256']
assert s['elapsed_seconds']<600 and s['peak_observed_RSS_bytes']<=1000000000 and sum(p.stat().st_size for p in D.iterdir() if p.is_file())<=64000000
assert r['new_admitted_documents']==r['new_admitted_tokens']==0 and r['actual_root_closed'] is False
O.mkdir(exist_ok=False);out={'status':'PASS_COMPLETE_FIRST128_PREFIX_CALIBRATION_METADATA_NOT_FULL_ARCHIVE','all58pins_and_source_stat_receipt_custody_verified_without_bodyreads':True,'SQLite_SHA256':dbhash,'SQLite_bytes':before.st_size,'SQLite_integrity_FK':'ok','pages':12800,'groups':128,'revision_occurrences':r['counts']['revision_occurrences'],'allIDs_ordinals_groupboundaries_spanbounds_revisionoccurrences_reconciled':True,'all128_actual_native_transcripts_match_independent_strict_XML_title_projection':True,'all128_raw_index_transcripts_match_immutable_rawlexemes':True,'references_decoded_once':references,'first1600page_rawSHA_grouprelativepositions_revisionIDs_textbytes_match_priorwholepagebuffer':True,'first16decodedgroupSHA_and_lengths_match_prioralgorithm_receipts':True,'namespace_counts':dict(namespaces),'flag_counts':dict(flagcounts),'exception_events':len(events),'exception_bytes':len(exceptions),'source_body_reads':0,'publisher_whole_archive_verified':False,'new_admitted_documents':0,'new_admitted_tokens':0,'elapsed_seconds':time.monotonic()-start,'output_pins':{p.name:h(p) for p in D.iterdir() if p.is_file()},'limitations':'Stored transcript verifies decoder/identity projection against frozen index; full raw source not reread. First1600 rawpage hash bridge independently compares prior separately verified algorithm. Prefix-only engineering calibration is not representative quality, full archive or admission.'}
(O/'verification.json').write_text(json.dumps(out,indent=2)+'\n');(O/'manifest.json').write_text(json.dumps({'verification.json':h(O/'verification.json'),'verifier_SHA256':h(__file__)},indent=2)+'\n');signal.setitimer(signal.ITIMER_REAL,0);print(h(O/'verification.json'),h(O/'manifest.json'))

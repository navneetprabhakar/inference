from pathlib import Path
import sys,json,hashlib,sqlite3,types,os,signal,time,collections
B=Path(__file__).resolve().parent;P=B/'enwiki-first128-calibration-preparation-v1';D=B/'m2-intake/enwiki-first128-native-calibration-v1';O=B/'enwiki-first128-partial-terminal-independent-verification-v1';sys.path.insert(0,str(P));import pilot
h=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def deadline(*a):raise TimeoutError('partial_verifier110seconds')
signal.signal(signal.SIGALRM,deadline);signal.setitimer(signal.ITIMER_REAL,110);start=time.monotonic()
profile,selection,rows,binding=pilot.verify(types.SimpleNamespace(code_pins_sha256='dc8d9f4ea3506df0657da54c3930dd28c3435beb41ece34e9b4e79c6e32026b7',profile_sha256='0d582266ff29bf118f6df3ef37a3a644c1254372a58cc8fe5338ec7bf503fee2'))
r=json.loads((D/'result.json').read_text());s=json.loads((D/'supervisor.json').read_text());owner=json.loads((D/'ownership.json').read_text());assert r['status']=='PARTIAL_CALIBRATION_NO_RETRY' and r['error']=='ValueError:ordered_native_index_identity_mismatch' and s['status']=='PARTIAL_CALIBRATION_NO_RETRY' and s['worker_exit_code']==1 and s['result_SHA256']==h(D/'result.json')
# Ownership key names are read from actual frozen handoff.
pids=[]
for k,v in owner.items():
 if 'pid' in k.lower() and isinstance(v,int):
  try:os.kill(v,0)
  except ProcessLookupError:pids.append(v)
  else:raise AssertionError('ownedPID_live')
assert 77315 in pids and 77316 in pids
path=D/'frame.sqlite';before=path.stat();dbhash=h(path);db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True);db.execute('pragma query_only=ON');assert db.execute('pragma integrity_check').fetchall()==[('ok',)] and db.execute('pragma foreign_key_check').fetchall()==[]
groups=db.execute('select group_ordinal,compressed_start,compressed_end_exclusive,decoded_bytes,first_page_ordinal,last_page_ordinal,page_count,raw_SHA256 from groups order by group_ordinal').fetchall();assert len(groups)==22
for g,w in zip(groups,selection['groups']):assert g[0]==w['group_ordinal'] and g[1:3]==(w['compressed_start'],w['compressed_end_exclusive']) and g[4:7]==(w['first_row_ordinal'],w['last_row_ordinal'],100) and len(g[7])==32
sqlrows=db.execute('select row_ordinal,page_id,first_revision_id,namespace,flags,model_code,revision_count,main_text_bytes,group_decoded_start,raw_XML_bytes,raw_SHA256 from pages order by row_ordinal').fetchall();assert len(sqlrows)==2200 and db.execute('select count(*),min(row_ordinal),max(row_ordinal) from pages').fetchone()==(2200,1,2200)
bridgepath=B/'enwiki-128-calibration-terminal-verifier-preparation-v1/first1600-bridge-reference.metadata.json';assert h(bridgepath)=='9d7d51ef14fbd4187aa670e80b9c2a7d1fce13fa5aaa2855187c9a41bcf98bbb';bridge=json.loads(bridgepath.read_text());assert all(h(p)==v for p,v in bridge['evidence_pins'].items());flags=json.loads((P/'contract.json').read_text())['outputs']['codec.json']['flag_bits'];lastend=0;previousgroup=0;namespaces=collections.Counter();flagcounts=collections.Counter();bridged=0
for v,w in zip(sqlrows,rows):
 ordinal,pid,rev,ns,fl,model,revc,textbytes,span,length,sha=v;gid=w[1];assert ordinal==w[0] and pid==w[2] and gid<=22 and revc>=0 and length>0 and len(sha)==32
 if gid!=previousgroup:lastend=0;previousgroup=gid
 assert span>=lastend and span+length<=groups[gid-1][3];lastend=span+length;namespaces[str(ns)]+=1;flagcounts[str(fl)]+=1
 actualrevs=db.execute('select revision_id,revision_ordinal from revisions where page_ordinal=? order by revision_ordinal',(ordinal,)).fetchall();assert len(actualrevs)==revc and [x[1] for x in actualrevs]==list(range(1,revc+1)) and rev==(actualrevs[0][0] if actualrevs else None)
 if ordinal<=1600:
  b=bridge['expected_SQL_fields'][ordinal-1];assert (pid,rev,ns,revc,textbytes,span,length,sha.hex())==(b['page_ID'],b['first_revision_ID'],b['namespace'],b['revision_count'],b['main_text_UTF8_bytes'],b['group_decoded_start'],b['raw_XML_bytes'],b['raw_SHA256']);assert bool(fl&flags['redirect'])==b['redirect_present'] and bool(fl&flags['nonzero_namespace'])==(ns!=0) and not fl&(flags['no_revision']|flags['multiple_revisions']|flags['main_unavailable']);bridged+=1
assert bridged==1600;revtotal=db.execute('select count(*) from revisions').fetchone()[0];assert revtotal==sum(v[6] for v in sqlrows)
oldsegments=json.loads((B/'m2-intake/enwiki-terminal-prefix-first16-frame-discovery-v2/segment-reconciliation.json').read_text())
for g,old in zip(groups[:16],oldsegments[1:]):assert g[3]==old['decoded_bytes'] and g[7].hex()==old['decoded_SHA256']
db.close();assert path.stat()==before;assert not(D/'group-receipts.json').exists() and not(D/'codec.json').exists() and not(D/'header-summary.json').exists();assert s['elapsed_seconds']<600 and s['peak_observed_RSS_bytes']<=1000000000 and sum(p.stat().st_size for p in D.iterdir() if p.is_file())<=64000000
exceptions=(D/'exceptions.jsonl').read_bytes();events=[json.loads(x) for x in exceptions.splitlines()];assert len(exceptions)<=8000000
O.mkdir(exist_ok=False);out={'status':'VERIFIED_TERMINAL_PARTIAL_CALIBRATION_NOT_COMPLETE_NO_RETRY','producer_worker_error':r['error'],'owned_PIDs_absent':pids,'all47frozen_code_runtime_metadatapins_verified':True,'source_stat_and_receipt_custody_reverified_without_bodyread':True,'SQLite_SHA256':dbhash,'SQLite_bytes':before.st_size,'SQLite_integrity_FK':'ok','committed_pages':2200,'committed_groups':22,'committed_revision_occurrences':revtotal,'all_committedIDs_ordinals_groupboundaries_spanbounds_revisionoccurrences_reconciled':True,'failed_group23_has_no_committed_rows':True,'first1600page_rawSHA_grouprelativepositions_revisionIDs_textbytes_match_priorwholepagebuffer':True,'first16decodedgroupSHA_and_lengths_match_prioralgorithm_receipts':True,'namespace_counts_for_committed_only':dict(namespaces),'flag_counts_for_committed_only':dict(flagcounts),'partial_exception_events':len(events),'partial_exception_bytes':len(exceptions),'partial_exception_ordinals_may_include_uncommitted_group23':True,'missing_complete_artifacts_expected':['group-receipts.json','codec.json','header-summary.json'],'title_scope':'CompactSQL has no title; committedID/order reconciled to frozenrows, sink enforced exactnative title at insertion. Independent rawSHA/positions bridge allfirst1600; no native title/body reread or globalfullframe assertion.','no_COMPLETE_or_yield_extrapolation':True,'new_admitted_documents':0,'native_index_archive_body_reads_network_ledger_tokenizer_training_operations':0,'elapsed_seconds':time.monotonic()-start,'output_pins':{p.name:h(p) for p in D.iterdir() if p.is_file()}}
(O/'verification.json').write_text(json.dumps(out,indent=2)+'\n');(O/'manifest.json').write_text(json.dumps({'verification.json':h(O/'verification.json'),'verifier_SHA256':h(__file__)},indent=2)+'\n');signal.setitimer(signal.ITIMER_REAL,0);print(h(O/'verification.json'),h(O/'manifest.json'))

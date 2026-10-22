"""Read-only live-ledger verification after terminal pilot; writes new diagnostics."""
import copy,datetime,fcntl,gzip,json,os,sqlite3
from pathlib import Path
from lxml import etree
import discover as d
p=d.DEST;ready=json.loads((d.HERE/'ready.json').read_text());failure=json.loads((p/'failure.json').read_text());supervisor=json.loads((p/'supervisor-result.json').read_text());start=json.loads((p/'supervisor-start.json').read_text());checks={};receipts=failure['successful_responses'];ns={'o':d.pmc.OAI}
checks['all_code_pins_unchanged']=all(d.sha(Path(n).read_bytes())==h for n,h in ready['input_code_sha256'].items())
checks['terminal_failed_no_retry']=failure['status']=='TERMINAL_FAILED_NO_RETRY' and failure['error']=='payload_request_manifest_mismatch' and supervisor['worker_exit_code']==1 and supervisor['retry'] is False
allids=[];headers=[];lasttoken=None
for i,r in enumerate(receipts):
 raw=Path(r['response_file']).read_bytes();plain=Path(r['decoded_file']).read_bytes();receipt=json.loads((p/f'response-{i:03d}.receipt.json').read_text());request=json.loads((p/f'request-{i:03d}.json').read_text())
 checks[f'response{i}_wire_hash_and_size']=len(raw)==r['body_bytes'] and d.sha(raw)==r['body_sha256']==receipt['body_sha256']
 checks[f'response{i}_independent_gzip_and_xml_hash']=gzip.decompress(raw)==plain and len(plain)==r['decoded_bytes'] and d.sha(plain)==r['decoded_sha256']==receipt['decoded_sha256']
 checks[f'response{i}_request_receipt_matches']=request['query']==r['query'] and request['url']==r['request_url']
 tree=etree.fromstring(plain,etree.XMLParser(resolve_entities=False,no_network=True,load_dtd=False));echo=tree.find('o:request',ns);listing=tree.find('o:ListRecords',ns);token=listing.find('o:resumptionToken',ns)
 records=listing.findall('o:record',ns);observed=[x.findtext('o:header/o:identifier',namespaces=ns) for x in records];allids+=observed
 checks[f'response{i}_native_records_cardinality']=len(observed)==10 and len(set(observed))==10
 checks[f'response{i}_scope_datestamps']=all(d.SCOPE['from']<=x.findtext('o:header/o:datestamp',namespaces=ns)[:10]<=d.SCOPE['until'] for x in records)
 if i==0:checks['first_response_exact_request_echo']=dict(echo.attrib)==r['query']
 else:
  checks['cursor_request_exactly_previous_response']=r['query']=={'verb':'ListRecords','resumptionToken':lasttoken}
  checks['second_response_empty_echo_preserved_refused']=dict(echo.attrib)=={} and dict(echo.attrib)!=r['query']
 headers.append({'index':i,'request_attributes':dict(echo.attrib),'record_identifiers':observed,'response_cursor':token.text,'processing':'FIRST_PAGE_VALIDATED_AND_EXTRACTED' if i==0 else 'RAW_ONLY_PROTOCOL_REFUSAL_NO_ELIGIBILITY'})
 lasttoken=token.text
checks['twenty_raw_distinct_headers_ten_processed_only']=len(allids)==len(set(allids))==20 and failure['records_observed_before_failure']==10 and not(p/'page-001.records.json').exists() and not(p/'records.jsonl').exists()
first=json.loads((p/'page-000.records.json').read_text());rows=first['rows'];fresh,extras,firsttoken,_=d.parse((p/'response-000.xml').read_bytes(),receipts[0]['query'],0)
for row,extra in zip(fresh,extras):
 if extra:row['serialized_article_sha256']=d.sha(extra['article_xml'])
checks['first_page_rows_reproduced_including_explicit_serialization_binding']=fresh==rows
checks['article_serializations_match_saved']=all((p/f"PMC{row['pmcid']}.article.xml").read_bytes()==extra['article_xml'] and d.sha(extra['article_xml'])==row['serialized_article_sha256'] for row,extra in zip(fresh,extras) if extra)
final=d.finalize(copy.deepcopy(rows));checks['final_local_family_eligibility_consistent']=all(r['metadata_filter_eligible']==(not r['holds']) for r in final)
checks['all_processed_sources_unadmitted']=all(r['training_admitted'] is False and r['raw_fulltext_not_admitted'] for r in final)
checks['incomplete_cursor_not_frame']=bool(firsttoken) and bool(lasttoken)
checks['serial_rate_compliant']=(datetime.datetime.fromisoformat(receipts[1]['guard']['last_start_utc'])-datetime.datetime.fromisoformat(receipts[0]['guard']['last_start_utc'])).total_seconds()>=1
try:os.kill(start['pid'],0)
except ProcessLookupError:checks['worker_pid_gone']=True
else:checks['worker_pid_gone']=False
with (d.ROOT/'charges/job.lock').open('a') as lock:
 try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:checks['global_ledger_released']=False
 else:checks['global_ledger_released']=True;fcntl.flock(lock,fcntl.LOCK_UN)
conn=sqlite3.connect('file:'+str(d.ROOT/'charges/ledger.sqlite')+'?mode=ro',uri=True)
try:
 attempts=[{'key':key,'charge':json.loads(charge),'state':state,'actual_body_bytes':count,'body_sha256':h} for key,charge,state,count,h in conn.execute("SELECT key,charge,state,actual_bytes,body_sha256 FROM attempts WHERE key LIKE 'pmc-native-oai-discovery-v1-%' ORDER BY rowid")]
 checks['exact_two_successful_global_charges']=len(attempts)==2 and all(r['state']=='complete' and r['actual_body_bytes']==receipts[i]['body_bytes'] and r['body_sha256']==receipts[i]['body_sha256'] for i,r in enumerate(attempts))
 checks['caps_and_conservative_reservations']=sum(x['charge']['body_bytes'] for x in attempts)==8000000<=d.BODY_CAP and sum(x['actual_body_bytes'] for x in attempts)==528785 and supervisor['elapsed_seconds']<600
 actual=conn.execute('SELECT coalesce(sum(actual_bytes),0) FROM attempts').fetchone()[0]
finally:conn.close()
assert all(checks.values()),checks
report={'status':'VERIFIED_TERMINAL_PROTOCOL_BINDING_FAILURE_WITH_FIRSTPAGE_DISCOVERY','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checks':checks,'headers_diagnostic':headers,'requests':2,'successful_compressed_wire_bytes':528785,'conservative_reserved_wire_bytes':8000000,'processed_first_page_records':10,'firstpage_eligible_before_family':sum(r['metadata_filter_eligible'] for r in rows),'firstpage_eligible_after_observed_local_family':sum(r['metadata_filter_eligible'] for r in final),'raw_only_secondpage_headers':10,'complete_frame':False,'firstpage_records_not_population_sample':True,'global_successful_response_body_bytes':actual,'ledger_attempts':attempts,'new_admitted_documents':0,'new_admitted_tokens':0,'scope':['Protocol failure is exact requestecho attribute omission in second response, not observed text-quality failure.','No parser relaxed or reattempt made. Secondpage remains raw and unaccepted.','Firstpage localfamily derivation cannot certify outsideframe relationships/retractions, rights or semantic quality.'],'manual_review_artifacts':[{'pmcid':r['pmcid'],'title':r['title'],'provisional_metadata_candidate':r['metadata_filter_eligible'],'holds':r['holds'],'body_characters':r['fulltext_body_characters'],'dependency_counts':r['structured_dependency_counts'],'article_xml':str(p/f"PMC{r['pmcid']}.article.xml"),'diagnostic_text':str(p/f"PMC{r['pmcid']}.diagnostic.txt")} for r in final]}
raw=(json.dumps(report,indent=2,ensure_ascii=False)+'\n').encode();derived=(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in final)).encode();d.OutputBudget(p,d.OUTPUT_CAP).ensure(len(raw)+len(derived))
for name,data in [('independent-first-page-local-family-diagnostic.jsonl',derived),('independent-terminal-verification.json',raw)]:
 with (p/name).open('xb') as handle:handle.write(data)
print(json.dumps({'checks':len(checks),'status':report['status'],'local_firstpage_eligible':report['firstpage_eligible_after_observed_local_family'],'global_ledger_released':checks['global_ledger_released'],'global_successful_bytes':actual,'report_sha256':d.sha(raw)}))

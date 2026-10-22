import pathlib,json,hashlib,sys,types,os,collections,xml.parsers.expat as expat,time,signal
B=pathlib.Path(__file__).resolve().parent;P=B/'enwiki-native-development20-capture-preparation-v1';O=B/'enwiki-native-development20-terminal-independent-verification-v1';start=time.monotonic()
def alarm(*a):raise TimeoutError('raw20_verifier55seconds')
signal.signal(signal.SIGALRM,alarm);signal.setitimer(signal.ITIMER_REAL,55);sys.path.insert(0,str(P));import capture
h=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest();p,selection,binding=capture.verify(types.SimpleNamespace(profile_sha256='e49e978ae16198bb97c5c0da31992a0290792aa2ee2da4f56a02299cae4fdd86',codepins_sha256='bc27fb4c0594de73966fb5808a67aa87dc9be20e756cb1f23055cb2175828b38'));D=pathlib.Path(p['output']);r=json.loads((D/'result.json').read_text());s=json.loads((D/'supervisor.json').read_text());own=json.loads((D/'ownership.json').read_text())
assert r['status']=='COMPLETE_RAW_DEVELOPMENT20_CAPTURE_NO_ADMISSION' and s['worker_exit_code']==0 and s['worker_reaped'] and h(D/'result.json')==s['result_SHA256']=='bc7342a4c242b7f1efb75141e1cf955a157771c254e2319befb2f785de56dcff'
for k in ['worker_PID','supervisor_PID']:
 try:os.kill(own[k],0)
 except ProcessLookupError:pass
 else:raise AssertionError('PID_live')
for n,v in r['artifacts'].items():assert (D/n).stat().st_size==v['bytes'] and h(D/n)==v['SHA256']
header=(D/'original-header.xml').read_bytes();assert hashlib.sha256(header).hexdigest()==p['header']['SHA256'] and len(header)==p['header']['bytes']
assert len(r['records'])==len(selection['selected'])==20 and r['groups_read_once']==sorted(g['group_ordinal'] for g in selection['groups']) and r['compressed_group_bytes_read']==sum(g['compressed_bytes'] for g in selection['groups']) and r['decoded_group_bytes']==sum(g['decoded_bytes'] for g in selection['groups'])
roles=collections.Counter();summaries=[];bytesread=0;URI='http://www.mediawiki.org/xml/export-0.11/}'
for observed,w in zip(r['records'],selection['selected']):
 assert observed['selection']==w and observed['CRC_EOF_verified'] and observed['raw_XML_bytes']==w['raw_XML_bytes'] and observed['raw_XML_SHA256']==w['raw_SHA256'];g=next(x for x in selection['groups'] if x['group_ordinal']==w['group_ordinal'])
 for k in ['compressed_start','compressed_end_exclusive','compressed_SHA256','decoded_SHA256']:assert observed['group_'+k]==g[k]
 raw=(D/observed['raw_XML_file']).read_bytes();bytesread+=len(raw);assert len(raw)==w['raw_XML_bytes'] and hashlib.sha256(raw).hexdigest()==w['raw_SHA256']
 parser=expat.ParserCreate(namespace_separator='}');stack=[];data={'pagecount':0,'pageID':'','ns':'','revisionIDs':[],'redirect':False,'textbytes':0};currentrev=[None]
 def st(name,attrs):
  stack.append(name)
  if name==URI+'page':assert len(stack)==2;data['pagecount']+=1
  if len(stack)==3 and name==URI+'redirect':data['redirect']=True
  if len(stack)==3 and name==URI+'revision':data['revisionIDs'].append('')
 def text(value):
  if len(stack)==3 and stack[-1]==URI+'id':data['pageID']+=value
  if len(stack)==3 and stack[-1]==URI+'ns':data['ns']+=value
  if len(stack)==4 and stack[-2:]==[URI+'revision',URI+'id']:data['revisionIDs'][-1]+=value
  if len(stack)==4 and stack[-2:]==[URI+'revision',URI+'text']:data['textbytes']+=len(value.encode())
 def end(name):assert stack.pop()==name
 parser.StartElementHandler=st;parser.EndElementHandler=end;parser.CharacterDataHandler=text;parser.StartDoctypeDeclHandler=lambda *a:(_ for _ in ()).throw(ValueError('DTD_forbidden'));parser.ExternalEntityRefHandler=lambda *a:0;parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
 parser.Parse(header,False);parser.Parse(raw,False);parser.SetReparseDeferralEnabled(False);parser.Parse(b'',False)
 assert stack==[URI+'mediawiki'] and data['pagecount']==1 and int(data['pageID'])==w['page_id'] and int(data['ns'])==w['namespace'] and len(data['revisionIDs'])==w['revision_count'] and int(data['revisionIDs'][0])==w['first_revision_id'] and data['textbytes']==w['main_text_bytes'] and data['redirect']==bool(w['flags']&1)
 roles[w['selection_role']]+=1;summaries.append({'row':w['row_ordinal'],'page_ID':w['page_id'],'namespace':w['namespace'],'redirect':data['redirect'],'revisionIDs':[int(x) for x in data['revisionIDs']],'maintext_decoded_UTF8_bytes':data['textbytes'],'raw_XML_bytes':len(raw),'SHA256':w['raw_SHA256']})
assert dict(roles)=={'ns0_nonredirect':16,'ns0_redirect':2,'nonzero_namespace':2} and bytesread==477409 and capture.stat(binding['path'])==binding['stat'] and s['elapsed_shared_seconds']<90 and s['peak_tree_RSS_bytes']<1000000000 and not r['whole_publisher_archive_verified']
O.mkdir(exist_ok=False);v={'status':'PASS_EXACT20_RAW_CAPTURE_STORED_OUTPUT_AND_STRUCTURAL_CONTEXT','all52pins_and_old128frame_locator_group_receipt_proofs_reconciled':True,'new_raw_XML_bytes_independently_hashed_and_structurally_parsed':bytesread,'original_header_context_exact':True,'synthetic_native_closing_or_namespace_bytes_added':0,'root_left_open_each_parse':True,'roles':dict(roles),'pages':summaries,'source_prefix_stat_unchanged':True,'ownedPIDs_absent':True,'original_compressed_native_source_body_reads':0,'native_range_CRC_scope':'Producer decoded20selectedgroups and matched inherited verified128compressed/decoded hashes+CRC receipts; terminal audit hashes saved exactpageoutputs only.','whole_publisher_archive_verified':False,'new_admitted_documents':0,'new_admitted_tokens':0,'scope':'Fixed biased engineering/development20 includes4negative roles, not acceptance/sourcewide yield or usable prose.','elapsed_seconds':time.monotonic()-start,'output_pins':{x.name:h(x) for x in D.iterdir() if x.is_file()}}
(O/'verification.json').write_text(json.dumps(v,indent=2)+'\n');(O/'manifest.json').write_text(json.dumps({'verification.json':h(O/'verification.json'),'verifier_SHA256':h(__file__)},indent=2)+'\n');print(h(O/'verification.json'),h(O/'manifest.json'))

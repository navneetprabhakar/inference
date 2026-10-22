"""Exact existing-response001 offline adapter. No network and no XML rewriting."""
import copy,gzip,hashlib,importlib.util,json,re,sqlite3,sys,time
from pathlib import Path
from lxml import etree
HERE=Path(__file__).resolve().parent;EXEC=HERE.parent
sys.path.insert(0,str(EXEC/'pmc-discovery-parallel-v1'))
import discover as original
BASE=original.BASE;NS={'o':original.pmc.OAI}
SOURCE=EXEC/'m2-intake/pmc-native-discovery-pilot-v1';DEST=EXEC/'m2-intake/pmc-continuation-adapter-discovery-v1'
PROPOSAL=EXEC/'pmc-protocol-deviation-proposal-v1/proposal.json'
PROPOSAL_SHA='0ec1e41885c3f3986afba9f6959784ce8a58b807e1750f31bf93315501f113fd'
CAP=100000000;LABEL='PMCcontinuationbindingdeviation'
def sha(b):return hashlib.sha256(b).hexdigest()
def require(b,msg):
 if not b:raise ValueError(msg)
def xml(b):
 require(len(b)<=original.DECODED_CAP and b'\0' not in b and not re.search(br'<!\s*(?:DOCTYPE|ENTITY)',b,re.I),'unsafe_or_oversize_XML')
 return etree.fromstring(b,etree.XMLParser(resolve_entities=False,no_network=True,load_dtd=False,huge_tree=False))
def envelope(plain):
 root=xml(plain);require(root.tag=='{'+original.pmc.OAI+'}OAI-PMH','unknown_OAI_root')
 require(len(root.findall('o:request',NS))==1 and len(root.findall('o:responseDate',NS))==1 and len(root.findall('o:ListRecords',NS))==1,'ambiguous_OAI_envelope')
 require(not root.findall('o:error',NS),'OAI_error_refused')
 echo=root.find('o:request',NS);require((echo.text or '').strip()==BASE,'wrong_endpoint_echo')
 listing=root.find('o:ListRecords',NS);require(len(listing.findall('o:resumptionToken',NS))<=1,'ambiguous_cursor')
 records=listing.findall('o:record',NS);require(len(records)<=10,'page_cardinality')
 ids=[]
 for r in records:
  require(len(r.findall('o:header',NS))==1,'ambiguous_header');head=r.find('o:header',NS)
  ident=head.findtext('o:identifier',namespaces=NS);stamp=head.findtext('o:datestamp',namespaces=NS)
  require(isinstance(stamp,str) and original.SCOPE['from']<=stamp[:10]<=original.SCOPE['until'],'outside_original_date_window')
  ids.append(ident)
 require(len(ids)==len(set(ids)),'duplicate_PM CID')
 token=listing.findtext('o:resumptionToken',default='',namespaces=NS) or ''
 require(len(token)<=4096,'cursor_bound')
 return root,dict(echo.attrib),token,ids

def transport(plain,wire,receipt,request):
 require(receipt['body_sha256']==sha(wire) and receipt['body_bytes']==len(wire),'wire_receipt_mismatch')
 require(receipt['decoded_sha256']==sha(plain) and receipt['decoded_bytes']==len(plain),'decoded_receipt_mismatch')
 require(original.decode(wire,receipt['headers'].get('Content-Encoding'))==plain,'decoded_wire_mismatch')
 require(receipt['request_url']==request['url'] and receipt['query']==request['query'],'transport_request_mismatch')
 require(original.pmc.query(request['url'])==request['query'],'endpoint_or_query_mismatch')
 require(request['local_scope']==original.SCOPE and request['charged_before_io'] is True,'original_scope_or_reservation_mismatch')
 require(request['key']==receipt['key'],'ledger_key_mismatch')

def bound_parse(prior,continuation,wire0,wire1,r0,r1,q0,q1,first_page=False):
 """Pure structural/transport validator; static source pins checked by execute first."""
 require(not first_page,'empty_echo_exception_never_first_page')
 transport(prior,wire0,r0,q0);transport(continuation,wire1,r1,q1)
 expected={'verb':'ListRecords','metadataPrefix':'pmc','set':'pmc-open',**original.SCOPE}
 require(q0['query']==expected,'first_selection_scope_mismatch')
 _,echo0,token0,ids0=envelope(prior)
 require(echo0==expected and bool(token0),'first_exact_echo_and_nonempty_cursor_required')
 require(q1['query']=={'verb':'ListRecords','resumptionToken':token0},'immediately_prior_cursor_mismatch')
 _,echo1,token1,ids1=envelope(continuation)
 require(echo1=={},'exception_requires_wholly_empty_continuation_echo')
 require(not(set(ids0)&set(ids1)),'cross_page_duplicate_PMCID')
 # After the stronger transport+prior-cursor proof, the frozen parser checks the
 # actual empty map against {}. XML bytes are never modified; all JATS, rights,
 # header/status/date and article/body checks still execute in original.parse.
 rows,extras,token,date=original.parse(continuation,{},1)
 require(token==token1,'cursor_parse_disagreement')
 for row in rows:
  row['protocol_binding_deviation']={'label':LABEL,'scope':'EXACT_ALREADY_DOWNLOADED_RESPONSE001_OFFLINE_ONLY','actual_outgoing_query':q1['query'],'observed_echo_attributes':{},'validation_policy':'Exact transport, original selection and preceding cursor proof substitutes for missing continuation echo attributes only.','original_source_XML_unmodified':True,'raw_source_response_sha256':sha(continuation),'prior_response_sha256':sha(prior),'original_failure_sha256':json.loads(PROPOSAL.read_text())['original_artifacts_sha256']['failure.json']}
 return rows,extras,token,date

def load_bound_sources():
 require(sha(PROPOSAL.read_bytes())==PROPOSAL_SHA,'proposal_pin_mismatch');proposal=json.loads(PROPOSAL.read_text());original.pins()
 for name,h in proposal['original_artifacts_sha256'].items():require(sha((SOURCE/name).read_bytes())==h,'original_artifact_pin_mismatch:'+name)
 receipts=[json.loads((SOURCE/f'response-{i:03d}.receipt.json').read_text()) for i in range(2)]
 requests=[json.loads((SOURCE/f'request-{i:03d}.json').read_text()) for i in range(2)]
 # Read only: no IntakeLedger constructor, lock, reservations, retries or writes.
 d=sqlite3.connect('file:'+str((original.ROOT/'charges/ledger.sqlite').resolve())+'?mode=ro',uri=True)
 attempts=[]
 try:
  for i,r in enumerate(receipts):
   got=d.execute('select key,charge,state,actual_bytes,body_sha256 from attempts where key=?',(r['key'],)).fetchone()
   require(got is not None and got[2]=='complete' and got[3]==r['body_bytes'] and got[4]==r['body_sha256'],'complete_global_ledger_transport_binding')
   charge=json.loads(got[1]);require(charge['requests']==1 and charge['body_bytes']==4000000,'original_conservative_ledger_reservation')
   attempts.append({'key':got[0],'charge':charge,'state':got[2],'actual_bytes':got[3],'body_sha256':got[4]})
 finally:d.close()
 return [(SOURCE/f'response-{i:03d}.xml').read_bytes() for i in range(2)],[(SOURCE/f'response-{i:03d}.body').read_bytes() for i in range(2)],receipts,requests,attempts

def save(name,data):
 b=data if isinstance(data,bytes) else (json.dumps(data,indent=2,ensure_ascii=False)+'\n').encode()
 original.OutputBudget(DEST,CAP).write(DEST/name,b)

def execute():
 started=time.monotonic();plain,wire,r,q,attempts=load_bound_sources()
 rows,extras,token,date=bound_parse(*plain,*wire,*r,*q)
 for row,extra in zip(rows,extras):
  if extra:row['serialized_article_sha256']=sha(extra['article_xml'])
 first,firstextras,_,_=original.parse(plain[0],q[0]['query'],0)
 for row,extra in zip(first,firstextras):
  if extra:row['serialized_article_sha256']=sha(extra['article_xml'])
 combined=original.finalize(copy.deepcopy(first+rows))
 require(all(x['metadata_filter_eligible']==(not x['holds']) for x in combined),'family_eligibility_inconsistent')
 DEST.mkdir(exist_ok=False)
 try:
  for row,extra in zip(rows,extras):
   if extra:
    row['serialized_article_sha256']=sha(extra['article_xml']);save(f"PMC{row['pmcid']}.article.xml",extra['article_xml']);save(f"PMC{row['pmcid']}.diagnostic.txt",extra['diagnostic_preview'])
  save('page-001.records.json',{'rows':rows,'response_date':date,'resumption_token':token,'original_XML_sha256':sha(plain[1]),'protocol_deviation':LABEL,'eligibility_scope':'PRE_CROSS_PAGE_FAMILY_CHECKS; cross-page-family-records.jsonl authoritative','frame_complete':not bool(token),'no_admission':True})
  save('cross-page-family-records.jsonl',(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in combined)).encode())
  result={'status':'OFFLINE_EXACT_RESPONSE001_DISCOVERY_WITH_VISIBLE_PROTOCOL_DEVIATION','protocol_deviation':LABEL,'proposal_sha256':PROPOSAL_SHA,'source_original_XML_sha256':sha(plain[1]),'original_failed_artifacts_unchanged':True,'complete_global_transport_bindings':attempts,'second_page_records':len(rows),'combined_records':len(combined),'metadata_filter_eligible_after_observed_cross_page_family':sum(x['metadata_filter_eligible'] for x in combined),'second_page_metadata_filter_eligible_after_family':sum(x['metadata_filter_eligible'] for x in combined[len(first):]),'resumption_token_remaining':token,'frame_complete_for_original_window':not bool(token),'representative_or_sourcewide_claim':False,'elapsed_seconds':time.monotonic()-started,'new_admitted_documents':0,'new_admitted_tokens':0,'network_requests':0,'limitations':['Metadata/license/status checks do not establish semantic quality or outside-frame retraction clearance.','Exact page exception only, no generalization or new network acquisition authorized.','Full JATS authoritative; flattened text diagnostic only.']}
  save('result.json',result)
  # Reverify immutable failure, source/parser pins and own original ledger rows.
  _,_,_,_,after=load_bound_sources();require(after==attempts,'original_ledger_rows_changed')
  print(json.dumps(result,indent=2))
 except BaseException as e:save('failure.json',{'status':'OFFLINE_ADAPTER_TERMINAL_FAILED','reason':str(e),'no_retry':True});raise
if __name__=='__main__':execute()

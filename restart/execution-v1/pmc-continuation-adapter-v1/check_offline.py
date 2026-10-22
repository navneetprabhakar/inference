import copy,gzip,json
from lxml import etree
from pathlib import Path
import adapter as a
checks=[]
p,w,r,q,ledger=a.load_bound_sources()
def args():return copy.deepcopy([*p,*w,*r,*q])
def refuse(x,**kw):
 try:a.bound_parse(*x,**kw)
 except (ValueError,KeyError):return
 raise AssertionError('tamper accepted')
def mutated(index,fn):
 x=args();root=a.xml(x[index]);fn(root);x[index]=etree.tostring(root);x[2+index]=gzip.compress(x[index]);rec=x[4+index];rec.update(body_sha256=a.sha(x[2+index]),body_bytes=len(x[2+index]),decoded_sha256=a.sha(x[index]),decoded_bytes=len(x[index]));return x
x=mutated(0,lambda root:root.find('o:request',a.NS).attrib.clear());refuse(x);refuse(args(),first_page=True);checks.append('first_response_empty_attributes_refused')
rows,extras,token,date=a.bound_parse(*args());assert len(rows)==10 and token and all(x['protocol_binding_deviation']['label']==a.LABEL for x in rows);checks.append('exact_continuation_chain_accepted_offline_only')
x=args();x[7]['query']['resumptionToken']='altered';refuse(x)
x=args();x[2]+=b'x';refuse(x)
x=args();x[4]['decoded_sha256']='0'*64;refuse(x);checks.append('different_cursor_altered_prior_wire_or_receipt_refused')
for attrs in [{'verb':'ListRecords'},{'verb':'GetRecord','resumptionToken':'wrong'}]:
 x=mutated(1,lambda root:root.find('o:request',a.NS).attrib.update(attrs));refuse(x)
checks.append('partial_or_conflicting_echo_refused')
x=args();x[7]['url']=x[5]['request_url']='https://example.com/redirect?verb=ListRecords';refuse(x)
x=mutated(1,lambda root:setattr(root.find('o:request',a.NS),'text','https://example.com/'));refuse(x);checks.append('wrong_endpoint_or_redirect_refused')
def dup(root):
 heads=root.findall('o:ListRecords/o:record/o:header/o:identifier',a.NS);heads[1].text=heads[0].text
refuse(mutated(1,dup))
refuse(mutated(1,lambda root:setattr(root.find('o:ListRecords/o:record/o:header/o:datestamp',a.NS),'text','2025-12-01')));checks.append('duplicate_PMCID_or_out_of_scope_stamp_refused')
def error(root):
 e=etree.SubElement(root,'{'+a.original.pmc.OAI+'}error');e.set('code','noRecordsMatch');e.text='No records'
refuse(mutated(1,error));checks.append('noRecordsMatch_or_OAI_error_refused')
assert bool(token) and token==a.envelope(p[1])[2];checks.append('nonempty_cursor_remains_incomplete')
a.load_bound_sources();checks.append('all_original_failed_artifacts_parser_and_complete_ledger_rows_unchanged')
result={'status':'PASS_NINE_PROPOSED_TAMPER_CASE_GROUPS_OFFLINE_ONLY','checks':checks,'count':len(checks),'new_admitted_documents':0,'new_admitted_tokens':0,'network_requests':0}
(Path(__file__).with_name('offline-checks.json')).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

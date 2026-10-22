import copy,json
from pathlib import Path
from lxml import etree
import adapter as a
checks={};p,w,r,q,before=a.load_bound_sources();out=a.DEST
page=json.loads((out/'page-001.records.json').read_text());result=json.loads((out/'result.json').read_text())
try:a.original.parse(p[1],q[1]['query'],1)
except ValueError as e:checks['original_parser_still_refuses_exact_original_XML']=str(e)=='payload_request_manifest_mismatch'
else:checks['original_parser_still_refuses_exact_original_XML']=False
fresh,extras,token,date=a.bound_parse(*p,*w,*r,*q)
for row,extra in zip(fresh,extras):
 if extra:row['serialized_article_sha256']=a.sha(extra['article_xml'])
checks['exact_new_page_rows_reproduced']=fresh==page['rows']
root=a.xml(p[1]);articles=root.findall('o:ListRecords/o:record/o:metadata',a.NS)
checks['all_ten_native_article_serializations_and_derivatives_exact']=len(articles)==len(fresh)==10 and all(etree.tostring(list(md)[0],encoding='utf-8')==(out/f"PMC{row['pmcid']}.article.xml").read_bytes()==extra['article_xml'] and a.sha(extra['article_xml'])==row['serialized_article_sha256'] and (out/f"PMC{row['pmcid']}.diagnostic.txt").read_bytes()==extra['diagnostic_preview'] for md,row,extra in zip(articles,fresh,extras))
first,e0,_,_=a.original.parse(p[0],q[0]['query'],0)
for row,extra in zip(first,e0):
 if extra:row['serialized_article_sha256']=a.sha(extra['article_xml'])
combined=a.original.finalize(copy.deepcopy(first+fresh));saved=[json.loads(l) for l in (out/'cross-page-family-records.jsonl').read_text().splitlines()]
checks['observed_cross_page_family_rows_exact']=combined==saved
checks['all_eligibility_flags_follow_final_holds']=all(x['metadata_filter_eligible']==(not x['holds']) for x in saved)
checks['counts11total3secondpage_no_clearance_claim']=sum(x['metadata_filter_eligible'] for x in saved)==11 and sum(x['metadata_filter_eligible'] for x in saved[10:])==3 and not result['frame_complete_for_original_window'] and not result['representative_or_sourcewide_claim']
checks['every_second_page_row_exposes_protocol_deviation']=all(x['protocol_binding_deviation']['label']==a.LABEL and x['protocol_binding_deviation']['raw_source_response_sha256']==a.sha(p[1]) for x in saved[10:])
checks['exact_nonempty_next_cursor_retained']=bool(token) and token==result['resumption_token_remaining']==page['resumption_token']
inspection=json.loads((out/'ten-record-scoped-inspection.json').read_text());proposal=json.loads((out/'complete-window-acquisition-proposal.json').read_text())
checks['ten_scoped_not_full_or_factual_reviews']=inspection['reviewed_record_count']==10 and inspection['full_document_reviews']==inspection['fact_audits']==0 and all(not x['full_review_pass'] for x in inspection['judgments'])
checks['new_network_proposal_only']=proposal['network_requests_executed']==0 and proposal['status'].startswith('PROPOSAL_ONLY')
_,_,_,_,after=a.load_bound_sources();checks['original_sources_parser_failure_and_ledger_rows_unchanged']=before==after
checks['aggregate_output_less100MB']=sum(f.stat().st_size for f in out.rglob('*') if f.is_file())<a.CAP
checks['zero_admission_training_network']=result['new_admitted_documents']==result['new_admitted_tokens']==result['network_requests']==0 and all(x['training_admitted'] is False for x in saved)
assert all(checks.values()),checks
report={'status':'PASS_EXACT_OFFLINE_ADAPTER_AND_OUTPUT_VERIFICATION','checks':checks,'check_count':len(checks),'output_sha256':{f.name:a.sha(f.read_bytes()) for f in out.iterdir() if f.is_file()},'new_admitted_documents':0,'new_admitted_tokens':0,'network_requests':0}
with (out/'independent-output-verification.json').open('x') as f:f.write(json.dumps(report,indent=2)+'\n')
print(json.dumps({'status':report['status'],'checks':len(checks),'report_sha256':a.sha((out/'independent-output-verification.json').read_bytes())}))

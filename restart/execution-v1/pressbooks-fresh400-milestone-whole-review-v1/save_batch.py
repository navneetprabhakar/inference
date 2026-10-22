from pathlib import Path
import json,hashlib,datetime,sys
B=Path(__file__).resolve().parents[1];O=Path(__file__).resolve().parent;C=B/'m2-intake/pressbooks-fresh400-whole-original-capture-v1';pp=B/'pressbooks-fresh400-semantic-review-protocol-v1/protocol.json';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();assert sha(pp)=='fc7ef67532bfe14a57c1914a6f674c2ac2e9d7d973befeb16df05b7e502d7490';assigned=sorted(json.loads(pp.read_text())['assignments']['milestone_audit']['records'],key=lambda x:x['text_UTF8_bytes'])
inputs=json.loads(Path(sys.argv[1]).read_text())
for x in inputs:
 i=x.pop('rank');a=assigned[i];stem=f"source-{a['source_id']}-row-{a['ordinal']:06d}";p=C/(stem+'.text.utf8');jpath=C/(stem+'.source.json');raw=p.read_bytes();s=raw.decode();obj=json.loads(jpath.read_text());assert sha(p)==a['text_SHA256'] and len(raw)==a['text_UTF8_bytes'] and obj['text']==s
 end=x.pop('read_char_end',len(s));assert 0<=end<=len(s)
 chunks=[]
 for start in range(0,end,10000):
  z=min(start+10000,end);b=s[start:z].encode();chunks.append({'char_start':start,'char_end':z,'UTF8_start':len(s[:start].encode()),'UTF8_end':len(s[:z].encode()),'SHA256':hashlib.sha256(b).hexdigest(),'visible_untruncated_read':True})
 whole=end==len(s);assert whole or x['quality_verdict']!='PASS'
 findings=[]
 for term in x.pop('exact_evidence_terms',[]):
  k=s.find(term);assert 0<=k<end and k+len(term)<=end,term;findings.append({'char_start':k,'char_end':k+len(term),'UTF8_start':len(s[:k].encode()),'UTF8_end':len(s[:k+len(term)].encode()),'exact_text':term})
 result={'status':'FRESH_FIXED_SAMPLE_INDEPENDENT_CONTENT_REVIEW_NO_ADMISSION','UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'reviewer':'milestone_audit','assignment_short_rank':i,**a,'capture_text_path':str(p),'original_JSON_SHA256':sha(jpath),'source_id_URL':obj['id'],'metadata':obj['metadata'],'whole_captured_record_read':whole,'whole_book_or_publication_claim':False,'read_char_end':end,'read_UTF8_bytes':len(s[:end].encode()),'source_characters':len(s),'chunks':chunks,'findings':findings,**x,'all_rights_family_near_protected_split_finaltokenizer_gates':'UNCLEARED','new_admitted_documents':0}
 target=O/(stem+'.review.json');assert not target.exists();target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');target.chmod(0o444)
records=[json.loads(p.read_text()) for p in O.glob('source-*.review.json')];summary={'status':'PARTIAL_ASSIGNED100_REVIEW_PROGRESS_NO_EXTRAPOLATION','protocol_SHA256':sha(pp),'capture_terminal_proof_SHA256':'5b312e92fd851ed7e4d92eedbc9ce5259ae1042f21deba2b5c5c6116ed81061d','reviewed_unique_records':len(records),'whole_read_records':sum(r['whole_captured_record_read'] for r in records),'read_UTF8_bytes':sum(r['read_UTF8_bytes'] for r in records),'quality_counts':{k:sum(r['quality_verdict']==k for r in records) for k in ['PASS','FAIL','INCONCLUSIVE']},'major_corruption_counts':{k:sum(r['major_corruption']==k for r in records) for k in ['YES','NO','UNASSESSED']},'review_files_SHA256':{p.name:sha(p) for p in O.glob('source-*.review.json')},'new_admitted_documents':0};(O/'progress.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({k:v for k,v in summary.items() if k!='review_files_SHA256'},indent=2))

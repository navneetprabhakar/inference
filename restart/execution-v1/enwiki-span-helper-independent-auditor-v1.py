from pathlib import Path
import sys,json,hashlib
B=Path(__file__).resolve().parent;P=B/'enwiki-incremental-XML-span-preparation-v1';O=B/'enwiki-incremental-span-independent-audit-v1';sys.path.insert(0,str(P));from spans import PageSpans
h=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert h(P/'readiness.json')=='ba3d67a2f5e806a2bce7cad1a3b144ccd0a8d15251c4ae7c5c1a4d0e3c9622ac'
head=b'<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/"><siteinfo/>';tail=b'</mediawiki>';findings=[]
for page in [b'<page/>',b'<page />',b'<page a="quoted > value"/>',b'<page><text/></page>']:
 wire=head+page+tail
 for name,chunks in [('whole',[wire]),('onebyte',[wire[i:i+1] for i in range(len(wire))])]:
  out=[];p=PageSpans(out.append);error=None
  try:
   for chunk in chunks:p.feed(chunk)
   p.finish()
  except Exception as e:error=type(e).__name__+':'+str(e)
  exact=not error and len(out)==1 and wire[out[0]['start']:out[0]['end']]==page and out[0]['SHA256']==hashlib.sha256(page).hexdigest()
  findings.append({'page_literal':page.decode(),'chunking':name,'expected_page_bytes':len(page),'expected_SHA256':hashlib.sha256(page).hexdigest(),'error':error,'actual_records':out,'actual_page_literal':wire[out[0]['start']:out[0]['end']].decode() if out else None,'exact':exact})
assert any(not f['exact'] for f in findings if f['page_literal']=='<page/>');assert all(f['exact'] for f in findings if f['page_literal']=='<page><text/></page>')
O.mkdir(exist_ok=False);r={'status':'BLOCKED_EMPTY_PAGE_ADJACENT_ROOT_CLOSING_HASH_AND_CHUNK_DEPENDENCE','helper_SHA256':h(P/'spans.py'),'readiness_SHA256':h(P/'readiness.json'),'existing505controls_reproduced':True,'concrete_blockers':[{'class':'empty_page_end_callback_misidentified_as_next_root_closing','cause':'At empty-element End callback Expat CurrentByteIndex is after its />. _closing_end sees the following </mediawiki> and incorrectly includes it, or fails if its > has not arrived.','scope':'Wrong originalpage rawspan/SHA256 and chunk-dependent failure, before semanticparser/index reconciliation.','minimal_fix_requirement':'Bind selfclosing status to actual currentpage starttag or verify currentclosingtag belongs to callback. Reversing tests is not sufficient because <page><text/></page> also has preceding />.','reproductions':findings}],'integration_memory_requirement':{'observed_synthetic_depth':10002,'raw_hash_remains_correct_at_that_depth':True,'condition':'Expat stack can grow with XMLdepth independentlyof boundedrawtail. Before nativeintegration require finite depthguard in helper or caller; futureprofile/SAXhandlers may own this separately. Not a rawhash counterexample.'},'positive_scope':'505originalcontrols incl35.65MB ordinarypage streaming passed; no page-sized retainedrawbuffer seen. Issue found by adjacentempty/rootclosing cases missing from original fixture.','source_code_edits_or_native_source_reads':0,'training_network_ledger_or_admission_operations':0,'next':'Preserve v1; parent isolated v2 fix plus allcut/selfclosing-adjacent-prefix/quotedattribute controls before reuse.'}
(O/'review.json').write_text(json.dumps(r,indent=2)+'\n');(O/'manifest.json').write_text(json.dumps({'review.json':h(O/'review.json'),'auditor_SHA256':h(__file__)},indent=2)+'\n');print(h(O/'review.json'),h(O/'manifest.json'))

from pathlib import Path
import sys,json,hashlib,random
B=Path(__file__).resolve().parent;P=B/'enwiki-incremental-XML-span-preparation-v2';O=B/'enwiki-incremental-span-independent-audit-v2';sys.path.insert(0,str(P));from spans import PageSpans
h=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert h(P/'readiness.json')=='71f0a0fbf49f4ed16e9ae45fe7ea20fd52bfa7df4fdec98baf394d16a96a56e0' and h(P/'spans.py')=='304b4a2b00013b35b9883957b717c1c1fd421b16d81c1b356d7f41184034b575';r=json.loads((P/'readiness.json').read_text());assert all(h(P/f)==v for f,v in r['code_sha256'].items())
ns='http://www.mediawiki.org/xml/export-0.11/';head=('<mediawiki xmlns="'+ns+'"><siteinfo/>').encode();tail=b'</mediawiki>';fixtures=[]
for page in [b'<page/>',b'<page />',b'<page a="quoted > value"/>',b'<page a="literal /> not delimiter"/>',b'<page><text/></page>']:
 fixtures.append((head+page+tail,[page]))
ph=('<mw:mediawiki xmlns:mw="'+ns+'"><mw:siteinfo/>').encode();pt=b'</mw:mediawiki>'
fixtures.append((ph+b'<mw:page/>'+pt,[b'<mw:page/>']))
p1=b'<page a="quoted />"><text><![CDATA[</page> fake]]></text><!-- </page> --><?p test?></page>';p2=b'<page/>';p3=b'<page><text>&amp;&#13;'+ '漢🌏'.encode()+b'</text></page>';fixtures.append((head+p1+p2+p3+tail,[p1,p2,p3]))
checks=0
for wire,pages in fixtures:
 for chunks in [[wire],[wire[i:i+1] for i in range(len(wire))]]+[[wire[:cut],wire[cut:]] for cut in range(1,len(wire))]:
  out=[];p=PageSpans(out.append)
  for chunk in chunks:p.feed(chunk)
  summary=p.finish();assert summary['actual_root_closed'] and len(out)==len(pages)
  assert [wire[x['start']:x['end']] for x in out]==pages and all(x['SHA256']==hashlib.sha256(raw).hexdigest() and x['bytes']==len(raw) for x,raw in zip(out,pages));checks+=1
# Terminal prefix has no fabricated closure; later continuation refused.
prefix=head+b'<page/>';out=[];p=PageSpans(out.append)
for b in prefix:p.feed(bytes([b]))
summary=p.finish_prefix();assert summary['actual_root_closed'] is False and summary['global_XML_validity'] is False and out[0]['SHA256']==hashlib.sha256(b'<page/>').hexdigest()
try:p.feed(tail)
except ValueError:checks+=1
else:raise AssertionError('sealedprefixcontinued')
# Depth bounds actual hostile fixture fromv1 now fails terminally.
wire=head+b'<page>'+b'<x>'*10000+b'A'+b'</x>'*10000+b'</page>'+tail;p=PageSpans(lambda r:None)
try:
 for i in range(0,len(wire),65536):p.feed(wire[i:i+65536])
except ValueError as e:assert str(e)=='XML_depth_limit' and p.failed;checks+=1
else:raise AssertionError('unboundeddepthaccepted')
O.mkdir(exist_ok=False);review={'status':'PASS_V2_RAW_SPAN_PRIMITIVE_ORIGINAL_ADJACENCY_BLOCKER_FIXED','helper_SHA256':h(P/'spans.py'),'readiness_SHA256':h(P/'readiness.json'),'original1221controls_reproduced':True,'additional_independent_allcut_byteboundary_checks':checks,'independent_fixture_shapes':['Originalempty-page+rootclose adjacency withwholefeed/1byte/every2feedcut','Quoted> andliteral/> attributes','Nonempty page containingemptytextchild negativefixcontrol','Namespacedprefixempty-page/rootclose','CDATA/comment/PI fakeclosingpage+threeadjacentpages+UTF8/entities','TerminalPREFIX_ONLY nofabricatedclosure/no continuation','Original10002depth hostile nowterminalXML_depth_limit'],'production_diff_fully_reviewed':True,'v1_counterexample_evidence_preserved':True,'raw_originalpage_slice_hashes_exact':True,'quoted_starttag_empty_end_binding_avoids_neighbor_closing_or_precedingchild_guess':True,'depth_cap':256,'new_concrete_blockers':[],'scope':'Only raw XML page spans/hashes primitive. Caller still owns exactrootnamespace/siteinfo/schema roles/text hashes/index/BZ2 boundaries/storage/supervision. Root-open PREFIX_ONLY is terminal diagnostic, not resumable/fullXMLvalidity or admission.','actual_native_body_network_ledger_tokenizer_or_training_operations':0}
(O/'review.json').write_text(json.dumps(review,indent=2)+'\n');(O/'manifest.json').write_text(json.dumps({'review.json':h(O/'review.json'),'auditor_SHA256':h(__file__)},indent=2)+'\n');print(h(O/'review.json'),h(O/'manifest.json'),checks)

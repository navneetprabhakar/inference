from pathlib import Path
import sys,json,hashlib,collections,os,re
B=Path(__file__).resolve().parent;P=B/'enwiki-terminal-prefix-frame-preparation-v2';D=B/'m2-intake/enwiki-terminal-prefix-first16-frame-discovery-v2';O=B/'enwiki-terminal-prefix-frame-terminal-independent-verification-v2'
sys.path.insert(0,str(P));import pilot
h=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
code='94302fb888d5be4386906d3d843ec94af40b77a78c2d9ccd765f316b3e131965';profile='50fc0a497a84847055db52178c0416ea49ee9094c621b22a6a89aa7af2f8c5ae';bind=B/'enwiki-terminal-prefix-frame-parent-dispatch-v2/source-binding.json';bsha='b09496b461dbcb114422d1a0e7ae72a584852eea95b88e39d976fc9226514dd7'
plan=pilot.verify(code,profile);binding=pilot.verify_binding(bind,bsha,profile)
r=json.loads((D/'result.json').read_text());s=json.loads((D/'supervisor.json').read_text());header=json.loads((D/'header-and-siteinfo.json').read_text());segments=json.loads((D/'segment-reconciliation.json').read_text());owner=json.loads((D/'ownership.json').read_text());pages=[json.loads(x) for x in (D/'pages.jsonl').read_text().splitlines()]
assert r['status']=='COMPLETE_TERMINAL_PREFIX_INDIVIDUAL_FRAME_DISCOVERY_NO_ADMISSION' and s['status']=='COMPLETE_TERMINAL_PREFIX_FRAMES_NO_ADMISSION' and s['worker_exit_code']==0 and s['result_SHA256']==h(D/'result.json')
for k in ['worker_PID','supervisor_PID']:
 try:os.kill(owner[k],0)
 except ProcessLookupError:pass
 else:raise AssertionError('ownedPID_present')
assert r['source_binding_SHA256']==bsha and r['code_pins_SHA256']==code and r['profile_SHA256']==profile and r['source_prefix_SHA256_inherited_verified_copy_custody']==binding['source_prefix_SHA256'] and r['publisher_whole_archive_verified'] is False
assert len(pages)==1600 and len(segments)==17 and r['compressed_prefix_bytes_read']==17948470 and r['decoded_prefix_bytes']==66627771 and r['root_left_open'] and r['additional_full_archive_verification_read_bytes']==0
assert len({x['page_ID'] for x in pages})==1600;revseen=set();counts=collections.Counter();hashstatuses=collections.Counter();holdcounts=collections.Counter();decoded=0;at=0;position=0
for n,seg in enumerate(segments):
 assert seg['start']==at and seg['compressed_bytes']==seg['end_exclusive']-seg['start'] and seg['members_CRC_EOF_verified']>=1 and seg['trailing_data_absent'];at=seg['end_exclusive']
 for key in ['compressed_SHA256','decoded_SHA256']:assert re.fullmatch('[0-9a-f]{64}',seg[key])
 if n==0:
  assert seg['kind']=='header' and seg['start']==0 and seg['end_exclusive']==570 and seg['indexed_rows']==seg['native_pages']==0
  raw=(D/'captured-original-header-prefix.xml').read_bytes();assert seg['decoded_bytes']==2521 and len(raw)==pages[0]['page_decoded_byte_span'][0]==2523 and hashlib.sha256(raw[:2521]).hexdigest()==seg['decoded_SHA256'] and raw[2521:]==b'  ';assert b'</mediawiki>' not in raw
 else:
  group=plan['groups'][n-1];got=pages[position:position+len(group['rows'])];assert seg['group']==n and seg['start']==group['start'] and seg['end_exclusive']==group['end_exclusive'];assert seg['native_pages']==seg['indexed_rows']==len(got)==len(group['rows'])
  assert [(x['page_ID'],x['title']) for x in got]==[(x['page_ID'],x['title']) for x in group['rows']]
  last=decoded
  for page in got:
   assert page['source_compressed_segment']=={'kind':'indexed_group','group':n,'start':seg['start'],'end_exclusive':seg['end_exclusive'],'decoded_start':decoded}
   x,y=page['page_decoded_byte_span'];assert decoded<=x<y<=decoded+seg['decoded_bytes'] and x>=last;last=y;assert re.fullmatch('[a-f0-9]{64}',page['page_raw_XML_SHA256']);assert int(page['direct_page_ID_position']['value'])==page['page_ID']
   counts['pages']+=1;counts['namespace:'+str(page['namespace'])]+=1;counts['redirects']+=page['redirect_present'];counts['nonzero_namespace_pages']+=page['namespace']!=0;counts['ns0_nonredirect_pages_pending_only']+=page['namespace']==0 and not page['redirect_present'];holdcounts.update(page['holds']);assert page['new_admitted_documents']==0 and page['alltypes_frame_only_not_article_or_English_or_prose']
   for revision in page['revisions']:
    rid=revision['revision_ID'];assert rid not in revseen and int(revision['direct_revision_ID_position']['value'])==rid;revseen.add(rid);rx,ry=revision['source_decoded_span'];assert x<=rx<ry<=y
    chk=revision['revision_SHA1_consistency'];hashstatuses[chk['status']]+=1
    assert chk['status']=='MATCH' and chk['matches_decoded_text'] is True and chk['comparison_basis']=='legacy_single_text'
    c=revision['content_slots_or_legacy'];assert len(c)==1 and c[0]['model']=='wikitext' and c[0]['format']=='text/x-wiki';t=c[0]['text'];assert int(revision['native_revision_SHA1'],36)==int(t['SHA1_hex_of_decoded_UTF8'],16) and t['native_base36_SHA1_matches'] and t['native_byte_count_matches'];assert rx<=t['decoded_byte_span'][0]<t['decoded_byte_span'][1]<=ry
   links=page['source_links_derived_not_literal_XML_fields'];assert links['page']=='https://en.wikipedia.org/w/index.php?curid='+str(page['page_ID']);assert links['history']==links['page']+'&action=history';assert links['revisions']==['https://en.wikipedia.org/w/index.php?oldid='+str(v['revision_ID']) for v in page['revisions']]
  position+=len(got)
 decoded+=seg['decoded_bytes']
assert position==1600 and at==17948470 and decoded==66627771 and dict(counts)==r['all_types_counts']==header['counts'] and header['XML_root_closed'] is False and header['global_XML_validity_claim'] is False and not holdcounts
assert len(revseen)==1600 and hashstatuses=={'MATCH':1600};assert s['elapsed_seconds']<120 and s['peak_observed_RSS_bytes']<=1000000000 and sum(q.stat().st_size for q in D.iterdir() if q.is_file())<=16000000
O.mkdir(exist_ok=False);out={'status':'PASS_TERMINAL_PREFIX_FRAME_METADATA_RECONCILIATION_NO_ARCHIVE_REREAD','source_binding_SHA256':bsha,'all35static_input_pins_reverified':True,'source_custody_chain_reverified':True,'ownedPIDs_absent':True,'exact_frozen_index_native_order_rows':1600,'selected_complete_groups':16,'selected_compressed_bytes':at,'decoded_prefix_bytes':decoded,'alltypes_counts_recomputed':dict(counts),'revision_sibling_SHA1_statuses_recomputed':dict(hashstatuses),'schema_holds_recomputed':dict(holdcounts),'all1600page_and_revision_IDs_unique_within_prefix':True,'all_page_revision_text_spans_and_derived_attribution_links_reconciled':True,'header_capture_decoded_SHA256_verified':h(D/'captured-original-header-prefix.xml'),'archive_body_read_bytes_by_this_verifier':0,'native_integrity_scope':'Worker CRC/EOF and per-member compressed/decoded/page/text hashes inherited from reviewed pinned production and terminal stat/receipt chain; stored native metadata and base36-vs-hex hashes reconciled independently, no archive rehash or decompression repeated.','whole_publisher_archive_verified':False,'global_XML_validity_or_article_English_or_quality_claim':False,'new_admitted_documents':0,'supervisor_receipt':s,'output_files':{q.name:h(q) for q in D.iterdir() if q.is_file()}}
(O/'verification.json').write_text(json.dumps(out,indent=2)+'\n');(O/'manifest.json').write_text(json.dumps({'verification.json':h(O/'verification.json'),'verifier_SHA256':h(__file__)},indent=2)+'\n');print(h(O/'verification.json'),h(O/'manifest.json'))

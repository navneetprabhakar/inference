"""Offline proposal only: exact-source spans, never writes a prose derivative."""
import hashlib,json,pathlib,re
D=pathlib.Path(__file__).resolve().parent;E=D.parent;C=E/'m2-intake/gutenberg-chapters-v1';RAW=E/'m2-intake/gutenberg-discovery-pilot-v3/text.raw';RIGHTS=E/'m2-intake/gutenberg-chapter-preparation-v1/rights-provenance-review.json'
SHA='3f6bb9d6f78e0293b56acd4714dd68cb7d6d1d293402031ce9d5a216bcaf9d75'
sha=lambda b:hashlib.sha256(b).hexdigest()
def balanced(b,start):
 if not (b[start:].startswith(b'[Illustration:') or b[start:].startswith(b'[Illustration]')):raise ValueError('Not an illustration opening')
 depth=0
 for i in range(start,len(b)):
  if b[i]==91:depth+=1
  elif b[i]==93:
   depth-=1
   if not depth:return i+1
 raise ValueError('Unclosed illustration wrapper')
def segments(start,end,removals):
 out=[];cursor=start
 for s,e in removals:
  if not cursor<=s<e<=end:raise ValueError('Overlap or out of range')
  if cursor<s:out.append(('keep',cursor,s))
  out.append(('remove',s,e));cursor=e
 if cursor<end:out.append(('keep',cursor,end))
 return out
# Meaningful boundary tests: nested copyright, adjacent wrappers, unclosed,
# Unicode byte/character distinction, and whole heading preservation.
tests=[]
b=b'[Illustration: title [Copyright x]]';assert balanced(b,0)==len(b);tests.append('nested_copyright_outer_bracket_included')
b=b'[Illustration: x][Illustration: y]';e=balanced(b,0);assert balanced(b,e)==len(b);tests.append('adjacent_illustrations_disjoint')
assert balanced(b'[Illustration]',0)==14;tests.append('bare_illustration_marker_complete_span')
try:balanced(b'[Illustration: [x]',0)
except ValueError:pass
else:raise AssertionError('unclosed accepted')
tests.append('unclosed_outer_wrapper_refused')
b='é[Illustration: “x”]'.encode();assert b.index(b'[')==2 and len(b[:2].decode())==1;tests.append('UTF8_byte_and_codepoint_offsets_distinguished')
b=b'[Illustration: title\r\nChapter I.]';h=b.index(b'Chapter I.');assert b[h:h+10]==b'Chapter I.';assert b''.join(b[s:e] for k,s,e in segments(0,len(b),[(0,h),(h+10,len(b))]) if k=='keep')==b'Chapter I.';tests.append('decorated_heading_retained_without_wrapper_brackets')
try:segments(0,10,[(0,6),(5,8)])
except ValueError:pass
else:raise AssertionError('overlap accepted')
tests.append('overlap_refused')
raw=RAW.read_bytes();assert sha(raw)==SHA;raw.decode('utf-8')
partition=json.loads((C/'partition.json').read_text());assert partition['source_sha256']==SHA
cursor=0;reconstruction=[]
for p in partition['parts']:
 assert p['start_byte']==cursor;chunk=raw[cursor:p['end_byte']];assert len(chunk)==p['bytes'] and sha(chunk)==p['sha256'];assert (C/p['file']).read_bytes()==chunk
 reconstruction.append(chunk);cursor=p['end_byte']
assert cursor==len(raw) and b''.join(reconstruction)==raw
chapters=[json.loads(l) for l in (C/'chapters.jsonl').read_text().splitlines()];assert len(chapters)==61
annotations=[];plans=[];differences=[];categories={};manual=[];totals={'source_chapter_bytes':0,'prospective_retained_bytes':0,'prospective_removed_bytes':0,'prospective_retained_unicode_codepoints':0,'prospective_retained_whitespace_words':0}
def span(s,e):
 chunk=raw[s:e]
 return {'source_start_byte':s,'source_end_byte':e,'source_start_unicode_codepoint':len(raw[:s].decode()),'source_end_unicode_codepoint':len(raw[:e].decode()),'bytes':e-s,'sha256':sha(chunk)}
for c in chapters:
 s,z=c['start_byte'],c['end_byte'];b=raw[s:z];assert sha(b)==c['sha256'] and b.decode()==c['text'] and (C/c['file']).read_bytes()==b
 old={a['start_byte']:a for a in c['annotation_spans'] if a['kind']=='illustration_caption'};found=list(re.finditer(rb'\[Illustration(?::|\])',b));assert sum(m.group().endswith(b':') for m in found)==len(old)
 removals=[];chapter_annotations=[]
 for m in found:
  start=s+m.start();end=s+balanced(b,m.start());oldspan=old.get(start,{'end_byte':end,'sha256':sha(raw[start:end])});assert sha(raw[start:oldspan['end_byte']])==oldspan['sha256']
  text=raw[start:end].decode();aid=f"chapter_{c['chapter_number']:02d}_illustration_{len(chapter_annotations)+1:02d}"
  head=re.search(rb'(?m)^Chapter I\.',raw[start:end]) if c['chapter_number']==1 else None
  if head:
   hs=start+head.start();he=start+head.end();assert aid=='chapter_01_illustration_01' and raw[hs:he]==b'Chapter I.'
   remove=[(start,hs),(he,end)];kind='decorated_chapter_heading';preserve=span(hs,he)
  else:
   remove=[(start,end)];preserve=None
   cleaned=re.sub(r'\[[_]?Copyright.*?\]','',text,flags=re.S).replace('[Illustration:','').rstrip(']').strip()
   kind='bare_illustration_marker' if text=='[Illustration]' else 'copyright_only_wrapper' if not cleaned else ('quoted_caption_or_quotation' if any(x in cleaned for x in ['“','”','‘','’']) else 'unquoted_illustration_label')
  nested=text.count('[')>1
  row={'id':aid,'chapter_number':c['chapter_number'],'balanced_source_span':span(start,end),'exact_annotation_text':text,'context_before':raw[:start].decode()[-120:],'context_after':raw[end:].decode()[:120],'classification':kind,'nested_brackets':nested,'legacy_span_end_byte':oldspan['end_byte'],'legacy_span_missing_outer_closure_bytes':end-oldspan['end_byte'],'proposed_remove_spans':[span(a,b) for a,b in remove],'preserve_heading_span':preserve,'manual_review_required':True,'manual_review_reason':'Confirm exact edition paratext boundaries and preserve all narrative outside wrapper; quotation resemblance does not establish caption authorship.','rights_disposition':'Separate paratext; no attribution to Austen solely from quotation marks or historical illustration credit.'}
  annotations.append(row);chapter_annotations.append(aid);removals.extend(remove);categories[kind]=categories.get(kind,0)+1
  if end!=oldspan['end_byte']:differences.append({'id':aid,'legacy_end_byte':oldspan['end_byte'],'balanced_end_byte':end,'extra_bytes':end-oldspan['end_byte'],'extra_exact_text':raw[oldspan['end_byte']:end].decode()})
  if head or nested or kind in ['copyright_only_wrapper','unquoted_illustration_label']:manual.append(aid)
 seg=segments(s,z,removals);assert b''.join(raw[a:e] for _,a,e in seg)==b
 kept=b''.join(raw[a:e] for k,a,e in seg if k=='keep');removed=b''.join(raw[a:e] for k,a,e in seg if k=='remove')
 # In-memory planning only; no derivative chapter is saved.
 assert b'[Illustration:' not in kept and kept.count(b'[')==kept.count(b']')
 if c['chapter_number']==1:assert kept.startswith(b'Chapter I.')
 else:assert re.match(rb'(?i)Chapter [IVXLCDM]+\.?\r',kept)
 plan={'chapter_number':c['chapter_number'],'source_span':span(s,z),'source_chapter_sha256':c['sha256'],'family_id':c['family_id'],'annotation_ids':chapter_annotations,'ordered_segments':[{'action':k,**span(a,e)} for k,a,e in seg],'source_reconstruction_exact':True,'prospective_retained_bytes':len(kept),'prospective_retained_sha256':sha(kept),'remaining_square_bracket_count':kept.count(b'[')+kept.count(b']'),'prospective_retained_unicode_codepoints':len(kept.decode()),'prospective_retained_whitespace_words':len(kept.decode().split()),'prospective_removed_bytes':len(removed),'derivative_saved':False,'tokens':None,'training_admitted':False}
 plans.append(plan);totals['source_chapter_bytes']+=len(b);totals['prospective_retained_bytes']+=len(kept);totals['prospective_removed_bytes']+=len(removed);totals['prospective_retained_unicode_codepoints']+=len(kept.decode());totals['prospective_retained_whitespace_words']+=len(kept.decode().split())
assert len(annotations)==155 and totals['source_chapter_bytes']==totals['prospective_retained_bytes']+totals['prospective_removed_bytes']
assert sha(RAW.read_bytes())==SHA
policy={'status':'PROPOSED_REVIEW_REQUIRED_NO_DERIVATIVE_SAVED','source_raw_sha256':SHA,'rights_evidence_sha256':sha(RIGHTS.read_bytes()),'rules':['Use only these exact source byte spans and hashes; stop on any mismatch.','Remove balanced outer illustration wrappers including nested copyright notices; preserve all removed exact spans separately in any future derivative.','For Chapter I only, retain the literal original Chapter I. bytes from inside the wrapper; remove prefix and outer closing bracket separately. No invented heading.','Retain all other bytes exactly: CRLF, spelling, italics underscores, quotation punctuation and paragraph whitespace. No normalization or line dewrapping in this policy.','Never delete quoted narrative outside the balanced illustration wrapper or deduplicate caption quotations against prose.','Chapter documents remain whole chapter units, all one Austen work family across every edition and derivative.','Preserve original complete raw file and partition, PG license/trademark/frontmatter/preface and source/transcription credits as provenance; their exclusion from narrative input is not deletion from archives.','Do not alter existing discovery annotation evidence; corrected proposal spans supersede only for a future explicitly versioned derivative.','Before derivative acceptance, manually review all 155 proposed annotation spans (70 captions and 85 bare markers), compare whole chapters around every deletion, rehash and retokenize actual saved output, and run overlap/family split gates.','No generic clearance of modern transcription/editorial contributions or distribution territories follows from expired original-work terms.'], 'rights_scope':{'original_novel':'Existing review identifies no ordinary term expiry obstacle for Austen original novel within reviewed Indian/UK scope; this is not a grant for all rendition bytes.','preface':'Saintsbury essay already separately partitioned; excluded from novel prose, not assigned to Austen.','illustration_labels_captions':'Remove proposed spans from future narrative derivative irrespective of whether some repeat Austen sentences; illustrator attribution does not resolve every caption author.','modern_transcription':'Keep PG source/release and credits linked; no scan identity or blanket modern editorial clearance inferred.','license_trademark':'Retain embedded PG materials unchanged in raw archive; release packaging must separately implement applicable PG mark/license terms.'},'high_attention_annotation_ids':manual,'manual_review_all_annotations':True,'prospective_counts_not_usable_counts':totals,'tokens':'PENDING actual derivative creation and pinned tokenizer run; prior 224240 chapter tokens include paratext and must not be called usable','new_admitted_documents':0,'new_admitted_tokens':0}
for name,obj in [('policy.json',policy),('annotation-span-proposal.json',annotations),('chapter-span-proposal.json',plans),('legacy-span-differences.json',differences),('checks.json',{'status':'PASS_PROPOSAL_ONLY','synthetic_cases':tests,'raw_bytes':len(raw),'partition_parts':len(partition['parts']),'chapters':61,'annotations':155,'legacy_caption_annotations':70,'additional_bare_illustration_markers':85,'annotations_with_corrected_nested_end':len(differences),'classifications':categories,'all_partition_and_chapter_file_hashes_rechecked':True,'all_chapter_keep_remove_segment_reconstructions_exact':True,'chapter_I_heading_exactly_preserved':True,'source_and_existing_outputs_modified':False,'network_requests':0,'derivative_saved':False,'totals':totals})]:
 (D/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
inputs={str(p):sha(p.read_bytes()) for p in [RAW,C/'partition.json',C/'chapters.jsonl',RIGHTS]}
manifest={'input_SHA256':inputs,'output_SHA256':{p.name:sha(p.read_bytes()) for p in sorted(D.iterdir()) if p.is_file() and p.name!='manifest.json'}};(D/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'checks':json.loads((D/'checks.json').read_text()),'manifest_sha256':sha((D/'manifest.json').read_bytes())},indent=2))

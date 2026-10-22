"""One pinned61chapter pass710500B + bounded exact rawspan seeks; no edits."""
import hashlib,json,re,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;EXEC=HERE.parent;SOURCE=EXEC/'m2-intake/gutenberg-novel-prose-seven-joins-v2';sha=lambda b:hashlib.sha256(b).hexdigest();start=time.monotonic();registry=SOURCE/'chapters.jsonl';registryraw=registry.read_bytes();rows=[json.loads(line) for line in registryraw.splitlines()];assert [r['chapter_number'] for r in rows]==list(range(1,62));recipepath=SOURCE/'formatting-recipe.json';reciperaw=recipepath.read_bytes();recipe=json.loads(reciperaw);spanpath=EXEC/'gutenberg-paratext-preparation-v1/chapter-span-proposal.json';spanraw=spanpath.read_bytes();spans={r['chapter_number']:r for r in json.loads(spanraw)};provenance=json.loads((EXEC/'gutenberg-novel-prose-v1/input-provenance.json').read_text());rawfile=Path(provenance['raw_file']);total=0;seekbytes=0;records=[];issues=[];chapterpins=[];chapterstats=[]
def old_offset(chapter,current):
 delta=0
 for patch in sorted([p for p in recipe['patches'] if p['chapter_number']==chapter],key=lambda p:p['derivative_start_byte']):
  begin=patch['derivative_start_byte'];end=patch['derivative_end_byte'];new_begin=begin+delta;new_end=new_begin+len(patch['replacement_ascii'].encode('ascii'))
  if current<new_begin:return current-delta
  if current==new_begin:return begin
  if current==new_end:return end
  if new_begin<current<new_end:raise ValueError('Ambiguouswithinreplacedwhitespace')
  delta+=len(patch['replacement_ascii'].encode('ascii'))-(end-begin)
 return current-delta

def ancestry(chapter,a,b,current_bytes):
 global seekbytes
 olda,oldb=old_offset(chapter,a),old_offset(chapter,b);assert oldb-olda==b-a,'Wrapperoverlapsformattingjoin';offset=0;pieces=[]
 for keep in spans[chapter]['ordered_segments']:
  if keep['action']!='keep':continue
  end=offset+keep['bytes'];lo=max(offset,olda);hi=min(end,oldb)
  if lo<hi:pieces.append({'start_byte':keep['source_start_byte']+lo-offset,'end_byte':keep['source_start_byte']+hi-offset})
  offset=end
 assert offset==spans[chapter]['prospective_retained_bytes'] and sum(p['end_byte']-p['start_byte'] for p in pieces)==b-a
 found=[]
 with rawfile.open('rb') as stream:
  for p in pieces:
   stream.seek(p['start_byte']);chunk=stream.read(p['end_byte']-p['start_byte']);seekbytes+=len(chunk);p['SHA256']=sha(chunk);found.append(chunk)
 assert b''.join(found)==current_bytes,'Rawancestryspan differs'
 return {'original_derivative_start_byte':olda,'original_derivative_end_byte':oldb,'raw_source_file':str(rawfile),'raw_source_SHA256_from_prior_pinned_provenance_not_rehashed_here':provenance['raw_sha256'],'raw_source_pieces':pieces,'exact_local_raw_span_comparison':True,'mapping':'Inverseexactsevenwhitespacepatches, then prior source orderedkeepsegments. No whole rawfilepass.'}
for row in rows:
 assert time.monotonic()-start<30
 chapter=row['chapter_number'];path=SOURCE/row['file'];raw=path.read_bytes();total+=len(raw);assert total<=1000000 and len(raw)==row['bytes'] and sha(raw)==row['sha256'];text=raw.decode('utf8','strict');assert row['source_derivative_sha256']==spans[chapter]['prospective_retained_sha256'];chapterpins.append({'chapter':chapter,'file':str(path.resolve()),'bytes':len(raw),'SHA256':sha(raw)});matches=[];opening=None;nested=False;localissues=[]
 for token in re.finditer(r'/\*|\*/',text):
  if token.group()=='/*':
   if opening is not None:nested=True;localissues.append({'style':'nested_C_comment_open','character_offset':token.start()})
   else:opening=token.start();nested=False
  elif opening is None:localissues.append({'style':'unmatched_C_comment_close','character_offset':token.start()})
  else:matches.append((opening,token.end(),nested));opening=None;nested=False
 if opening is not None:localissues.append({'style':'unclosed_C_comment_open','character_offset':opening})
 known_nind_spans=[]
 for a,b,isnested in matches:
  exact=text[a:b];full=re.fullmatch(r'/\* NIND (?P<internal>.*?) \*/',exact,re.S);status='EXACT_LITERAL_NIND_WRAPPER_PENDING_PARENT_DECISION' if full and not isnested else 'HOLD_OTHER_OR_AMBIGUOUS_COMMENT_NO_GENERIC_STRIPPING';ba=len(text[:a].encode());bb=len(text[:b].encode());item={'chapter':chapter,'chapter_SHA256':row['sha256'],'chapter_file':str(path.resolve()),'status':status,'start_character':a,'end_character':b,'start_byte':ba,'end_byte':bb,'exact_wrapper':exact,'wrapper_SHA256':sha(raw[ba:bb]),'context_before':text[max(0,a-140):a],'context_after':text[b:min(len(text),b+140)],'no_action_applied':True}
  if full and not isnested:
   known_nind_spans.append((a,b));ia=a+full.start('internal');ib=a+full.end('internal');pba=len(text[:ia].encode());pbb=len(text[:ib].encode());item.update({'internal_exact_text':full.group('internal'),'internal_start_character':ia,'internal_end_character':ib,'internal_start_byte':pba,'internal_end_byte':pbb,'internal_SHA256':sha(raw[pba:pbb]),'precise_presentation_marker_spans_not_authorized_edits':[{'start_byte':ba,'end_byte':pba,'exact_text':raw[ba:pba].decode(),'SHA256':sha(raw[ba:pba])},{'start_byte':pbb,'end_byte':bb,'exact_text':raw[pbb:bb].decode(),'SHA256':sha(raw[pbb:bb])}],'internal_text_must_be_preserved':True})
  try:item['native_ancestry']=ancestry(chapter,ba,bb,raw[ba:bb])
  except Exception as error:item['native_ancestry']={'status':'HOLD_ANCESTRY_AMBIGUITY','error':str(error)};item['status']='HOLD_ANCESTRY_AMBIGUITY_NO_ACTION'
  records.append(item)
 for token in re.finditer(r'\bNIND\b',text):
  if not any(a<=token.start()<b for a,b in known_nind_spans):localissues.append({'style':'NIND_outside_exact_unambiguous_wrapper','character_offset':token.start()})
 for token in re.finditer(r'<!--|-->|(?m:^\s*//)',text):localissues.append({'style':'other_comment_like_delimiter_hold','character_offset':token.start(),'exact_token':token.group()})
 for issue in localissues:issues.append({'chapter':chapter,'chapter_SHA256':row['sha256'],**issue})
 chapterstats.append({'chapter':chapter,'literal_comment_pairs':len(matches),'exact_NIND_wrappers':len(known_nind_spans),'other_ambiguity_issues':len(localissues)})
assert total==710500 and total+seekbytes<1000000
summary={'status':'COMPLETE_ONE_PASS61_LITERAL_WRAPPER_INVENTORY_NO_EDITS','chapters_scanned':61,'chapter_text_bytes_read_once':total,'additional_raw_ancestry_span_bytes_read':seekbytes,'total_corpus_bytes_read':total+seekbytes,'all_literal_comment_pairs':len(records),'exact_NIND_wrappers':sum(r['status']=='EXACT_LITERAL_NIND_WRAPPER_PENDING_PARENT_DECISION' for r in records),'other_or_ambiguous_wrapper_records':sum(r['status']!='EXACT_LITERAL_NIND_WRAPPER_PENDING_PARENT_DECISION' for r in records),'other_delimiter_ambiguity_issues':len(issues),'chapters_with_wrappers':sorted({r['chapter'] for r in records}),'precise_marker_bytes_identified_not_removed':sum(sum(p['end_byte']-p['start_byte'] for p in r.get('precise_presentation_marker_spans_not_authorized_edits',[])) for r in records),'native_ancestry_verified_for_occurrences':sum(r.get('native_ancestry',{}).get('exact_local_raw_span_comparison',False) for r in records),'raw_complete_file_rehash_in_this_scan':False,'raw_identity_scope':'Rawfile SHA from already pinned ancestry; only exactwrapper source spans newlyreadandcompared. All61 currentchapter fileSHAs validated during single pass.','no_generic_comment_strip_rule':True,'source_registry_SHA256':sha(registryraw),'formatting_recipe_SHA256':sha(reciperaw),'prior_keep_span_registry_SHA256':sha(spanraw),'source_or_registry_edits':0,'new_admitted_documents':0,'new_admitted_tokens':0,'classifier_runs':0,'tokenizations':0,'training_updates':0,'elapsed_seconds':time.monotonic()-start}
for name,obj in [('occurrences.json',records),('other-ambiguous-delimiters.json',issues),('chapter-inventory.json',chapterstats),('source-chapter-pins.json',chapterpins),('summary.json',summary)]: (HERE/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
(HERE/'manifest.json').write_text(json.dumps({'outputs_SHA256':{p.name:sha(p.read_bytes()) for p in HERE.iterdir() if p.is_file() and p.name!='manifest.json'},'input_metadata_SHA256':{str(registry.resolve()):sha(registryraw),str(recipepath.resolve()):sha(reciperaw),str(spanpath.resolve()):sha(spanraw)},'all61_source_chapter_pins':'source-chapter-pins.json'},indent=2)+'\n');print(json.dumps(summary));print('manifest_SHA256',sha((HERE/'manifest.json').read_bytes()));print('examples',json.dumps([{'chapter':r['chapter'],'wrapper':r['exact_wrapper'],'internal':r.get('internal_exact_text'),'marker_spans':r.get('precise_presentation_marker_spans_not_authorized_edits'),'status':r['status']} for r in records[:5]],ensure_ascii=False))

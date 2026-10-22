"""Independent saved-output reconstruction and direct core retokenization."""
import hashlib,json,pathlib
from tokenizers import Tokenizer
E=pathlib.Path(__file__).resolve().parent.parent;D=E/'gutenberg-novel-prose-v1';raw=(E/'m2-intake/gutenberg-discovery-pilot-v3/text.raw').read_bytes();sha=lambda b:hashlib.sha256(b).hexdigest();assert sha(raw)=='3f6bb9d6f78e0293b56acd4714dd68cb7d6d1d293402031ce9d5a216bcaf9d75'
tokdir=E/'tokenizer-8192';assert sha((tokdir/'manifest.json').read_bytes())=='577c0f59ffc594931650de802c4630f3171ebde139cc32c742f5f264e7f98812';assert sha((tokdir/'core.json').read_bytes())=='5892586252d16641b38483659dacc1c19a048fb59b3ba381831e4b68515645d9';tok=Tokenizer.from_file(str(tokdir/'core.json'))
removed={x['id']:x for x in json.loads((D/'removed-spans.json').read_text())};chapters=[json.loads(l) for l in (D/'chapters.jsonl').read_text().splitlines()];assert len(chapters)==61;used=set();total=0
for c in chapters:
 b=(D/c['file']).read_bytes();assert len(b)==c['bytes'] and sha(b)==c['sha256'] and b.decode()==c['text'];assert '[Illustration' not in b.decode();assert tok.encode(b.decode()).ids is not None;count=len(tok.encode(b.decode()).ids);assert count==c['content_tokens_existing_M1_BPE'];total+=count;parts=[];derivative_cursor=0
 for s in c['ordered_segments']:
  if s['action']=='keep':
   assert s['derivative_start_byte']==derivative_cursor;chunk=b[s['derivative_start_byte']:s['derivative_end_byte']];assert chunk==raw[s['source_start_byte']:s['source_end_byte']] and sha(chunk)==s['sha256'];derivative_cursor=s['derivative_end_byte']
  else:
   rid=s['removed_span_id'];assert rid not in used;used.add(rid);r=removed[rid];chunk=r['exact_text'].encode();assert sha(chunk)==r['sha256'] and chunk==raw[r['source_start_byte']:r['source_end_byte']]
  parts.append(chunk)
 assert derivative_cursor==len(b);reconstructed=b''.join(parts);assert reconstructed==raw[c['source_start_byte']:c['source_end_byte']] and sha(reconstructed)==c['source_chapter_sha256']
assert used==set(removed);assert (D/chapters[0]['file']).read_bytes().startswith(b'Chapter I.\r\n');assert len({c['family_id'] for c in chapters})==1
result={'status':'PASS_INDEPENDENT_SAVED_OUTPUT_CHECKS','chapters':61,'removed_spans_reconstructed':len(removed),'all_source_chapters_reconstructed_exactly':True,'all_saved_text_files_and_JSON_hashes_verified':True,'all_actual_saved_texts_retokenized_direct_core':True,'content_tokens_existing_M1_BPE':total,'original_ChapterI_heading_preserved':True,'work_families':1,'network_requests':0,'new_admitted_tokens':0}
(D/'independent-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

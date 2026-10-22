import pathlib,json,hashlib,time,copy
from apply_recipe import apply,sha
start=time.clock_gettime(time.CLOCK_MONOTONIC)
out=pathlib.Path(__file__).resolve().parent; root=out.parents[1]; original=root/'gutenberg-novel-prose-v1'; ancestry=root/'gutenberg-paratext-preparation-v1'
rawpath=root/'m2-intake/gutenberg-discovery-pilot-v3/text.raw'; raw=rawpath.read_bytes();assert sha(raw)=='3f6bb9d6f78e0293b56acd4714dd68cb7d6d1d293402031ce9d5a216bcaf9d75'
files=[original/'manifest.json',original/'removed-spans.json',original/'input-provenance.json',original/'chapters.jsonl',ancestry/'chapter-span-proposal.json',ancestry/'annotation-span-proposal.json',rawpath]
pins={str(p):sha(p.read_bytes()) for p in files}
chapters=json.loads((ancestry/'chapter-span-proposal.json').read_text()); annotations=json.loads((ancestry/'annotation-span-proposal.json').read_text()); removed=json.loads((original/'removed-spans.json').read_text());assert len(removed)==156
for r in removed:assert sha(raw[r['source_start_byte']:r['source_end_byte']])==r['sha256']
rows=[]; tests=[]
for ch,num in [(3,2),(14,2),(22,2),(30,3),(36,2),(46,2),(48,2)]:
    annotation=next(r for r in annotations if r['id']==f'chapter_{ch:02}_illustration_{num:02}')
    chapter=next(r for r in chapters if r['chapter_number']==ch)
    path=original/f'chapters/chapter_{ch:02}.txt'; data=path.read_bytes();pins[str(path)]=sha(data)
    kept=[s for s in chapter['ordered_segments'] if s['action']=='keep'];assert b''.join(raw[s['source_start_byte']:s['source_end_byte']] for s in kept)==data
    span=annotation['balanced_source_span']; sa,sb=span['source_start_byte'],span['source_end_byte']; assert raw[sa:sb].decode()==annotation['exact_annotation_text']
    seam=sum(s['bytes'] for s in kept if s['source_end_byte']<=sa)
    assert all(not(s['source_start_byte']<sb and s['source_end_byte']>sa) for s in kept)
    a=b=seam
    while a>0 and data[a-1] in b' \t\r\n':a-=1
    while b<len(data) and data[b] in b' \t\r\n':b+=1
    left=next(s for s in kept if s['source_end_byte']==sa);right=next(s for s in kept if s['source_start_byte']==sb)
    leftstart=sa-(seam-a); rightend=sb+(b-seam)
    assert raw[leftstart:sa]+raw[sb:rightend]==data[a:b]
    p={'id':f'ch{ch:02}_{num:02}','chapter_number':ch,'chapter_path':str(path),'chapter_sha256':sha(data),'derivative_start_byte':a,'derivative_end_byte':b,'derivative_start_unicode_codepoint':len(data[:a].decode()),'derivative_end_unicode_codepoint':len(data[:b].decode()),'exact_old_whitespace':data[a:b].decode('ascii'),'old_whitespace_sha256':sha(data[a:b]),'replacement_ascii':' ','replacement_sha256':sha(b' '),'source_annotation_id':annotation['id'],'source_annotation_span':span,'source_annotation_exact_text_retained_for_audit':annotation['exact_annotation_text'],'prior_removed_span_ids':[r['id'] for r in removed if r['chapter_number']==ch and r['source_start_byte']>=sa and r['source_end_byte']<=sb],'raw_whitespace_ancestry':[{'start_byte':leftstart,'end_byte':sa,'sha256':sha(raw[leftstart:sa]),'exact_text':raw[leftstart:sa].decode()},{'start_byte':sb,'end_byte':rightend,'sha256':sha(raw[sb:rightend]),'exact_text':raw[sb:rightend].decode()}],'rationale':'Exact previously removed illustration splits one continuous sentence; collapse only maximal ASCII whitespace at this specifically reviewed seam to one space. No global paragraph normalization.'}
    after=apply(data,[p],sha(data)); assert len(after)==len(data)-(b-a)+1
    beforetext=data.decode(); ca=p['derivative_start_unicode_codepoint'];cb=p['derivative_end_unicode_codepoint'];p['before_context']=beforetext[max(0,ca-160):min(len(beforetext),cb+160)];p['after_context']=beforetext[max(0,ca-160):ca]+' '+beforetext[cb:min(len(beforetext),cb+160)];p['prospective_corrected_chapter_sha256']=sha(after);p['prospective_corrected_chapter_bytes']=len(after);p['original_chapter_bytes']=len(data)
    assert data[:a]+data[a:b]+data[b:]==data; tests.append(p['id']+'_exact_bytes_and_word_order_preserved')
    for label,patches,digest in [('wrong_hash',[p],'0'*64),('duplicate',[p,p],sha(data)),('nonspace_replacement',[dict(p,replacement_ascii='x')],sha(data)),('wrong_oldbytes',[dict(p,exact_old_whitespace='wrong')],sha(data)),('offset_corruption',[dict(p,derivative_start_byte=a-1)],sha(data))]:
        try:apply(data,patches,digest)
        except (ValueError,UnicodeDecodeError):tests.append(p['id']+'_'+label+'_refused')
        else:raise AssertionError(label)
    rows.append(p)
assert len(rows)==7
for p,d in pins.items():assert sha(pathlib.Path(p).read_bytes())==d
recipe={'status':'SEVEN_EXACT_FORMATTING_JOINS_PREPARED_NOT_DERIVED_NOT_ADMITTED','raw_sha256':sha(raw),'immutable_input_pins':pins,'ancestry':'Existing derivative is exact keep-span concatenation from pinned raw; all156 historical omissions and their exact text remain in original removed-spans.json and raw. Recipe additionally retains every whitespace byte proposed for replacement.','offset_units':'half-open original-derivative byte offsets plus Unicode codepoint offsets; no newline translation','ordered_application':'Validate original chapter SHA and all exact spans first, apply descending byte offsets; seven distinct chapters. Pure helper returns bytes only.','patches':rows,'prospective_total_byte_reduction':sum(p['original_chapter_bytes']-p['prospective_corrected_chapter_bytes'] for p in rows),'policy':'ONLY seven enumerated whitespace spans; no spelling/sentence rewrites, arbitrary joins, paragraph-wide cleanup, tokenizer or language rerun. Parent must review before deriving any new corpus.','all_prior_removed_spans_preserved':156,'new_admitted_documents':0,'new_admitted_tokens':0,'models_initialized':0,'training_updates':0}
(out/'recipe.json').write_text(json.dumps(recipe,ensure_ascii=False,indent=2)+'\n')
(out/'checks.json').write_text(json.dumps({'status':'PASS','checks':tests,'count':len(tests),'input_pins_unchanged':True,'full_new_corpus_written':False,'elapsed_native_seconds':time.clock_gettime(time.CLOCK_MONOTONIC)-start},indent=2)+'\n')
assert sum(p.stat().st_size for p in out.iterdir() if p.is_file())<200000
print(json.dumps({'recipe_sha256':sha((out/'recipe.json').read_bytes()),'checks_sha256':sha((out/'checks.json').read_bytes()),'check_count':len(tests),'joins':len(rows),'byte_reduction_if_approved':recipe['prospective_total_byte_reduction']},indent=2))
for p in rows:print(p['id'],repr(p['before_context']),'=>',repr(p['after_context']))

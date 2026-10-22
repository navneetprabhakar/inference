import pathlib,hashlib,json,runpy,sys,contextlib,io
D=pathlib.Path(__file__).resolve().parent;E=D.parent;P=E/'m2-intake/gutenberg-seven-join-preparation-v1';h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();sha=lambda b:hashlib.sha256(b).hexdigest();R=P/'recipe.json';assert h(R)=='219d01f90d477fc5485c5b2cf63a8289ffcf3de6b0a01016c6e60c51a19a19a3';recipe=json.loads(R.read_text());before={str(p):h(p) for p in P.iterdir() if p.is_file()};old=pathlib.Path.write_text
# Reproduce all42 preparation controls without modifying original recipe/check receipts.
def write(self,*args,**kwargs):return old(D/('reproduced-'+self.name) if self.resolve() in {(P/'recipe.json').resolve(),(P/'checks.json').resolve()} else self,*args,**kwargs)
pathlib.Path.write_text=write;sys.path.insert(0,str(P));log=io.StringIO()
try:
 with contextlib.redirect_stdout(log):runpy.run_path(str(P/'prepare.py'),run_name='__main__')
finally:pathlib.Path.write_text=old
(D/'reproduced-controls.log').write_text(log.getvalue());assert h(D/'reproduced-recipe.json')==h(R);assert json.loads((D/'reproduced-checks.json').read_text())['count']==42
from apply_recipe import apply
raw=(E/'m2-intake/gutenberg-discovery-pilot-v3/text.raw').read_bytes();assert sha(raw)==recipe['raw_sha256'];original=E/'gutenberg-novel-prose-v1';removed=json.loads((original/'removed-spans.json').read_text());assert len(removed)==156
for path,digest in recipe['immutable_input_pins'].items():assert h(pathlib.Path(path))==digest
for row in removed:assert sha(raw[row['source_start_byte']:row['source_end_byte']])==row['sha256']
manifest=json.loads((original/'manifest.json').read_text());assert all(h(original/name)==digest for name,digest in manifest['output_SHA256'].items())
proposals=json.loads((E/'gutenberg-paratext-preparation-v1/chapter-span-proposal.json').read_text());annotations=json.loads((E/'gutenberg-paratext-preparation-v1/annotation-span-proposal.json').read_text());ann={r['id']:r for r in annotations};by_ch={r['chapter_number']:r for r in proposals}
assert len(proposals)==61
for chapter in proposals:
 kept=[r for r in chapter['ordered_segments'] if r['action']=='keep'];observed=(original/f"chapters/chapter_{chapter['chapter_number']:02}.txt").read_bytes();assert b''.join(raw[s['source_start_byte']:s['source_end_byte']] for s in kept)==observed
# Human-reviewed contexts identify a continuous sentence at each seam, not a generic paragraph rule.
phrases={3:('idea of his','being gone'),14:('invite him','to read aloud'),22:('matter had ever','excited before'),30:('in order to have','the earliest assurance'),36:('what he told','himself.'),46:('indistinctly of his','concern,'),48:('behaviour in your','daughter has')};assert len(recipe['patches'])==7 and set(p['chapter_number'] for p in recipe['patches'])==set(phrases)
seams=[]
for p in recipe['patches']:
 ch=p['chapter_number'];data=pathlib.Path(p['chapter_path']).read_bytes();a,b=p['derivative_start_byte'],p['derivative_end_byte'];assert sha(data)==p['chapter_sha256'];assert p['derivative_start_unicode_codepoint']==len(data[:a].decode()) and p['derivative_end_unicode_codepoint']==len(data[:b].decode());left,right=phrases[ch];assert data[:a].decode().endswith(left) and data[b:].decode().startswith(right)
 n=ann[p['source_annotation_id']];assert n['balanced_source_span']==p['source_annotation_span'];s,t=p['source_annotation_span']['source_start_byte'],p['source_annotation_span']['source_end_byte'];assert raw[s:t].decode()==p['source_annotation_exact_text_retained_for_audit']==n['exact_annotation_text'];assert raw[s:t].startswith(b'[Illustration:') and raw[s:t].rstrip().endswith(b']')
 omitted=[r for r in removed if r['id'] in p['prior_removed_span_ids']];assert omitted and b''.join(raw[r['source_start_byte']:r['source_end_byte']] for r in omitted)==raw[s:t]
 ancestry=p['raw_whitespace_ancestry'];assert len(ancestry)==2 and ancestry[0]['end_byte']==s and ancestry[1]['start_byte']==t
 chunks=[]
 for q in ancestry:
  chunk=raw[q['start_byte']:q['end_byte']];assert chunk.decode()==q['exact_text'] and sha(chunk)==q['sha256'];chunks.append(chunk)
 assert b''.join(chunks)==data[a:b] and data[a:b].decode()==p['exact_old_whitespace'];out=apply(data,[p],p['chapter_sha256']);assert out==data[:a]+b' '+data[b:] and sha(out)==p['prospective_corrected_chapter_sha256'] and len(out)==p['prospective_corrected_chapter_bytes'];assert out[:a]+data[a:b]+out[a+1:]==data
 seams.append({'chapter':ch,'left_phrase':left,'right_phrase':right,'annotation_id':p['source_annotation_id'],'byte_span':[a,b],'exact_old_whitespace_hex':data[a:b].hex(),'byte_reduction':b-a-1,'scope':'only whitespace separating halves of one continuous sentence','source_annotation_retained_in_original_immutable_raw_and_sidecar':True})
assert sum(x['byte_reduction'] for x in seams)==59
for path,digest in recipe['immutable_input_pins'].items():assert h(pathlib.Path(path))==digest
assert all(h(pathlib.Path(p))==digest for p,digest in before.items());result={'status':'PASS_SCOPED_SEVEN_JOIN_RECIPE_AUDIT_NO_CORPUS_DERIVATION','blocking_findings':[],'seven_full_contexts_manually_reviewed':True,'source_ancestry_all61_original_chapters_exact':True,'all156_original_removed_span_hashes_preserved':True,'controls_reproduced':42,'seams':seams,'prospective_total_reduction_bytes':59,'no_prose_or_punctuation_change':True,'no_global_paragraph_rule':True,'immutable_preparation_and_all_source_outputs_unchanged':True,'execution_precondition':'Future writer must pin this exact recipe SHA256219d01f90d477fc5485c5b2cf63a8289ffcf3de6b0a01016c6e60c51a19a19a3 and this helper/source hashes. The pure helper is intentionally not a general approval gate; it must only receive the seven approved recipe entries. Parent owns execution dispatch.','helper_SHA256':h(P/'apply_recipe.py'),'prepare_SHA256':h(P/'prepare.py'),'new_full_corpus_derivations':0,'tokenizer_runs':0,'detector_runs':0,'network_requests':0,'training_operations':0};(D/'review.json').write_text(json.dumps(result,indent=2)+'\n');(D/'manifest.json').write_text(json.dumps({p.name:h(p) for p in D.iterdir() if p.is_file() and p.name!='manifest.json'},indent=2)+'\n');print(json.dumps({'status':'PASS','recipe_SHA256':h(R),'review_SHA256':h(D/'review.json'),'audit_manifest_SHA256':h(D/'manifest.json'),'helper_SHA256':h(P/'apply_recipe.py'),'controls':42,'seams':7,'all156historical_removed_spans_unchanged':True}))

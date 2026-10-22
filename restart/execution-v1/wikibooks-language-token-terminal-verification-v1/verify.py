"""Independent saved-score coverage/projection reconstruction and direct M1 counts.
No detector rerun, source rewrite, fitting, models or admission.
"""
import hashlib,json,math,pathlib,sqlite3,sys,time
from tokenizers import Tokenizer
P=pathlib.Path(__file__).resolve().parent;E=P.parent;PREP=E/'wikibooks-language-token-preparation-v1';PROFILE=PREP/'profile.json';EXPECTED_PROFILE='8f0c7233d2f0af5920e48f0874c1ed94a2e9169191ff26c7f8ecd1499d2b835e';D=E/'m2-intake/wikibooks-language-token-v1';OUT=E/'m2-intake/wikibooks-language-token-independent-verification-v1';h=lambda p:hashlib.file_digest(p.open('rb'),'sha256').hexdigest()
def ro(p):return sqlite3.connect(pathlib.Path(p).resolve().as_uri()+'?mode=ro',uri=True)
def digest(b):return hashlib.sha256(b).digest()
def windows(text):
 yield ('whole',0,len(text),sum(c.isalpha() for c in text),True,None,text)
 for start in range(0,len(text),1024):
  chunk=text[start:start+1024];alpha=sum(c.isalpha() for c in chunk);yield ('chunk',start,start+len(chunk),alpha,alpha>=40,None if alpha>=40 else 'fewer_than_40_alphabetic_characters',chunk)
def main():
 began=time.monotonic();assert h(PROFILE)==EXPECTED_PROFILE;profile=json.loads(PROFILE.read_text());worker=json.loads((D/'result.json').read_text());sup=json.loads((D/'supervisor-result.json').read_text())
 if worker['status']!='COMPLETE_LANGUAGE_DIAGNOSTICS_PROVISIONAL_M1_COUNTS_NO_ADMISSION' or sup['status']!='COMPLETE_LANGUAGE_TOKEN_DIAGNOSTICS_NO_ADMISSION':raise RuntimeError('Parent-confirmed complete terminal required')
 assert sup['worker_exit_code']==0 and sup['reason'] is None and sup['elapsed_seconds']<=600 and sup['peak_observed_process_tree_RSS_bytes']<=1000000000 and sup['worker_receipt_sha256']==h(D/'result.json');assert h(D/'screening.sqlite3')==worker['database_sha256'];assert sum(p.stat().st_size for p in D.rglob('*') if p.is_file())<=100000000;assert not list(D.glob('*.sqlite3-journal'));OUT.mkdir(exist_ok=False)
 for item in profile['inputs']:assert h(pathlib.Path(item['path']))==item['sha256']
 core=pathlib.Path(profile['tokenizer_core']['path']);manifest=json.loads(pathlib.Path(profile['tokenizer_manifest']['path']).read_text());assert manifest['files']['core.json']==h(core);tokenizer=Tokenizer.from_file(str(core));config=json.loads(tokenizer.to_str());assert all(config[k] is None for k in ['normalizer','post_processor','truncation','padding']) and not config['added_tokens']
 final=ro(profile['finalizer']['path']);targets={o:(page,rev,family,title,sha,n,b) for o,page,rev,family,title,sha,n,b in final.execute("select p.source_ordinal,p.page_id,p.revision_id,p.family,p.title,p.text_sha256,p.characters,p.utf8_bytes from pages p join final_pages f on f.source_ordinal=p.source_ordinal where f.holds='[]'")};assert len(targets)==27585 and sum(x[-1] for x in targets.values())==111989353;assert final.execute('select count(*) from cross_family_block_groups').fetchone()[0]==15720;final.close()
 db=ro(D/'screening.sqlite3');db.row_factory=sqlite3.Row;assert db.execute('pragma integrity_check').fetchone()[0]=='ok';docs={r['source_ordinal']:dict(r) for r in db.execute('select * from main.docs')};assert set(docs)==set(targets);known={r['source_ordinal']:r for r in json.loads(pathlib.Path(profile['discovery_holds']['path']).read_text())['records']};assert len(known)==20 and sum(x['post_finalizer_candidate'] for x in known.values())==6
 saved_known={r['source_ordinal']:r for r in db.execute('select * from main.discovery_reviews')};assert set(saved_known)==set(known)
 for o,r in saved_known.items():assert json.loads(r['metadata'])==known[o] and r['post_finalizer_candidate']==int(known[o]['post_finalizer_candidate']) and r['disposition']==known[o]['disposition']
 aggregate={k:{'documents':0,'provisional_M1_content_tokens':0,'provisional_content_plus_one_EOS_each':0,'source_UTF8_bytes':0} for k in ['all_post_finalizer','raw_language_pass','language_pass_after_known_discovery_holds']};seen=set();scored=skipped=allwindows=0;tail_fails=0;known_present=0
 for item in profile['shards']:
  source=ro(item['path'])
  for ordinal,page,rev,family,payload in source.execute('select source_ordinal,page_id,revision_id,family,data from rendered order by source_ordinal'):
   if ordinal not in targets:continue
   if time.monotonic()-began>=285:raise TimeoutError('285second terminal verifier cap')
   assert ordinal not in seen;seen.add(ordinal);r=json.loads(payload);text=r['text'];raw=text.encode();identity=targets[ordinal];stored=docs[ordinal];assert (page,rev,family,r['title'],hashlib.sha256(raw).hexdigest(),len(text),len(raw))==identity;assert (stored['page_id'],stored['revision_id'],stored['family'],stored['title'],stored['text_sha256'],stored['characters'],stored['utf8_bytes'])==identity
   actual_windows=db.execute('select * from main.windows where source_ordinal=? order by ordinal',(ordinal,)).fetchall();expected=list(windows(text));assert len(actual_windows)==len(expected);english=[];docskip=0
   for index,(s,e) in enumerate(zip(actual_windows,expected)):
    kind,start,end,alpha,score,reason,chunk=e;projected=chunk.replace('\n',' ').replace('\r',' ').replace('</s>','< /s >').encode();assert (s['ordinal'],s['kind'],s['start'],s['end'],s['alphabetics'],s['scored'],s['skip_reason'])==(index,kind,start,end,alpha,int(score),reason);assert s['raw_sha256']==digest(chunk.encode()) and s['projection_sha256']==digest(projected);allwindows+=1
    if score:
     p=float(s['raw_probability']);assert math.isfinite(p) and 0<=p<=1.001 and p==s['top_probability'];en=p if s['label']=='__label__en' else 0.;passed=int(en>=.8);assert en==s['english_probability'] and passed==s['policy_pass'];english.append(en);scored+=1
     if kind=='chunk' and end-start<1024 and not passed:tail_fails+=1
    else:
     assert all(s[k] is None for k in ['label','raw_probability','top_probability','english_probability','policy_pass']);skipped+=1;docskip+=1
   assert english;passed=min(english)>=.8;assert (stored['language_pass'],stored['minimum_english_probability'],stored['scored_lines'],stored['skipped_chunks'])==(int(passed),min(english),len(english),docskip)
   tok=len(tokenizer.encode(text,add_special_tokens=False).ids);assert stored['content_tokens']==tok and stored['tokens_plus_one_EOS']==tok+1;assert stored['known_discovery_hold']==int(ordinal in known);known_present+=ordinal in known
   holds=[]
   if not passed:holds.append('whole_document_or_1024character_window_language')
   if ordinal in known:holds.append('known_discovery_review_hold_or_exclusion')
   assert json.loads(stored['holds'])==holds
   for name,include in [('all_post_finalizer',True),('raw_language_pass',passed),('language_pass_after_known_discovery_holds',passed and ordinal not in known)]:
    if include:
     a=aggregate[name];a['documents']+=1;a['provisional_M1_content_tokens']+=tok;a['provisional_content_plus_one_EOS_each']+=tok+1;a['source_UTF8_bytes']+=len(raw)
  source.close()
 assert seen==set(targets) and known_present==6 and scored<=150471 and allwindows<=150471;assert db.execute('select count(*) from main.windows').fetchone()[0]==allwindows;assert db.execute('select count(*) from main.windows where scored=1').fetchone()[0]==scored;assert worker['summary']==aggregate and worker['stats']['documents']==27585 and worker['stats']['source_UTF8_bytes']==111989353 and worker['stats']['content_tokens']==aggregate['all_post_finalizer']['provisional_M1_content_tokens'] and worker['stats']['scored_lines']==scored and worker['stats']['skipped_chunks']==skipped and worker['stats']['all_windows']==allwindows
 db.close()
 for item in profile['inputs']:assert h(pathlib.Path(item['path']))==item['sha256']
 assert h(PROFILE)==EXPECTED_PROFILE and h(D/'screening.sqlite3')==worker['database_sha256'];result={'status':'PASS_INDEPENDENT_ALL_DOCUMENT_WINDOW_SCORE_HOLD_AND_DIRECT_TOKEN_VERIFICATION_NO_ADMISSION','documents':len(seen),'source_UTF8_bytes':111989353,'whole_and_chunk_windows':allwindows,'scored_lines':scored,'explicit_skipped_chunks':skipped,'eligible_short_tail_failures_preserved':tail_fails,'all20_discovery_reviews_preserved':True,'known_candidate_additive_holds_verified':known_present,'direct_M1_retokenization_all_documents':True,'content_and_exactly_one_EOS_separate':True,'independent_summary':aggregate,'language_output_database_SHA256':worker['database_sha256'],'worker_receipt_SHA256':h(D/'result.json'),'all_pinned_source_inputs_unchanged':True,'all_original_finalizer_holds_and_cross_family_groups_unchanged':True,'detector_reruns':0,'network_requests':0,'training_operations':0,'elapsed_seconds':time.monotonic()-began,'remaining':'These are provisional language-filtered counts, not usable/admitted/rights/factual or cross-source leakage clearance.','new_admitted_documents':0,'new_admitted_tokens':0};(OUT/'verification.json').write_text(json.dumps(result,indent=2)+'\n');(OUT/'manifest.json').write_text(json.dumps({'verifier_SHA256':h(pathlib.Path(__file__)),'verification_SHA256':h(OUT/'verification.json')},indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()

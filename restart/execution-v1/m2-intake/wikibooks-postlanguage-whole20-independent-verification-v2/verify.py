import pathlib,json,hashlib,sqlite3,signal,time,subprocess
signal.signal(signal.SIGALRM,lambda *_: (_ for _ in ()).throw(TimeoutError('verify60seconds')));signal.alarm(60);started=time.monotonic()
HERE=pathlib.Path(__file__).resolve().parent;BASE=HERE.parents[1];P=BASE/'wikibooks-postlanguage-whole-capture-preparation-v2';OUT=HERE.parent/'wikibooks-postlanguage-development-whole20-v2';SELECTION=HERE.parent/'wikibooks-postlanguage-development-preparation-v3';SCREEN=HERE.parent/'wikibooks-language-token-v1/screening.sqlite3';FINAL=HERE.parent/'wikibooks-global-finalization-v3/finalized.sqlite3'
def H(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while b:=f.read(65536):h.update(b)
 return h.hexdigest()
def ro(p):
 c=sqlite3.connect(p.resolve().as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row;c.execute('pragma query_only=ON');c.execute('pragma cache_size=-2048');return c
def load(p):return json.loads(p.read_text())
assert H(P/'code-pins.json')=='47477c9aa81ac4d1dfb944ad25e0b917cecfef13fb7461e3005ddfb44314db98' and H(P/'profile.json')=='2791df4ee3b81779df42596f76a993ffe56327d6434e82beff2da315fe1574f1'
registry=load(P/'code-pins.json');assert len(registry['files'])==44
for p,h in registry['files'].items():assert not pathlib.Path(p).is_symlink() and H(pathlib.Path(p))==h,p
assert H(SELECTION/'proposal.json')=='401780eb5af47cc2fcbfa21618f145a07efe2899dff2dccfbdea867a128b6570';prop=load(SELECTION/'proposal.json');selected=prop['selected'];result=load(OUT/'result.json');sup=load(OUT/'supervisor.json');own=load(OUT/'ownership.json');assert result['status']=='COMPLETE_FIXED20_WHOLE_CAPTURE_DEVELOPMENT_ONLY' and sup['status']=='COMPLETE_DEVELOPMENT_ONLY' and sup['worker_exit_code']==0 and sup['worker_receipt_SHA256']==H(OUT/'result.json');assert sup['elapsed_seconds']<60 and result['elapsed_seconds']<55 and sup['peak_observed_tree_RSS_bytes']<=1000000000
for key in ['supervisor_PID','worker_PID']:
 ps=subprocess.run(['/bin/ps','-p',str(own[key]),'-o','pid='],capture_output=True,text=True);assert not ps.stdout.strip(),key
assert len(result['records'])==20 and [r['ordinal'] for r in result['records']]==[r['source_ordinal'] for r in selected]
proof=[];expectedfiles={'ownership.json','result.json','supervisor.json','worker.log'}
with ro(SCREEN) as screen,ro(FINAL) as final:
 for e,finished in zip(selected,result['records']):
  ordinal=e['source_ordinal'];receipt=load(OUT/finished['receipt_file']);assert H(OUT/finished['receipt_file'])==finished['receipt_SHA256'];assert receipt['selection']==e and receipt['status']==finished['status']=='WHOLE_ORIGINAL_TEXT_CAPTURED_DEVELOPMENT_ONLY'
  for flag in ['not_acceptance','original_holds_preserved','no_tokenization_or_language_rerun']:assert receipt[flag] is True
  body=(OUT/receipt['body_file']).read_bytes();native=(OUT/receipt['native_record_file']).read_bytes();obj=json.loads(native);meta=receipt['metadata'];text=body.decode('utf8');digest=hashlib.sha256(body).hexdigest();assert digest==e['text_sha256']==receipt['body_SHA256']==obj['extracted_text_sha256'] and len(body)==e['utf8_bytes']==receipt['body_bytes']==obj['text_UTF8_bytes'] and len(text)==e['characters']==obj['text_unicode_characters'];assert obj['text'].encode('utf8')==body and len(native)==receipt['native_record_bytes'] and hashlib.sha256(native).hexdigest()==meta['native_record_SHA256']
  assert (obj['canonical_source_ordinal'],obj['page_id'],obj['revision_id'],obj['family_id'],obj['title'],obj['training_admitted'])==(ordinal,e['page_id'],e['revision_id'],e['family'],e['title'],False)
  with ro(pathlib.Path(e['source_shard']['path'])) as source:
   original=source.execute('select * from rendered where source_ordinal=?',(ordinal,)).fetchone();assert original['data'].encode('utf8')==native;assert (original['page_id'],original['revision_id'],original['family'])==(e['page_id'],e['revision_id'],e['family']);blocks=[dict(r) for r in source.execute('select * from blocks where source_ordinal=? order by ordinal',(ordinal,))]
  assert blocks==meta['blocks'];last=0
  for n,b in enumerate(blocks):
   assert b['ordinal']==n and b['source_ordinal']==ordinal and b['start']==last and b['characters']==b['end']-b['start'];assert hashlib.sha256(text[b['start']:b['end']].encode()).hexdigest()==b['hash'];last=b['end']+2
  assert '\n\n'.join(text[b['start']:b['end']] for b in blocks)==text
  current=dict(screen.execute('select * from docs where source_ordinal=?',(ordinal,)).fetchone());assert current==meta['screening'] and all(current[k]==e[k] for k in current);page=dict(final.execute('select * from pages where source_ordinal=?',(ordinal,)).fetchone());role=dict(final.execute('select * from final_pages where source_ordinal=?',(ordinal,)).fetchone());assert page==meta['finalizer_page'] and role==meta['finalizer_role'];assert all(page[k]==e[k] for k in ['page_id','revision_id','family','title','text_sha256','characters','utf8_bytes'])
  for key,value in meta['original_source_location_fields'].items():assert obj.get(key)==value
  assert obj['training_admitted'] is False and receipt['new_admitted_documents']==0
  expectedfiles|={finished['receipt_file'],receipt['body_file'],receipt['native_record_file']};proof.append({'source_ordinal':ordinal,'page_id':e['page_id'],'revision_id':e['revision_id'],'family':e['family'],'title':e['title'],'SHA256':digest,'UTF8_bytes':len(body),'characters':len(text),'stored_M1_tokens':e['content_tokens'],'blocks_verified':len(blocks),'screening_holds':current['holds'],'finalizer_holds':role['holds'],'whole_original_exact_inverse':True})
assert set(f.name for f in OUT.iterdir() if f.is_file())==expectedfiles
files={f.name:{'bytes':f.stat().st_size,'SHA256':H(f)} for f in OUT.iterdir() if f.is_file()};assert sum(v['bytes'] for v in files.values())==sup['output_bytes']<=5000000
assert sum(v['UTF8_bytes'] for v in proof)==result['whole_text_captured_bytes']==45288 and sum(v['stored_M1_tokens'] for v in proof)==14527 and result['whole_captured']==20 and result['held_outcomes']==0
prior=HERE.parent/'wikibooks-postlanguage-development-whole20-v1';old=load(HERE.parent/'wikibooks-postlanguage-whole20-partial-verification-v1/verification.json');assert all(H(prior/n)==d['SHA256'] for n,d in old['files'].items())
for p,h in registry['files'].items():assert H(pathlib.Path(p))==h,p
report={'status':'PASS_EXACT20_CAPTURE_NOT_QUALITY_OR_ADMISSION','input_pins_rehashed_twice':44,'verified_whole_documents':20,'verified_whole_UTF8_bytes':45288,'existing_stored_M1_tokens_not_recomputed':14527,'negative_or_held_capture_outcomes':0,'proof':proof,'output_files':files,'supervisor':sup,'worker_and_supervisor_absent':True,'failedv1_outputs_unchanged':True,'new_admitted_documents':0,'new_admitted_tokens':0,'no_normalization_tokenizer_model_training_network_ledger':True,'elapsed_seconds':time.monotonic()-started};(HERE/'verification.json').write_text(json.dumps(report,indent=2)+'\n');(HERE/'manifest.json').write_text(json.dumps({'files':{p.name:{'bytes':p.stat().st_size,'SHA256':H(p)} for p in HERE.iterdir() if p.is_file()}},indent=2)+'\n');print(json.dumps({'status':report['status'],'verification_SHA256':H(HERE/'verification.json'),'manifest_SHA256':H(HERE/'manifest.json')}))

from pathlib import Path
import sys,json,hashlib,types,os,collections
B=Path(__file__).resolve().parent;P=B/'wikibooks-heading-context-whole-capture-preparation-v1';D=B/'m2-intake/wikibooks-heading-context-development-whole20-v1';O=B/'wikibooks-heading-whole20-terminal-independent-verification-v1';sys.path.insert(0,str(P));import capture as c
h=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
code='431b43bac36af102c6e18c903db3af165a6b2d198b4447a59258b73c4d69c88a';profile='d8531f0de36777a93f6590276ec38db5bf873f4bfd3e31cbef90d762bb253360';selected=c.verify(types.SimpleNamespace(code_pins_sha256=code,profile_sha256=profile));r=json.loads((D/'result.json').read_text());s=json.loads((D/'supervisor.json').read_text());owner=json.loads((D/'ownership.json').read_text())
assert h(D/'result.json')=='28647d448c54704a504f22ae0605042d06cadbe4164dddb35b3cfb4c0ba69433' and h(D/'supervisor.json')=='c85ce27cbef8d0b2a6721a8c01bff414d43b5b547f12dfc0741ad21f644bcccb'
assert r['status']=='COMPLETE_FIXED20_WHOLE_CAPTURE_DEVELOPMENT_ONLY' and s['status']=='COMPLETE_DEVELOPMENT_ONLY' and s['worker_exit_code']==0 and s['worker_receipt_SHA256']==h(D/'result.json') and r['whole_captured']==20 and r['held_outcomes']==0 and r['whole_text_captured_bytes']==60972
for k in ['supervisor_PID','worker_PID']:
 try:os.kill(owner[k],0)
 except ProcessLookupError:pass
 else:raise AssertionError('PID_present')
assert s['elapsed_seconds']<60 and s['peak_observed_tree_RSS_bytes']<=1000000000 and sum(q.stat().st_size for q in D.iterdir() if q.is_file())<=5000000
assert [x['ordinal'] for x in r['records']]==[x['source_ordinal'] for x in selected];verified=[];totalbytes=0;totaltokens=0;blocks=0
screen=c.ro(c.SCREEN);final=c.ro(c.FINAL)
for x,expect in zip(r['records'],selected):
 i=x['ordinal'];receipt=D/x['receipt_file'];assert h(receipt)==x['receipt_SHA256'];q=json.loads(receipt.read_text());assert q['selection']==expect and q['source_ordinal']==i and q['status']=='WHOLE_ORIGINAL_TEXT_CAPTURED_DEVELOPMENT_ONLY' and q['not_acceptance'] and q['new_admitted_documents']==0
 body=(D/q['body_file']).read_bytes();native=(D/q['native_record_file']).read_bytes();obj=json.loads(native);text=body.decode('utf8');assert obj['text'].encode('utf8')==body and h(D/q['body_file'])==q['body_SHA256']==expect['text_sha256'] and len(body)==q['body_bytes']==expect['utf8_bytes'] and len(text)==expect['characters'];assert len(native)==q['native_record_bytes'] and hashlib.sha256(native).hexdigest()==q['metadata']['native_record_SHA256']
 assert (obj['canonical_source_ordinal'],obj['page_id'],obj['revision_id'],obj['family_id'],obj['title'],obj['extracted_text_sha256'],obj['text_unicode_characters'],obj['text_UTF8_bytes'],obj['training_admitted'])==(i,expect['page_id'],expect['revision_id'],expect['family'],expect['title'],expect['text_sha256'],expect['characters'],expect['utf8_bytes'],False)
 rows=q['metadata']['blocks'];parts=[]
 for n,b in enumerate(rows):
  assert b['source_ordinal']==i and b['ordinal']==n and b['start']==(0 if n==0 else rows[n-1]['end']+2) and 0<=b['start']<=b['end']<=len(text) and b['characters']==b['end']-b['start'];v=text[b['start']:b['end']];assert hashlib.sha256(v.encode('utf8')).hexdigest()==b['hash'];parts.append(v)
 assert '\n\n'.join(parts)==text;blocks+=len(rows)
 current=dict(screen.execute('select * from docs where source_ordinal=?',(i,)).fetchone());assert current==q['metadata']['screening'];assert all(expect[k]==v for k,v in current.items())
 fp=dict(final.execute('select * from pages where source_ordinal=?',(i,)).fetchone());fr=dict(final.execute('select * from final_pages where source_ordinal=?',(i,)).fetchone());assert fp==expect['expected_finalizer_page']==q['metadata']['finalizer_page'] and fr==expect['expected_finalizer_role']==q['metadata']['finalizer_role'];assert fp['active']==1 and json.loads(fp['holds'])==json.loads(fr['holds'])==[]
 assert q['metadata']['original_source_location_fields']=={k:obj.get(k) for k in q['metadata']['original_source_location_fields']}
 totalbytes+=len(body);totaltokens+=expect['content_tokens'];verified.append({'source_ordinal':i,'page_id':expect['page_id'],'revision_id':expect['revision_id'],'family':expect['family'],'body_SHA256':q['body_SHA256'],'UTF8_bytes':len(body),'stored_M1_tokens_not_recounted':expect['content_tokens'],'whole_native_and_block_inverse':True,'current_finalizer_holds_and_owner_unchanged':True})
screen.close();final.close();assert totalbytes==60972 and totaltokens==20313
O.mkdir(exist_ok=False);out={'status':'PASS_ACTUAL20_WHOLE_CAPTURE_AND_TERMINAL_CUSTODY_NO_ACCEPTANCE','all42code_input_pins_verified_including14DB_fullstream_hashes':True,'source_DB_verification_binary_bytes':1734524928,'source_body_rows_requeried':0,'saved_wholetexts_read_and_native_JSON_inverse_verified':20,'UTF8_bytes':totalbytes,'stored_M1_content_tokens_not_retokenized':totaltokens,'exact_block_spans_and_hashes_verified':blocks,'all20current_screen_finalizer_pages_roles_holds_reconciled':True,'all20selection_outcomes_no_replacement':True,'PIDs_absent':True,'limits':s,'per_document':verified,'not_semantic_or_factual_acceptance':True,'new_admitted_documents':0,'network_ledger_tokenizer_model_training_operations':0,'output_pins':{q.name:h(q) for q in D.iterdir() if q.is_file()}}
(O/'verification.json').write_text(json.dumps(out,indent=2)+'\n');(O/'manifest.json').write_text(json.dumps({'verification.json':h(O/'verification.json'),'verifier_SHA256':h(__file__)},indent=2)+'\n');print(h(O/'verification.json'),h(O/'manifest.json'))

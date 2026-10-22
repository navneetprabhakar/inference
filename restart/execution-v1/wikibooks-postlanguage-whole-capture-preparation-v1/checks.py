"""Production selected-row/wholeworker and supervisor controls on synthetic sources only."""
import pathlib,sys,tempfile,json,hashlib,sqlite3,argparse,os,time,subprocess,signal
from unittest.mock import patch
HERE=pathlib.Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import capture as c
H=lambda b:hashlib.sha256(b).hexdigest();checks=[]
def yes(name):checks.append({'check':name,'PASS':True})
def reject(fn,expected=Exception):
 try:fn()
 except expected:return
 raise AssertionError('expected rejection')
with tempfile.TemporaryDirectory() as tmp:
 root=pathlib.Path(tmp);screen=root/'screen.sqlite';final=root/'final.sqlite';renderer=root/'renderer.sqlite';db=sqlite3.connect(screen);db.execute('create table docs(source_ordinal integer primary key,page_id,revision_id,family,title,text_sha256,characters,utf8_bytes,content_tokens,tokens_plus_one_EOS,scored_lines,skipped_chunks,language_pass,minimum_english_probability,known_discovery_hold,holds)');fd=sqlite3.connect(final);fd.execute('create table pages(source_ordinal integer primary key,page_id,revision_id,family,title,depth,text_sha256,characters,utf8_bytes,holds,active)');fd.execute('create table final_pages(source_ordinal integer primary key,holds,exact_owner)');rd=sqlite3.connect(renderer);rd.execute('create table rendered(source_ordinal integer primary key,page_id,revision_id,family,data)');rd.execute('create table blocks(source_ordinal,ordinal,kind,hash,characters,start,end)');selected=[]
 for n in range(20):
  first='é first'+str(n);second='second'+str(n);text=first+'\n\n'+second;body=text.encode();d={'source_ordinal':n,'page_id':n+100,'revision_id':n+1000,'family':'family'+str(n),'title':'Synthetic'+str(n),'text_sha256':H(body),'characters':len(text),'utf8_bytes':len(body),'content_tokens':n+10,'tokens_plus_one_EOS':n+11,'scored_lines':1,'skipped_chunks':0,'language_pass':1,'minimum_english_probability':.99,'known_discovery_hold':0,'holds':'[]'};db.execute('insert into docs values ('+','.join('?' for _ in d)+')',list(d.values()));fd.execute('insert into pages values (?,?,?,?,?,?,?,?,?,?,?)',(n,n+100,n+1000,d['family'],d['title'],1,H(body),len(text),len(body),'["prior"]',1));fd.execute('insert into final_pages values (?,?,?)',(n,'["global"]',None));r={'canonical_source_ordinal':n,'page_id':n+100,'revision_id':n+1000,'family_id':d['family'],'title':d['title'],'text':text,'extracted_text_sha256':H(body),'text_unicode_characters':len(text),'text_UTF8_bytes':len(body),'training_admitted':False,'archive_sha256':'1'*64,'member':'synthetic.jsonl','member_ordinal':1,'line':n+1,'record_sha256':'2'*64,'record_bytes':100,'html_sha256':'3'*64,'renderer_sha256':'4'*64,'url':'https://example.invalid/'+str(n),'revision_url':'https://example.invalid/r'+str(n),'license_original_metadata':[{'identifier':'synthetic'}],'structural_holds':['original']};rd.execute('insert into rendered values (?,?,?,?,?)',(n,n+100,n+1000,d['family'],json.dumps(r,ensure_ascii=False)));start=0
  for i,b in enumerate([first,second]):rd.execute('insert into blocks values (?,?,?,?,?,?,?)',(n,i,'p',H(b.encode()),len(b),start,start+len(b)));start+=len(b)+2
  selected.append({**d,'source_shard':{'path':str(renderer),'SHA256':'synthetic'}})
 for d in [db,fd,rd]:d.commit();d.close()
 args=argparse.Namespace(start=str(time.monotonic()),supervisor_pid=os.getppid(),code_pins_sha256='a'*64,profile_sha256='b'*64)
 with patch.object(c,'SCREEN',screen),patch.object(c,'FINAL',final):
  native,body,meta=c.read_one(selected[0]);assert body=='é first0\n\nsecond0'.encode() and meta['finalizer_role']['holds']=='["global"]' and meta['finalizer_page']['holds']=='["prior"]';yes('actual_selectedrow_exact_UTF8_wholetext_and_currentholds')
  assert json.loads(native)['text'].encode()==body and len(meta['blocks'])==2;yes('native_JSON_lossless_and_block_unicode_offsets')
  wrong={**selected[0],'revision_id':-1};reject(lambda:c.read_one(wrong),c.SelectedHold);yes('different_revision_held_not_substituted')
  with patch.dict(c.LIMITS,{'per_document_UTF8_cap':1}):reject(lambda:c.read_one(selected[0]),c.SelectedHold)
  yes('oversize_wholetext_held_no_prefix')
  with patch.dict(c.LIMITS,{'per_source_JSON_cap':1}):reject(lambda:c.read_one(selected[0]),c.SelectedHold)
  yes('oversize_nativeJSON_held_before_payload_fetch')
  wrong={**selected[0],'source_ordinal':999};reject(lambda:c.read_one(wrong),c.SelectedHold);yes('unavailable_selection_explicit_hold')
  q=root/'wholeworker';q.mkdir()
  for name,n in c.SLOTS.items():(q/name).write_bytes(b' '*n)
  with patch.object(c,'OUT',q),patch.object(c,'verify',return_value=selected),patch.object(c,'guard',return_value=None):c.worker(args)
  result=json.loads((q/'result.json').read_text());assert result['selected_count']==20 and result['whole_captured']==20 and len(list(q.glob('*.txt')))==20;yes('actual_worker20_whole_originals_fixedoutcomes')
  assert all((q/(str(v['source_ordinal'])+'.txt')).read_bytes()==json.loads((q/(str(v['source_ordinal'])+'.native.json')).read_text())['text'].encode() for v in selected);yes('all20_whole_body_inverse_nativeJSON')
  for where in ['before','after']:
   q=root/('workerfail'+where);q.mkdir()
   for name,n in c.SLOTS.items():(q/name).write_bytes(b' '*n)
   calls=[ValueError('fixturepin')] if where=='before' else [selected,ValueError('fixturepinchanged')]
   with patch.object(c,'OUT',q),patch.object(c,'verify',side_effect=calls),patch.object(c,'guard',return_value=None):reject(lambda:c.worker(args),ValueError)
   assert json.loads((q/'result.json').read_text())['status']=='PARTIAL_NO_RETRY_NO_ADMISSION';yes('actual_worker_'+where+'_pin_failure_no_complete')
  q=root/'heldworker';q.mkdir()
  for name,n in c.SLOTS.items():(q/name).write_bytes(b' '*n)
  real=c.read_one
  def held(v):
   if v['source_ordinal']==3:raise c.SelectedHold('syntheticnegative')
   return real(v)
  with patch.object(c,'OUT',q),patch.object(c,'verify',return_value=selected),patch.object(c,'read_one',side_effect=held),patch.object(c,'guard',return_value=None):c.worker(args)
  result=json.loads((q/'result.json').read_text());assert result['selected_count']==20 and result['held_outcomes']==1 and not (q/'3.txt').exists();yes('selected_negative_kept_no_replacement_or_snippet')
 for phase in ['verify','disk']:
  for mode in ['alarm','TERM','INT']:
   q=root/(phase+mode);limits={**c.LIMITS,'external_seconds':.05}
   def block(*_):
    if mode!='alarm':os.kill(os.getpid(),getattr(signal,'SIG'+mode))
    time.sleep(.2)
   with patch.object(c,'OUT',q),patch.object(c,'LIMITS',limits),patch.object(c,'verify',side_effect=block if phase=='verify' else lambda *_:[]),patch.object(c,'disk',side_effect=block if phase=='disk' else lambda:None):reject(lambda:c.supervise(args),TimeoutError)
   assert not q.exists();yes('actual_supervisor_early_'+phase+'_'+mode)
 realPopen=subprocess.Popen
 for mode in ['watchdog','RSS']:
  q=root/('live'+mode);children=[]
  def spawn(cmd,**kw):
   assert str(HERE/'capture.py') in cmd and '-I' in cmd and '-B' in cmd
   ch=realPopen([sys.executable,'-I','-B','-c','import time;time.sleep(4)'],**kw);children.append(ch);return ch
  with patch.object(c,'OUT',q),patch.dict(c.LIMITS,{'external_seconds':.06 if mode=='watchdog' else 1}),patch.object(c,'verify',return_value=[]),patch.object(c,'disk',return_value=None),patch.object(c,'guard',return_value=None),patch.object(c.subprocess,'Popen',side_effect=spawn),patch.object(c,'tree_rss',return_value=2000000000 if mode=='RSS' else 1000):reject(lambda:c.supervise(args))
  assert children[0].poll() is not None and json.loads((q/'supervisor.json').read_text())['child_reaped'];yes('actual_livechild_'+mode+'_kill_reap')
 for snapshot in ['',f'{os.getpid()} 1 0\n','999999999 1 4\n']:
  reject(lambda:c.parse_rss_snapshot(snapshot,os.getpid()),ValueError)
 yes('required_RSS_snapshot_failclosed')
 q=root/'budget';q.mkdir()
 with patch.object(c,'OUT',q),patch.object(c.shutil,'disk_usage',return_value=type('Usage',(),{'free':10**12})()):reject(lambda:c.write_raw('too-big',b'x'*5000001,time.monotonic()),ValueError)
 assert not (q/'too-big').exists();yes('aggregate_output_prewrite_no_overshoot')
print(json.dumps({'status':'PASS_ACTUAL_SYNTHETIC_CAPTURE_AND_LIFECYCLE_NO_SELECTED_BODY_READ','count':len(checks),'checks':checks,'retained_body_reads':0},indent=2))

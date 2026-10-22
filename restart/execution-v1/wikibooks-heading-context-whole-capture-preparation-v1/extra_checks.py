"""Focused metadata-only pin, role hold and production RSS controls; synthetic only."""
import json,pathlib,tempfile,types,os,hashlib,sqlite3,copy
from unittest.mock import patch
import capture as c,pins
checks=[]
with tempfile.TemporaryDirectory() as td:
 root=pathlib.Path(td);db=root/'SYNTHETIC.sqlite';db.write_bytes(b'SYNTHETIC bytes never read in metadata-only guard');reg=root/'code-pins.json';digest='a'*64;reg.write_text(json.dumps({'files':{str(db):digest},'source_database_paths':[str(db)]}));regsha=c.sha(reg);realopen=pathlib.Path.open
 def noDBopen(path,*a,**kw):
  if path==db:raise AssertionError('metadata-only source_DB_body_open')
  return realopen(path,*a,**kw)
 with patch.object(pins,'HERE',root),patch.object(c,'expected_inventory',return_value={str(db)}),patch.object(c,'source_database_paths',return_value={str(db)}),patch.object(pathlib.Path,'open',noDBopen):pins.verify(regsha,metadata_only=True)
 checks.append('actual_metadata_only_pin_guard_never_opens_source_DB')
 reg.write_text(json.dumps({'files':{str(db):digest},'source_database_paths':[]}));regsha=c.sha(reg)
 with patch.object(pins,'HERE',root),patch.object(c,'expected_inventory',return_value={str(db)}),patch.object(c,'source_database_paths',return_value={str(db)}):
  try:pins.verify(regsha,metadata_only=True)
  except ValueError:pass
  else:raise AssertionError('unknown skipinventory allowed')
 checks.append('metadata_only_exact_source_skip_inventory_required')
 # read_one must preserve exact role/hold values, including exact_owner and active.
 screen=root/'screen';final=root/'final';renderer=root/'renderer';body=b'Complete synthetic definition.';sha=hashlib.sha256(body).hexdigest();d={'source_ordinal':1,'page_id':2,'revision_id':3,'family':'synthetic','title':'Synthetic','text_sha256':sha,'characters':len(body),'utf8_bytes':len(body),'content_tokens':5,'tokens_plus_one_EOS':6,'scored_lines':1,'skipped_chunks':0,'language_pass':1,'minimum_english_probability':.99,'known_discovery_hold':0,'holds':'[]'}
 f={'source_ordinal':1,'page_id':2,'revision_id':3,'family':'synthetic','title':'Synthetic','depth':0,'text_sha256':sha,'characters':len(body),'utf8_bytes':len(body),'holds':'[]','active':1};role={'source_ordinal':1,'holds':'[]','exact_owner':None}
 for p,table,row in [(screen,'docs',d),(final,'pages',f)]:
  con=sqlite3.connect(p);con.execute('create table '+table+'('+','.join(row)+')');con.execute('insert into '+table+' values('+','.join('?'*len(row))+')',list(row.values()));con.commit();con.close()
 con=sqlite3.connect(final);con.execute('create table final_pages(source_ordinal,holds,exact_owner)');con.execute('insert into final_pages values(?,?,?)',list(role.values()));con.commit();con.close()
 native={'canonical_source_ordinal':1,'page_id':2,'revision_id':3,'family_id':'synthetic','title':'Synthetic','text':body.decode(),'extracted_text_sha256':sha,'text_unicode_characters':len(body),'text_UTF8_bytes':len(body),'training_admitted':False}
 con=sqlite3.connect(renderer);con.execute('create table rendered(source_ordinal,page_id,revision_id,family,data)');con.execute('insert into rendered values(?,?,?,?,?)',(1,2,3,'synthetic',json.dumps(native)));con.execute('create table blocks(source_ordinal,ordinal,kind,hash,characters,start,end)');con.execute('insert into blocks values(?,?,?,?,?,?,?)',(1,0,'dd',sha,len(body),0,len(body)));con.commit();con.close()
 expected={**d,'source_shard':{'path':str(renderer)},'expected_finalizer_page':f,'expected_finalizer_role':role}
 with patch.object(c,'SCREEN',screen),patch.object(c,'FINAL',final):
  assert c.read_one(expected)[1]==body;checks.append('whole_dd_definition_retained_no_semantic_rejection')
  for field in ['holds','active']:
   changed=copy.deepcopy(expected);changed['expected_finalizer_page'][field]='["changed"]' if field=='holds' else 0
   try:c.read_one(changed)
   except c.SelectedHold:pass
   else:raise AssertionError('pagehold changed ignored')
   checks.append('exact_finalizer_page_'+field+'_required')
  for field in ['holds','exact_owner']:
   changed=copy.deepcopy(expected);changed['expected_finalizer_role'][field]='["changed"]' if field=='holds' else 999
   try:c.read_one(changed)
   except c.SelectedHold:pass
   else:raise AssertionError('role changed ignored')
   checks.append('exact_finalizer_role_'+field+'_required')
# Actual production supervisor must not emit COMPLETE for malformed RSS.
with tempfile.TemporaryDirectory() as td:
 root=pathlib.Path(td);out=root/'out';a=types.SimpleNamespace(code_pins_sha256='A',profile_sha256='B')
 class Child:
  pid=987654321;returncode=None
  def poll(self):return self.returncode
  def wait(self,timeout):return self.returncode
 child=Child()
 def launch(*x,**k):return child
 def kill(ch):ch.returncode=-9;ch.wait(timeout=3)
 with patch.object(c,'ROOT',root),patch.object(c,'OUT',out),patch.object(c,'verify',return_value=[]),patch.object(c,'disk',return_value=None),patch.object(c,'guard',return_value=None),patch.object(c.subprocess,'Popen',launch),patch.object(c.subprocess,'run',return_value=types.SimpleNamespace(stdout=f'{os.getpid()} 1 42\nmalformed\n')),patch.object(c,'kill',kill):
  try:c.supervise(a)
  except ValueError:pass
  else:raise AssertionError('false complete malformed RSS')
 assert child.returncode==-9 and json.loads((out/'supervisor.json').read_text())['status']=='PARTIAL_NO_RETRY';checks.append('actual_supervisor_malformed_RSS_partial_kill_reap')
print(json.dumps({'status':'PASS_FOCUSED_SYNTHETIC_ONLY','count':len(checks),'checks':checks,'retained_body_reads':0},indent=2))

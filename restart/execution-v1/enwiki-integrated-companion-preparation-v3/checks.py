import sys,os,time,json,tempfile,signal,hashlib,argparse
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run
results=[]
def check(name,fn):fn();results.append({'name':name,'PASS':True})
def reject(fn):
 try:fn()
 except BaseException:return
 raise AssertionError('expected refusal')
a=argparse.Namespace(start=str(time.monotonic()),supervisor_pid=os.getppid(),code_pins_sha256='a'*64,profile_sha256='b'*64)
def fixture(tmp):
 rows=[]
 for n in range(20):
  role='redirect' if n<9 else 'nonarticle' if n<15 else 'pending';text='Complete paragraph [[word|word]].\n\n== Section ==\nSecond complete paragraph. Citation<ref>{{cite web|title={{unknown}}}}</ref>.';p=tmp/f'source{n}';p.write_text(text);raw=p.read_bytes()
  r={'selected_index_row':{'row_ordinal':n},'native_page_id':str(n),'native_revision':{'id':str(n+100)},'native_title':f'Fixture{n}','status':'originalfixturehold','holds':['priorfixturehold'],'source_text':{'bytes':len(raw),'local_SHA256':hashlib.sha256(raw).hexdigest()}}
  rows.append({'record':r,'source':p,'role':role})
 return rows
# Production parser refuses successful but incomplete/corrupt ps snapshots.
for name,snapshot in [('empty',''),('missingroot','1 0 10'),('malformed','77 1 nope'),('duplicate','77 1 10\n77 1 20'),('negative','77 1 -10'),('selfparent','77 77 10'),('zeroPID','0 1 10'),('zerorootRSS','77 1 0'),('extra','77 1 10 extra')]:
 reject(lambda s=snapshot:run.parse_rss_snapshot(s,77));check('RSS_snapshot_refuse_'+name,lambda:None)
assert run.parse_rss_snapshot('77 1 10\n78 77 20\n79 78 3\n99 1 50',77)==33*1024
check('RSS_snapshot_exact_transitive_owned_tree',lambda:None)
with patch.object(run.subprocess,'run',return_value=argparse.Namespace(stdout='')):reject(run.tree_rss)
check('production_treeRSS_success_empty_refused',lambda:None)
with tempfile.TemporaryDirectory() as t:
 t=Path(t);rows=fixture(t);m,core=run.parser_preflight();integrated,reference,rules=run.integration_preflight(m,core);check('actual_isolated_runtime_allimports_and_synthetic_preflight',lambda:None)
 out=t/'worker';out.mkdir()
 for n,k in run.SLOTS.items():(out/n).write_bytes(b' '*k)
 with patch.object(run,'saved_regions',return_value=None),patch.object(run,'OUT',out),patch.object(run,'verify',return_value=(rows,m,core,integrated,reference,rules)),patch.object(run,'guard',return_value=None):run.worker(a)
 r=json.loads((out/'result.json').read_text());assert r['records_count']==20;check('actual_worker_synthetic20_complete',lambda:None)
 outputs=[json.loads((out/f'row-{n}.json').read_text()) for n in range(20)]
 assert all('frame' not in r for r in outputs[:15]);check('negative15_never_parsed_or_extracted',lambda:None)
 assert all('frame' in r and ''.join(s['raw'] for s in r['frame']['sections'])==rows[15]['source'].read_text() for r in outputs[15:]);check('five_pending_exact_allbyte_section_inverse',lambda:None)
 assert all(r['prior_holds']==['priorfixturehold'] and r['no_admission'] for r in outputs);check('all_prior_holds_retained',lambda:None)
 assert all(r['frame']['sections'][-1]['reference_semantic_companion_holds'] and r['frame']['sections'][-1]['semantic_companion_holds'] and r['frame']['sections'][-1]['provisional_prose_preview'] is not None for r in outputs[15:]);check('actual_worker_serializes_citation_component_holds_without_claiming_admission',lambda:None)
 # Real worker late pin failure produces partial terminal; no native source is used.
 for where in ['before','after']:
  q=t/f'worker-fail-{where}';q.mkdir()
  for n,k in run.SLOTS.items():(q/n).write_bytes(b' '*k)
  calls=[ValueError('fixturepin')] if where=='before' else [(rows,m,core,integrated,reference,rules),ValueError('fixturepinchanged')]
  with patch.object(run,'saved_regions',return_value=None),patch.object(run,'OUT',q),patch.object(run,'verify',side_effect=calls),patch.object(run,'guard',return_value=None):reject(lambda:run.worker(a))
  assert json.loads((q/'result.json').read_text())['status']=='PARTIAL_NO_RETRY_NO_ADMISSION';check('actual_worker_'+where+'_pin_failure_partial',lambda:None)
 # Block actual supervisor preflight until its early alarm/TERM/INT handler fires.
 for phase in ['verify','disk']:
  for stop in ['alarm','TERM','INT']:
   q=t/f'{phase}-{stop}';limits={**run.LIMITS,'external_seconds':.06}
   def block(*args):
    if stop!='alarm':os.kill(os.getpid(),getattr(signal,'SIG'+stop))
    time.sleep(.2)
   with patch.object(run,'OUT',q),patch.object(run,'LIMITS',limits),patch.object(run,'verify',side_effect=block if phase=='verify' else lambda x:([],m,core,integrated,reference,rules)),patch.object(run,'disk',side_effect=block if phase=='disk' else lambda:None):reject(lambda:run.supervise(a))
   assert not q.exists();check('actual_supervisor_early_'+phase+'_'+stop,lambda:None)
 q=t/'existing';q.mkdir();(q/'sentinel').write_text('unchanged')
 with patch.object(run,'OUT',q),patch.object(run,'verify',return_value=([],m,core,integrated,reference,rules)):reject(lambda:run.supervise(a))
 assert (q/'sentinel').read_text()=='unchanged' and not (q/'supervisor.json').exists();check('existing_output_never_overwritten',lambda:None)
 # Actual supervisor launches a tiny child, observes nonzero exit, reaps and saves partial.
 class Child:
  pid=999999;returncode=1
  def poll(self):return self.returncode
  def wait(self,timeout=None):return self.returncode
 def fake_launch(cmd,**kwargs):
  assert '-I' in cmd and '-B' in cmd and a.code_pins_sha256 in cmd and a.profile_sha256 in cmd
  run.terminal('result.json',{'status':'fixturefailure'});return Child()
 q=t/'childpartial'
 with patch.object(run,'OUT',q),patch.object(run,'verify',return_value=([],m,core,integrated,reference,rules)),patch.object(run,'disk',return_value=None),patch.object(run.subprocess,'Popen',side_effect=fake_launch),patch.object(run,'guard',return_value=None):assert run.supervise(a)==1
 assert json.loads((q/'supervisor.json').read_text())['status']=='PARTIAL_NO_RETRY';check('actual_supervisor_childfailure_reaped_pins_propagated',lambda:None)
 # Exact saved-original region identity uses the real production helper.
 saved=t/'saved';saved.mkdir();record=rows[15]['record'];row=record['selected_index_row']['row_ordinal']
 fixture_record={'preserved_role':'pending','source_text_SHA256':record['source_text']['local_SHA256'],'native_page_ID':record['native_page_id'],'native_revision_ID':record['native_revision']['id'],'frame':{'sections':[{'source_char_span':[0,10]}]}}
 savedfile=saved/f'row-{row}.json';savedfile.write_text(json.dumps(fixture_record))
 with patch.object(run,'SAVED',saved):assert run.saved_regions(record)==[[0,10]]
 check('actual_saved_region_binding_positive',lambda:None)
 fixture_record['native_revision_ID']='wrong';savedfile.write_text(json.dumps(fixture_record))
 with patch.object(run,'SAVED',saved):reject(lambda:run.saved_regions(record))
 check('actual_saved_region_wrong_revision_refused',lambda:None)
 # Actual sleeping subprocess cleanup under the production watchdog/RSS path.
 import subprocess
 real_Popen=subprocess.Popen
 for mode in ['watchdog','RSS']:
  q=t/('livechild-'+mode);children=[]
  def sleeping_launch(cmd,**kwargs):
   assert a.code_pins_sha256 in cmd and a.profile_sha256 in cmd
   c=real_Popen([sys.executable,'-I','-B','-c','import time;time.sleep(5)'],**kwargs);children.append(c);return c
  limits={**run.LIMITS,'external_seconds':.08 if mode=='watchdog' else 1}
  with patch.object(run,'OUT',q),patch.object(run,'LIMITS',limits),patch.object(run,'verify',return_value=([],m,core,integrated,reference,rules)),patch.object(run,'disk',return_value=None),patch.object(run.subprocess,'Popen',side_effect=sleeping_launch),patch.object(run,'guard',return_value=None),patch.object(run,'tree_rss',return_value=2000000000 if mode=='RSS' else 1000):reject(lambda:run.supervise(a))
  assert len(children)==1 and children[0].poll() is not None
  assert json.loads((q/'supervisor.json').read_text())['child_reaped']
  check('actual_live_child_'+mode+'_killed_and_reaped',lambda:None)
 # Registry refusal requires both external digest and exact inventory, using no real registry writes.
 import pins
 fake=json.dumps({'files':{}}).encode();digest=hashlib.sha256(fake).hexdigest()
 with patch.object(Path,'read_bytes',return_value=fake):
  reject(lambda:pins.verify('0'*64));reject(lambda:pins.verify(digest))
 check('external_digest_and_empty_registry_refused',lambda:None)
print(json.dumps({'status':'PASS_ACTUAL_SYNTHETIC_WORKER_LIFECYCLE_NO_NATIVE_PARSE','checks':len(results),'cases':results},indent=2))

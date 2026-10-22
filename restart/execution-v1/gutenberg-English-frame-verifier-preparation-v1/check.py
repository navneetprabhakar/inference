"""Pure helpers and terminal gates only. No full source/frame data scan."""
import copy,json,tempfile
from pathlib import Path
from unittest.mock import patch
import verify as v
cases=[]
def test(name,ok):assert ok,name;cases.append(name)
def refuses(fn):
 try:fn()
 except Exception:return True
 return False
raw=(v.c.ROOT/'gutenberg-discovery-pilot-v2/metadata.raw').read_bytes();native=v.c.parse_rdf.parse(raw,'pg1342.rdf');items=[]
for eid in range(1,5):
 n=copy.deepcopy(native);n['ebook_ID']=eid;n['titles']=['Synthetic '+str(eid)];n['native_relations_and_credits']=[];items.append(n)
items[1]['titles']=items[0]['titles'];items[2]['native_relations_and_credits']=[{'attributes':{},'text':'https://www.gutenberg.org/ebooks/2'}]
c=v.Components()
for row in items:c.add(row)
test('independent_transitive_family_closure',c.resolve()==0 and [c.root(i) for i in range(1,5)]==[1,1,1,4]);test('shared_creator_alone_no_merge',c.root(4)==4)
test('global_duplicate_ID_refused',refuses(lambda:c.add(items[0])))
n=copy.deepcopy(items[0]);n['ebook_ID']=5;n['titles']=['UniqueSynthetic5'];n['native_relations_and_credits']=[{'attributes':{},'text':'https://www.gutenberg.org/ebooks/'+x} for x in ['4suffix','4?x=1','4#part','4/','999']];c.add(n);test('strict_complete_URL_edges_and_missing_target_count',c.resolve()==1 and c.root(5)==5)
classified=v.f.classified(native,{});restored=dict(classified['original_native_remaining_fields']);restored.update({old:classified[new] for old,new in v.NATIVE_MAP.items()});test('independent_all_native_reconstruction',restored==native)
actual=v.overlays();test('exacttwo_actual_verified_overlays_only',set(actual)=={17579,18683})
with tempfile.TemporaryDirectory() as td:
 root=Path(td);out=root/'out';out.mkdir()
 with patch.object(v,'DEST',out):
  test('worker_deadline',refuses(lambda:v.Guard(v.c.clock()-571).check()))
  with patch.object(v,'OUTPUT',2000000):test('evidence_prewrite_cap',refuses(lambda:v.Guard(v.c.clock()).check(1000000)))
  source=root/'source';source.mkdir();(source/'worker-result.json').write_text('{}');(source/'supervisor-result.json').write_text('{}')
  with patch.object(v.f,'DEST',source):test('unbound_or_noncomplete_terminal_refused_before_scan',refuses(lambda:v.verify_data('0'*64,'0'*64,v.Guard(v.c.clock()))))
(v.HERE/'checks.json').write_text(json.dumps({'status':'PASS','cases':cases,'count':len(cases),'full_source_scans':0,'actual_verifier_runs':0,'network_requests':0},indent=2)+'\n');print(len(cases),'PASS')
good={'environment':v.c.environment(),'files_SHA256':{str(p.resolve()):v.c.file_sha(p) for p in v.dependencies()}}
with tempfile.TemporaryDirectory() as td:
 path=Path(td)/'manifest.json'
 def verify(m,expected=None):
  path.write_text(json.dumps(m))
  with patch.object(v,'MANIFEST',path):return v.pins(v.c.file_sha(path) if expected is None else expected)
 verify(good);test('exactverifier_and_actualframe/sourceprepinputpins',True)
 for label in ['empty','missing','extra','substitute','runtime']:
  bad=copy.deepcopy(good)
  if label=='empty':bad['files_SHA256']={}
  elif label=='missing':bad['files_SHA256'].pop(next(iter(bad['files_SHA256'])))
  elif label=='extra':bad['files_SHA256']['/tmp/extra']='0'*64
  elif label=='substitute':bad['files_SHA256'][next(iter(bad['files_SHA256']))]='0'*64
  else:bad['environment']={}
  test('manifest_'+label+'_rejected',refuses(lambda:verify(bad)))
 test('parentmanifestdigest_rejected',refuses(lambda:verify(good,'0'*64)))
(v.HERE/'checks.json').write_text(json.dumps({'status':'PASS','cases':cases,'count':len(cases),'full_source_scans':0,'actual_verifier_runs':0,'network_requests':0},indent=2)+'\n');print(len(cases),'total PASS')

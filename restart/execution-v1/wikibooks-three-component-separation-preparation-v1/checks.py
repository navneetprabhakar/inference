"""Synthetic component and real synthetic-child lifecycle controls; no retained derivation."""
import copy,importlib.util,json,pathlib,subprocess,sys,tempfile
spec=importlib.util.spec_from_file_location('separate',pathlib.Path(__file__).with_name('separate.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
cases=[]
def yes(name,fn):fn();cases.append(name)
def rejects(fn):
 try:fn()
 except (ValueError,UnicodeDecodeError,TimeoutError):return
 raise AssertionError('expected refusal')
for label,raw,a,b in [('prefix',b'HEADER\n\nmain prose',8,18),('suffix',b'main\n\nINDEX',0,4),('both',b'H\nmain\nT',2,6),('unicode','h\né—x\nnav'.encode(),2,9),('paragraphs',b'head\n\npara1\n\npara2\n',6,19)]:
 def check(raw=raw,a=a,b=b):
  main,spans=m.partition(raw,a,b);assert main==raw[a:b];assert m.inverse(main,spans)==raw
 yes(label,check)
for a,b in [(-1,2),(0,0),(0,100),(True,2)]:yes('range_refusal_'+str((a,b)),lambda a=a,b=b:rejects(lambda:m.partition(b'abc',a,b)))
yes('UTF8_boundary_refusal',lambda:rejects(lambda:m.partition('éx'.encode(),1,3)))
raw=b'HEAD\nmain\nNAV';main,spans=m.partition(raw,5,9)
yes('main_tamper_refusal',lambda:rejects(lambda:m.inverse(b'MAIN',spans)))
bad=copy.deepcopy(spans);bad[0]['text']='other';yes('sidecar_tamper_refusal',lambda:rejects(lambda:m.inverse(main,bad)))
bad=copy.deepcopy(spans);bad[1]['source_UTF8_range'][0]+=1;yes('gap_refusal',lambda:rejects(lambda:m.inverse(main,bad)))
bad=copy.deepcopy(spans);bad[1]['role']='unknown';yes('unknown_role_refusal',lambda:rejects(lambda:m.inverse(main,bad)))
with tempfile.TemporaryDirectory(prefix='wb-components-synthetic-') as t:
 out=pathlib.Path(t)/'success'
 code="import pathlib,json,sys; p=pathlib.Path(sys.argv[1])/'result.json'; b=json.dumps({'status':'COMPLETE_SYNTHETIC'}).encode();p.write_bytes(b+b' '*(32768-len(b)))"
 m.supervise(out,lambda start:[sys.executable,'-I','-B','-c',code,str(out)])
 assert json.loads((out/'supervisor.json').read_text())['child_reaped'];cases.append('actual_synthetic_child_complete_and_reaped')
 out=pathlib.Path(t)/'failure'
 rejects(lambda:m.supervise(out,lambda start:[sys.executable,'-I','-B','-c','raise SystemExit(7)']))
 assert json.loads((out/'supervisor.json').read_text())['status']=='PARTIAL_NO_RETRY';cases.append('actual_synthetic_child_failure_receipt_and_reaped')
 out=pathlib.Path(t)/'preflight'
 def fail():raise ValueError('synthetic_preflight')
 rejects(lambda:m.supervise(out,lambda start:[],fail));assert not out.exists();cases.append('preflight_failure_before_output')
result={'status':'PASS','controls':cases,'count':len(cases),'retained_source_derivatives_executed':False,'synthetic_lifecycle_only':True}
print(json.dumps(result,indent=2))

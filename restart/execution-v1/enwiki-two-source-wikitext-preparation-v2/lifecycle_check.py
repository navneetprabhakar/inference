"""Execute actual worker on tiny synthetic inputs only; no corpus derivative."""
import argparse,hashlib,importlib.util,json,os,pathlib,sys,tempfile,time,types
HERE=pathlib.Path(__file__).resolve().parent
sha=lambda b:hashlib.sha256(b).hexdigest()
def run(case):
 path=HERE/'render.py' if case!='old-regression' else HERE.parent/'enwiki-two-source-wikitext-preparation-v1/render.py'
 spec=importlib.util.spec_from_file_location('synthetic_worker_'+case.replace('-','_'),path);r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
 with tempfile.TemporaryDirectory() as tmp:
  root=pathlib.Path(tmp);prep=root/'prep';prep.mkdir();out=root/'out';out.mkdir();source=root/'synthetic.utf8';native=b'PREFIX\n[[Target|label]] remains awkward.\nEND';source.write_bytes(native);policy=root/'policy';policy.write_bytes(b'FROZEN_SYNTHETIC_POLICY')
  ops=[]
  for original,replacement,kind in [(b'PREFIX\n',b'','omit_prefix'),(b'[[Target|label]]',b'label','displayed_label'),(b'END',b'','omit_suffix')]:
   a=native.index(original);ops.append({'start_byte':a,'end_exclusive_byte':a+len(original),'original_hex':original.hex(),'original_SHA256':sha(original),'replacement_hex':replacement.hex(),'operation':kind})
  recipe={'title':'SYNTHETIC_NOT_RETAINED_SOURCE','index_row_ordinal':1,'source_text_path':str(source),'source_text_SHA256':sha(native),'source_text_bytes':len(native),'source_native_XML_SHA256':'SYNTHETIC','operations':ops,'derivative_content_bytes_arithmetic_only':len(native)+sum(len(bytes.fromhex(o['replacement_hex']))-(o['end_exclusive_byte']-o['start_byte']) for o in ops),'complete_native_units':[{'ordinal':1,'source_start_byte':7,'source_end_exclusive_byte':len(native)-3,'status':'REVERSIBLE_DEVELOPMENT_PREVIEW_NOT_ACCEPTED','dependency_holds':[]}],'reference_occurrences':[],'native_citation_definitions':{}}
  package={'recipes':[recipe]};(prep/'literal-recipes.json').write_text(json.dumps(package));(prep/'all20-original-decisions.json').write_text(json.dumps([{'synthetic_row':i,'held':True} for i in range(20)]))
  r.HERE=prep;r.OUT=out;r.ROOT=root;r.FREE=0
  for name,size in r.SLOTS.items():(out/name).write_bytes(b' '*size)
  frozen={str(p):sha(p.read_bytes()) for p in [source,policy,prep/'literal-recipes.json',prep/'all20-original-decisions.json']};calls=[]
  def fixture_pins(code,profile):
   assert code=='EXPLICIT_SYNTHETIC_CODEPIN' and profile=='EXPLICIT_SYNTHETIC_PROFILEPIN'
   calls.append((code,profile))
   if any(sha(pathlib.Path(p).read_bytes())!=h for p,h in frozen.items()):raise ValueError('synthetic_final_input_pin_tamper')
   return package
  r.verify=fixture_pins;realwrite=r.write
  def write(name,data):
   realwrite(name,data)
   if case=='final-pin-tamper' and name.endswith('.omissions-and-dependencies.json'):policy.write_bytes(b'CHANGED')
  r.write=write;args=types.SimpleNamespace(code_pins_sha256='EXPLICIT_SYNTHETIC_CODEPIN',profile_sha256='EXPLICIT_SYNTHETIC_PROFILEPIN',start=str(r.clk()),supervisor_pid=os.getppid());error=None
  try:r.worker(args)
  except BaseException as e:error=type(e).__name__+':'+str(e)
  result=json.loads((out/'result.json').read_text())
  if case=='new-pass':
   assert error is None and len(calls)==2 and result['status']=='COMPLETE_TWO_SOURCE_REVERSIBLE_DEVELOPMENT_PREVIEWS_ONLY' and (out/'manifest.json').is_file()
   assert sha((out/'manifest.json').read_bytes())==result['manifest_SHA256']
   assert (out/'row-1.development-preview.utf8').read_bytes()==b'label remains awkward.\n'
  elif case=='old-regression':assert error.startswith('AttributeError:') and len(calls)==1 and result['status']=='TERMINAL_PARTIAL_TWO_SOURCE_DEVELOPMENT_NO_RETRY' and not (out/'manifest.json').exists()
  elif case=='final-pin-tamper':assert error=='ValueError:synthetic_final_input_pin_tamper' and len(calls)==2 and result['status']=='TERMINAL_PARTIAL_TWO_SOURCE_DEVELOPMENT_NO_RETRY' and not (out/'manifest.json').exists()
  else:raise ValueError('unknown_fixture')
  return {'case':case,'PASS':True,'actual_worker_function_executed':True,'pin_check_calls':len(calls),'terminal_status':result['status'],'observed_expected_error':error,'retained_sources_read_or_rendered':0,'temporary_output_bytes':sum(p.stat().st_size for p in out.iterdir())}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--case',required=True,choices=['new-pass','old-regression','final-pin-tamper']);a=p.parse_args();print(json.dumps(run(a.case)))

import hashlib,importlib.util,json,os,pathlib,shutil,signal,subprocess,sys,time
import render as r
P=pathlib.Path(__file__).resolve().parent;E=P.parent;D=E/'m2-intake/openstax-structured-development-v2';CAP=100000000;FLOOR=20*1024**3+32000000000
h=lambda p:hashlib.file_digest(p.open('rb'),'sha256').hexdigest()
def pins():
 m=json.loads((P/'frozen-profile.json').read_text())
 for name,v in m['input_SHA256'].items():assert h(pathlib.Path(name))==v,name
 return m

def worker():
 assert os.getppid()==int(os.environ['CNXML_PARENT']);start=float(os.environ['CNXML_START']);m=pins();sample=json.loads((P/'development-sample.json').read_text());rows=[]
 def write(name,b):
  if time.monotonic()-start>=290:raise TimeoutError('290second worker bound')
  b=b if isinstance(b,bytes) else (json.dumps(b,indent=2,ensure_ascii=False)+'\n').encode()
  if sum(p.stat().st_size for p in D.rglob('*') if p.is_file())+len(b)>CAP-100000:raise ValueError('100MB output prewrite cap')
  if shutil.disk_usage(D).free<FLOOR+len(b):raise ValueError('weights scratch freefloor')
  with (D/name).open('xb') as f:f.write(b)
 for x in sample['selected_modules']:
  raw=(r.SOURCE/(x['module_ID']+'.cnxml')).read_bytes();result,text,view,ast=r.render(raw,x);result['source_file']=str(r.SOURCE/(x['module_ID']+'.cnxml'));mid=x['module_ID'];write(mid+'.json',result);write(mid+'.txt',text.encode());write(mid+'.html',view.encode());write(mid+'.AST.json',ast)
  for b in result['blocks']:assert r.sha(raw[b['source_start_byte']:b['source_end_byte']])==b['source_exact_subtree_sha256']
  rows.append({'module_ID':mid,'title':result['blocks'][0]['text'],'source_sha256':r.sha(raw),'blocks':len(result['blocks']),'dependencies':len(result['dependencies']),'holds':result['holds'],'preview_bytes':len(text.encode()),'unmapped_node_names':result['unmapped_node_names']})
 assert len(rows)==20;pins();assert not any(x['unmapped_node_names'] for x in rows)
 write('receipt.json',{'status':'TWENTY_FROZEN_UNIFORM_DEVELOPMENT_MODULES_STRUCTURED_PREVIEWS_NOT_ACCEPTANCE','source_modules_verified':162,'development_modules':20,'selected_module_results':rows,'selection_SHA256':h(P/'development-sample.json'),'frozen_profile_SHA256':h(P/'frozen-profile.json'),'renderer_SHA256':h(P/'render.py'),'elapsed_seconds':time.monotonic()-start,'source_immutable':True,'tokens':'PENDING; previews include explicit editorial dependency markers and are not training prose','remaining':['Parent full-module semantic review','Fresh acceptance cohort after profile review; these20 remain DEVELOPMENT','Question/media/reference resolution or documented exclusion policy preserving dependent paragraphs','Rights/figure credit, language, dedup and leakage gates'],'new_admitted_documents':0,'new_admitted_tokens':0})

def main():
 if '--worker' in sys.argv:return worker()
 pins();D.mkdir(exist_ok=False);assert shutil.disk_usage(D).free>FLOOR+CAP;start=time.monotonic();p=subprocess.Popen([sys.executable,str(pathlib.Path(__file__).resolve()),'--worker'],env=dict(os.environ,CNXML_PARENT=str(os.getpid()),CNXML_START=str(start)),start_new_session=True);peak=0;reason=None
 # Reuse the reviewed process-tree RSS observer.
 sys.path.insert(0,str(E/'wikibooks-identity-frame-preparation-v1'));from supervisor import tree_rss_from_ps
 while p.poll() is None:
  ps=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,check=True,timeout=1);rss,_=tree_rss_from_ps(ps.stdout,os.getpid());peak=max(peak,rss)
  if time.monotonic()-start>=300:reason='external300secondcap'
  if rss>1000000000:reason='observed_owned_tree1GB_RSS_cap'
  if reason:os.killpg(p.pid,signal.SIGKILL);break
  time.sleep(.1)
 code=p.wait(timeout=3);sup={'worker_exit_code':code,'reason':reason,'peak_observed_owned_tree_RSS_bytes':peak,'elapsed_seconds':time.monotonic()-start,'limits':{'seconds':300,'output_bytes':CAP,'observed_owned_tree_RSS_bytes':1000000000},'RSS_scope':'0.1second observations; transient unobserved peaks not proven absent','network_requests':0,'model_operations':0,'retry':False};(D/'supervisor.json').write_text(json.dumps(sup,indent=2)+'\n');raise SystemExit(0 if code==0 and reason is None else 1)
if __name__=='__main__':main()

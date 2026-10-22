"""One bounded offline exact-span derivative; no admission."""
import hashlib,json,os,pathlib,shutil,signal,subprocess,sys,time
HERE=pathlib.Path(__file__).resolve().parent;E=HERE.parent;REPO=E.parents[1];DEST=E/'gutenberg-novel-prose-v1';RAW=E/'m2-intake/gutenberg-discovery-pilot-v3/text.raw';CAP=5000000
PINS={'parent-review.json':'d05fdff24918ec18c46b78d75165222d5428970a7e566f65ad6501a02e147226','chapter-span-proposal.json':'34c86d1c4f7bc33ac1402f88e541a75783d7f6ad26a80c57796b1f400b8a84cc','annotation-span-proposal.json':'2d84673e7ab98047650f0379962e0a7a01af9cfa22cacb2bf3887c245a4d1893','policy.json':'30ce85d9e89aea772efbe5b0ca6b50ca1230a5437673586ae19ab892ee8fd16d'}
RAW_SHA='3f6bb9d6f78e0293b56acd4714dd68cb7d6d1d293402031ce9d5a216bcaf9d75';TOK_SHA='577c0f59ffc594931650de802c4630f3171ebde139cc32c742f5f264e7f98812';FAMILY='austen:pride-and-prejudice:original-work-all-editions'
sha=lambda b:hashlib.sha256(b).hexdigest()
def write(name,b):
 b=b if isinstance(b,bytes) else (json.dumps(b,indent=2,ensure_ascii=False)+'\n').encode()
 if sum(p.stat().st_size for p in DEST.rglob('*') if p.is_file())+len(b)>CAP-100000:raise ValueError('5MB output prewrite bound')
 p=DEST/name;p.parent.mkdir(exist_ok=True,parents=True)
 with p.open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
def check_inputs():
 for n,h in PINS.items():assert sha((HERE/n).read_bytes())==h
 assert sha(RAW.read_bytes())==RAW_SHA
 tok=E/'tokenizer-8192';assert sha((tok/'manifest.json').read_bytes())==TOK_SHA
 manifest=json.loads((tok/'manifest.json').read_text());assert sha((tok/'core.json').read_bytes())==manifest['files']['core.json']
 return tok

def worker():
 assert os.getppid()==int(os.environ['PG_PROSE_PARENT']);start=float(os.environ['PG_PROSE_START']);tok=check_inputs();raw=RAW.read_bytes();plans=json.loads((HERE/'chapter-span-proposal.json').read_text());sys.path.insert(0,str(REPO/'src'));from slm.common.tokenizer import BPE
 tokenizer=BPE.load(tok);chapters=[];removed=[]
 dp=json.loads((E/'disk-budget.json').read_text());assert shutil.disk_usage(E).free>dp['free_disk_floor_bytes']+dp['weights_checkpoints_reserved_bytes']+dp['scratch_cap_bytes']+CAP
 for plan in plans:
  if time.monotonic()-start>=110:raise TimeoutError('110 second worker deadline')
  pieces=[];mapping=[];offset=0;cursor=plan['source_span']['source_start_byte']
  for index,seg in enumerate(plan['ordered_segments']):
   s,z=seg['source_start_byte'],seg['source_end_byte'];assert s==cursor;cursor=z;b=raw[s:z];assert len(b)==seg['bytes'] and sha(b)==seg['sha256']
   if seg['action']=='keep':pieces.append(b);mapping.append({'action':'keep','source_start_byte':s,'source_end_byte':z,'derivative_start_byte':offset,'derivative_end_byte':offset+len(b),'sha256':sha(b)});offset+=len(b)
   else:
    rid=f"chapter_{plan['chapter_number']:02d}_removed_{index:03d}";removed.append({'id':rid,'chapter_number':plan['chapter_number'],'source_start_byte':s,'source_end_byte':z,'sha256':sha(b),'exact_text':b.decode()});mapping.append({'action':'remove','removed_span_id':rid})
  assert cursor==plan['source_span']['source_end_byte'];b=b''.join(pieces);assert len(b)==plan['prospective_retained_bytes'] and sha(b)==plan['prospective_retained_sha256'];text=b.decode();assert '[Illustration' not in text
  name=f"chapters/chapter_{plan['chapter_number']:02d}.txt";write(name,b)
  chapters.append({'chapter_number':plan['chapter_number'],'file':name,'bytes':len(b),'sha256':sha(b),'text':text,'words_whitespace':len(text.split()),'content_tokens_existing_M1_BPE':len(tokenizer._core.encode(text).ids),'tokenizer_manifest_sha256':TOK_SHA,'source_raw_sha256':RAW_SHA,'source_chapter_sha256':plan['source_chapter_sha256'],'source_start_byte':plan['source_span']['source_start_byte'],'source_end_byte':plan['source_span']['source_end_byte'],'family_id':FAMILY,'ordered_segments':mapping,'split':None,'training_admitted':False,'holds':['pending_whole_novel_semantic_review','pending_rights_release_packaging','pending_overlap_checks','preserved_blanklines_can_split_sentences_at_removed_illustrations','existing_M1_tokenizer_provisional_not_final_M3']})
 write('chapters.jsonl',''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in chapters).encode());write('removed-spans.json',removed);write('input-provenance.json',{'raw_file':str(RAW),'raw_sha256':RAW_SHA,'parent_review_pins':PINS,'tokenizer_manifest_sha256':TOK_SHA,'tokenizer_core_sha256':sha((tok/'core.json').read_bytes()),'original_proposal_manifest_sha256':sha((HERE/'manifest.json').read_bytes()),'execution_code_sha256':sha(pathlib.Path(__file__).read_bytes()),'independent_verifier_sha256':sha((HERE/'verify_derivative.py').read_bytes()),'policy':'Exact byte omissions only; no newline, text or spelling normalization; complete raw and removed notices retained.'})
 code=subprocess.run([sys.executable,str(HERE/'verify_derivative.py')],timeout=max(.01,110-(time.monotonic()-start))).returncode;assert code==0
 write('receipt.json',{'status':'PROVISIONAL_NOVEL_PROSE_DERIVATIVE_NOT_ADMITTED','chapters':len(chapters),'work_families':1,'bytes':sum(x['bytes'] for x in chapters),'whitespace_words':sum(x['words_whitespace'] for x in chapters),'content_tokens_existing_M1_BPE':sum(x['content_tokens_existing_M1_BPE'] for x in chapters),'removed_spans':len(removed),'removed_bytes':sum(len(x['exact_text'].encode()) for x in removed),'tokenizer_manifest_sha256':TOK_SHA,'source_unchanged':sha(RAW.read_bytes())==RAW_SHA,'all_input_pins_unchanged':all(sha((HERE/n).read_bytes())==h for n,h in PINS.items()),'elapsed_seconds':time.monotonic()-start,'limits':{'seconds':120,'output_bytes':CAP},'known_limitation':'Preserved whitespace may leave paragraph breaks within sentences where illustrations interrupted prose. No normalization authorized.','new_admitted_documents':0,'new_admitted_tokens':0,'models_initialized':0,'training_updates':0})

def main():
 if '--worker' in sys.argv:return worker()
 check_inputs();DEST.mkdir(exist_ok=False);start=time.monotonic();env=dict(os.environ,PG_PROSE_PARENT=str(os.getpid()),PG_PROSE_START=str(start));p=subprocess.Popen([sys.executable,str(pathlib.Path(__file__).resolve()),'--worker'],env=env,start_new_session=True);expired=False
 try:code=p.wait(timeout=120)
 except subprocess.TimeoutExpired:expired=True;os.killpg(p.pid,signal.SIGKILL);code=p.wait(timeout=3)
 write('supervisor.json',{'worker_exit_code':code,'external_timeout':expired,'elapsed_seconds':time.monotonic()-start,'retry':False,'network_requests':0});raise SystemExit(0 if code==0 and not expired else 1)
if __name__=='__main__':main()

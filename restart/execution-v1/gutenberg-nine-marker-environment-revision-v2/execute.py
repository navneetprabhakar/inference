"""Exactly18 parent-approved literal marker removals; no regex rewrite or training."""
import argparse,hashlib,importlib.util,json,os,re,shutil,signal,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;EXEC=HERE.parent;SOURCE=EXEC/'m2-intake/gutenberg-novel-prose-seven-joins-v2';DEST=EXEC/'m2-intake/gutenberg-novel-prose-nine-markers-v4';PACKET=EXEC/'gutenberg-NIND-all61-inventory-v1/parent-all9-manual-review-packet.json';PROFILE=HERE/'limits.json';MANIFEST=HERE/'code-pins.json'
import utilities as c
RULES=EXEC/'wikibooks-language-token-preparation-v1/rules.py';FAST=Path('/Users/navneetprabhakar/Documents/git/image/inference-history-20261021/data/language-detector-v4/fasttext');DETECTOR=FAST.parent/'lid.176.ftz';CORE=EXEC/'tokenizer-8192/core.json';TMAN=CORE.parent/'manifest.json';CAP=8000000;WORKER=55;EXTERNAL=60;RSS=1000000000;CHANGED={7,13,47,48,49,52,60,61}
def verify(expected):
 if not isinstance(expected,str) or not re.fullmatch('[0-9a-f]{64}',expected) or MANIFEST.is_symlink() or c.file_sha(MANIFEST)!=expected:raise ValueError('Exact executor manifestSHA required')
 m=json.loads(MANIFEST.read_text());p=json.loads(PROFILE.read_text());required={str(x.resolve()) for x in [HERE/'execute.py',PROFILE,HERE/'check.py',HERE/'utilities.py']}
 required.update(p['input_pins'])
 if set(m.get('files_SHA256',{}))!=required or m['environment']!=c.environment():raise ValueError('Exact executor dependency inventory/runtime')
 for name,h in m['files_SHA256'].items():
  path=Path(name)
  if path.is_symlink() or not path.is_file() or c.file_sha(path)!=h:raise ValueError('Immutable input changed:'+name)
 if c.file_sha(PACKET)!='3067a68c4bdf21c965adfaff3f9b3a515f90128c467149331a8b30fb0f4ec880' or c.file_sha(EXEC/'gutenberg-NIND-all61-inventory-v1/manifest.json')!='7fe34fc8f684f4d8ad948d843a11793931156ec719704027cd9fdeb125388198':raise ValueError('Exact approved nine packet/inventory required')
 return p
class Guard:
 def __init__(self,start):
  self.start=start;p=json.loads((EXEC/'disk-budget.json').read_text());self.reserve=sum(p[k] for k in ['weights_checkpoints_reserved_bytes','scratch_cap_bytes','free_disk_floor_bytes'])
  if c.size(c.ROOT)+CAP>p['processed_data_cap_bytes']:raise ValueError('Combined processed data cap')
 def check(self,additional=0):
  if not 0<=c.clock()-self.start<WORKER:raise TimeoutError('55secondworker')
  if c.size(DEST)+additional>CAP-1048576:raise ValueError('8MB prewrite output cap')
  if shutil.disk_usage(DEST).free<self.reserve+additional+32000000:raise ValueError('Protected disk reserves')
def write(name,data,guard):
 b=data if isinstance(data,bytes) else (json.dumps(data,indent=2,ensure_ascii=False)+'\n').encode();guard.check(len(b));path=DEST/name;path.parent.mkdir(exist_ok=True)
 with path.open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
 return {'file':name,'bytes':len(b),'SHA256':c.sha(b)}
def transform(data,operations):
 ordered=sorted(operations,key=lambda p:p['start_byte']);prior=0;removed=0;ancestry=[];pieces=[]
 for op in ordered:
  a,b=op['start_byte'],op['end_byte'];old=op['exact_text'].encode();
  if not 0<=prior<=a<b<=len(data) or data[a:b]!=old or c.sha(old)!=op['SHA256']:raise ValueError('Exact nonoverlap approved marker mismatch')
  pieces.append(data[prior:a]);ancestry.append({**op,'new_insertion_byte_for_inverse':a-removed,'exact_removed_marker':old.decode()});prior=b;removed+=b-a
 pieces.append(data[prior:]);new=b''.join(pieces);inverse=new
 for op in reversed(ancestry):
  a=op['new_insertion_byte_for_inverse'];inverse=inverse[:a]+op['exact_removed_marker'].encode()+inverse[a:]
 if inverse!=data or len(data)-len(new)!=removed:raise ValueError('Exact inverse marker composition')
 return new,ancestry

def worker(expected):
 profile=verify(expected)
 if os.getppid()!=int(os.environ['MARKER_PARENT_PID']):raise ValueError('Direct supervisor required')
 guard=Guard(float(os.environ['MARKER_START']))
 try:
  spec=importlib.util.spec_from_file_location('frozen_strict_language',RULES);rules=importlib.util.module_from_spec(spec);spec.loader.exec_module(rules);tokenizer=rules.load_tokenizer({'tokenizer_manifest':{'path':str(TMAN)},'tokenizer_core':{'path':str(CORE)}})
  packet=json.loads(PACKET.read_text());source_rows=[json.loads(line) for line in (SOURCE/'chapters.jsonl').read_text().splitlines()];recipe=json.loads((SOURCE/'formatting-recipe.json').read_text());oldspans={x['chapter_number']:x for x in json.loads((EXEC/'gutenberg-paratext-preparation-v1/chapter-span-proposal.json').read_text())};removed=json.loads((EXEC/'gutenberg-novel-prose-v1/removed-spans.json').read_text());rawpath=EXEC/'m2-intake/gutenberg-discovery-pilot-v3/text.raw';rawsource=rawpath.read_bytes();assert len(packet)==9 and len(removed)==156 and len(recipe['patches'])==7
  for omission in removed:assert c.sha(rawsource[omission['source_start_byte']:omission['source_end_byte']])==omission['sha256']
  ops={};wrappers={}
  for item in packet:
   ch=item['chapter'];wrappers.setdefault(ch,[]).append(item);ops.setdefault(ch,[]).extend(item['precise_presentation_marker_spans_not_authorized_edits'])
  assert set(ops)==CHANGED and sum(map(len,ops.values()))==18 and sum(p['end_byte']-p['start_byte'] for v in ops.values() for p in v)==87
  assert [r['chapter_number'] for r in source_rows]==list(range(1,62));results=[];ancestries=[];docs=[];inputs=[];mapping=[];oldtotal=newtotal=tokens=0
  for source in source_rows:
   guard.check();ch=source['chapter_number'];data=(SOURCE/source['file']).read_bytes();assert c.sha(data)==source['sha256'] and len(data)==source['bytes'];new,changes=transform(data,ops.get(ch,[]));assert (new!=data)==(ch in CHANGED)
   for item in wrappers.get(ch,[]):
    a,b=item['internal_start_byte'],item['internal_end_byte'];internal=data[a:b];assert internal.decode()==item['internal_exact_text'] and c.sha(internal)==item['internal_SHA256'];before=sum(o['end_byte']-o['start_byte'] for o in ops[ch] if o['end_byte']<=a);assert new[a-before:b-before]==internal
   oldv1=data
   for patch in [p for p in recipe['patches'] if p['chapter_number']==ch]:
    a=patch['derivative_start_byte'];assert oldv1[a:a+1]==patch['replacement_ascii'].encode();oldv1=oldv1[:a]+patch['exact_old_whitespace'].encode()+oldv1[a+1:]
   sourcev1=EXEC/'gutenberg-novel-prose-v1'/source['file'];assert sourcev1.read_bytes()==oldv1 and c.sha(oldv1)==source['source_derivative_sha256'];keep=b''.join(rawsource[s['source_start_byte']:s['source_end_byte']] for s in oldspans[ch]['ordered_segments'] if s['action']=='keep');assert keep==oldv1
   text=new.decode('utf8');n_tokens=len(tokenizer.encode(text,add_special_tokens=False).ids);write(source['file'],new,guard);oldtotal+=len(data);newtotal+=len(new);tokens+=n_tokens
   row={**source,'bytes':len(new),'sha256':c.sha(new),'content_tokens_existing_M1_BPE':n_tokens,'source_derivative_file':str(SOURCE/source['file']),'source_derivative_sha256':source['sha256'],'formatting_marker_removals':len(changes),'formatting_patch_ID':None,'prior_seven_join_patch_ID':source['formatting_patch_ID'],'training_admitted':False,'split':None,'holds':list(source['holds'])};results.append(row);ancestries.append({'chapter_number':ch,'source_v2_SHA256':source['sha256'],'new_v3_SHA256':c.sha(new),'old_v1_SHA256':c.sha(oldv1),'exact_inverse_marker_to_v2':True,'exact_inverse_seven_joins_to_v1':True,'v1_equals_pinned_raw_keep_spans':True,'removed_marker_spans':changes,'wrapper_internal_texts_preserved':[{'exact_text':x['internal_exact_text'],'SHA256':x['internal_SHA256'],'native_ancestry':x['native_ancestry']} for x in wrappers.get(ch,[])]})
   if ch in CHANGED:
    windows=[]
    for i,(window,chunk) in enumerate(rules.windows(text)):
     projection=rules.projection(chunk);w={**window,'window_ordinal':i,'raw_UTF8_SHA256':c.sha(chunk.encode()),'projected_UTF8_SHA256':c.sha(projection.encode())}
     if window['scored']:w['prediction_line_ordinal']=len(inputs);inputs.append(projection);mapping.append(w)
     windows.append(w)
    docs.append({'chapter_number':ch,'new_v3_SHA256':c.sha(new),'windows':windows})
  assert oldtotal==710500 and newtotal==710413 and len(results)==61 and sum(r['formatting_marker_removals'] for r in results)==18
  stream=('\n'.join(inputs)+'\n').encode();write('detector-input.txt',stream,guard);remaining=WORKER-(c.clock()-guard.start);guard.check();native=subprocess.run([str(FAST),'predict-prob',str(DETECTOR),'-','1'],input=stream,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=max(.01,remaining));write('predictions.raw',native.stdout,guard);write('detector-stderr.raw',native.stderr,guard);assert native.returncode==0 and len(native.stdout)<=1000000 and len(native.stderr)<=100000
  lines=native.stdout.decode('utf8').splitlines();assert len(lines)==len(mapping)
  for window,line in zip(mapping,lines):
   label,rawp,top,english,passed=rules.prediction(line);window.update(label=label,raw_probability=rawp,top_probability=top,english_probability=english,policy_pass=passed,exact_prediction_line=line)
  for doc in docs:doc['scored_windows']=sum(w['scored'] for w in doc['windows']);doc['skipped_windows']=sum(not w['scored'] for w in doc['windows']);doc['language_pass']=all(w['policy_pass'] for w in doc['windows'] if w['scored'])
  assert len(docs)==8 and set(d['chapter_number'] for d in docs)==CHANGED
  c45=next(r for r in results if r['chapter_number']==45);assert c45['sha256']==next(r for r in source_rows if r['chapter_number']==45)['sha256']=='81e45c5330259139db97f29317521888f6eedc830e3c361ee13338a040cd26c7'
  write('chapters.jsonl',b''.join((json.dumps(r,ensure_ascii=False)+'\n').encode() for r in results),guard);write('chapter-ancestry.json',ancestries,guard);write('exact-approved-marker-recipe.json',{'approved_packet_SHA256':c.file_sha(PACKET),'parent_authorization':profile['parent_authorization'],'operations':ops,'source_seven_join_recipe_SHA256':c.file_sha(SOURCE/'formatting-recipe.json'),'historical156_removed_span_registry_SHA256':c.file_sha(EXEC/'gutenberg-novel-prose-v1/removed-spans.json'),'generic_comment_stripping':False},guard)
  write('changed8-language-results.json',{'strict_rules_SHA256':c.file_sha(RULES),'detector_SHA256':c.file_sha(DETECTOR),'documents':docs,'pass':sum(d['language_pass'] for d in docs),'fail':sum(not d['language_pass'] for d in docs),'scored_windows':len(lines),'skipped_windows':sum(d['skipped_windows'] for d in docs),'chapter45':{'sha256':c45['sha256'],'rescored':False,'existing_failure_probability':0.78168,'threshold':0.8,'hold_preserved':True}},guard)
  verify(expected);guard.check();receipt={'status':'COMPLETE_EXACT18_MARKER_REMOVALS_87BYTES_NO_ADMISSION','executor_manifest_SHA256':expected,'executor_code_SHA256':c.file_sha(HERE/'execute.py'),'limits_profile_SHA256':c.file_sha(PROFILE),'parent_authorization':profile['parent_authorization'],'approved_packet_SHA256':c.file_sha(PACKET),'old_source_manifest_SHA256':c.file_sha(SOURCE/'manifest.json'),'chapters':61,'changed_chapters':sorted(CHANGED),'marker_removals':18,'removed_presentation_bytes':87,'original_v2_bytes':oldtotal,'derivative_v3_bytes':newtotal,'provisional_existing_M1_content_tokens':tokens,'all61_inverse_exact_to_v2_v1_and_raw_keeps':True,'all9_internal_greetings_dates_openquotes_italics_preserved':True,'all156_prior_omissions_and7_joins_ancestry_preserved':True,'all_old_input_hashes_unchanged':True,'changed8_language_pass':sum(d['language_pass'] for d in docs),'changed8_language_fail':sum(not d['language_pass'] for d in docs),'chapter45_failure_hold_untouched':True,'no_new_overlap_or_fresh_acceptance_claim':True,'elapsed_seconds':c.clock()-guard.start,'new_admitted_documents':0,'new_admitted_tokens':0,'SLM_weights_initialized':0,'models_initialized':0,'training_updates':0,'network_requests':0}
  write('receipt.json',receipt,guard);manifest={str(p.relative_to(DEST)):c.file_sha(p) for p in sorted(DEST.rglob('*')) if p.is_file() and p.name not in {'manifest.json','worker.log','supervisor.json','worker-result.json'}};write('manifest.json',manifest,guard);c.terminal_write(DEST/'worker-result.json',{'status':'COMPLETE','receipt_SHA256':c.file_sha(DEST/'receipt.json'),'manifest_SHA256':c.file_sha(DEST/'manifest.json'),'elapsed_seconds':c.clock()-guard.start},CAP)
 except BaseException as error:c.terminal_write(DEST/'worker-result.json',{'status':'TERMINAL_FAILED_NO_RETRY','error':str(error),'elapsed_seconds':c.clock()-guard.start,'new_admitted_documents':0},CAP);raise

def execute(expected):
 start=c.clock();verify(expected);DEST.mkdir(exist_ok=False);guard=Guard(start);guard.check();proc=None;peak=0;reason=None;c.terminal_write(DEST/'worker-result.json',{'status':'NOT_STARTED'},CAP)
 def stop():
  if proc and proc.poll() is None:
   os.killpg(proc.pid,signal.SIGTERM)
   try:proc.wait(timeout=1)
   except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=2)
 try:
  with (DEST/'worker.log').open('xb') as log:
   env=dict(os.environ,MARKER_PARENT_PID=str(os.getpid()),MARKER_START=str(start));proc=subprocess.Popen([sys.executable,str(HERE/'execute.py'),'--worker','--manifest-sha256',expected],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
   while proc.poll() is None:
    left=EXTERNAL-(c.clock()-start)
    if left<=0:reason='external60secondcap';stop();break
    ps=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,check=True,timeout=min(1,left));rss,_=c.tree_rss_from_ps(ps.stdout,os.getpid());peak=max(peak,rss)
    if rss>RSS or c.size(DEST)>CAP-1048576 or shutil.disk_usage(DEST).free<guard.reserve+32000000:reason='RSS_output_or_diskcap';stop();break
    time.sleep(min(.05,max(0,EXTERNAL-(c.clock()-start))))
   code=proc.wait(timeout=2)
  w=json.loads((DEST/'worker-result.json').read_text());success=code==0 and reason is None and w['status']=='COMPLETE' and c.clock()-start<EXTERNAL;verify(expected)
  if success:success=c.file_sha(DEST/'receipt.json')==w['receipt_SHA256'] and c.file_sha(DEST/'manifest.json')==w['manifest_SHA256']
  output={'status':'COMPLETE' if success else 'FAILED_NO_RETRY','reason':reason,'worker_exit_code':code,'worker_pid':proc.pid,'elapsed_seconds':c.clock()-start,'executor_manifest_SHA256':expected,'worker_result_SHA256':c.file_sha(DEST/'worker-result.json'),'peak_observed_process_tree_RSS_bytes':peak,'RSS_scope':'0.05sec process-tree observations,transientpeaksnotproven','output_bytes_before_supervisor':c.size(DEST),'network_requests':0,'retry':False,'new_admitted_documents':0};guard.check(len(json.dumps(output).encode())+4096);write('supervisor.json',output,guard);raise SystemExit(0 if success else 1)
 except SystemExit:raise
 except BaseException as error:
  stop()
  if not (DEST/'supervisor.json').exists():c.terminal_write(DEST/'supervisor.json',{'status':'FAILED_NO_RETRY','error':str(error),'network_requests':0,'new_admitted_documents':0},CAP,'supervisor')
  raise
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--manifest-sha256',required=True);parser.add_argument('--execute',action='store_true');parser.add_argument('--worker',action='store_true');args=parser.parse_args();verify(args.manifest_sha256)
 if args.worker:worker(args.manifest_sha256)
 elif args.execute:execute(args.manifest_sha256)
 else:print(json.dumps({'status':'READY_NOT_EXECUTED','manifest_SHA256':args.manifest_sha256}))

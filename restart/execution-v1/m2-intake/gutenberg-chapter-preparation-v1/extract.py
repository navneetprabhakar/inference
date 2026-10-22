"""PG1342 exact-byte chapter partition; raw annotations retained, never admission."""
import argparse,hashlib,json,os,pathlib,re,shutil,signal,subprocess,sys,time
HERE=pathlib.Path(__file__).resolve().parent;EXEC=HERE.parents[1];REPO=EXEC.parents[1]
RAW=HERE.parent/'gutenberg-discovery-pilot-v3/text.raw'
RAW_SHA='3f6bb9d6f78e0293b56acd4714dd68cb7d6d1d293402031ce9d5a216bcaf9d75'
DEST=HERE.parent/'gutenberg-chapters-v1';CAP=100000000;WALL=110;EXTERNAL=120
FAMILY='austen:pride-and-prejudice:original-work-all-editions'
def sha(b):return hashlib.sha256(b).hexdigest()
def roman(n):
 out=''
 for v,k in [(100,'C'),(90,'XC'),(50,'L'),(40,'XL'),(10,'X'),(9,'IX'),(5,'V'),(4,'IV'),(1,'I')]:
  while n>=v:out+=k;n-=v
 return out
def annotations(b,base):
 out=[]
 patterns={'illustration_caption':rb'\[Illustration:[^\]]*\]','footnote_candidate':rb'\[(?:\d+|Footnote[^\]]*|[Tt]ranscriber[^\]]*)\]','modern_editorial_candidate':rb'(?i)transcriber.{0,100}|proofread.{0,100}|Project Gutenberg.{0,100}|Internet Archive.{0,100}|editor.s note.{0,100}'}
 for kind,p in patterns.items():
  for m in re.finditer(p,b):out.append({'kind':kind,'start_byte':base+m.start(),'end_byte':base+m.end(),'sha256':sha(m.group())})
 return sorted(out,key=lambda x:(x['start_byte'],x['kind']))
def partition(raw):
 raw.decode('utf-8',errors='strict')
 start=list(re.finditer(rb'(?m)^\*\*\* START OF THE PROJECT GUTENBERG EBOOK[^\r\n]*\*\*\*',raw));end=list(re.finditer(rb'(?m)^\*\*\* END OF THE PROJECT GUTENBERG EBOOK[^\r\n]*\*\*\*',raw))
 if len(start)!=1 or len(end)!=1 or start[0].end()>=end[0].start():raise ValueError('Unique ordered PG markers required')
 a,z=start[0].end(),end[0].start()
 pre=list(re.finditer(rb'(?m)^PREFACE\.\r?$',raw[a:z]));ilist=list(re.finditer(rb'\[Illustration: List of Illustrations\.\]',raw[a:z]))
 if len(pre)!=1 or len(ilist)!=1:raise ValueError('Exact preface/illustration-list boundaries required')
 p=a+pre[0].start();il=a+ilist[0].start()
 captions=list(re.finditer(rb'\[Illustration:[^\]]*\]',raw[il:z]));first=[m for m in captions if re.search(rb'(?m)^Chapter I\.\]\s*$',m.group())]
 if len(first)!=1:raise ValueError('Unique ChapterI decorated caption required')
 c1=il+first[0].start();heads=list(re.finditer(rb'(?mi)^CHAPTER[ \t]+([IVXLCDM]+)\.?\r?$',raw[c1:z]));expected=[roman(i).encode() for i in range(2,62)]
 if [m.group(1).upper() for m in heads]!=expected:raise ValueError('Exactly continuous II-LXI standalone headings required')
 starts=[c1]+[c1+m.start() for m in heads]
 closing=[m for m in re.finditer(rb'\[Illustration:[^\]]*\]',raw[starts[-1]:z]) if re.search(rb'\bTHE\s+END\b',m.group(),re.I)]
 if len(closing)!=1:raise ValueError('Unique final illustration/colophon boundary required')
 cend=starts[-1]+closing[0].start()
 if b'of uniting them.' not in raw[max(starts[-1],cend-1000):cend]:raise ValueError('Final novel sentence anchor missing')
 cuts=[(0,a,'pg_header'),(a,p,'print_frontmatter'),(p,il,'saintsbury_preface'),(il,c1,'illustration_list')]
 cuts +=[(v,starts[i+1] if i<60 else cend,'chapter_%02d'%(i+1)) for i,v in enumerate(starts)]
 cuts +=[(cend,z,'print_endmatter'),(z,len(raw),'pg_end_and_license')]
 if cuts[0][0]!=0 or cuts[-1][1]!=len(raw) or any(x[1]!=y[0] for x,y in zip(cuts,cuts[1:])) or any(a>=b for a,b,_ in cuts):raise ValueError('Nonempty contiguous exact coverage required')
 return [{'name':name,'start_byte':a,'end_byte':b,'bytes':b-a,'sha256':sha(raw[a:b]),'annotation_spans':annotations(raw[a:b],a)} for a,b,name in cuts]
def tree_bytes():return sum(p.stat().st_size for p in DEST.rglob('*') if p.is_file())
def write(name,b):
 if tree_bytes()+len(b)>CAP-1000000:raise ValueError('Prewrite output cap')
 p=DEST/name;p.parent.mkdir(exist_ok=True,parents=True)
 with p.open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
def jwrite(name,v):write(name,(json.dumps(v,indent=2,ensure_ascii=False)+'\n').encode())
def worker():
 if os.getppid()!=int(os.environ['PG_CHAPTER_PARENT']):raise ValueError('Parent supervision required')
 began=time.monotonic();raw=RAW.read_bytes()
 if sha(raw)!=RAW_SHA:raise ValueError('Exact verified raw source required')
 policy=json.loads((EXEC/'disk-budget.json').read_text());reserve=policy['free_disk_floor_bytes']+policy['weights_checkpoints_reserved_bytes']+policy['scratch_cap_bytes']
 if shutil.disk_usage(DEST).free<reserve+CAP:raise ValueError('Disk reserves')
 parts=partition(raw);chapters=[];tokenizer=None;tokpin=None
 sys.path.insert(0,str(REPO/'src'))
 try:
  from slm.common.tokenizer import BPE
  tokdir=EXEC/'tokenizer-8192';tokpin=sha((tokdir/'manifest.json').read_bytes())
  if tokpin!='577c0f59ffc594931650de802c4630f3171ebde139cc32c742f5f264e7f98812':raise ValueError('Existing tokenizer pin changed')
  tokenizer=BPE.load(tokdir)
 except ImportError:tokenizer=None
 for part in parts:
  if time.monotonic()-began>=WALL:raise TimeoutError('Worker110second cap')
  b=raw[part['start_byte']:part['end_byte']];name=part['name'];suffix='.txt' if name.startswith('chapter_') else '.bin';write('parts/'+name+suffix,b)
  part['file']='parts/'+name+suffix
  if name.startswith('chapter_'):
   text=b.decode('utf-8');tokens=len(tokenizer._core.encode(text).ids) if tokenizer else None
   chapters.append({**part,'chapter_number':int(name.split('_')[1]),'source_raw_sha256':RAW_SHA,'family_id':FAMILY,'edition':'PG1342observed1894GeorgeAllen/Saintsbury/Thomson rendition; exact physical-source identity not fully established','text':text,'words_whitespace':len(text.split()),'content_tokens_existing_M1_BPE':tokens,'tokenizer_manifest_sha256':tokpin if tokenizer else None,'split':None,'holds':['pending_rights_and_quality_and_overlap_review']+(['retained_illustration_captions'] if any(x['kind']=='illustration_caption' for x in part['annotation_spans']) else [])+(['editorial_or_footnote_candidate'] if any(x['kind']!='illustration_caption' for x in part['annotation_spans']) else []),'training_admitted':False})
 write('chapters.jsonl',''.join(json.dumps(c,ensure_ascii=False)+'\n' for c in chapters).encode())
 jwrite('partition.json',{'source':str(RAW),'source_sha256':RAW_SHA,'parts':parts,'raw_bytes':len(raw),'total_partition_bytes':sum(x['bytes'] for x in parts),'reconstruction_sha256':sha(b''.join((DEST/p['file']).read_bytes() for p in parts)),'all_raw_bytes_covered_once':True})
 jwrite('receipt.json',{'status':'LOSSLESS_CHAPTER_DISCOVERY_NOT_ADMITTED','chapters':len(chapters),'work_families':1,'chapter_bytes':sum(x['bytes'] for x in chapters),'chapter_words_whitespace':sum(x['words_whitespace'] for x in chapters),'chapter_content_tokens_existing_M1_BPE':sum(x['content_tokens_existing_M1_BPE'] for x in chapters) if tokenizer else None,'tokenizer_manifest_sha256':tokpin if tokenizer else None,'chapters_with_annotation_spans':sum(bool(x['annotation_spans']) for x in chapters),'all_raw_bytes':len(raw),'output_bytes_before_receipt':tree_bytes(),'limits':{'output_bytes':CAP,'worker_seconds':WALL,'external_seconds':EXTERNAL},'elapsed_seconds':time.monotonic()-began,'raw_source_unchanged':sha(RAW.read_bytes())==RAW_SHA,'new_admitted_tokens':0,'limitations':['Existing M1tokenizer provides provisional content counts, not finalM3tokenizer counts','Caption/footnote/editorial detector is incomplete and source spans remain unchanged','Onebookfamily doesnot establish independent source/genre coverage','Wholechapters retain illustrationcaptions and require review or separately versioned extraction']})
def main():
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--worker',action='store_true');a=p.parse_args()
 if a.worker:return worker()
 if not a.execute:print('Prepared offline lossless PG1342partition; no execution');return
 DEST.mkdir(exist_ok=False);start=time.monotonic();env=dict(os.environ,PG_CHAPTER_PARENT=str(os.getpid()));child=subprocess.Popen([sys.executable,str(HERE/'extract.py'),'--worker'],env=env,start_new_session=True);expired=False
 try:code=child.wait(timeout=EXTERNAL)
 except subprocess.TimeoutExpired:expired=True;os.killpg(child.pid,signal.SIGKILL);code=child.wait()
 jwrite('supervisor.json',{'exit_code':code,'timeout':expired,'elapsed_seconds':time.monotonic()-start,'network':False,'retry':False});raise SystemExit(0 if code==0 else 1)
if __name__=='__main__':main()

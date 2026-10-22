"""Permitted synthetic CPU/metadata benchmark; no raw PB bodies/student model."""
import pathlib,json,time,tempfile,hashlib,signal,resource,sys
import engine,rules
HERE=pathlib.Path(__file__).resolve().parent;p=json.loads((HERE/'profile.json').read_text());p['known_targets']=json.loads((HERE/'known-targets.json').read_text())
def alarm(*a):raise TimeoutError('synthetic_benchmark240seconds')
signal.signal(signal.SIGALRM,alarm);signal.setitimer(signal.ITIMER_REAL,240)
for key in ['fasttext','language_model','tokenizer_manifest','tokenizer_core']:assert rules.sha(p[key]['path'])==p[key]['sha256']
t=rules.load_tokenizer(p);start=time.monotonic();times={'prepare':0.,'tokenizer':0.,'classifier_and_SQL':0.};rawbytes=chars=docs=0;batch=[];proj=0;largest=0
sentence=('The river flows past the town while people study how water moves through the valley. A clear explanation connects each observation to the evidence and describes the limits of the measurement. Students compare two examples, ask questions, and check whether the conclusion follows from the facts.\n')
mixture='नमस्ते दुनिया. 中文测试. مرحبا بالعالم. naïve café. α β 42.\n'
with tempfile.TemporaryDirectory(prefix='PB-synthetic-CPU-') as z:
 store=engine.Store(z,p['limits'],lambda *a:None)
 def flush():
  global batch,proj
  if batch:
   before=time.monotonic();store.batch(p,batch,240-(time.monotonic()-start));times['classifier_and_SQL']+=time.monotonic()-before;batch=[];proj=0
 for n in range(1,2049):
  text=(sentence+(mixture if n%8==0 else ''))*45;text=f'Synthetic example {n}.\n'+text
  before=time.monotonic();windows,size=engine.prepared(text);times['prepare']+=time.monotonic()-before
  if batch and (len(batch)>=64 or proj+size>8388608):flush()
  before=time.monotonic();tokens=len(t.encode(text,add_special_tokens=False).ids);times['tokenizer']+=time.monotonic()-before
  data=text.encode();rawbytes+=len(data);chars+=len(text);docs+=1;largest=max(largest,len(data));identity={'source':1,'ordinal':n,'id':f'synthetic://example/{n}','text_SHA256':hashlib.sha256(data).hexdigest(),'line_SHA256':hashlib.sha256(data).hexdigest(),'characters':len(text),'UTF8_bytes':len(data),'source_flags':0};batch.append({'doc':docs,'identity':identity,'explicit_flags':0,'tokens':tokens,'windows':windows});proj+=size
 # One maximum-size natural-language document exercises bounded whole+chunks.
 text=(sentence*8000)[:2195961];before=time.monotonic();windows,size=engine.prepared(text);times['prepare']+=time.monotonic()-before
 if batch and proj+size>8388608:flush()
 before=time.monotonic();tokens=len(t.encode(text,add_special_tokens=False).ids);times['tokenizer']+=time.monotonic()-before
 data=text.encode();rawbytes+=len(data);chars+=len(text);docs+=1;largest=max(largest,len(data));batch.append({'doc':docs,'identity':{'source':1,'ordinal':docs,'id':'synthetic://maximum-natural-document','text_SHA256':hashlib.sha256(data).hexdigest(),'line_SHA256':hashlib.sha256(data).hexdigest(),'characters':len(text),'UTF8_bytes':len(data),'source_flags':0},'explicit_flags':0,'tokens':tokens,'windows':windows});proj+=size;flush();stats=store.stats.copy();store.summary();store.close();dbbytes=(pathlib.Path(z)/'screening.sqlite').stat().st_size
 elapsed=time.monotonic()-start;ratios={'bytes':1478854368/rawbytes,'windows':1593650/stats['all_windows'],'documents':106881/docs};linear={k:elapsed*v for k,v in ratios.items()};conservative=max(linear.values())*2+120
 result={'status':'SYNTHETIC_PINNED_CLASSIFIER_TOKENIZER_AND_SQL_BENCHMARK_NO_PB_RUN','synthetic_documents':docs,'UTF8_bytes':rawbytes,'characters':chars,'windows':stats['all_windows'],'scored':stats['scored'],'skipped':stats['skipped'],'content_tokens':stats['content_tokens'],'max_document_UTF8_bytes':largest,'elapsed_seconds':elapsed,'phase_seconds':times,'M1_tokens_per_second':stats['content_tokens']/elapsed,'UTF8_bytes_per_second':rawbytes/elapsed,'windows_per_second':stats['all_windows']/elapsed,'projection_linear_full_seconds':linear,'conservative_2x_largest_plus120seconds':conservative,'SQLite_bytes':dbbytes,'peak_RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024),'source_body_reads':0,'student_model_operations':0,'limitations':'Synthetic2kdocs mostly natural English plus one-eighth mixed-script and one max-size natural document; actualPB token patterns/byteBPE longwords/language labels/gzip/storage/systemload may differ. Scaling is not a completion guarantee. Temporary DB deleted, no text copies retained.'};print(json.dumps(result,indent=2))
signal.setitimer(signal.ITIMER_REAL,0)

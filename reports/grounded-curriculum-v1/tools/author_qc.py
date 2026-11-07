"""Descriptive candidate quality inventory; not independent verification or admission."""
import collections,hashlib,json,pathlib,re,sqlite3,sys
ROOT=pathlib.Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT));from tokenizer import load
TOK=load()
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def normalize(text):return re.sub(r'(?<![A-Za-z])[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?','<NUMBER>',re.sub(r'\s+',' ',text.casefold()).strip())
def stats(values):
 s=sorted(values);return dict(count=len(s),minimum=s[0],median=s[len(s)//2],p95=s[min(len(s)-1,int(.95*len(s)))],maximum=s[-1]) if s else {}
reports={}
for name in ['grounded-tool-candidates-v1','grounded-session-candidates-v1']:
 p=ROOT/'data'/name;db=p/'candidates.sqlite';c=sqlite3.connect('file:'+str(db)+'?mode=ro',uri=True);c.row_factory=sqlite3.Row;out={};sets={}
 for split in ['train','exposed-development']:
  rows=list(c.execute('select * from documents where split=?',(split,)));answers=collections.Counter();ngrams=collections.Counter();lens=[];units=collections.Counter();ops=collections.Counter();surfaces=set();kinds=collections.Counter();histories=[];normalized=[];calls=set();params=set();sourcecounts=collections.Counter();finalmodes=collections.Counter()
  for row in rows:
   lesson=json.loads(row['original_lesson_json']);task=json.loads(row['task_json']);surfaces.add((row['family'],task['form_index']));kinds[task['kind']]+=1;histories.append(row['text']);normalized.append(normalize(row['text']));params.add(json.dumps(task['parameters'],sort_keys=True));finalmodes[task['group']]+=1
   for m in lesson['history']:
    if m['role']=='assistant' and 'text' in m:
     text=m['text'];answers[text]+=1;lens.append(len(TOK.encode(text)));words=text.casefold().split();ngrams.update(' '.join(words[i:i+6]) for i in range(max(0,len(words)-5)))
    if 'call' in m:
     call=m['call'];calls.add(json.dumps(call,sort_keys=True));a=call['arguments']
     if call['name']=='convert':units[a['from']+'->'+a['to']]+=1
     else:ops[a['op']]+=1
   for o in lesson['observations']:sourcecounts[o['source']]+=1
  sets[split]=dict(histories=set(histories),normalized=set(normalized),calls=calls,parameters=params)
  out[split]=dict(lessons=len(rows),exact_complete_history_duplicates=len(histories)-len(set(histories)),normalized_complete_history_duplicates=len(normalized)-len(set(normalized)),answer_token_lengths=stats(lens),distinct_complete_answers=len(answers),top_complete_answers=answers.most_common(10),top_six_word_phrases=ngrams.most_common(10),actual_operation_calls=dict(ops),actual_conversion_directions=dict(units),retained_surface_form_count=len(surfaces),kinds=dict(kinds),groups=dict(finalmodes),observation_provenance=dict(sourcecounts))
 out['cross_split_overlap']={k:len(sets['train'][k]&sets['exposed-development'][k]) for k in sets['train']};out['database_sha256']=digest(db);out['candidate_manifest_sha256']=digest(p/'candidate-manifest.json');out['scope']='Author descriptive QC only; not independent semantic verification or admission.';reports[name]=out;c.close()
output=ROOT/'reports/grounded-curriculum-v1/tools/author-qc.json';output.write_text(json.dumps(reports,indent=2)+'\n');print(json.dumps({name:{'train':v['train']['answer_token_lengths'],'dev':v['exposed-development']['answer_token_lengths'],'overlap':v['cross_split_overlap'],'dev_conversion_directions':v['exposed-development']['actual_conversion_directions']} for name,v in reports.items()},indent=2))

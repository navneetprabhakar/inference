import collections,hashlib,json,pathlib,re,sqlite3,time,os
R=pathlib.Path(__file__).resolve().parents[2];D=R/'data/sft-readiness-v4';V=R/'data/sft-readiness-v3'
SUM3='Provide a concise, objective summary of the input text in up to three sentences, focusing on key actions and intentions without using second or third person pronouns.'
SUM1='Extract and present the main key point of the input text in one very short sentence, including essential details like dates or locations if necessary.'
REWRITE={"You're an AI assistant for text re-writing. Rewrite the input text to make it "+s for s in ('more concise while preserving its core meaning.','more friendly and approachable while maintaining its main points.','more professional and formal while retaining its essential content.')}
PRON=re.compile(r'\b(?:you|your|yours|yourself|yourselves|he|him|his|himself|she|her|hers|herself|it|its|itself|they|them|their|theirs|themselves)\b',re.I)
NUM=re.compile(r'(?<!\w)[+-]?\d[\d,]*(?:\.\d+)?')
META=re.compile(r'\[(relation|num_sentences|num_highlights|response_options)\]',re.I)
FICTION=re.compile(r'\b(?:role.?play|fictional|pretend|imagine you|you are (?:an? |the )?(?:mythical|dragon|dwarf|elf|elven|wizard|prospector|old prospector|police officer|antique book seller)|you are a \d+ year old)\b',re.I)
IDENT=re.compile(r'\b(?:my (?:last update|knowledge cutoff)(?: was| is| in)?|I (?:was|am) (?:created|developed|trained) by|I (?:have |just |already )?(?:sent|booked|scheduled|emailed|purchased|accessed|browsed|searched the web|set (?:the |your |a )?reminder))\b',re.I)
def sentences(t):
 t=re.sub(r'\b(?:Mr|Mrs|Ms|Dr|Prof|St)\.',lambda m:m[0][:-1]+'<DOT>',t)
 t=re.sub(r'(?<=\d)\.(?=\d)','<DOT>',t)
 return len([x for x in re.split(r'[.!?]+(?:\s+|$)',t.strip()) if x.strip()])
def rules(h):
 system=h[0]['text'] if h[0]['role']=='system' else '';out=set();fiction=bool(FICTION.search('\n'.join(x['text'] for x in h if x['role'] in ('system','user'))));user=''
 for x in h:
  t=x['text']
  if x['role']=='user':user=t
  if x['role'] in ('user','assistant'):
   for key in META.findall(t):
    if not re.search(r'\b'+key+r'\s*:\s*[^;\s)]+',user,re.I):out.add('unresolved_meta_placeholder')
  if x['role']!='assistant':continue
  if system in (SUM1,SUM3) and sentences(t)>(1 if system==SUM1 else 3):out.add('summary_sentence_limit')
  if system==SUM3 and PRON.search(t):out.add('summary_banned_pronoun')
  if system in {SUM1,SUM3}|REWRITE and {n.replace(',','') for n in NUM.findall(t)}-{n.replace(',','') for n in NUM.findall(user)}:out.add('unsupported_numeric_literal')
  if not fiction and IDENT.search(t):out.add('own_identity_or_external_claim')
 return sorted(out)
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def main():
 os.nice(10);start=time.monotonic();D.mkdir(exist_ok=True);assert not(D/'receipt.json').exists()
 pins={str(p):sha(p) for p in (V/'candidates.sqlite',V/'partial-candidate-manifest.json',V/'custody.json',V/'quality-review.json',V/'quality-selection.json',pathlib.Path(__file__),pathlib.Path(__file__).with_name('FILTER_PROTOCOL.md'),pathlib.Path(__file__).with_name('verify_filter.py'))}
 m=json.loads((V/'partial-candidate-manifest.json').read_text());assert pins[str(V/'candidates.sqlite')]==m['database']['sha256']
 ex=set(json.loads((V/'custody.json').read_text())['excluded_doc_ids'])|set(json.loads((V/'quality-review.json').read_text())['proposed_excluded_doc_ids']);prior={x['doc_id'] for x in json.loads((V/'quality-selection.json').read_text())['sample_ids']};counts=collections.defaultdict(collections.Counter);excluded=[];survivors=[]
 con=sqlite3.connect(f'file:{V}/candidates.sqlite?mode=ro',uri=True);con.row_factory=sqlite3.Row
 for n,row in enumerate(con.execute('select doc_id,source,split,input_tokens,target_tokens,selected_history_json from documents')):
  if n%1000==0:assert time.monotonic()-start<900 and not(R/'runs/STOP').exists() and not(D/'STOP').exists()
  row=dict(row)
  if row['doc_id'] in ex:continue
  rs=rules(json.loads(row['selected_history_json']));c=counts[row['source']+':'+row['split']];c['before_docs']+=1;c['before_targets']+=row['target_tokens']
  if rs:
   excluded.append(dict(doc_id=row['doc_id'],source=row['source'],split=row['split'],rules=rs));c['excluded_docs']+=1
   for rule in rs:c['rule_'+rule]+=1
  else:
   c['remaining_docs']+=1;c['remaining_targets']+=row['target_tokens']
   if row['split']=='train' and row['doc_id'] not in prior:survivors.append(row)
 chosen=[]
 for source in sorted({x['source'] for x in survivors}):
  pool=sorted((x for x in survivors if x['source']==source),key=lambda x:(x['input_tokens'],x['doc_id']))
  for q in range(4):
   part=[x for i,x in enumerate(pool) if min(3,i*4//len(pool))==q];part.sort(key=lambda x:hashlib.sha256(('sft-v4-quality-20261106|'+source+'|'+x['doc_id']).encode()).hexdigest());chosen.extend(dict(x,quartile=q+1) for x in part[:2])
 (D/'excluded.json').write_text(json.dumps(excluded,indent=2)+'\n');(D/'samples.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in chosen));receipt=dict(state='filtered_not_admitted_sample_frozen_before_review',pins=pins,counts=dict(counts),excluded_sha256=sha(D/'excluded.json'),sample_sha256=sha(D/'samples.jsonl'),sample_count=len(chosen),seconds=time.monotonic()-start);(D/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt['counts']))
if __name__=='__main__':main()

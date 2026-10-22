"""Full offline corpus audit staging. Does not import any model/training runtime."""
import json,sqlite3,hashlib,re,unicodedata,struct,os
from pathlib import Path
from collections import Counter
from urllib.parse import urlsplit
from tokenizers import Tokenizer
R=Path(__file__).resolve().parents[2];H=R.parent/'inference-history-20261021';D=H/'data';O=Path(__file__).resolve().parent
os.environ['TOKENIZERS_PARALLELISM']='false'
T=D/'iteration-two-foundation-tokenizers-v1/vocab-16384/core.json';tok=Tokenizer.from_file(str(T))
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for x in iter(lambda:f.read(8*1024**2),b''):h.update(x)
 return h.hexdigest()
def norm(t):return ' '.join(re.findall(r'\w+',unicodedata.normalize('NFKC',t).casefold()))
def lines(p):
 with p.open() as f:
  for line in f:
   if line.strip():yield json.loads(line)
assert not (O/'audit.sqlite').exists()
db=sqlite3.connect(O/'audit.sqlite');db.executescript('''
PRAGMA journal_mode=WAL;PRAGMA synchronous=NORMAL;
CREATE TABLE docs(id INTEGER PRIMARY KEY,source TEXT,text TEXT,normalized TEXT,sha TEXT,tokens INTEGER,held INTEGER,reasons TEXT,families TEXT,reference TEXT);
CREATE TABLE files(path TEXT PRIMARY KEY,sha256 TEXT,bytes INTEGER);
CREATE TABLE protections(id INTEGER PRIMARY KEY,text TEXT,normalized TEXT UNIQUE,origin TEXT);
''')
for p in [T,D/'language-detector-v4/fasttext',D/'language-detector-v4/lid.176.ftz',O/'policy.json']:
 db.execute('INSERT OR IGNORE INTO files VALUES(?,?,?)',(str(p),sha(p),p.stat().st_size))
window=(O/'language-input.txt').open('w');mapping=(O/'language-map.bin').open('wb');near=(O/'near-input.txt').open('w');pending=[];n=0;windows=0;stats=Counter()
def pin(p):db.execute('INSERT OR IGNORE INTO files VALUES(?,?,?)',(str(p),sha(p),p.stat().st_size))
def flush():
 global pending
 if not pending:return
 for item,encoding in zip(pending,tok.encode_batch([x[1] for x in pending])):
  docid,text=item;assert tok.decode(encoding.ids)==text,docid
  db.execute('UPDATE docs SET tokens=? WHERE id=?',(len(encoding.ids),docid))
 pending=[]
def add(source,text,held=False,families=(),reference='',seed=None,score=None):
 global n,windows
 if not isinstance(text,str) or not text.strip():return
 n+=1;stats[source]+=1
 normal=norm(text);words=normal.split();reasons=[]
 if source=='Cosmopedia':reasons.append('unresolved_seed_document_ancestry')
 if len(words)<50:reasons.append('short')
 if len(words)>6000:reasons.append('long')
 if '\ufffd' in text or any(ord(c)<32 and c not in '\r\n\t' for c in text):reasons.append('corrupt_encoding_or_controls')
 if text.count('\\n')>max(3,text.count('\n')*3):reasons.append('literal_escapes')
 if sum(c.isalpha() for c in text)/max(1,len(text))<.5:reasons.append('nonprose_character_ratio')
 if re.search(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|-----BEGIN .*PRIVATE KEY|\bAKIA[A-Z0-9]{16}\b',text):reasons.append('contact_or_secret_signal')
 if len(re.findall(r'<[^>]{1,100}>',text))>=4 or len(re.findall(r'(?i)cookie policy|all rights reserved|javascript|subscribe to our newsletter|privacy policy',text))>=3:reasons.append('markup_or_boilerplate')
 ls=[norm(x) for x in text.splitlines() if x.strip()]
 if len(ls)>=8 and 1-len(set(ls))/len(ls)>.3:reasons.append('repeated_lines')
 if words and max(Counter(words).values())/len(words)>.15:reasons.append('dominant_word')
 shingles=[' '.join(words[i:i+5]) for i in range(max(0,len(words)-4))]
 if shingles and 1-len(set(shingles))/len(shingles)>.2:reasons.append('repeated_fivegrams')
 if score is not None and score<.8:reasons.append('source_english_score')
 db.execute('INSERT INTO docs VALUES(?,?,?,?,?,?,?,?,?,?)',(n,source,text,normal,hashlib.sha256(normal.encode()).hexdigest(),None,int(held),json.dumps(reasons),json.dumps(list(families)),reference))
 pending.append((n,text))
 if len(pending)>=128:flush()
 # Whole document and all windows; no skipping language checks on rejected candidates.
 if source in ['TinyStories','FineWeb','Cosmopedia']:
  chunks=[text]+[text[i:i+1024] for i in range(0,len(text),1024) if sum(c.isalpha() for c in text[i:i+1024])>=40]
  for chunk in chunks:window.write(' '.join(chunk.split())+'\n');mapping.write(struct.pack('<I',n));windows+=1
 # Normalized complete text for C++ exact prefix join; no truncation.
 near.write(normal+'\n')
 if n%10000==0:db.commit();print('docs',n,dict(stats),flush=True)
def cache_rows(folder,prefix):
 base=D/folder;c=sqlite3.connect(f'file:{base}/charges/ledger.sqlite?mode=ro&immutable=1',uri=True)
 for key,size,expected in c.execute('select key,size,sha256 from payloads order by key'):
  if not key.startswith(prefix):continue
  p=base/'cache'/(hashlib.sha256(json.dumps(key,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()+'.bin')
  assert p.stat().st_size==size and sha(p)==expected;pin(p)
  for i,row in enumerate(lines(p)):yield row,f'{p}#{i+1}'
 c.close()
for folder,source,prefix in [('tinystories-range-intake-v1','TinyStories','records/'),('fineweb-candidate-intake-v1','FineWeb','rows/'),('cosmopedia-candidate-intake-v1','Cosmopedia','rows/')]:
 for r,ref in cache_rows(folder,prefix):
  row=r['row'];held=r.get('partition') in ['test','validation'] or r.get('decision',{}).get('original_frozen_partition') in ['test','validation']
  fam=[]
  if source=='TinyStories':fam=['story:'+r.get('file','')+':'+str(row.get('start'))]
  elif source=='FineWeb':
   fam=['source-id:'+row.get('id','')];url=row.get('url','');host=(urlsplit(url).hostname or '').lower().removeprefix('www.');fam+=['host:'+host] if host else [];fam+=['url:'+url] if url else []
  else:fam=['prompt:'+hashlib.sha256(norm(row.get('prompt','')).encode()).hexdigest()]
  add(source,row['text'],held,fam,ref,score=row.get('language_score'))
for rel,source in [('fineweb-parquet-rowgroup-audit-v1/rows.jsonl','FineWeb'),('cosmopedia-distributed-audit-v1/rows.jsonl','Cosmopedia')]:
 p=D/rel;pin(p)
 for i,r in enumerate(lines(p)):
  row=r['row'];fam=[]
  if source=='FineWeb':
   url=row.get('url','');host=(urlsplit(url).hostname or '').lower().removeprefix('www.');fam=['source-id:'+row.get('id','')]+(['host:'+host] if host else [])
  add(source,row['text'],r.get('original_frozen_partition') in ['test','validation'],fam,f'{p}#{i+1}',score=row.get('language_score'))
# Historical fixed/blocked rows are protection evidence only; no old candidate counts/scores used.
p=D/'global-exact-families-v2/families.sqlite';pin(p);old=sqlite3.connect(f'file:{p}?mode=ro&immutable=1',uri=True)
for sid,data in old.execute('select sid,data from records where fixed>0 or blocked>0'):
 row=json.loads(data)
 for facet,text in row.get('texts',{}).items():
  if text: add('HistoricalProtection',text,True,row.get('families',()),f'{p}#{sid}:{facet}')
old.close()
# Original article-level QA holdouts and all reserved QA content, not just question strings.
for split in ['train','dev']:
 p=D/f'grounded-qa-intake-v1/{split}-v1.1.json';pin(p)
 for article in json.loads(p.read_text())['data']:
  for i,para in enumerate(article['paragraphs']):add('SQuADProtection',para['context'],True,['article:'+article['title']],f'{p}#{article["title"]}:{i}')
# Entire upstream conversation test, separated message facets to detect excerpt reuse.
p=D/'conversation-corpus-intake-v1/upstream-test.jsonl';pin(p)
for i,r in enumerate(lines(p)):
 for j,m in enumerate(r['messages']):add('ConversationProtection',m['content'],True,['conversation:'+str(i)],f'{p}#{i}:{j}')
# All versions of explicit evaluation exclusions and complete short-answer contexts.
protection_count=0
def protect(text,origin):
 global protection_count
 if isinstance(text,str) and len(norm(text).split())>=4:
  db.execute('INSERT OR IGNORE INTO protections(text,normalized,origin) VALUES(?,?,?)',(text,norm(text),origin));protection_count+=1
for p in sorted(D.glob('evaluation-exclusions-v*/inventory.json')):
 pin(p)
 for r in json.loads(p.read_text()).get('entries',[]):protect(r['text'],str(p)+':'+','.join(r.get('origins',[])))
for p in sorted(D.glob('evaluation-exclusions-v*/short-context-protections.json')):
 pin(p)
 for r in json.loads(p.read_text()):
  for m in r.get('complete_context',[]):protect(m.get('content',''),str(p))
# Extract human-authored old evaluation strings from configs and current gate examples, not score numbers.
KEYS={'text','content','prompt','prefix','context','question','expected','expected_text','answer','continuation','response','user','assistant'}
def walk(x,origin):
 if isinstance(x,dict):
  for k,v in x.items():
   if k in KEYS and isinstance(v,str):protect(v,origin)
   elif isinstance(v,(dict,list)):walk(v,origin)
 elif isinstance(x,list):
  for y in x:walk(y,origin)
for p in sorted((H/'configs').glob('*.json')):
 if any(k in p.name for k in ['eval','gate','acceptance','probe','language','conversation']):
  pin(p)
  try:walk(json.loads(p.read_text()),str(p))
  except json.JSONDecodeError:pass
flush();window.close();mapping.close();near.close();db.commit()
summary={'documents':n,'source_counts':dict(stats),'language_windows':windows,'protection_strings':db.execute('select count(*) from protections').fetchone()[0],'tokenizer_sha256':sha(T),'policy_sha256':sha(O/'policy.json'),'training_approved':False}
(O/'build-summary.json').write_text(json.dumps(summary,indent=2)+'\n');db.execute('PRAGMA wal_checkpoint(TRUNCATE)');db.close();print(summary,flush=True)

"""Local content census only. No network, model initialization, or training."""
from pathlib import Path
from collections import Counter, defaultdict
import json,hashlib,sqlite3,re,random,statistics,unicodedata,zlib
from tokenizers import Tokenizer
ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/'data'; OUT=ROOT/'restart'
if not DATA.exists(): DATA=ROOT.parent/'inference-history-20261021/data'
TOKENIZER=DATA/'iteration-two-foundation-tokenizers-v1/vocab-16384/core.json'
tok=Tokenizer.from_file(str(TOKENIZER)); rng=random.Random(20261021)
stats={};seen={};samples=defaultdict(list);holdouts=set();lineage=[]
def h(x):return hashlib.sha256(x.encode()).hexdigest()
def normalized(t):return ' '.join(unicodedata.normalize('NFKC',t).casefold().split())
def records(p):
 with p.open() as f:
  for line in f:
   if line.strip():yield json.loads(line)
def payloads(d,prefix):
 base=DATA/d;c=sqlite3.connect(f'file:{base}/charges/ledger.sqlite?mode=ro',uri=True)
 for key,size,sha in c.execute('select key,size,sha256 from payloads order by key'):
  if key.startswith(prefix):
   p=base/'cache'/(h(json.dumps(key,sort_keys=True,separators=(',',':'),ensure_ascii=False))+'.bin')
   raw=p.read_bytes();assert len(raw)==size and hashlib.sha256(raw).hexdigest()==sha
   lineage.append({'path':'data/'+str(p.relative_to(DATA)),'key':key,'sha256':sha,'bytes':size})
   yield key,p
 c.close()
def add(source,text,held=False,english=True,kind='',family='',provisional=None):
 s=stats.setdefault(source,Counter());s['raw_documents']+=1;s['heldout_documents']+=int(held)
 if not isinstance(text,str):s['invalid_text']+=1;return
 words=re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?",text);n=normalized(text);digest=h(n)
 reasons=[]
 if not english:reasons.append('declared_non_english')
 if len(words)<30:reasons.append('short_lt30_words')
 if len(words)>6000:reasons.append('long_gt6000_words')
 if text.count('\\n')>max(3,text.count('\n')*3):reasons.append('literal_escape_artifact')
 if '\ufffd' in text:reasons.append('replacement_character')
 letters=sum(c.isalpha() for c in text);ascii_letters=sum(c.isascii() and c.isalpha() for c in text)
 if letters and ascii_letters/letters<.85:reasons.append('non_latin_signal')
 if len(words)>100 and len(set(w.lower() for w in words))/len(words)<.12:reasons.append('low_word_diversity')
 if re.search(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|-----BEGIN .*PRIVATE KEY|\bAKIA[A-Z0-9]{16}\b',text):reasons.append('contact_or_secret_pattern')
 for reason in reasons:s['reject_'+reason]+=1
 if provisional is not None:s['old_provisional_pass']+=int(provisional)
 s['bytes']+=len(text.encode());s['words']+=len(words)
 if digest in seen:s['normalized_duplicate']+=1
 else:seen[digest]=(source,held)
 if held:holdouts.add(digest)
 usable=not reasons and not held
 if usable:s['heuristic_pass_before_dedup']+=1
 if usable and digest not in unique_pass:
  unique_pass.add(digest);s['unique_heuristic_pass']+=1;s['unique_pass_bytes']+=len(text.encode())
 if held:held_records.append((source,digest))
 elif usable:train_records.append((source,digest))
 # reservoir sample independent of prefix/order
 item=(text,usable,kind,family)
 a=samples[source];i=s['raw_documents']
 if len(a)<1000:a.append(item)
 else:
  j=rng.randrange(i)
  if j<1000:a[j]=item
 s['kind_'+kind]+=1
unique_pass=set();held_records=[];train_records=[]
for d,name in [('tinystories-range-intake-v1','TinyStories'),('fineweb-candidate-intake-v1','FineWeb'),('cosmopedia-candidate-intake-v1','Cosmopedia')]:
 prefix='records/' if name=='TinyStories' else 'rows/'
 for key,p in payloads(d,prefix):
  for r in records(p):
   row=r.get('row',r);add(name,row.get('text',''),r.get('partition') in ['validation','test'],row.get('language','en')=='en',row.get('format','story' if name=='TinyStories' else 'web_prose'),r.get('prompt_family',row.get('url','')),r.get('provisional_quality_pass'))
 print('censused',name,stats[name]['raw_documents'],flush=True)
# Additional original sampled rows, exact copies are counted and deduplicated globally.
for name,rel in [('FineWeb','fineweb-parquet-rowgroup-audit-v1/rows.jsonl'),('Cosmopedia','cosmopedia-distributed-audit-v1/rows.jsonl'),('Wikipedia','wikipedia-distributed-audit-v1/rows.jsonl')]:
 for r in records(DATA/rel):
  row=r.get('row',r);add(name,row.get('text',''),False,True,row.get('format','factual_prose'),row.get('url',row.get('id','')))
for r in records(DATA/'dolly-complete-v1/rows.jsonl'):add('Dolly','\n'.join(r.get(k,'') for k in ['instruction','context','response']),kind='instruction_qa')
for p in sorted((DATA/'conversation-parquet-intake-v3').glob('rows-*.jsonl')):
 for r in records(p):add('UltraChat','\n'.join(m['content'] for m in r['messages']),r.get('official_split')=='test',kind='synthetic_dialogue')
for r in records(DATA/'conversation-corpus-intake-v1/upstream-test.jsonl'):add('UltraChat','\n'.join(m['content'] for m in r['messages']),True,kind='synthetic_dialogue')
for r in records(DATA/'smol-smoltalk-audit-v1/sample/rows.jsonl'):add('SmolTalk','\n'.join(m['content'] for m in r['messages']),kind='synthetic_dialogue')
def flatten(node):
 yield node
 for child in node.get('replies',[]):yield from flatten(child)
for r in records(DATA/'iteration-two-oasst2-snapshot-v1/trees.jsonl'):
 ns=list(flatten(r['prompt']));en=all(n.get('lang')=='en' for n in ns)
 add('OASST2','\n'.join(n.get('text','') for n in ns),english=en,kind='dialogue_tree',family=r['message_tree_id'])
for split in ['train','dev']:
 j=json.loads((DATA/f'grounded-qa-intake-v1/{split}-v1.1.json').read_text());q=0
 for article in j['data']:
  for para in article['paragraphs']:
   q+=len(para['qas']);add('SQuAD',para['context'],split=='dev',kind='factual_passage',family=article['title'])
 stats['SQuAD'][split+'_questions']=q
print('all content counted',flush=True)
# Token estimates use the same existing BPE, no special tokens; full corpus bytes * sampled tokens/bytes.
near_samples=[]
for name,a in samples.items():
 enc=tok.encode_batch([x[0] for x in a]);nt=[len(x.ids) for x in enc];nb=[len(x[0].encode()) for x in a]
 s=stats[name];s['token_sample_documents']=len(a);s['sample_tokens']=sum(nt);s['sample_bytes']=sum(nb)
 s['estimated_raw_tokens']=round(s['bytes']*sum(nt)/max(1,sum(nb)))
 pairs=[(n,b) for n,b,x in zip(nt,nb,a) if x[1]]
 ratio=sum(n for n,b in pairs)/max(1,sum(b for n,b in pairs))
 s['estimated_unique_heuristic_tokens']=round(s['unique_pass_bytes']*ratio)
 s['token_ratio_sample_sd']=statistics.stdev([n/max(1,b) for n,b in pairs]) if len(pairs)>1 else 0
 for i,(t,ok,kind,fam) in enumerate(a):
  if ok and name in ['TinyStories','FineWeb','Cosmopedia','Wikipedia']:near_samples.append((name,i,t))
 (OUT/f'sample-{name}.json').write_text(json.dumps([{'excerpt':x[0][:1200],'heuristic_pass':x[1],'kind':x[2]} for x in a[:8]],indent=2))
 print('tokenized sample',name,flush=True)
# Near duplicate candidates: share >=1 of 12 smallest stable five-word shingle hashes.
# Exact Jaccard >=.8 confirms pairs; misses possible, sample lower bound only.
index=defaultdict(list);sets=[];hits=set();candidate_pairs=0
for name,i,t in near_samples:
 words=re.findall(r"[a-z]+(?:'[a-z]+)?",normalized(t))[:3000]
 sh={zlib.crc32(' '.join(words[j:j+5]).encode()) for j in range(len(words)-4)}
 sig=sorted(sh)[:12];candidates=set(k for v in sig for k in index[v]);cur=len(sets)
 for k in candidates:
  other=sets[k];candidate_pairs+=1
  if sh and len(sh&other)/len(sh|other)>=.8:hits.update([cur,k])
 sets.append(sh)
 for v in sig:index[v].append(cur)
leaks=Counter(source for source,dig in train_records if dig in holdouts)
for source,n in leaks.items():stats[source]['heuristic_train_rows_matching_official_heldout']=n
result={'method':'Original local snapshots/cache row payloads, normalized exact global dedup. Heuristic usable is provisional; not final English/rights/near/leakage admission. No historical scores used.',
 'tokenizer':str(TOKENIZER),'tokenizer_sha256':hashlib.sha256(TOKENIZER.read_bytes()).hexdigest(),'vocab_size':tok.get_vocab_size()+10,
 'token_estimator':'1000-row seeded reservoir per source; estimated tokens = full text bytes * sample token/byte ratio; no BOS/EOS. Unique means distinct normalized documents, not distinct token types. No confidence interval asserted; mixtures can bias estimate.',
 'stats':stats,'near_duplicate_sample':{'documents':len(near_samples),'candidate_pairs':candidate_pairs,'participating_documents_at_jaccard_0_8':len(hits),'rate_lower_bound':len(hits)/max(1,len(sets)),'method':'12 bottom five-word CRC32 shingles, exact hashed-shingle Jaccard >=.8; <=3000 words/document; heuristic-pass prose sample only; no corpus extrapolation'},'payloads_verified':lineage}
(OUT/'data-census.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'stats':stats,'near':result['near_duplicate_sample']},indent=2),flush=True)

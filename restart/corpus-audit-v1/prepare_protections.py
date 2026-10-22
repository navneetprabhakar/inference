import sqlite3,re,json,hashlib
from pathlib import Path
O=Path(__file__).resolve().parent;R=O.parents[1]
c=sqlite3.connect(O/'audit.sqlite')
p=R/'restart/ENGLISH_GATE.md'
for text in re.findall(r'`([^`\n]+)`',p.read_text()):
 normal=' '.join(re.findall(r'\w+',__import__('unicodedata').normalize('NFKC',text).casefold()))
 if len(normal.split())>=4:c.execute('insert or ignore into protections(text,normalized,origin) values(?,?,?)',(text,normal,str(p)))
# Include the retained upstream TinyStories evaluation prompts explicitly.
import yaml,unicodedata
from tokenizers import Tokenizer
H=R.parent/'inference-history-20261021';key='body/evaluation-prompts'
p=H/'data/tinystories-range-intake-v1/cache'/(hashlib.sha256(json.dumps(key,separators=(',',':')).encode()).hexdigest()+'.bin')
for text in yaml.safe_load(p.read_text()):
 normal=' '.join(re.findall(r'\w+',unicodedata.normalize('NFKC',text).casefold()))
 c.execute('insert or ignore into protections(text,normalized,origin) values(?,?,?)',(text,normal,str(p)))
c.execute('insert or ignore into files values(?,?,?)',(str(p),hashlib.sha256(p.read_bytes()).hexdigest(),p.stat().st_size))
# Every distinct protection text also participates in the full near join.
tok=Tokenizer.from_file(str(H/'data/iteration-two-foundation-tokenizers-v1/vocab-16384/core.json'))
existing={x[0] for x in c.execute('select sha from docs')};added=0
with (O/'near-input.txt').open('a') as out:
 for text,normal,origin in c.execute('select text,normalized,origin from protections').fetchall():
  digest=hashlib.sha256(normal.encode()).hexdigest()
  if digest in existing:continue
  existing.add(digest);encoded=tok.encode(text);assert tok.decode(encoded.ids)==text
  c.execute('insert into docs(source,text,normalized,sha,tokens,held,reasons,families,reference) values(?,?,?,?,?,?,?,?,?)',('EvaluationProtection',text,normal,digest,len(encoded.ids),1,'[]','[]',origin));out.write(normal+'\n');added+=1
summary=json.loads((O/'build-summary.json').read_text());summary['documents']=c.execute('select count(*) from docs').fetchone()[0];summary['source_counts']['EvaluationProtection']=added;summary['protection_strings']=c.execute('select count(*) from protections').fetchone()[0];(O/'build-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
c.commit()
seen=set();n=0
with (O/'protection-input.txt').open('w') as f:
 for i,t in c.execute('select id,normalized from docs where held=1'):
  if t not in seen:seen.add(t);f.write(f'{i}\t{t}\n');n+=1
 for i,t in c.execute('select id,normalized from protections'):
  if t not in seen:seen.add(t);f.write(f'{1000000000+i}\t{t}\n');n+=1
print('Protection normalized texts',n);c.close()

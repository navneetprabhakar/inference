"""Blind lexical overlap audit; emit IDs and scores, never protected text."""
import argparse,difflib,hashlib,json,re
from pathlib import Path
def norm(s):return ' '.join(re.findall(r'\w+',s.casefold()))
def signature(text):
 words=text.split();return set(tuple(words[i:i+3]) for i in range(len(words)-2))
def read(p):return [json.loads(s) for s in p.read_text().splitlines() if s.strip()]
def text(r):return norm(' '.join(m['content'] for m in r['messages'] if m['role']=='user'))
def main(a):
 protected=[];pins={}
 for split in ['development','confirmation']:
  p=a.evaluation/(split+'.jsonl');pins[split]=hashlib.sha256(p.read_bytes()).hexdigest()
  for r in read(p):
   t=norm(' '.join(m['user'] for m in r['turns']));protected.append((split,t,signature(t)))
 existing=[]
 if a.existing:
  for r in read(a.existing):
   t=text(r);existing.append((r['id'],t,signature(t)))
 warnings=[];rows=read(a.data)
 for r in rows:
  t=text(r);sig=signature(t)
  for group,collection in [('protected',protected),('existing',existing)]:
   for key,u,usig in collection:
    union=sig|usig
    if t!=u and (not union or len(sig&usig)/len(union)<.2):continue
    ratio=difflib.SequenceMatcher(None,t,u,autojunk=False).ratio()
    if ratio>=.85:warnings.append({'training_id':r['id'],'against':group,'split_or_id':key,'similarity':ratio,'exact':t==u})
 report={'kind':'blind_full_user_conversation_lexical_screen','records':len(rows),'source_sha256':hashlib.sha256(a.data.read_bytes()).hexdigest(),'protected_sha256':pins,'existing_sha256':hashlib.sha256(a.existing.read_bytes()).hexdigest() if a.existing else None,'warnings':warnings,'limitation':'TrigramJaccard>=.2 prefilter and sequence>=.85; lexical screen, not semantic independence certification.'}
 a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'records':len(rows),'warnings':warnings}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('data',type=Path);p.add_argument('--evaluation',type=Path,required=True);p.add_argument('--existing',type=Path);p.add_argument('--output',type=Path,required=True);main(p.parse_args())

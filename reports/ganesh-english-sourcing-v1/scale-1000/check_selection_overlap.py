"""Lexical candidate overlap audit. Opens only named already-exposed comparators."""
import argparse,hashlib,json,re,unicodedata
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
EXPOSED=['reports/english-first-v1/fit-train.jsonl','reports/english-first-v1/development-reference.jsonl','reports/ganesh-conversation-pilot-v1/train.jsonl','reports/ganesh-conversation-pilot-v1/development.jsonl','reports/ganesh-english-curriculum-v2/train.jsonl']
def fingerprint(row):
 text=' '.join(' '.join(unicodedata.normalize('NFKC',m.get('content','')).casefold().split()) for m in row['messages'] if m['role'] in ('user','assistant'))
 words=re.findall(r'\w+',text)
 return text,{tuple(words[i:i+5]) for i in range(len(words)-4)}
def main():
 p=argparse.ArgumentParser();p.add_argument('selection');p.add_argument('receipt');a=p.parse_args()
 rows=[json.loads(l) for l in Path(a.selection).read_text().splitlines()]
 comparators=[];bounds={}
 for name in EXPOSED:
  path=ROOT/name;bounds[name]=hashlib.sha256(path.read_bytes()).hexdigest()
  comparators.extend((name,r) for r in map(json.loads,path.read_text().splitlines()) if 'messages' in r)
 oldcount=len(comparators);prepared=[(path,r.get('group',r.get('id')),fingerprint(r)) for path,r in comparators]
 exact=[];near=[]
 for row in rows:
  text,sh=fingerprint(row)
  for path,group,(other,osh) in prepared:
   if text==other:exact.append({'group':row['group'],'other':group,'path':path})
   # Bound impossible intersections before set operations.
   if min(len(sh),len(osh))/max(1,max(len(sh),len(osh)))<.35:continue
   intersection=len(sh&osh);score=intersection/max(1,len(sh)+len(osh)-intersection)
   if score>=.35:near.append({'group':row['group'],'other':group,'path':path,'fivegram_jaccard':score})
  prepared.append((a.selection,row['group'],(text,sh)))
 result={'selection_sha256':hashlib.sha256(Path(a.selection).read_bytes()).hexdigest(),'sessions':len(rows),'exposed_comparator_count':oldcount,'bound_files':bounds,'exact_matches':exact,'near_matches':near,'threshold':.35,'limitations':['Lexical check does not establish semantic/template independence.','Full historical pretraining corpus unavailable; no exhaustive contamination claim.','Sealed release not opened.']}
 Path(a.receipt).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ['bound_files','exact_matches','near_matches']},indent=2));print('exact',len(exact),'near',len(near))
if __name__=='__main__':main()

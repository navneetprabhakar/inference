"""Complete targeted near join and protected-span screening for 56 candidates."""
import collections,hashlib,json,pathlib,sqlite3,subprocess,time
from slm.restart.edu_filter import normalized
O=pathlib.Path(__file__).resolve().parent;R=O.parents[1];I=O/'m2-intake/individual-salvage-v1';D=I/'overlap-v1'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def grams(norm):
 w=norm.split();return {tuple(w[i:i+5]) for i in range(len(w)-4)}
def main():
 if D.exists():raise FileExistsError('Immutable overlap audit exists')
 receipt=json.loads((I/'receipt.json').read_text());assert sha(I/'candidates.jsonl')==receipt['candidates_sha256']
 items=[json.loads(x) for x in (I/'candidates.jsonl').read_text().splitlines()]
 norms=[normalized(r['text']) for r in items];sets=[grams(t) for t in norms]
 index=collections.defaultdict(list)
 for i,g in enumerate(sets):
  for value in g:index[value].append(i)
 D.mkdir();db=sqlite3.connect((R/'restart/corpus-audit-v1/audit.sqlite').as_uri()+'?mode=ro',uri=True)
 # Full string sets; no hashing, sampling or truncation in the near comparison.
 hits=[];scanned=0;started=time.time()
 for ident,source,norm,held,families in db.execute('SELECT id,source,normalized,held,families FROM docs'):
  g=grams(norm);counts=collections.Counter()
  for value in g:
   for i in index.get(value,()):counts[i]+=1
  for i,intersection in counts.items():
   union=len(g)+len(sets[i])-intersection
   if intersection*5>=union*4:
    hits.append(dict(candidate=i,audit_id=ident,source=source,held=held,families=families,intersection=intersection,union=union,jaccard=intersection/union))
  scanned+=1
  if scanned%50000==0:print(scanned,'documents',round(time.time()-started,1),'seconds',flush=True)
 internal=[]
 for i,a in enumerate(sets):
  for j in range(i):
   n=len(a&sets[j]);d=len(a|sets[j])
   if n*5>=d*4:internal.append(dict(left=i,right=j,jaccard=n/d))
 protections=[(f'legacy:{r[0]}',r[1]) for r in db.execute('SELECT id,normalized FROM protections')]
 inputs={}
 for split in ['development','final']:
  for suite in ['grammar','grounded','narrative','copy']:
   path=O/f'evaluation-frozen-v1/{split}/{suite}.jsonl';inputs[str(path.relative_to(O))]=sha(path)
   for line in path.read_text().splitlines():
    row=json.loads(line);texts=[]
    if suite=='grammar':texts=row['alternatives']
    elif suite=='grounded':texts=[row['passage'],row['question'],*row['alternatives'],row['prompt'],row['controls']['shuffled_prompt']]
    elif suite=='narrative':texts=[row['prefix']]
    else:
     for role in ['training','heldout']:
      audit_id=int(row[role]['audit_id']);text=db.execute('SELECT text FROM docs WHERE id=?',(audit_id,)).fetchone()[0]
      assert hashlib.sha256(text.encode()).hexdigest()==row[role]['original_text_sha256'];texts.append(text)
    for n,text in enumerate(texts):protections.append((f'{split}:{suite}:{row.get("id",row.get("pair_id"))}:{n}',normalized(text)))
 db.close()
 with (D/'protections.tsv').open('w') as f:
  for i,(_,norm) in enumerate(protections):f.write(str(i+1000000)+'\t'+norm+'\n')
 (D/'input.txt').write_text('\n'.join(norms)+'\n')
 program=R/'restart/corpus-audit-v1/containment'
 subprocess.run([str(program),str(D/'protections.tsv'),str(D/'input.txt'),str(D/'containment.tsv')],check=True)
 exact=[{'candidate':i,'protection':name} for i,norm in enumerate(norms) for name,p in protections if norm==p]
 result=dict(status='OVERLAP_SCREEN_COMPLETE_NOT_ADMISSION',candidate_documents=len(items),scanned_legacy_documents=scanned,near_threshold=.8,
  near_matches=hits,internal_near_matches=internal,protected_units=len(protections),protected_exact_matches=exact,
  containment_hits=sum(1 for _ in (D/'containment.tsv').open()),elapsed_seconds=time.time()-started,
  candidates_sha256=sha(I/'candidates.jsonl'),frozen_evaluation_sha256=inputs,containment_program_sha256=sha(program),
  containment_policy='Full protected strings >=12 words; fixed 32-word blocks stride16; shorter strings only whole-document equality.',
  limits=['No semantic-paraphrase or unknown-ancestry guarantee.','Family/URL disposition, language, factual-risk and licensing gates remain.'],training_admitted=False)
 (D/'protection-identities.json').write_text(json.dumps({str(i+1000000):x[0] for i,x in enumerate(protections)},indent=2)+'\n')
 (D/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['scanned_legacy_documents','near_matches','internal_near_matches','containment_hits','protected_exact_matches']},indent=2))
if __name__=='__main__':main()

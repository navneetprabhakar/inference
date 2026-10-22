import random,subprocess,tempfile
from pathlib import Path
O=Path(__file__).resolve().parent;r=random.Random(42)
texts=[]
for i in range(250):
 words=[str(r.randrange(50)) for _ in range(r.randrange(6,110))];texts.append(' '.join(words))
 for j in range(2):
  v=words.copy();v[r.randrange(len(v))]='changed';texts.append(' '.join(v))
texts+=texts[:15]+['tiny','other tiny']
sets=[{' '.join(t.split()[i:i+5]) for i in range(len(t.split())-4)} for t in texts]
# Join reports exact aliases as representative edges; compare resulting components to brute force.
def graph(edges):
 p=list(range(len(texts)))
 def root(i):
  while p[i]!=i:p[i]=p[p[i]];i=p[i]
  return i
 for a,b in edges:p[root(b)]=root(a)
 return [min(j for j in range(len(texts)) if root(j)==root(i)) for i in range(len(texts))]
expected=[]
for a,s in enumerate(sets):
 for b in range(a):
  u=sets[b]
  if texts[a]==texts[b] or (s and u and 5*len(s&u)>=4*len(s|u)):expected.append((a,b))
with tempfile.TemporaryDirectory() as d:
 inp=Path(d)/'input';out=Path(d)/'output';inp.write_text('\n'.join(texts)+'\n')
 subprocess.run([str(O/'near_join'),str(inp),str(out)],check=True,capture_output=True)
 actual=[tuple(int(z)-1 for z in x.split('\t')[:2]) for x in out.read_text().splitlines()]
 assert graph(actual)==graph(expected)
print('PASS: complete near/exact connected components equal brute-force all-pairs on 767 synthetic strings; no model initialized')

"""Frozen-normalization exact/full5gram/held-string policies adapted from PGv3."""
import collections,hashlib,pathlib,sys
REPO=pathlib.Path(__file__).resolve().parents[3];sys.path.insert(0,str(REPO/'src'))
from slm.restart.edu_filter import normalized
sha=lambda b:hashlib.sha256(b).hexdigest()
def grams(w,n):return {tuple(w[i:i+n]) for i in range(len(w)-n+1)}
class Index:
 def __init__(self,texts):
  self.norms=[normalized(t) for t in texts];self.words=[n.split() for n in self.norms];self.sets=[grams(w,5) for w in self.words];self.idx=collections.defaultdict(set);self.idx12=collections.defaultdict(list);self.idx32=collections.defaultdict(set)
  for i,w in enumerate(self.words):
   for g in self.sets[i]:self.idx[g].add(i)
   for a in range(len(w)-11):self.idx12[tuple(w[a:a+12])].append((i,a))
   for g in grams(w,32):self.idx32[g].add(i)
 def containment(self,w):
  found={}
  if len(w)<12:
   for i,v in enumerate(self.norms):
    if v==' '.join(w):found[i]={'kind':'short_whole_document_equality'}
  elif len(w)<32:
   for i,off in self.idx12.get(tuple(w[:12]),()):
    if self.words[i][off:off+len(w)]==w:found[i]={'kind':'whole_source12_to31words','source_word_offset':0,'words':len(w),'text':' '.join(w)}
  else:
   for off in range(0,len(w)-31,16):
    for i in self.idx32.get(tuple(w[off:off+32]),()):
     if i not in found:found[i]={'kind':'source32word_stride16_all_candidate_offsets','source_word_offset':off,'words':32,'text':' '.join(w[off:off+32])}
  return found
 def compare(self,norm):
  w=norm.split();g=grams(w,5);counts=collections.Counter();matches={}
  for value in g:
   for i in self.idx.get(value,()):counts[i]+=1
  for i,value in enumerate(self.norms):
   if norm==value:matches.setdefault(i,{})['normalized_exact']=True
  for i,n in counts.items():
   union=len(g)+len(self.sets[i])-n
   if union and n*5>=union*4:matches.setdefault(i,{})['fivegram_Jaccard_gte_0p8']={'intersection':n,'union':union,'jaccard':n/union}
  for i,detail in self.containment(w).items():matches.setdefault(i,{})['containment']=detail
  return matches

def reconcile_protections(lines,identities,units):
 if len(lines)!=len(identities) or len(units)!=len(lines) or len(set(identities))!=len(identities):raise ValueError('protection_inventory_length_or_duplicate_identity')
 output=[]
 for n,(line,identity,u) in enumerate(zip(lines,identities,units)):
  ordinal,norm=line.split('\t',1)
  if int(ordinal)!=n or u['ordinal']!=n or u['identity']!=identity or u['role']!='protected-never-added-to-training' or sha(norm.encode())!=u['normalized_text_sha256']:raise ValueError('protected_identity_hash_role_mismatch')
  output.append((n+1000000,identity,norm))
 return output

def disposition(protected,same_current_ancestor):
 return 'PROTECTED_FAMILY_HOLD' if protected else ('EXACT_REGISTERED_CURRENT_UNIT_OR_CAPTURED_RAW_ANCESTOR_ALIAS_NOT_NEW_DOCUMENT' if same_current_ancestor else 'BODY_MATCH_REQUIRES_CUSTODY_REVIEW')

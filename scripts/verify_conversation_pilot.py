"""Read-only checks of the conversation pilot; does not train or rewrite data."""
import hashlib,json,sys
from pathlib import Path
import numpy as np
from tokenizers import Tokenizer
from sft_common import ROOT,encode_episode,render
from prepare_conversation_pilot import norm,substantive,Near,fingerprint

def main():
 p=ROOT/'data/conversations-v1';m=json.loads((p/'manifest.json').read_text());rr=[json.loads(x) for x in (p/'pilot-1000.jsonl').read_text().splitlines()]
 assert len(rr)==1000 and len({r['id'] for r in rr})==1000
 assert sum(r['provenance']['method']=='newly authored by assistant in this chat' for r in rr)==200
 assert sum(r['provenance']['method']=='curated_local_unrewritten' for r in rr)==800
 for name,h in m['files'].items():assert hashlib.sha256((p/name).read_bytes()).hexdigest()==h,name
 t=Tokenizer.from_file(str(ROOT/'data/sft-v3/tokenizer.json'));arrays=np.load(p/'pilot-episodes.npz');seen=set();protected=set();near=Near()
 for path,meta in m['protected_sets'].items():
  f=ROOT/path;assert hashlib.sha256(f.read_bytes()).hexdigest()==meta['sha256'],path
  for line in f.read_text().splitlines():
   r=json.loads(line)
   for s in substantive(r.get('episode',r.get('messages',[]))):protected.add(norm(s));near.add(fingerprint(norm(s)))
 for i,r in enumerate(rr):
  ms=r['messages'];assert len(ms)>=4 and len(ms)%2==0
  assert all(x['role']==('user' if j%2==0 else 'assistant') for j,x in enumerate(ms))
  text=render(ms);assert text not in seen;seen.add(text)
  ids,mask,n=encode_episode(t,ms);assert n<=513
  assert np.array_equal(ids,arrays['ids'][i]) and np.array_equal(mask,arrays['mask'][i]) and n==arrays['length'][i]
  # Check each role span, including every assistant EOS, not only the final turn.
  cursor=0
  for turn in ms:
   prefix=t.encode('<|'+turn['role']+'|>').ids
   body=t.encode(turn['content']+('<|endoftext|>' if turn['role']=='assistant' else '\n')).ids
   start=cursor+len(prefix)
   for pos in range(start,start+len(body)):
    if pos:assert mask[pos-1]==int(turn['role']=='assistant'),r['id']
   if turn['role']=='assistant':assert ids[start+len(body)-1]==1
   cursor+=len(prefix)+len(body)
  assert not any(norm(s) in protected or near.contains(fingerprint(norm(s))) for s in substantive(ms)),r['id']
 assert not m['training_started'] and m['cloud_spend_usd']==0
 print(json.dumps({'verified_conversations':len(rr),'authored':200,'curated':800,'mask_roundtrips':len(rr),'protected_sets_unchanged':len(m['protected_sets']),'training_started':False,'limitations':'Near matching is heuristic; semantic independence and human quality remain unproven.'},indent=2))
if __name__=='__main__':main()

"""Whole scenario/request containment; retain short-request complete contexts."""
# Creator: Navneet Prabhakar
import collections,json,time
from pathlib import Path
from slm.data.prose_screen import RequestGuard,word_key
from slm.data.schema import digest
from slm.data.stream_hash import sha
ROOT=Path('data/core-english-development-v1')
def main():
 output=ROOT/'containment-audit-v4.json'
 if output.exists():raise FileExistsError(output)
 p=json.loads((ROOT/'protocol-v2.json').read_text());first=RequestGuard([c['turns'][0]['user'] for c in p['conversations']]);keys=collections.defaultdict(list);longtexts=[];shortcontexts=[]
 for case in p['conversations']:
  for i,t in enumerate(case['turns']):
   key=word_key(t['user'])
   if len(key)>=16 and len(key.split())>=4:longtexts.append(t['user']);keys[digest(key)].append((case['id'],i+1))
   else:shortcontexts.append('\n'.join(s['user'] for s in case['turns'][:i+1]))
 alltexts=RequestGuard(longtexts);shortguard=RequestGuard(shortcontexts);counts=collections.Counter();witnesses=[];short_hits=[];start=time.monotonic();bytesread=0
 paths=[Path('data/iteration-two-foundation-research-v1/train-00000.jsonl'),Path('data/english-recovery-corpus-v1/train.jsonl'),Path('data/local-conversation-sft-v2/train.jsonl'),Path('data/grounded-replay-sft-v1/train.jsonl')];bindings={str(v):sha(v) for v in paths}
 for path in paths:
  for line in path.open():
   bytesread+=len(line.encode())
   if bytesread>512*1024**2 or time.monotonic()-start>1800:raise ValueError('Bounded complete source containment audit')
   r=json.loads(line);text=r.get('text') if 'messages' not in r else '\n'.join(m['content'] for m in r['messages']);hits=alltexts.matches(text);specific=set(first.matches(text));counts[str(path)]+=1
   usertext='\n'.join(m['content'] for m in r.get('messages',[]) if m['role']=='user')
   if shortguard.matches(usertext or text):short_hits.append(dict(source=str(path),record_identity=r.get('example_id',r.get('id',r.get('row_index')))))
   if hits:witnesses.append(dict(source=str(path),record_identity=r.get('example_id',r.get('id',r.get('row_index'))),requests=[dict(conversation=case,turn=turn,first_scenario=h in specific) for h in hits for case,turn in keys[h]]))
 if any(sha(path)!=h for path,h in bindings.items()):raise ValueError('Source changed during read-only audit')
 result=dict(creator='Navneet Prabhakar',complete=True,protocol_sha256=sha(ROOT/'protocol-v2.json'),short_request_contexts=len(shortcontexts),short_context_hits=short_hits,source_rows=dict(counts),source_bytes_scanned=bytesread,first_scenario_request_containment_hits=sum(z['first_scenario'] for w in witnesses for z in w['requests']),all_request_containment_hits=sum(len(w['requests']) for w in witnesses),witnesses=witnesses,failed_v3_receipt_sha256=sha(ROOT/'containment-v3-failure.json'),source_sha256=bindings,elapsed_seconds=time.monotonic()-start,scope='Conservative whole-text containment against all original foundation train records/all finite prose train records (more than selected gradient prefixes), old1226SFT and current4096QA. Generic English followups can recur without the new scenario being present. No semantic/paraphrase-family or random-population claim. Unchanged source files; no student capture or gradient.')
 output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='witnesses'},indent=2));print('Witness records',len(witnesses))
if __name__=='__main__':main()

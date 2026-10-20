"""Whole normalized scenario/request containment against conservative prior train supplies."""
# Creator: Navneet Prabhakar
import collections,json,time
from pathlib import Path
from slm.data.prose_screen import RequestGuard,word_key
from slm.data.schema import digest
from slm.data.stream_hash import sha
ROOT=Path('data/core-english-development-v1')
def main():
 output=ROOT/'containment-audit-v3.json'
 if output.exists():raise FileExistsError(output)
 p=json.loads((ROOT/'protocol-v2.json').read_text());first=RequestGuard([c['turns'][0]['user'] for c in p['conversations']]);alltexts=RequestGuard([t['user'] for c in p['conversations'] for t in c['turns']]);keys={digest(word_key(t['user'])):(c['id'],i+1) for c in p['conversations'] for i,t in enumerate(c['turns'])};counts=collections.Counter();witnesses=[];start=time.monotonic();bytesread=0
 paths=[Path('data/iteration-two-foundation-research-v1/train-00000.jsonl'),Path('data/english-recovery-corpus-v1/train.jsonl'),Path('data/local-conversation-sft-v2/train.jsonl'),Path('data/grounded-replay-sft-v1/train.jsonl')];bindings={str(v):sha(v) for v in paths}
 for path in paths:
  for line in path.open():
   bytesread+=len(line.encode())
   if bytesread>512*1024**2 or time.monotonic()-start>1800:raise ValueError('Bounded complete source containment audit')
   r=json.loads(line);text=r.get('text') if 'messages' not in r else '\n'.join(m['content'] for m in r['messages']);hits=alltexts.matches(text);specific=set(first.matches(text));counts[str(path)]+=1
   if hits:witnesses.append(dict(source=str(path),record_identity=r.get('example_id',r.get('id',r.get('row_index'))),requests=[dict(conversation=keys[h][0],turn=keys[h][1],first_scenario=h in specific) for h in hits]))
 if any(sha(path)!=h for path,h in bindings.items()):raise ValueError('Source changed during read-only audit')
 result=dict(creator='Navneet Prabhakar',complete=True,protocol_sha256=sha(ROOT/'protocol-v2.json'),source_rows=dict(counts),source_bytes_scanned=bytesread,first_scenario_request_containment_hits=sum(z['first_scenario'] for w in witnesses for z in w['requests']),all_request_containment_hits=sum(len(w['requests']) for w in witnesses),witnesses=witnesses,source_sha256=bindings,elapsed_seconds=time.monotonic()-start,scope='Conservative whole-text containment against all original foundation train records/all finite prose train records (more than selected gradient prefixes), old1226SFT and current4096QA. Generic English followups can recur without the new scenario being present. No semantic/paraphrase-family or random-population claim. Unchanged source files; no student capture or gradient.')
 output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='witnesses'},indent=2));print('Witness records',len(witnesses))
if __name__=='__main__':main()

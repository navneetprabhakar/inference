"""Bounded public metadata census; no source-row admission or training."""
# Creator: Navneet Prabhakar
import json,urllib.request
from pathlib import Path
from slm.data.intake_ledger import IntakeLedger
from slm.data.stream_hash import sha
ROOT=Path('data/conversation-corpus-intake-v1');CONFIG=Path('configs/conversation-corpus-intake-v1.json')

def main():
 if ROOT.exists():raise FileExistsError('Preserve existing corpus attempt')
 p=json.loads(CONFIG.read_text());ROOT.mkdir();(ROOT/'payloads').mkdir()
 with_ledger=IntakeLedger(ROOT/'ledger',p)
 try:
  for label,url in [('metadata','https://huggingface.co/api/datasets/HuggingFaceTB/smol-smoltalk'),('tree','https://huggingface.co/api/datasets/HuggingFaceTB/smol-smoltalk/tree/'+p['revision']+'?recursive=true&expand=false')]:
   key='census-'+label;limit=4*1024**2;with_ledger.reserve(key,requests=1,body_bytes=limit+1,output_bytes=limit)
   try:
    req=urllib.request.Request(url,headers={'User-Agent':'portable-slm-conversation-census/1','Accept-Encoding':'identity'})
    with urllib.request.urlopen(req,timeout=45) as response:raw=response.read(limit+1)
    if len(raw)>limit:raise ValueError('Bounded metadata body required')
    value=json.loads(raw)
    if label=='metadata' and value['sha']!=p['revision']:raise ValueError('Current viewer would not match pinned source; use pinned files only')
    (ROOT/'payloads'/(label+'.json')).write_bytes(raw);with_ledger.finish(key,raw=raw)
   except BaseException:with_ledger.finish(key);raise
  (ROOT/'census.json').write_text(json.dumps(dict(creator='Navneet Prabhakar',complete=True,metadata_sha256=sha(ROOT/'payloads/metadata.json'),tree_sha256=sha(ROOT/'payloads/tree.json'),ledger=with_ledger.snapshot(),training_approved=False),indent=2,sort_keys=True)+'\n')
 finally:with_ledger.close()
 print('Pinned public source census complete; no data rows decoded')
if __name__=='__main__':main()

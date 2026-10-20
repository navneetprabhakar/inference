"""Finite serial public conversation acquisition; no authentication or admission."""
# Creator: Navneet Prabhakar
import hashlib,json,urllib.request
from pathlib import Path


def fetch(ledger,key,url,path,maximum,*,rows=0,revision=None,opener=urllib.request.urlopen):
 path=Path(path)
 if path.exists():raise FileExistsError('Retain existing payload; no automatic replay')
 ledger.reserve(key,requests=1,body_bytes=maximum+1,output_bytes=maximum,rows=rows)
 try:
  request=urllib.request.Request(url,headers={'User-Agent':'portable-slm-bounded-conversations/1','Accept-Encoding':'identity'})
  with opener(request,timeout=45) as response:
   if response.status!=200:raise ValueError('Complete successful public response required')
   if revision is not None and response.headers.get('x-revision')!=revision:raise ValueError('Pinned source revision differs')
   raw=response.read(maximum+1)
  if len(raw)>maximum:raise ValueError('Bounded response body exceeded')
  path.write_bytes(raw);ledger.finish(key,raw=raw);return raw
 except BaseException:
  ledger.finish(key);raise


def validate_page(raw,offset,length,revision,total):
 body=json.loads(raw)
 if body.get('partial') or body.get('num_rows_total')!=total or len(body['rows'])!=length:raise ValueError('Complete fixed source page required')
 rows=[]
 for i,entry in enumerate(body['rows']):
  if entry.get('truncated_cells') or entry.get('row_idx')!=offset+i:raise ValueError('Intact exact row identity required')
  row=entry['row']
  if set(row)!= {'messages','source'} or not isinstance(row['source'],str) or not isinstance(row['messages'],list):raise ValueError('Pinned source schema differs')
  rows.append(row)
 return rows

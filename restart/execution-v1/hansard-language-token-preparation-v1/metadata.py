"""Pure Hansard metadata-to-reviewed-count-engine adapter; no body reads."""
import json
from stream_core import Lines,gzip_stream
def unique(pairs):
 out={}
 for k,v in pairs:
  if k in out:raise ValueError('duplicate_JSON_key')
  out[k]=v
 return out
def nofloat(value):raise ValueError('nonfinite_JSON')
def adapted(row):
 sid,ordinal,offset,n,LF,lineSHA,flags,identity,source,added,year,language,license,textSHA,textbytes,chars=row
 rights=1 if source=='uk-hansard-northern-ireland-assembly' else 2 if source=='uk-hansard-london-mayors-questions' else 0
 return (ordinal,offset,n,LF,lineSHA,flags,identity,None,None,None,None,None,None,None,None,None,None,textSHA,textbytes,chars,rights)

"""One complete first JSONL record per gzip prefix; never whole gzip validation."""
import hashlib,json,zlib
class Budget:
 def __init__(self,cap):self.cap=cap;self.used=0
 def charge(self,n):
  if n<0 or self.used+n>self.cap:raise ValueError('compressed_total_cap')
  self.used+=n

def first(read,budget,check,line_cap=4000000,decoded_cap=8000000):
 dec=zlib.decompressobj(16+zlib.MAX_WBITS);line=bytearray();decoded=0;compressed=0
 while True:
  check();n=min(65536,budget.cap-budget.used)
  if n<=0:raise ValueError('compressed_total_cap_before_first_line')
  raw=read(n)
  if not raw:raise ValueError('no_complete_first_JSONL_line')
  budget.charge(len(raw));compressed+=len(raw)
  pending=raw
  while pending:
   check();chunk=dec.decompress(pending,min(65536,decoded_cap-decoded+1));pending=dec.unconsumed_tail
   decoded+=len(chunk)
   if decoded>decoded_cap:raise ValueError('decoded_per_file_cap')
   newline=chunk.find(b'\n');piece=chunk if newline<0 else chunk[:newline+1]
   if len(line)+len(piece)>line_cap:raise ValueError('first_line_cap_no_truncation')
   line.extend(piece)
   if newline>=0:
    return bytes(line),{'compressed_bytes_read':compressed,'decoded_bytes_produced':decoded,'raw_line_bytes':len(line),'raw_line_SHA256':hashlib.sha256(line).hexdigest(),'raw_line_offset':0,'complete_LF_line':True,'whole_gzip_CRC_EOF_validation_claimed':False,'gzip_member_EOF_observed_during_prefix':dec.eof}
   if dec.eof:raise ValueError('member_ended_before_complete_first_line')

def pairs(p):
 d={}
 for k,v in p:
  if k in d:raise ValueError('duplicate_JSON_key')
  d[k]=v
 return d

def parse(raw):
 x=json.loads(raw.decode('utf8',errors='strict'),object_pairs_hook=pairs,parse_constant=lambda s:(_ for _ in ()).throw(ValueError('nonfinite_JSON')))
 if type(x) is not dict:raise ValueError('first_record_not_object')
 def walk(v,depth=0):
  if depth>64:raise ValueError('JSON_depth')
  if isinstance(v,str):v.encode('utf8',errors='strict')
  elif isinstance(v,dict):
   for k,w in v.items():walk(k,depth+1);walk(w,depth+1)
  elif isinstance(v,list):
   for w in v:walk(w,depth+1)
 walk(x);return x

def describe(x):
 def shape(v,depth=0):
  if depth>12:return {'type':type(v).__name__,'deeper_shape_not_expanded':True}
  if type(v) is dict:return {'type':'object','fields':{k:shape(w,depth+1) for k,w in v.items()}}
  if type(v) is list:return {'type':'array','length':len(v),'element_types':sorted({type(w).__name__ for w in v})}
  return {'type':type(v).__name__}
 text=x.get('text');metadata={k:v for k,v in x.items() if k!='text'}
 return {'schema':shape(x),'all_nontext_fields_exact':metadata,'text_type':type(text).__name__,'text_UTF8_bytes':len(text.encode('utf8')) if isinstance(text,str) else None,'text_SHA256':hashlib.sha256(text.encode('utf8')).hexdigest() if isinstance(text,str) else None,'schema_example_bias':'First physical row of each completed shard; not representative; no family/English/rights/quality/admission inference.'}

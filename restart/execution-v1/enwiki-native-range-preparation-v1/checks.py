"""Focused offline transport/selection checks; no network or global ledger."""
import copy,email.message,hashlib,io,json,pathlib,tempfile
import range_core as c
HERE=pathlib.Path(__file__).resolve().parent
class Response:
 def __init__(self,body=b'abc',code=206,url=c.URL,headers=None):
  self.code=code;self.url=url;self.headers=email.message.Message();self.body=io.BytesIO(body)
  for k,v in (headers or [('Content-Range',f'bytes 10-12/{c.XML_BYTES}'),('Content-Length','3')]):self.headers.add_header(k,v)
 def geturl(self):return self.url
 def read1(self,n):return self.body.read(n)
def run():
 results=[]
 def test(name,fn,reject=False):
  try:fn()
  except (ValueError,KeyError,TypeError) as e:
   if not reject:raise
   results.append({'check':name,'PASS':True,'rejected':str(e)});return
  if reject:raise AssertionError('accepted '+name)
  results.append({'check':name,'PASS':True})
 block={'URL':c.URL,'start':10,'end_exclusive':13,'bytes':3,'reservation_bytes':4}
 test('exact206_headers',lambda:c.validate_response(Response(),block))
 for code in [200,301,302,416,500]:test('rejectHTTP'+str(code),lambda code=code:c.validate_response(Response(code=code),block),True)
 test('redirect_URL',lambda:c.validate_response(Response(url=c.URL+'?x'),block),True)
 for name,val in [('Content-Range',f'bytes 11-13/{c.XML_BYTES}'),('Content-Range','bytes 10-12/*'),('Content-Range',f'bytes 10-12/{c.XML_BYTES+1}'),('Content-Length','4'),('Content-Length','03'),('Content-Encoding','gzip'),('Transfer-Encoding','chunked')]:
  h=[('Content-Range',f'bytes 10-12/{c.XML_BYTES}'),('Content-Length','3')];h=[(k,v) for k,v in h if k!=name]+[(name,val)]
  test(name+'_'+val,lambda h=h:c.validate_response(Response(headers=h),block),True)
 for name in ['Content-Length','Content-Range']:
  h=[('Content-Range',f'bytes 10-12/{c.XML_BYTES}'),('Content-Length','3')]
  test('duplicate_'+name,lambda h=h,name=name:c.validate_response(Response(headers=h+[(name,dict(h)[name])]),block),True)
  test('missing_'+name,lambda h=h,name=name:c.validate_response(Response(headers=[x for x in h if x[0]!=name]),block),True)
 with tempfile.TemporaryDirectory() as tmp:
  p=pathlib.Path(tmp)
  def valid():
   n,h=c.stream(Response(),p/'good',block,lambda n=0:None)
   assert n==3 and h==hashlib.sha256(b'abc').hexdigest() and (p/'good').read_bytes()==b'abc'
  test('exact_body_EOF_hash',valid)
  test('short_body',lambda:c.stream(Response(b'ab'),p/'short',block,lambda n=0:None),True)
  test('overrun_reserved_probe',lambda:c.stream(Response(b'abcdxxxx'),p/'over',block,lambda n=0:None),True)
  test('overrun_prefix_capped',lambda: (_ for _ in ()).throw(AssertionError()) if (p/'over').stat().st_size!=4 else None)
  def denied(n=0):
   if n:raise ValueError('prewrite_capacity')
  test('capacity_before_write',lambda:c.stream(Response(),p/'cap',block,denied),True)
  assert (p/'cap').stat().st_size==0
 selection=json.loads((HERE.parent/'m2-intake/enwiki-native-index-assessment-v1/selection.json').read_text())
 original=copy.deepcopy(selection);plan=c.freeze(selection)
 test('all20_kept_no_mutation',lambda:None if len(plan['selected_rows'])==20 and selection==original else (_ for _ in ()).throw(AssertionError()))
 test('actual_reservation_bounded',lambda:None if plan['reserved_body_bytes']<=50000000 else (_ for _ in ()).throw(AssertionError()))
 for field,val in [('status','PARTIAL'),('sample_rows',19),('XML_file_checksums_verified',True)]:
  s=copy.deepcopy(selection);s[field]=val;test('selection_'+field,lambda s=s:c.freeze(s),True)
 for field,val in [('raw_line_sha256','0'*64),('page_ID_observed',0),('compressed_XML_block_end_exclusive',c.XML_BYTES+1),('sampling_priority_sha256','0'*64)]:
  s=copy.deepcopy(selection);s['records'][0][field]=val;test('row_'+field,lambda s=s:c.freeze(s),True)
 s=copy.deepcopy(selection);s['records'].reverse();test('priority_order',lambda:c.freeze(s),True)
 s=copy.deepcopy(selection);r=s['records'][0];r['compressed_XML_block_end_exclusive']=r['compressed_XML_block_start']+c.PER_RANGE_CAP+1;r['compressed_XML_block_bytes']=c.PER_RANGE_CAP+1;r['compressed_range_HTTP_header']=f"bytes={r['compressed_XML_block_start']}-{r['compressed_XML_block_end_exclusive']-1}";held=c.freeze(s)
 test('oversize_held_without_replacement',lambda:None if len(held['selected_rows'])==20 and any(b['status']=='HELD_OVERSIZE_NO_REPLACEMENT' and b['reservation_bytes']==0 for b in held['distinct_ranges']) else (_ for _ in ()).throw(AssertionError()))
 return {'status':'PASS','count':len(results),'checks':results,'no_network':True,'no_global_ledger_opened':True}
if __name__=='__main__':print(json.dumps(run(),indent=2))

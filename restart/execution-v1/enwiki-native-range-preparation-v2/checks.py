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
def lifecycle():
 import ast,sys
 import ranges as r
 sys.path[:0]=[str(r.REPO/'src'),str(r.BASE)]
 from slm.data.intake_ledger import IntakeLedger
 results=[]
 contract={'limits':{'requests':50,'body_bytes':50000000,'rows':100,'output_bytes':100000000},'wall_seconds':60}
 with tempfile.TemporaryDirectory() as tmp:
  base=pathlib.Path(tmp);path=base/'success';ledger=IntakeLedger(path,contract)
  r.reserve_output(ledger);assert ledger.totals()=={'requests':0,'body_bytes':0,'rows':0,'output_bytes':56000000};ledger.close()
  ledger=IntakeLedger(path,contract);r.require_pending_output(ledger)
  results.append({'check':'supervisor_allocation_durable_close_worker_reopen_exact_pending','PASS':True})
  ledger.reserve('test-range',requests=1,body_bytes=4,output_bytes=10004)
  original_out,original_cap=r.old.OUT,r.old.OUTPUT_CAP
  try:
   r.old.OUT=base/'files';r.old.OUT.mkdir();r.old.OUTPUT_CAP=56000000
   response=Response(headers=[('Content-Range',f'bytes 10-12/{c.XML_BYTES}'),('Content-Length','3'),('X-Large-Valid-Header','x'*20000)])
   c.validate_response(response,{'URL':c.URL,'start':10,'end_exclusive':13,'bytes':3})
   r.write('headers.json',{'headers':list(response.headers.items())})
   actual=r.size(r.old.OUT);assert actual>10004 and actual<ledger.totals()['output_bytes']
   results.append({'check':'valid206_largeheader_beyond_perrange_output_still_profile_precharged','PASS':True,'actual_header_json_bytes':actual})
  finally:r.old.OUT,r.old.OUTPUT_CAP=original_out,original_cap
  ledger.finish('test-range',raw=b'abc');r.settle_output(ledger,True)
  row=ledger.db.execute('select state,actual_bytes,body_sha256 from attempts where key=?',(r.OUTPUT_KEY,)).fetchone()
  assert row==('complete',0,hashlib.sha256(b'').hexdigest()) and ledger.totals()['output_bytes']==56010004
  ledger.close();results.append({'check':'success_outputallocation_zeroactualbody_no_refund','PASS':True})
  ledger=IntakeLedger(base/'partial',contract);r.reserve_output(ledger);r.settle_output(ledger,False)
  assert ledger.db.execute('select state,actual_bytes from attempts where key=?',(r.OUTPUT_KEY,)).fetchone()==('failed',None) and ledger.totals()['output_bytes']==56000000
  try:r.require_pending_output(ledger)
  except ValueError:pass
  else:raise AssertionError('failed_output_reaccepted')
  ledger.close();results.append({'check':'partial_failed_allocation_charge_retained_not_reusable','PASS':True})
  orig=r.dependencies
  try:
   r.dependencies=lambda:(lambda root,c: IntakeLedger(base/'cleanup',contract),contract,None)
   r.supervisor_reserve_output();states=r.cleanup_ledger()
   assert any(x=={'key':r.OUTPUT_KEY,'state':'failed'} for x in states)
   results.append({'check':'postreaped_cleanup_exact_outputkey_pending_to_failed','PASS':True})
  finally:r.dependencies=orig
 source=(HERE/'ranges.py').read_text();node=next(x for x in ast.parse(source).body if isinstance(x,ast.FunctionDef) and x.name=='supervise')
 text=ast.get_source_segment(source,node)
 assert text.index('supervisor_reserve_output()')<text.index('for name,n in SLOTS.items()')<text.index('child=subprocess.Popen')<text.index("write('ownership.json'")
 assert "if output_charged:" in text and 'ledger_state=cleanup_ledger()' in text
 results.append({'check':'allocation_precedes_firstslot_ownership_child_setup_insidecleanup_try','PASS':True})
 return results
if __name__=='__main__':
 result=run();result['checks'].extend(lifecycle());result['count']=len(result['checks']);print(json.dumps(result,indent=2))

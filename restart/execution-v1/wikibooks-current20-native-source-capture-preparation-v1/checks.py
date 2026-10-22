"""Small synthetic raw-source/EOF/lifecycle fixtures only; no real archive read."""
import copy,gzip,hashlib,io,json,pathlib,subprocess,sys,tarfile,tempfile,time
import capture
def run():
 cases=[]
 def no(name,fn):
  try:fn()
  except (ValueError,OSError,EOFError):cases.append(name);return
  raise AssertionError(name)
 obj={'identifier':7,'version':{'identifier':9},'name':'Synthetic page','url':'https://en.wikibooks.org/wiki/Synthetic_page','license':[{'url':'https://creativecommons.org/licenses/by-sa/4.0/'}],'article_body':{'html':'<p>é <b>literal</b></p>','wikitext':'é literal'}}
 raw=(json.dumps(obj,ensure_ascii=False)+'\n').encode();loc={'member':'synthetic.ndjson','member_ordinal':1,'line':1,'record_bytes':len(raw),'record_sha256':capture.digest(raw)}
 e={**loc,'source_ordinal':1,'page_id':7,'revision_id':9,'title':obj['name'],'url':obj['url'],'license_original_metadata':obj['license'],'html_sha256':capture.digest(obj['article_body']['html'].encode()),'wikitext_sha256':capture.digest(obj['article_body']['wikitext'].encode())}
 detail=capture.bind_source(raw,loc,e);assert detail['HTML_UTF8_bytes']==len(obj['article_body']['html'].encode());cases.append('exact_native_record_location_identity_HTML_wikitext_license')
 for key,value in [('member','other.ndjson'),('member_ordinal',2),('line',2),('record_bytes',len(raw)+1),('record_sha256','0'*64)]:no('tampered_location_'+key,lambda key=key,value=value:capture.bind_source(raw,{**loc,key:value},e))
 for key,value in [('page_id',8),('revision_id',10),('title','other'),('url','https://wrong.example'),('license_original_metadata',[]),('html_sha256','0'*64),('wikitext_sha256','0'*64)]:no('tampered_identity_'+key,lambda key=key,value=value:capture.bind_source(raw,loc,{**e,key:value}))
 no('body_byte_mutation',lambda:capture.bind_source(raw+b' ',loc,e));no('missing_raw_not_replaced',lambda:capture.bind_source(None,loc,e))
 with tempfile.TemporaryDirectory(prefix='WB20-native-synthetic-') as t:
  root=pathlib.Path(t);buf=io.BytesIO()
  with tarfile.open(fileobj=buf,mode='w') as tar:
   ti=tarfile.TarInfo('synthetic.ndjson');ti.size=len(raw);tar.addfile(ti,io.BytesIO(raw))
  data=buf.getvalue();archive=root/'synthetic.tar.gz';archive.write_bytes(gzip.compress(data));out=root/'capture';out.mkdir()
  limits={'decoded_bytes':100000,'output_bytes':8000000,'seconds':110,'parsed_record_bytes':1000,'oversize_chunk_bytes':64,'tar_members':2,'member_name_bytes':64}
  stats,found=capture.process(archive,out,time.clock_gettime(time.CLOCK_MONOTONIC),[e],limits,1,len(data));assert set(found)=={1};assert (out/'1.source.json').read_bytes()==raw;assert stats['gzip_eof_crc_verified'] and stats['tar_end_blocks_verified'];cases.append('actual_reader_full_EOF_CRC_native_bytes_exact')
  no('missing_selected_kept_failure_no_replacement',lambda:capture.process(archive,root,time.clock_gettime(time.CLOCK_MONOTONIC),[{**e,'source_ordinal':2}],limits,1,len(data)))
  broken=root/'bad.tar.gz';b=bytearray(archive.read_bytes());b[-8]^=1;broken.write_bytes(b);partial=root/'partial';partial.mkdir();no('gzip_CRC_failure_preserves_captured_prefix',lambda:capture.process(broken,partial,time.clock_gettime(time.CLOCK_MONOTONIC),[e],limits,1,len(data)));assert (partial/'1.source.json').read_bytes()==raw
  low=root/'low';low.mkdir();no('decoded_cap_holds',lambda:capture.process(archive,low,time.clock_gettime(time.CLOCK_MONOTONIC),[e],{**limits,'decoded_bytes':len(data)-1},1,len(data)))
  output=root/'life';code="import pathlib,json,sys;p=pathlib.Path(sys.argv[1])/'result.json';b=json.dumps({'status':'COMPLETE_SYNTHETIC'}).encode();p.write_bytes(b+b' '*(32768-len(b)))"
  capture.supervisor.supervise(output,lambda start:[sys.executable,'-B','-c',code,str(output)]);s=json.loads((output/'supervisor.json').read_text());assert s['child_reaped'] and s['status']=='COMPLETE';assert json.loads((output/'ownership.json').read_text())['worker_PID']==s['child_pid'];cases.append('actual_supervisor_synthetic_child_complete_ownership_reaped')
 return {'status':'PASS','controls':len(cases),'cases':cases,'real_archive_opened_or_selected_sources_parsed':False}
if __name__=='__main__':print(json.dumps(run(),indent=2))

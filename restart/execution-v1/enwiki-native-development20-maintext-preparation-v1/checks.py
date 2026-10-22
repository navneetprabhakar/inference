"""Synthetic XML fidelity/unsupported content tests; no retained body reads."""
import hashlib,json
from pathlib import Path
import extract_core
SEM=Path(__file__).resolve().parent.parent/'enwiki-semantic-SAX-metadata-preparation-v3/semantic.py'
H=b'<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/"><siteinfo><base>https://en.wikipedia.org/wiki/Main_Page</base><namespaces><namespace key="0"/><namespace key="4"/></namespaces></siteinfo>'
def b36(n):
 s='';alphabet='0123456789abcdefghijklmnopqrstuvwxyz'
 while n:n,r=divmod(n,36);s=alphabet[r]+s
 return s or'0'
def fixture(value='[[A|B]] & <x>\n{{literal}}',encoded=None,slot=None,model='wikitext',ns=0,redirect=False,deleted=False,extra='',multi=False,badbyte=False,badSHA=False):
 expected=value.encode();digest=b36(int(hashlib.sha1(expected).hexdigest(),16));encoded=encoded if encoded is not None else value.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
 native_hash='0' if badSHA else digest;attrs=f'bytes="{len(expected)+(1 if badbyte else 0)}" sha1="{native_hash}"'+(' deleted="deleted"' if deleted else'')
 content=f'<model>{model}</model><format>text/x-wiki</format><text {attrs}>{encoded}</text>'
 if slot is not None:content=f'<slots><slot role="{slot}">{content}<sha1>{digest}</sha1></slot></slots>'
 revision=f'<revision><id>11</id>{content}<sha1>{digest}</sha1>{extra}</revision>'
 raw=(f'<page><title>A &amp; B</title><ns>{ns}</ns><id>1</id>'+('<redirect title="Other"/>' if redirect else'')+revision+(revision.replace('<id>11</id>','<id>12</id>') if multi else'')+'</page>').encode()
 selection={'page_id':1,'namespace':ns,'flags':1 if redirect else 0,'first_revision_id':11,'revision_count':2 if multi else 1,'main_text_bytes':len(expected) if slot in (None,'main') else -1,'row_ordinal':777}
 exp={'raw_XML_bytes':len(raw),'raw_XML_SHA256':hashlib.sha256(raw).hexdigest(),'selection':selection,'expected_model':model if slot in (None,'main') and not multi else None,'expected_format':'text/x-wiki' if slot in (None,'main') and not multi else None}
 return raw,exp,expected
checks=[]
def control(name,fn):fn();checks.append(name)
def success(**kw):
 raw,exp,want=fixture(**kw);record,text=extract_core.extract(H,raw,exp,SEM,lambda:None);assert text==want and not record['extraction_holds'];assert record['actual_main_text_SHA256']==hashlib.sha256(want).hexdigest();assert record['actual_root_left_open'] and record['invented_XML_bytes']==0;assert record['source_title']=='A & B';return record
control('legacy exactSAX chars retain wikitext markup hashes nativeSHA1',success)
for name,args in [('entities',{'value':'&<>"\'','encoded':'&amp;&lt;&gt;&quot;&apos;'}),('numeric',{'value':'😀 &','encoded':'&#x1F600; &#38;'}),('CDATA',{'value':'A<&B','encoded':'<![CDATA[A<&B]]>'}),('doubleescape',{'value':'&amp;','encoded':'&amp;amp;'}),('literalCRLF standardXML',{'value':'A\nB','encoded':'A\r\nB'}),('CRnumericpreserved',{'value':'A\rB','encoded':'A&#13;B'}),('main slot',{'slot':'main'}),('empty native0bytes',{'value':''}),('nonzero',{'ns':4}),('redirect',{'redirect':True})]:control(name,lambda args=args:success(**args))
def held(**kw):
 raw,exp,want=fixture(**kw);r,text=extract_core.extract(H,raw,exp,SEM,lambda:None);assert text is None and r['extraction_holds'] and r['outcome']=='HELD_UNSUPPORTED_OR_UNVERIFIED_NO_MAIN_TEXT_OUTPUT'
for name,args in [('deleted',{'deleted':True}),('auxslot',{'slot':'aux'}),('unknown model',{'model':'json'}),('multirevision',{'multi':True}),('bad byte count',{'badbyte':True}),('bad SHA1',{'badSHA':True}),('unknown child schema',{'extra':'<unknown>opaque</unknown>'}),('opaque inherited title',{'extra':'<unknown><title>fake</title><text>fake</text></unknown>'}),('text child cannot flatten',{'value':'AC','encoded':'A<x>B</x>C'})]:control('held '+name,lambda args=args:held(**args))
def DTD():
 raw,exp,want=fixture();badheader=b'<!DOCTYPE mediawiki [<!ENTITY p SYSTEM "file:///never">]>'+H
 try:extract_core.extract(badheader,raw,exp,SEM,lambda:None)
 except ValueError:return
 raise AssertionError('DTD accepted')
control('DTD/entities rejected no external access',DTD)
def wrong_header():
 raw,exp,want=fixture();bad=H.replace(b'https://en.wikipedia.org/wiki/Main_Page',b'https://evil.invalid/wiki/Main_Page')
 try:extract_core.extract(bad,raw,exp,SEM,lambda:None)
 except ValueError:return
 raise AssertionError('badbase accepted')
control('actualheader base required no invented namespace/root',wrong_header)
def identity():
 raw,exp,want=fixture();exp['selection']['page_id']=2
 try:extract_core.extract(H,raw,exp,SEM,lambda:None)
 except ValueError:return
 raise AssertionError('identity mismatch accepted')
control('frozen capturedpage/revision/model identity equality',identity)
def worker_lifecycle(wrong_owner=False):
 import tempfile,os,types,signal
 from unittest.mock import patch
 import extract
 with tempfile.TemporaryDirectory() as z:
  root=Path(z).resolve();out=root/'out';out.mkdir();source=root/'source';source.mkdir();header=source/'header.xml';header.write_bytes(H)
  inputs={'header':{'path':str(header),'stat':extract.stat(header),'bytes':len(H),'SHA256':hashlib.sha256(H).hexdigest()},'records':[]}
  for i in range(20):
   raw,row,want=fixture();raw=raw.replace(b'<id>11</id>',f'<id>{i+11}</id>'.encode()).replace(b'<id>1</id>',f'<id>{i+1}</id>'.encode());row['selection'].update({'page_id':i+1,'first_revision_id':i+11,'row_ordinal':1000+i});row['raw_XML_bytes']=len(raw);row['raw_XML_SHA256']=hashlib.sha256(raw).hexdigest();file=source/f'page{i}.xml';file.write_bytes(raw);row.update({'path':str(file),'stat':extract.stat(file)});inputs['records'].append(row)
  for name,n in extract.SLOTS.items():(out/name).write_bytes(b' '*n)
  arg=types.SimpleNamespace(start=extract.clock(),supervisor_pid=os.getppid(),profile_sha256='P',codepins_sha256='C');owner={'worker_PID':os.getpid()+(1 if wrong_owner else 0),'supervisor_PID':os.getppid(),'shared_start':arg.start,'profile_SHA256':'P','codepins_SHA256':'C'};(out/'ownership.json').write_text(json.dumps(owner));p={'output':str(out),'semantic_module':str(SEM)}
  calls=[0]
  def verify(a):calls[0]+=1;return p,inputs
  with patch.object(extract,'verify',verify),patch.object(extract,'dependencies',lambda p:(None,None)),patch.object(extract,'disk',lambda *a:None):
   if wrong_owner:
    try:extract.worker(arg)
    except ValueError as e:assert str(e)=='owned_worker_receipt'
    else:raise AssertionError('wrongowner accepted')
    assert not list(out.glob('*.utf8'))
   else:
    extract.worker(arg);r=json.loads((out/'result.json').read_text());assert r['status']=='COMPLETE_EXACT20_NATIVE_MAIN_WIKITEXT_NO_ADMISSION' and r['exact_text_outputs']==20 and calls[0]==2
    assert len(list(out.glob('*.utf8')))==20
control('actual worker20syntheticXML read hashes ownership artifacts postflight lifecycle',worker_lifecycle)
control('actual worker wrongownership no rawtext output',lambda:worker_lifecycle(True))
def early():
 import extract,time,types
 from unittest.mock import patch
 old=extract.START
 try:
  extract.START=extract.clock()-39.95
  with patch.object(extract,'verify',lambda a:time.sleep(.3)):
   try:extract.supervise(types.SimpleNamespace())
   except TimeoutError:return
   raise AssertionError('earlyalarm missed')
 finally:extract.START=old
control('actual supervisor shared preflight deadline before body reads',early)

print(json.dumps({'status':'PASS_SYNTHETIC_ONLY','count':len(checks),'checks':checks,'retained_rawXML_reads':0,'network_ledger_training':0},indent=2))

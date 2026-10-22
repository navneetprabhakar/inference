import copy,io,json,pathlib,tempfile,time,unittest.mock as mock
import discover as d
META=('''<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:pg="http://www.gutenberg.org/2009/pgterms/" xmlns:dct="http://purl.org/dc/terms/" xmlns:rel="http://id.loc.gov/vocabulary/relators/"><pg:ebook rdf:about="ebooks/1342"><dct:title>Pride and Prejudice</dct:title><dct:language><rdf:Description><rdf:value>en</rdf:value></rdf:Description></dct:language><dct:creator><pg:agent><pg:name>Austen, Jane</pg:name></pg:agent></dct:creator><rel:aui><pg:agent><pg:name>Saintsbury, George</pg:name></pg:agent></rel:aui><dct:hasFormat><pg:file rdf:about="'''+d.CANONICAL+'''"/></dct:hasFormat></pg:ebook></rdf:RDF>''').encode()
TEXT=b'''The Project Gutenberg eBook of Pride and Prejudice\nAuthor: Jane Austen\nGeorge Saintsbury Hugh Thomson George Allen 1894\n*** START OF THE PROJECT GUTENBERG EBOOK PRIDE AND PREJUDICE ***\nChapter I.\nSynthetic narrative fixture, not source text.\n*** END OF THE PROJECT GUTENBERG EBOOK PRIDE AND PREJUDICE ***\nTHE FULL PROJECT GUTENBERG LICENSE\n'''
results=[]
def good(name,f):f();results.append(name)
def rejects(name,f):
 try:f()
 except (ValueError,TimeoutError,FileExistsError):results.append(name);return
 raise AssertionError(name+' failed to refuse')
good('metadata_identity_and_all_roles',lambda:len(d.parse_metadata(META)['all_contributors_and_roles'])==2 or (_ for _ in ()).throw(AssertionError()))
rejects('wrong_id',lambda:d.parse_metadata(META.replace(b'ebooks/1342',b'ebooks/42671')))
rejects('wrong_title',lambda:d.parse_metadata(META.replace(b'Pride and Prejudice',b'Other book')))
rejects('wrong_language',lambda:d.parse_metadata(META.replace(b'>en<',b'>fr<')))
rejects('missing_author',lambda:d.parse_metadata(META.replace(b'Austen, Jane',b'Other Author')))
rejects('translated_edition',lambda:d.parse_metadata(META.replace(b'rel:aui',b'rel:trl')))
rejects('unobserved_format',lambda:d.parse_metadata(META.replace(d.CANONICAL.encode(),b'https://bad.example/book.txt')))
rejects('xml_entity',lambda:d.parse_metadata(b'<!DOCTYPE x [<!ENTITY a "b">]>'+META))
good('complete_edition_and_frontmatter_retained',lambda:d.inspect_text(TEXT))
rejects('missing_license',lambda:d.inspect_text(TEXT.replace(b'GUTENBERG LICENSE',b'LICENSE MISSING')))
rejects('missing_end',lambda:d.inspect_text(TEXT.replace(b'*** END OF',b'END OF')))
rejects('different_edition',lambda:d.inspect_text(TEXT.replace(b'George Saintsbury',b'Other Preface')))
rejects('duplicate_start',lambda:d.inspect_text(TEXT+b'\n*** START OF THE PROJECT GUTENBERG EBOOK OTHER ***'))
rejects('invalid_utf8',lambda:d.inspect_text(TEXT+b'\xff'))
class Ledger:
 def __init__(self):self.reserved=False;self.state='pending';self.db=self;self.received=None
 def reserve(self,key,**charges):assert not self.reserved;self.reserved=True
 def check_time(self):assert self.reserved
 def finish(self,key,raw=None):self.state='complete' if raw is not None else 'failed';self.received=raw
 def execute(self,*args):return self
 def fetchone(self):return (self.state,)
class Response(io.BytesIO):
 def __init__(self,b,url,headers=None):super().__init__(b);self.url=url;self.headers=headers or {'Content-Length':str(len(b))}
 def geturl(self):return self.url
class Opener:
 def __init__(self,response,ledger):self.response=response;self.ledger=ledger;self.calls=0
 def open(self,*a,**kw):assert self.ledger.reserved;self.calls+=1;return self.response
with tempfile.TemporaryDirectory() as td:
 root=pathlib.Path(td)
 l=Ledger();op=Opener(Response(b'abc',d.META),l)
 with mock.patch.object(d,'ROOT',root):d.transfer(l,'metadata',root,time.monotonic(),0,op)
 assert l.received==b'abc' and op.calls==1 and (root/'metadata.raw').read_bytes()==b'abc';results.append('reserve_before_single_request_atomic_exact_raw')
 rejects('payload_replay',lambda:d.transfer(l,'metadata',root,time.monotonic(),0,op))
with tempfile.TemporaryDirectory() as td:
 root=pathlib.Path(td);l=Ledger();op=Opener(Response(b'abc','https://bad.example/'),l)
 with mock.patch.object(d,'ROOT',root):rejects('redirect_body_refused_and_failedcharged',lambda:d.transfer(l,'metadata',root,time.monotonic(),0,op))
 assert l.state=='failed' and op.calls==1
with tempfile.TemporaryDirectory() as td:
 root=pathlib.Path(td);l=Ledger();op=Opener(Response(b'abc',d.META,{'Content-Length':'9'}),l)
 with mock.patch.object(d,'ROOT',root):rejects('truncated_body',lambda:d.transfer(l,'metadata',root,time.monotonic(),0,op))
with tempfile.TemporaryDirectory() as td:
 root=pathlib.Path(td);(root/'existing').write_bytes(b'12345')
 with mock.patch.object(d,'OUTPUT_CAP',10),mock.patch.object(d,'TERMINAL_RESERVE',2):rejects('aggregate_existing_output_prewrite',lambda:d.output_guard(root,4))
with tempfile.TemporaryDirectory() as td:
 root=pathlib.Path(td);l=Ledger();op=Opener(Response(b'abc',d.META),l)
 with mock.patch.object(d,'ROOT',root):rejects('persistent_worker_deadline',lambda:d.transfer(l,'metadata',root,time.monotonic()-d.WORKER_SECONDS-1,0,op))
with tempfile.TemporaryDirectory() as td:
 root=pathlib.Path(td);l=Ledger();op=Opener(Response(b'abc',d.META,{'Content-Type':'application/rdf+xml'}),l)
 with mock.patch.object(d,'ROOT',root),mock.patch.dict(d.CAPS,{'metadata':3}):rejects('body_cap_no_unreserved_eof_probe',lambda:d.transfer(l,'metadata',root,time.monotonic(),0,op))
 assert l.state=='failed' and op.calls==1
with tempfile.TemporaryDirectory() as td:
 root=pathlib.Path(td);l=Ledger();op=Opener(Response(b'abc',d.META,{'Content-Length':str(d.CAPS['metadata'])}),l)
 with mock.patch.object(d,'ROOT',root):rejects('declared_length_at_cap',lambda:d.transfer(l,'metadata',root,time.monotonic(),0,op))
 assert l.state=='failed'
rejects('redirect_handler_refuses_implicit_hop',lambda:d.NoRedirect().redirect_request(None,None,302,'Found',{},'https://elsewhere.example/'))
with tempfile.TemporaryDirectory() as td:
 root=pathlib.Path(td)
 with mock.patch.object(d,'ROOT',root),mock.patch.object(d.shutil,'disk_usage',return_value=type('Usage',(),{'free':0})()):rejects('weights_scratch_free_floor',d.storage)
out={'status':'PASS_SYNTHETIC_NO_NETWORK_OR_GLOBAL_LEDGER','checks':len(results),'cases':results,'full_raw_preservation':True,'actual_source_downloads':0}
pathlib.Path(__file__).with_name('synthetic-check-result.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))

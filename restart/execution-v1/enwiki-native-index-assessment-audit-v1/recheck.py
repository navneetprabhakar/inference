import pathlib,sys,json,hashlib,runpy,contextlib,io,bz2,copy
P=pathlib.Path(__file__).resolve().parent;D=P.parent/'enwiki-native-index-assessment-preparation-v1';h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();assert h(D/'code-pins.json')=='54f74daf0b6acd26280e9c5a5743ceeec4ad4319a74ac543779eea74180f4474';assert h(D/'profile.json')=='a3a09138d5860c7c92c3bde797afd66d86ea96b21c4c6872501939bb8fa70840';before={str(p):h(p) for p in D.iterdir() if p.is_file()};sys.path.insert(0,str(D));log=io.StringIO()
with contextlib.redirect_stdout(log):runpy.run_path(str(D/'checks.py'),run_name='__main__')
(P/'baseline-checks.json').write_text(log.getvalue());import run as r,core
profile=r.verify('54f74daf0b6acd26280e9c5a5743ceeec4ad4319a74ac543779eea74180f4474','a3a09138d5860c7c92c3bde797afd66d86ea96b21c4c6872501939bb8fa70840');p=json.loads((D/'profile.json').read_text());w=json.loads((r.DOWNLOAD/'worker-result.json').read_text());s=json.loads((r.DOWNLOAD/'supervisor-result.json').read_text());assert h(r.DOWNLOAD/'worker-result.json')==p['source_worker_receipt_sha256'] and h(r.DOWNLOAD/'supervisor-result.json')==p['source_supervisor_receipt_sha256'];assert s['status']=='COMPLETE_INDEX_ACQUISITION_NO_ADMISSION' and s['worker_receipt_sha256']==h(r.DOWNLOAD/'worker-result.json') and w['local_SHA256']==p['source_SHA256'];options=json.loads((r.ROOT/'enwiki-native-html-option-v1/acquisition-options.json').read_text());xml=[x for x in options['native_XML_option']['files'] if x['name'].endswith('multistream.xml.bz2')];assert len(xml)==1 and xml[0]['size']==p['publisher_XML_bytes'];cases=[]
def check(name,condition):assert condition,name;cases.append(name)
class Tiny:
 def __init__(self,b,n):self.b=b;self.n=n;self.p=0
 def read(self,n):chunk=self.b[self.p:self.p+min(n,self.n)];self.p+=len(chunk);return chunk

def go(raw,compressed=None,chunk=None,limits=None,expected=None):
 encoded=bz2.compress(raw) if compressed is None else compressed;c=dict(core.CAPS);c.update(limits or {});h2=hashlib.sha256(encoded).hexdigest();return core.assess(io.BytesIO(encoded) if chunk is None else Tiny(encoded,chunk),h2 if expected is None else expected,hashlib.md5(encoded).hexdigest(),hashlib.sha1(encoded).hexdigest(),len(encoded),1000000,'f'*64,c)
# Independent full sort for64rows rather than reproducing streamingheap logic.
lines=[(str((i-1)//4*100)+':'+str((i%7)+1)+':Title:'+str(i)+':字\n').encode() for i in range(1,65)];raw=b''.join(lines);encoded=bz2.compress(raw);result=go(raw);sourcehash=hashlib.sha256(encoded).hexdigest();priority=lambda ordinal:hashlib.sha256(('enwiki-native-index-row-discovery-v1\n'+'f'*64+'\n'+sourcehash+'\n'+str(ordinal)).encode()).hexdigest();chosen=sorted(range(1,65),key=lambda o:(priority(o),o))[:20];check('lowest20_ROW_priorities_match_independent_fullsort',[x['row_ordinal'] for x in result['samples']]==chosen)
for item in result['samples']:
 o=item['row_ordinal'];check('exact_line_colon_UTF8_and_group_range_row'+str(o),bytes.fromhex(item['raw_line_including_delimiter_hex'])==lines[o-1] and item['raw_line_sha256']==hashlib.sha256(lines[o-1]).hexdigest() and item['title_observed']=='Title:'+str(o)+':字' and item['compressed_XML_block_end_exclusive']==(((o-1)//4+1)*100 if o<=60 else 1000000))
check('duplicate_native_IDs_remain_ROW_population_not_deduplicated',result['stats']['rows']==64 and result['global_page_ID_uniqueness_proven'] is False)
# Decompressor headers, UTF8 and a logical line can cross arbitrary compressed member boundaries.
logical='0:1:co:字\n10:2:unterminated'.encode();split=logical.index('字'.encode())+1;joined=bz2.compress(logical[:split])+bz2.compress(logical[split:]);res=go(logical,joined,chunk=1,limits={'sample_rows':2});check('concatenated_headers_bytewise_and_split_UTF8_logical_line',res['stats']['bzip2_members']==2 and res['stats']['rows']==2 and res['stats']['unterminated_final_rows']==1 and res['all_bzip2_members_EOF_and_CRC_verified'])
large=b''.join((str(i*5)+':'+str(i+1)+':'+('x'*200)+'\n').encode() for i in range(1000));res=go(large);check('max_length_drain_over_multiple64KiB_outputs',res['stats']['rows']==1000 and res['stats']['decoded_bytes']==len(large))
for label,encoded in [('trailing_BZh_incomplete',bz2.compress(raw)+b'BZh'),('trailing_invalid_header',bz2.compress(raw)+b'BZh0'),('truncated_second_member',bz2.compress(raw)+bz2.compress(b'1000:1:B\n')[:-2])]:
 try:go(b'',encoded)
 except (ValueError,OSError):check(label+'_fails_no_complete_result',True)
 else:raise AssertionError(label)
try:go(raw,expected='0'*64)
except ValueError:check('compressed_sourceSHA_mismatch_fails_before_result',True)
else:raise AssertionError('hash')
assert all(h(pathlib.Path(p))==d for p,d in before.items());report={'status':'PASS_BOUNDED_INDEX_FIDELITY_AND_ROW_SAMPLE_PREPARATION','baseline_controls_reproduced':15,'independent_assertions':len(cases),'independent_checks':cases,'source_receipts_and_XMLsize_metadata_bound':True,'preparation_unchanged':True,'actual_index_decompressions':0,'actual_index_file_reads':0,'actual_XML_requests':0,'network_requests':0,'models_initialized':0};(P/'focused-checks.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'status':'PASS','baseline':15,'independent_assertions':len(cases),'real_index_decode':0}))

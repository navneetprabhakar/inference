"""Synthetic raw capture and lifecycle controls; no retained native body read."""
import bz2,copy,hashlib,json,os,signal,subprocess,tempfile,time,types
from pathlib import Path
from unittest.mock import patch
import capture,capture_core,selection
checks=[]
def test(name,fn):fn();checks.append(name)
def fixture():
    pages=[];groups=[];payloads={};offset=570
    for g in (1,2):
        decoded=bytearray()
        for i in range((g-1)*10+1,g*10+1):
            body=(f'<page><title>T{i}</title><id>{i}</id></page>').encode();start=len(decoded);decoded.extend(body)
            pages.append({'row_ordinal':i,'page_id':i,'group_ordinal':g,'group_decoded_start':start,'raw_XML_bytes':len(body),'raw_SHA256':hashlib.sha256(body).hexdigest(),'namespace':0 if i<=18 else 4,'flags':1 if 17<=i<=18 else 0,'selection_role':'ns0_nonredirect' if i<=16 else'ns0_redirect' if i<=18 else'nonzero_namespace'})
        raw=bz2.compress(decoded);groups.append({'group_ordinal':g,'compressed_start':offset,'compressed_end_exclusive':offset+len(raw),'compressed_bytes':len(raw),'decoded_bytes':len(decoded),'compressed_SHA256':hashlib.sha256(raw).hexdigest(),'decoded_SHA256':hashlib.sha256(decoded).hexdigest(),'CRC_EOF_members':1});payloads[g]=raw;offset+=len(raw)
    return {'limits':dict(capture.LIMITS)},{'selected':pages,'groups':groups},payloads

def run(change=lambda p,s,b:(p,s,b),want_fail=False):
    p,s,b=change(*fixture());written={};read=[]
    def group(g):read.append(g['group_ordinal']);return b[g['group_ordinal']]
    def write(n,data):assert n not in written;written[n]=bytes(data)
    try:r=capture_core.run(p,s,group,lambda:b'<mediawiki native="exact">',write,lambda:None)
    except Exception:
        if not want_fail:raise
        return written,read
    if want_fail:raise AssertionError('expected fail')
    assert len(r['records'])==20 and len(read)==2 and len(set(read))==2 and r['source_text_changed'] is False
    assert written['original-header.xml']==b'<mediawiki native="exact">'
    for record in r['records']:assert hashlib.sha256(written[record['raw_XML_file']]).hexdigest()==record['raw_XML_SHA256']
    assert [r['selection']['selection_role'] for r in r['records']].count('ns0_redirect')==2
    return r

test('exact20 raw bytes originalheader locators SHA allroles retained groupsonce',run)
def wrong_compressed(p,s,b):s['groups'][0]['compressed_SHA256']='0'*64;return p,s,b
def wrong_decoded(p,s,b):s['groups'][0]['decoded_SHA256']='0'*64;return p,s,b
def wrong_page(p,s,b):s['selected'][0]['raw_SHA256']='0'*64;return p,s,b
def wrong_span(p,s,b):s['selected'][0]['group_decoded_start']=10000000;return p,s,b
def too_big(p,s,b):s['selected'][0]['raw_XML_bytes']=1000001;return p,s,b
def members(p,s,b):s['groups'][0]['CRC_EOF_members']=2;return p,s,b
def decodedcap(p,s,b):p['limits']['decoded_bytes']=1;return p,s,b
def compressedcap(p,s,b):p['limits']['compressed_bytes']=1;return p,s,b
def duplicated(p,s,b):s['groups'].append(s['groups'][0]);return p,s,b
for name,fn in [('compressedSHA',wrong_compressed),('decodedSHA',wrong_decoded),('pageSHA',wrong_page),('locator',wrong_span),('1MBpagecap',too_big),('membercount',members),('decodedcap',decodedcap),('compressedcap',compressedcap),('duplicate group',duplicated)]:test('failclosed '+name,lambda fn=fn:run(fn,True))
def crc(p,s,b):
    raw=bytearray(b[1]);raw[-4]^=1;b[1]=bytes(raw);s['groups'][0]['compressed_SHA256']=hashlib.sha256(b[1]).hexdigest();return p,s,b
def CRC_atomic():
    written,reads=run(crc,True);assert list(written)==['original-header.xml'] and reads==[1]
test('CRCfailure before any rawpages from group',CRC_atomic)
def selection_test():
    rows=[];i=0
    for lo,hi in selection.BUCKETS:
        for k in range(3):i+=1;rows.append({'row_ordinal':i,'group_ordinal':i,'namespace':0,'flags':0,'raw_XML_bytes':lo})
    for k in range(3):i+=1;rows.append({'row_ordinal':i,'group_ordinal':i,'namespace':0,'flags':1,'raw_XML_bytes':100})
    for k in range(3):i+=1;rows.append({'row_ordinal':i,'group_ordinal':i,'namespace':4+k,'flags':0,'raw_XML_bytes':100})
    a=selection.select(rows);assert a==selection.select(list(reversed(rows))) and len(a)==20 and len({r['group_ordinal'] for r in a})==20
    assert sum(r['selection_role']=='ns0_nonredirect' for r in a)==16
    # Explicit actual LF vs literal backslash-n changes preimage and is not used.
    r=a[0];actual=hashlib.sha256(f'{selection.SEED}\n{r["selection_role"]}\n{r["raw_size_bucket"]}\n{r["row_ordinal"]}'.encode()).hexdigest();assert actual==r['priority_SHA256']
test('metadata selector deterministic quota buckets actualLF20distinctgroups',selection_test)
def custody_fixture():
    with tempfile.TemporaryDirectory() as z:
        path=Path(z).resolve()/'source';path.write_bytes(b'abcdef');header=path.with_name('header');header.write_bytes(b'<mediawiki>')
        p={'header':{'path':str(header),'stat':capture.stat(header),'bytes':11,'SHA256':hashlib.sha256(b'<mediawiki>').hexdigest()}}
        s={'groups':[{'group_ordinal':1,'compressed_start':0,'compressed_end_exclusive':3}]};binding={'path':str(path),'stat':capture.stat(path),'bytes':6}
        try:
            with capture.readers(p,s,binding,lambda:None) as (read,h,proof):
                assert h()==b'<mediawiki>' and read(s['groups'][0])==b'abc'
                try:read(s['groups'][0])
                except ValueError:pass
                else:raise AssertionError('read twice')
                path.write_bytes(b'UVWXYZ');proof()
        except ValueError as e:assert str(e)=='native_source_FD_path_custody'
        else:raise AssertionError('mutation accepted')
test('actual ROFD/sourceheader binding duplicate read and source mutation',custody_fixture)
def early():
    oldstart=capture.START
    try:
        capture.START=capture.clock()-84.95
        with patch.object(capture,'verify',lambda a:time.sleep(.3)):
            try:capture.supervise(types.SimpleNamespace())
            except TimeoutError:return
            raise AssertionError('preflight alarm missed')
    finally:capture.START=oldstart
test('actual supervisor early shared alarm before source/output',early)
def kill():
    child=subprocess.Popen([__import__('sys').executable,'-c','import time;time.sleep(30)'],start_new_session=True);capture.kill(child);assert child.poll() is not None
test('actual owned worker processgroup kill reap',kill)
def worker_fixture(bad_owner=False):
    import contextlib
    p,s,payloads=fixture()
    with tempfile.TemporaryDirectory() as z:
        out=Path(z).resolve();p['output']=str(out)
        for n,cap in capture.SLOTS.items():(out/n).write_bytes(b' '*cap)
        arg=types.SimpleNamespace(start=capture.clock(),supervisor_pid=os.getppid(),profile_sha256='P',codepins_sha256='C')
        own={'worker_PID':os.getpid()+(1 if bad_owner else 0),'supervisor_PID':os.getppid(),'shared_start':arg.start,'profile_SHA256':'P','codepins_SHA256':'C'};(out/'ownership.json').write_text(json.dumps(own))
        closed=[False];opened=[False];calls=[0]
        def verify(a):calls[0]+=1;return p,s,{'SHA256':'f'*64}
        @contextlib.contextmanager
        def readers(p,s,b,check):
            opened[0]=True
            def custody():
                if closed[0]:raise OSError('closed_FD')
            try:yield (lambda g:payloads[g['group_ordinal']]),(lambda:b'<mediawiki original="unchanged">'),custody
            finally:closed[0]=True
        with patch.object(capture,'verify',verify),patch.object(capture,'dependencies',lambda p:(None,None)),patch.object(capture,'disk',lambda *a:None),patch.object(capture,'readers',readers):
            if bad_owner:
                try:capture.worker(arg)
                except ValueError as e:assert str(e)=='owned_worker_receipt'
                else:raise AssertionError('bad owner accepted')
                assert not opened[0]
            else:
                capture.worker(arg);assert closed[0] and calls[0]==2
                r=json.loads((out/'result.json').read_text());assert r['status']=='COMPLETE_RAW_DEVELOPMENT20_CAPTURE_NO_ADMISSION' and len(r['records'])==20
                assert sum(q.suffix=='.xml' for q in out.iterdir())==21

test('actual worker20artifact lifecycle readerclosed before postflight',worker_fixture)
test('actual worker ownership mismatch before sourceopen',lambda:worker_fixture(True))

def RSS():
    import rss_guard
    assert rss_guard.tree_rss('10 1 20\n11 10 30\n',10,11)==51200
    for bad in ['', '10 1 0\n','10 1 20\n10 1 21\n','10 10 20\n','10 1 -1\n']:
        try:rss_guard.tree_rss(bad,10)
        except ValueError:continue
        raise AssertionError('RSS failopen')
test('pure helper import preflight strict root ownedRSS negative cases',RSS)

print(json.dumps({'status':'PASS_SYNTHETIC_ONLY','count':len(checks),'checks':checks,'retained_native_reads':0,'network_ledger_model_operations':0},indent=2))

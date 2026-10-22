"""Synthetic transport and actual isolated ledger/lifecycle controls; no GET."""
import copy,hashlib,io,json,os,signal,subprocess,sys,tempfile,time
from email.message import Message
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import acquire as a
import transport as t
sys.path.insert(0,str(a.REPO/'src'))
from slm.data.intake_ledger import IntakeLedger
C={'version':'ISOLATED_SYNTHETIC_ONLY','limits':{'requests':100,'body_bytes':1000000,'rows':100,'output_bytes':1000000},'wall_seconds':120}
RESULT=[]
def control(name,fn):
    fn();RESULT.append(name)
def must(fn):
    try:fn()
    except BaseException:return
    raise AssertionError('expected refusal')
def digest(b):return hashlib.sha256(b).hexdigest()
class Response:
    def __init__(self,b=b'abc',status=200,headers=None,url='https://huggingface.co/exact'):
        self.b=io.BytesIO(b);self.code=status;self.headers=Message();self.url=url;self.reads=0;self.closed=False
        for k,v in (headers or []):self.headers[k]=v
    def geturl(self):return self.url
    def read1(self,n):self.reads+=1;return self.b.read(n)
    def close(self):self.closed=True
class Opener:
    def __init__(self,responses,ledger):self.responses=responses;self.calls=0;self.ledger=ledger
    def open(self,request,timeout):
        assert timeout>0 and request.get_header('Authorization') is None and request.get_header('Cookie') is None
        assert self.ledger.db.execute("SELECT COUNT(*) FROM attempts WHERE state='pending' AND json_extract(charge,'$.requests')=1").fetchone()[0]==1
        self.calls+=1;r=self.responses[self.calls-1]
        if isinstance(r,BaseException):raise r
        r.url=request.full_url;return r

def run(responses,expected=b'abc',guard=None,hook=None):
    with tempfile.TemporaryDirectory() as z:
        root=Path(z);ledger=IntakeLedger(root/'ledger',C);out=root/'raw.partial';saved={};instant=[100.]
        item={'ordinal':0,'url':'https://huggingface.co/exact','expected_bytes':len(expected),'expected_sha256':digest(expected),'revision':'abc123'}
        op=Opener(responses,ledger);state={'last_start':None,'requests':0}
        def save(name,r,replace):saved[name]=copy.deepcopy(r)
        def sleep(n):instant[0]+=n+.000001
        error=None;receipt=None
        try:
            with patch.object(t,'clock',lambda:instant[0]),patch.object(t.time,'sleep',sleep):
                receipt=t.acquire(item,out,ledger,'b',['h0','h1','h2'],op,guard or (lambda:None),save,state,lambda:10)
        except BaseException as e:error=e
        if hook:hook(ledger,op,out,saved,receipt,error,responses)
        if receipt is None:
            assert error is not None
            for key in ['b','h0','h1','h2']:
                row=ledger.db.execute('SELECT state FROM attempts WHERE key=?',(key,)).fetchone()
                if row==('pending',):ledger.finish(key,raw=None)
            assert not ledger.db.execute("SELECT 1 FROM attempts WHERE state='pending'").fetchall()
        ledger.close()
        return receipt,error,saved

def ok():
    def check(l,o,p,s,r,e,rr):
        assert e is None and r['bytes']==3 and p.read_bytes()==b'abc' and o.calls==1
        assert l.totals()['body_bytes']==4 and l.totals()['requests']==1 and rr[0].closed
    run([Response()],hook=check)
control('exact EOF publisher hash + durable request before opener',ok)
for name,response in [('short',Response(b'ab')),('excess probe retained',Response(b'abcd')),('wrong hash',Response(b'xyz')),('HTTP500 no body',Response(b'secret',500)),('declared short',Response(headers=[('Content-Length','2')])),('declared duplicate',Response(headers=[('Content-Length','3'),('Content-Length','3')])),('gzip refused',Response(headers=[('Content-Encoding','gzip')])),('transfer encoding refused',Response(headers=[('Transfer-Encoding','chunked')])),('linked hash mismatch',Response(headers=[('X-Linked-Etag','wrong')])),('commit mismatch',Response(headers=[('X-Repo-Commit','wrong')])),('aggregate large headers',Response(headers=[('X-Large','a'*65536)])),('no external exception body',RuntimeError('SIGNED_QUERY_SECRET'))]:
    def case(response=response):
        r,e,s=run([response]);assert r is None and e is not None and 'SIGNED_QUERY_SECRET' not in json.dumps(s)
        if isinstance(response,Response) and response.code!=200:assert response.reads==0
    control(name,case)
for n in (1,2):
    def case(n=n):
        rs=[Response(status=302,headers=[('Location','https://us.aws.cdn.hf.co/file?signature=SIGNED_QUERY_SECRET')]) for _ in range(n)]+[Response()]
        def check(l,o,p,s,r,e,rr):
            assert e is None and o.calls==n+1 and l.totals()['body_bytes']==4 and l.totals()['requests']==n+1
            assert all(x.reads==0 and x.closed for x in rr[:-1]);assert 'SIGNED_QUERY_SECRET' not in json.dumps(s)
            assert all(r['hops'][i+1]['start_monotonic']-r['hops'][i]['start_monotonic']>=1 for i in range(n))
        run(rs,hook=check)
    control(f'{n} explicit redirects body once query redacted gap1sec',case)
for label,loc in [('offhost','https://evil.example/a'),('userinfo','https://u:SIGNED_QUERY_SECRET@huggingface.co/a'),('HTTP','http://huggingface.co/a'),('fragment','https://huggingface.co/a#x'),('port','https://huggingface.co:444/a'),('Unicode control','https://huggingface.co/a\u200b')]:
    def case(loc=loc):
        r,e,s=run([Response(status=302,headers=[('Location',loc)])]);assert r is None and 'SIGNED_QUERY_SECRET' not in json.dumps(s)
    control('redirect '+label+' refused before second GET',case)
control('third redirect refused no fourth GET',lambda:run([Response(status=302,headers=[('Location','/again')]) for _ in range(3)],hook=lambda l,o,p,s,r,e,rr:(_ for _ in ()).throw(AssertionError()) if o.calls!=3 or e is None else None))
control('deadline before body allocation requests no GET',lambda:run([Response()],guard=lambda:(_ for _ in ()).throw(TimeoutError()),hook=lambda l,o,p,s,r,e,rr:(_ for _ in ()).throw(AssertionError()) if o.calls or p.exists() else None))
for label,value in [('credential','https://x:y@huggingface.co/a'),('prefixhost','https://huggingface.co.evil/a'),('encoded whitespace','https://huggingface.co/a\n'),('empty',''),('badport','https://huggingface.co:invalid/a')]:control('URL '+label,lambda value=value:must(lambda:t.url(value)))

def owned_cleanup():
    with tempfile.TemporaryDirectory() as z:
        l=IntakeLedger(Path(z)/'l',C);p={'key':'x','files':[{'ordinal':0}]}
        l.reserve('unrelated',body_bytes=2);l.reserve('x-output',output_bytes=10);l.reserve('x-body-000',body_bytes=4)
        assert set(a.settle(l,p))=={'x-output','x-body-000'}
        assert l.db.execute('SELECT state FROM attempts WHERE key=?',('unrelated',)).fetchone()==('pending',)
        assert l.totals()['body_bytes']==6 and l.totals()['output_bytes']==10;l.close()
control('cleanup exact owned pending only charges never refunded',owned_cleanup)

def supervisor_failure(busy=False):
    with tempfile.TemporaryDirectory() as z:
        root=Path(z);out=root/'out';p={'key':'fixture','output':str(out),'files':[],'limits':{'output_precharge_bytes':100000,'external_seconds_including_preflight_hashes_and_terminal':30,'body_reservation_including_one_byte_EOF_probe_per_file':0,'max_physical_GETs':0}}
        source=SimpleNamespace(source='pressbooks');ledger=IntakeLedger(root/'charges',C) if busy else None
        def helper():return IntakeLedger,C,None
        def failwrite(*args,**kwargs):raise OSError('synthetic slot write failure')
        old=a.ROOT;a.ROOT=root
        try:
            with patch.object(a,'verify',lambda x:p),patch.object(a,'handoff',lambda x:{}),patch.object(a,'disk',lambda *x:None),patch.object(a,'helpers',helper),patch.object(Path,'write_bytes',failwrite):
                assert a.supervise(source,a.clock())==1
            if busy:assert not out.exists()
            else:
                l=IntakeLedger(root/'charges',C);row=l.db.execute('SELECT charge,state FROM attempts WHERE key=?',('fixture-output',)).fetchone();assert row[1]=='failed' and json.loads(row[0])['output_bytes']==100000;l.close()
                assert json.loads((out/'supervisor-result.json').read_text())['worker_reaped']
        finally:
            signal.setitimer(signal.ITIMER_REAL,0);a.ROOT=old
            if ledger:ledger.close()
control('actual nonblocking busy ledger no output no GET',lambda:supervisor_failure(True))
control('actual first profile slot fault precharged before write settled failed',supervisor_failure)

def actual_kill():
    child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'],start_new_session=True)
    a.kill(child);assert child.poll() is not None
    must(lambda:os.kill(child.pid,0))
control('actual owned subprocess group SIGKILL and wait reaps',actual_kill)

def early_clock():
    with tempfile.TemporaryDirectory() as z:
        d=Path(z);(d/'entry.py').write_bytes((a.HERE/'entry.py').read_bytes());(d/'acquire.py').write_text('import time\ntime.sleep(2)\nraise AssertionError("must be interrupted")\n')
        paths=[d/'acquire.py'];(d/'profiles.json').write_text(json.dumps({'required_inventory':[str(x) for x in paths]}));(d/'code-pins.json').write_text(json.dumps({'SHA256':{str(x):a.sha(x) for x in paths}}))
        start=a.clock()-1189.8;before=a.clock()
        r=subprocess.run([sys.executable,'-B',str(d/'entry.py'),'--source','pressbooks','--worker','--start',str(start),'--code-pins-sha256',a.sha(d/'code-pins.json'),'--profiles-sha256',a.sha(d/'profiles.json')],capture_output=True,timeout=3)
        assert r.returncode==1 and b'TimeoutError' in r.stdout and a.clock()-before<1
control('actual launcher shared alarm interrupts own module import preflight',early_clock)

def independent():
    with tempfile.TemporaryDirectory() as z:
        root=Path(z);l=IntakeLedger(root/'ledger',C);f=root/'raw';f.write_bytes(b'abc');p={'key':'x','output':str(root),'files':[{'ordinal':0,'path':'raw','expected_bytes':3,'expected_sha256':digest(b'abc')}],'limits':{'max_physical_GETs':3}}
        l.reserve('x-body-000',requests=0,body_bytes=4);a.mark_body_complete(l,'x-body-000',{'bytes':3,'SHA256':digest(b'abc')});l.reserve('x-hop-000-0',requests=1);l.finish('x-hop-000-0',raw=b'')
        receipt={'source_ordinal':0,'file':'raw','body_key':'x-body-000','status':'COMPLETE_EXACT_BYTES_SHA256_RAW_FILE','expected_bytes':3,'expected_SHA256':digest(b'abc'),'bytes':3,'SHA256':digest(b'abc'),'stat':a.stat(f),'hops':[{'key':'x-hop-000-0','hop':0,'request_precharged':True,'headers':{'status':200},'start_monotonic':100.}]}
        file=root/'file-000.receipt.json';file.write_text(json.dumps(receipt));w={'records':[receipt],'physical_GETs':1,'verified_raw_bytes':3};assert a.independent_files(l,p,w,lambda:None)==[receipt]
        for field,value in [('source_ordinal',1),('file','other'),('bytes',2),('body_key','unrelated')]:
            bad=copy.deepcopy(receipt);bad[field]=value;file.write_text(json.dumps(bad));must(lambda:a.independent_files(l,p,w,lambda:None))
        bad=copy.deepcopy(receipt);bad['hops'][0]['key']='unrelated';file.write_text(json.dumps(bad));must(lambda:a.independent_files(l,p,w,lambda:None))
        file.write_text(json.dumps(receipt));l.reserve('x-hop-000-2',requests=1);l.finish('x-hop-000-2',raw=b'');must(lambda:a.independent_files(l,p,w,lambda:None));l.close()
control('independent actual SQLite bytes + ordinal/body/hop/unusedcharge tamper',independent)

def production_worker():
    with tempfile.TemporaryDirectory() as z:
        root=Path(z);out=root/'out';out.mkdir()
        for name,n in a.SLOTS.items():(out/name).write_bytes(b' '*n)
        item={'ordinal':0,'url':'https://huggingface.co/exact','path':'data/raw.gz','expected_bytes':3,'expected_sha256':digest(b'abc'),'revision':'abc123'}
        p={'key':'fixture','output':str(out),'files':[item],'limits':{'worker_seconds':30,'per_file_seconds_all_hops':5,'output_precharge_bytes':100000}}
        ledger=IntakeLedger(root/'charges',C);ledger.reserve('fixture-output',output_bytes=100000);ledger.close()
        class ManagedOpener:
            def open(self,request,timeout):
                db=__import__('sqlite3').connect(root/'charges/ledger.sqlite');row=db.execute("SELECT state FROM attempts WHERE key='fixture-hop-000-0'").fetchone();db.close();assert row==('pending',)
                r=Response();r.url=request.full_url;return r
        old=a.ROOT;a.ROOT=root
        try:
            with patch.object(a,'verify',lambda x:p),patch.object(a,'helpers',lambda:(IntakeLedger,C,None)),patch.object(a,'disk',lambda *x:None),patch.object(a.urllib.request,'build_opener',lambda *x:ManagedOpener()):
                assert a.worker(SimpleNamespace(supervisor_pid=os.getppid()),a.clock())==0
            signal.setitimer(signal.ITIMER_REAL,0)
            result=json.loads((out/'worker-result.json').read_text());assert result['status']=='COMPLETE_WORKER_RAW_FILES_PENDING_INDEPENDENT_SUPERVISOR'
            assert (out/item['path']).read_bytes()==b'abc' and not (out/(item['path']+'.partial')).exists()
            ledger=IntakeLedger(root/'charges',C);assert ledger.db.execute("SELECT state FROM attempts WHERE key='fixture-output'").fetchone()==('pending',)
            assert a.independent_files(ledger,{**p,'limits':{'max_physical_GETs':3}},result,lambda:None)
            ledger.close()
        finally:a.ROOT=old;signal.setitimer(signal.ITIMER_REAL,0)
control('production worker mock network complete rename + independent ledger file verification',production_worker)

def output_bound():
    with tempfile.TemporaryDirectory() as z:
        root=Path(z);out=root/'out';out.mkdir();p={'output':str(out),'limits':{'output_precharge_bytes':2000000}}
        with patch.object(a,'ROOT',root),patch.object(a.shutil,'disk_usage',lambda x:SimpleNamespace(free=10**12)):
            must(lambda:a.disk(p,2000000));assert not list(out.iterdir())
        with patch.object(a,'ROOT',root),patch.object(a.shutil,'disk_usage',lambda x:SimpleNamespace(free=a.FREE)):
            must(lambda:a.disk(p))
control('production prewrite output cap and protected weights-scratch-free floor',output_bound)

def receipt_capacity():
    r,e,_=run([Response(status=302,headers=[('Location','https://cas-bridge.xethub.hf.co/a?signature=SECRET')]),Response(status=302,headers=[('Location','https://us.aws.cdn.hf.co/a?signature=SECRET')]),Response()]);assert e is None
    records=[]
    for i in range(11):
        q=copy.deepcopy(r);q['file']='uk_hansard/00000_ukhansard.jsonl.gz';q['source_ordinal']=i;q['body_key']='common-pile-uk-hansard-raw-v1-body-000';q['stat']=[10**18]*5
        for hop in q['hops']:hop['key']='common-pile-uk-hansard-raw-v1-hop-000-0'
        records.append(q)
    value={'status':'COMPLETE_WORKER_RAW_FILES_PENDING_INDEPENDENT_SUPERVISOR','records':records,'physical_GETs':33,'verified_raw_bytes':3203457551,'elapsed_seconds':7189,'new_admitted_documents':0,'no_decompression_or_quality_claim':True}
    assert len((json.dumps(value,indent=2)+'\n').encode())<a.SLOTS['worker-result.json']
control('11file 33hop aggregate receipt fits precharged fixed worker slot',receipt_capacity)

def pacing_boundary(clock_values,expected_sleeps):
    with tempfile.TemporaryDirectory() as z:
        root=Path(z);l=IntakeLedger(root/'ledger',C);op=Opener([Response(status=302,headers=[('Location','https://us.aws.cdn.hf.co/file?signature=SECRET')]),Response()],l)
        times=iter(clock_values);sleeps=[]
        def sleep(n):assert n>0;sleeps.append(n)
        item={'ordinal':0,'url':'https://huggingface.co/exact','expected_bytes':3,'expected_sha256':digest(b'abc'),'revision':'abc123'}
        with patch.object(t,'clock',lambda:next(times)),patch.object(t.time,'sleep',sleep):
            receipt=t.acquire(item,root/'partial',l,'body',['h0','h1','h2'],op,lambda:None,lambda *x:None,{'last_start':None,'requests':0},lambda:10)
        assert op.calls==2 and len(sleeps)==expected_sleeps and receipt['hops'][1]['start_monotonic']-receipt['hops'][0]['start_monotonic']>=1
        assert (root/'partial').read_bytes()==b'abc';l.close()
control('pacing race boundary crossed between old check and sleep now positive single sample',lambda:pacing_boundary([100.,100.999999,101.000001,101.000002],1))
control('pacing exact one-second boundary no sleep',lambda:pacing_boundary([100.,101.,101.000001],0))
control('pacing already over-boundary no sleep',lambda:pacing_boundary([100.,101.5,101.500001],0))

if __name__=='__main__':
    print(json.dumps({'status':'PASS','controls':len(RESULT),'names':RESULT,'network_calls':0,'global_ledger_opened':False,'retained_source_bodies_read':False},indent=2))

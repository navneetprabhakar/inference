"""Exact20 SAX maintext; no network/rendering/model/IntakeLedger."""
import time
START=time.clock_gettime(time.CLOCK_MONOTONIC)
import argparse,contextlib,hashlib,importlib.util,json,os,signal,sqlite3,shutil,subprocess,sys
from pathlib import Path
import extract_core
HERE=Path(__file__).resolve().parent;BASE=HERE.parent;ROOT=BASE/'m2-intake';FREE=53474836480
LIMITS={'pages':20,'page_bytes':1000000,'output_bytes':16000000,'worker_seconds':30,'external_seconds':45,'RSS_bytes':1000000000}
SLOTS={'result.json':1048576,'supervisor.json':1048576}
def clock():return time.clock_gettime(time.CLOCK_MONOTONIC)
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def stat(p):
    s=Path(p).stat();return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def alarm(*args):raise TimeoutError('shared_deadline_or_signal')
def required(p):
    return {str(HERE/n) for n in ['extract.py','extract_core.py','checks.py','profile.json','inputs.json','contract.json']}|set(p['runtime_pins'])|{p[k] for k in ['semantic_module','span_helper','supervisor_helpers','size_helper']}|set(p['metadata_proof_paths'])
def verify(a):
    if sha(HERE/'profile.json')!=a.profile_sha256 or sha(HERE/'code-pins.json')!=a.codepins_sha256:raise ValueError('external_profile_codepins')
    p=json.loads((HERE/'profile.json').read_text());pins=json.loads((HERE/'code-pins.json').read_text())['SHA256']
    if p['limits']!=LIMITS or set(pins)!=required(p):raise ValueError('exact_limits_code_inventory')
    for path,digest in pins.items():
        if Path(path).is_symlink() or sha(path)!=digest:raise ValueError('pinned_code_metadata_changed')
    if str(Path(sys.executable).resolve())!=p['python']:raise ValueError('runtime_path')
    inputs=json.loads((HERE/'inputs.json').read_text());records=inputs['records']
    if len(records)!=20 or len({r['selection']['row_ordinal'] for r in records})!=20:raise ValueError('exact20capturedinputs')
    original=json.loads(Path(p['capture_result']).read_text());supervisor=json.loads(Path(p['capture_supervisor']).read_text());proof=json.loads(Path(p['capture_verification']).read_text())
    if original['status']!='COMPLETE_RAW_DEVELOPMENT20_CAPTURE_NO_ADMISSION' or supervisor['status']!='COMPLETE_RAW20_CAPTURE_NO_ADMISSION' or supervisor['worker_reaped'] is not True or supervisor['result_SHA256']!=sha(p['capture_result']) or proof['status']!='PASS_EXACT20_RAW_CAPTURE_STORED_OUTPUT_AND_STRUCTURAL_CONTEXT':raise ValueError('independently_verified_capture_terminal')
    if inputs['source_records']!=original['records']:raise ValueError('frozen_capture_records')
    for row,source in zip(records,original['records']):
        if row['selection']!=source['selection'] or row['raw_XML_SHA256']!=source['raw_XML_SHA256'] or row['raw_XML_bytes']!=source['raw_XML_bytes'] or row['path']!=str(Path(p['capture_root'])/source['raw_XML_file']):raise ValueError('exact_original_capture_binding')
        path=Path(row['path'])
        if path.is_symlink() or str(path.resolve())!=str(path) or stat(path)!=row['stat'] or not 0<row['raw_XML_bytes']<=1000000:raise ValueError('raw_XML_input_stat_cap')
        code=source['selection']['model_code'];model=p['model_dictionary'].get(str(code))
        if row['expected_model']!=(None if model is None else model['model']) or row['expected_format']!=(None if model is None else model['format']):raise ValueError('expected_native_model_code')
    header=inputs['header'];hp=Path(header['path'])
    if header['SHA256']!=original['artifacts']['original-header.xml']['SHA256'] or hp.is_symlink() or stat(hp)!=header['stat'] or header['bytes']>65536:raise ValueError('original_header_stat_and_proof')
    dependencies(p)
    return p,inputs

def dependencies(p):
    size=load('raw20_size',p['size_helper']).census;helpers=load('raw20_supervisor_helpers',p['supervisor_helpers'])
    return size,helpers

def disk(out,extra,size):
    n=size(out);remaining=max(0,LIMITS['output_bytes']-n)
    if extra<0 or n+extra>LIMITS['output_bytes'] or size(ROOT)+remaining>64000000000 or shutil.disk_usage(ROOT).free<FREE+remaining:raise ValueError('disk_output_protected_reserves')
def terminal(out,name,obj):
    raw=(json.dumps(obj,sort_keys=True)+'\n').encode();cap=SLOTS[name]
    if len(raw)>cap:raise ValueError('terminal_slot')
    with (Path(out)/name).open('r+b') as f:f.write(raw+b' '*(cap-len(raw)));f.flush();os.fsync(f.fileno())
def read_exact(row,cap):
    path=Path(row['path'])
    if path.is_symlink() or str(path.resolve())!=str(path) or stat(path)!=row['stat']:raise ValueError('captured_input_before_stat')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        a=os.fstat(fd)
        if [a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns,a.st_ctime_ns]!=row['stat']:raise ValueError('captured_input_FD_stat')
        body=bytearray()
        while True:
            data=os.read(fd,min(65536,cap+1-len(body)))
            if not data:break
            body.extend(data)
            if len(body)>cap:raise ValueError('captured_input_read_bound')
        a=os.fstat(fd)
        if [a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns,a.st_ctime_ns]!=row['stat'] or stat(path)!=row['stat']:raise ValueError('captured_input_after_stat')
    finally:os.close(fd)
    expected=row.get('bytes',row.get('raw_XML_bytes'));digest=row.get('SHA256',row.get('raw_XML_SHA256'))
    if len(body)!=expected or hashlib.sha256(body).hexdigest()!=digest:raise ValueError('captured_input_exact_bytes_SHA256')
    return bytes(body)

def worker(a):
    out=None;owned=False;size=None
    for sig in [signal.SIGALRM,signal.SIGTERM,signal.SIGINT]:signal.signal(sig,alarm)
    try:
        remaining=a.start+30-clock()
        if remaining<=0:raise TimeoutError('worker_start_expired')
        signal.setitimer(signal.ITIMER_REAL,remaining);p,inputs=verify(a);out=Path(p['output']);size,helpers=dependencies(p)
        if os.getppid()!=a.supervisor_pid:raise ValueError('actual_parent_PID')
        until=min(clock()+3,a.start+30)
        while not (out/'ownership.json').exists() and clock()<until:time.sleep(.01)
        own=json.loads((out/'ownership.json').read_text())
        if own!={'worker_PID':os.getpid(),'supervisor_PID':a.supervisor_pid,'shared_start':a.start,'profile_SHA256':a.profile_sha256,'codepins_SHA256':a.codepins_sha256}:raise ValueError('owned_worker_receipt')
        owned=True
        def check():
            if clock()-a.start>=30:raise TimeoutError('worker_shared_deadline')
            disk(out,0,size)
        def write(name,data):
            check();disk(out,len(data),size)
            with (out/name).open('xb') as f:
                if f.write(data)!=len(data):raise ValueError('short_output_write')
                f.flush();os.fsync(f.fileno())
        header=read_exact(inputs['header'],65536);records=[]
        for row in inputs['records']:
            check();raw=read_exact(row,1000000)
            record,text=extract_core.extract(header,raw,row,p['semantic_module'],check)
            record['captured_XML_path']=row['path'];record['captured_XML_stat']=row['stat'];record['captured_original_header_SHA256']=inputs['header']['SHA256']
            record['capture_group_provenance']={k:row[k] for k in ['group_compressed_start','group_compressed_end_exclusive','group_compressed_SHA256','group_decoded_SHA256','CRC_EOF_verified'] if k in row}
            if text is not None:
                name=f'page-{row["selection"]["row_ordinal"]:08d}-{row["selection"]["page_id"]}.wikitext.utf8';write(name,text);record['exact_main_text_file']=name
            else:record['exact_main_text_file']=None
            records.append(record)
        if len(records)!=20:raise ValueError('all20outcomes')
        write('records.json',(json.dumps({'records':records,'no_rendering_or_admission':True},ensure_ascii=False,indent=2)+'\n').encode())
        verify(a);check()
        result={'status':'COMPLETE_EXACT20_NATIVE_MAIN_WIKITEXT_NO_ADMISSION','records':records,'exact_text_outputs':sum(r['exact_main_text_file'] is not None for r in records),'held_outputs':sum(r['exact_main_text_file'] is None for r in records),
            'artifacts':{q.name:{'bytes':q.stat().st_size,'SHA256':sha(q)} for q in out.iterdir() if q.is_file() and q.name not in SLOTS},
            'profile_SHA256':a.profile_sha256,'codepins_SHA256':a.codepins_sha256,'source_rawXML_total_bytes':sum(r['raw_XML_bytes'] for r in inputs['records']),
            'no_17GB_source_or_group_reads':True,'no_wikitext_rendering_rewrite_template_expansion':True,'new_admitted_documents':0,'new_admitted_tokens':0,'elapsed_shared_seconds':clock()-a.start}
        terminal(out,'result.json',result)
    except BaseException as e:
        if owned:terminal(out,'result.json',{'status':'PARTIAL_MAIN20_EXTRACTION_NO_RETRY','error':type(e).__name__+':'+str(e)[:1000],'new_admitted_documents':0})
        raise
    finally:signal.setitimer(signal.ITIMER_REAL,0)

def kill(child):
    if child.poll() is None:
        try:os.killpg(child.pid,signal.SIGKILL)
        except ProcessLookupError:pass
    child.wait(timeout=3)
def supervise(a):
    child=None;created=False;out=None;peak=0;old={}
    try:
        for sig in [signal.SIGALRM,signal.SIGTERM,signal.SIGINT]:old[sig]=signal.signal(sig,alarm)
        remain=START+40-clock()
        if remain<=0:raise TimeoutError('supervisor_preflight_expired')
        signal.setitimer(signal.ITIMER_REAL,remain);p,inputs=verify(a);out=Path(p['output']);size,helpers=dependencies(p)
        if out.exists() or out.is_symlink():raise ValueError('once_only_output')
        if size(ROOT)+16000000>64000000000 or shutil.disk_usage(ROOT).free<FREE+16000000:raise ValueError('initial_reserves')
        out.mkdir();created=True
        for n,cap in SLOTS.items():(out/n).write_bytes(b' '*cap)
        child=subprocess.Popen([sys.executable,'-B',str(HERE/'extract.py'),'--worker','--start',str(START),'--supervisor-pid',str(os.getpid()),'--profile-sha256',a.profile_sha256,'--codepins-sha256',a.codepins_sha256],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        own={'worker_PID':child.pid,'supervisor_PID':os.getpid(),'shared_start':START,'profile_SHA256':a.profile_sha256,'codepins_SHA256':a.codepins_sha256}
        with (out/'ownership.json').open('x') as f:json.dump(own,f);f.flush();os.fsync(f.fileno())
        while child.poll() is None:
            if clock()-START>=40:raise TimeoutError('external_deadline')
            rss=helpers.tree_rss(subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,check=True,timeout=1).stdout,os.getpid(),child.pid if child.poll() is None else None);peak=max(peak,rss)
            if peak>1000000000:raise ValueError('owned_RSS_cap')
            disk(out,0,size);time.sleep(.1)
        child.wait(timeout=3);verify(a);disk(out,0,size);r=json.loads((out/'result.json').read_text());ok=child.returncode==0 and r.get('status')=='COMPLETE_EXACT20_NATIVE_MAIN_WIKITEXT_NO_ADMISSION'
        terminal(out,'supervisor.json',{'status':'COMPLETE_EXACT_MAIN20_EXTRACTION_NO_ADMISSION' if ok else 'PARTIAL_MAIN20_EXTRACTION_NO_RETRY','worker_exit_code':child.returncode,'worker_reaped':True,'result_SHA256':sha(out/'result.json'),'elapsed_shared_seconds':clock()-START,'peak_tree_RSS_bytes':peak,'new_admitted_documents':0})
        return 0 if ok else 1
    except BaseException as e:
        signal.setitimer(signal.ITIMER_REAL,max(.001,START+45-clock()))
        if child is not None:kill(child)
        if created:terminal(out,'supervisor.json',{'status':'PARTIAL_MAIN20_EXTRACTION_NO_RETRY','worker_reaped':child is None or child.poll() is not None,'error':type(e).__name__+':'+str(e)[:1000],'new_admitted_documents':0})
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        for sig,handler in old.items():signal.signal(sig,handler)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--profile-sha256',required=True);p.add_argument('--codepins-sha256',required=True);p.add_argument('--execute',action='store_true');p.add_argument('--worker',action='store_true');p.add_argument('--start',type=float);p.add_argument('--supervisor-pid',type=int);a=p.parse_args()
    if a.worker:worker(a)
    elif a.execute:raise SystemExit(supervise(a))
    else:verify(a);print('READY_CODE_METADATA_STAT_ONLY_NO_RAWXML_PARSE')

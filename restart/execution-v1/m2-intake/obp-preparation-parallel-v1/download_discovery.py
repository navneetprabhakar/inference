"""One bounded OBP metadata/EPUB discovery attempt; explicit --execute required.
No network or ledger access at import. Must be dispatched by parent after global
ledger ownership is available. All source content remains unadmitted.
"""
import argparse,datetime,hashlib,json,os,shutil,signal,subprocess,sys,time
from pathlib import Path
import urllib.request
import zipfile
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit,unquote

HERE=Path(__file__).resolve().parent
EXEC=HERE.parents[1]
REPO=EXEC.parents[1]
sys.path.insert(0,str(REPO/'src'));sys.path.insert(0,str(EXEC))
from acquire_sources import ROOT,CONTRACT,IntakeLedger
from prepare_frame import evaluate,license_key
from inspect_epub import inspect,norm,OutputBudget

DEST=ROOT/'obp-discovery-pilot-v1'
TOTAL_CAP=29000000
META_CAP=1000000
EPUB_CAP=8000000
PROCESSED_CAP=100000000
TERMINAL_RESERVE=1000000
WALL=300

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise ValueError('Redirect refused; no implicit additional HTTP requests')

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(65536),b''):h.update(chunk)
    return h.hexdigest()

def write(path,value):
    payload=(json.dumps(value,indent=2,ensure_ascii=False)+'\n').encode()
    if Path(path).resolve().is_relative_to(DEST.resolve()):OutputBudget(DEST,PROCESSED_CAP).ensure(len(payload))
    with Path(path).open('xb') as f:
        f.write(payload);f.flush();os.fsync(f.fileno())

def storage(additional):
    policy=json.loads((EXEC/'disk-budget.json').read_text())
    total=0
    for base,dirs,files in os.walk(ROOT):
        for name in dirs+files:
            p=Path(base)/name
            if p.is_symlink():raise ValueError('Intake symlink refused')
        total+=sum((Path(base)/name).stat().st_size for name in files)
    # Conservative combined intake footprint charged against both storage caps.
    if total+additional>min(policy['raw_download_cap_bytes'],policy['processed_data_cap_bytes']):raise ValueError('Conservative intake storage ceiling')
    protected=policy['free_disk_floor_bytes']+policy['weights_checkpoints_reserved_bytes']+policy['scratch_cap_bytes']
    free=shutil.disk_usage(ROOT).free
    if free<protected+additional:raise ValueError('Weights/scratch/free floor headroom')
    return {'all_intake_bytes':total,'free_bytes':free,'protected_bytes':protected,'disk_policy_sha256':sha(EXEC/'disk-budget.json')}

def same_url(actual,expected):
    a=urlsplit(actual);e=urlsplit(expected)
    return a.scheme==e.scheme=='https' and a.netloc==e.netloc and unquote(a.path)==unquote(e.path) and a.query==e.query=='' and not a.fragment and not e.fragment

def transfer(ledger,key,url,path,cap,kind,started,spent,opener=None):
    if cap<=0 or spent+cap>TOTAL_CAP:raise ValueError('Per-run response body budget')
    path=Path(path);partial=path.with_name(path.name+'.partial')
    if path.exists() or partial.exists():raise FileExistsError('Payload already exists; no replay')
    headroom=storage(cap+PROCESSED_CAP)
    OutputBudget(DEST if path.resolve().is_relative_to(DEST.resolve()) else path.parent,PROCESSED_CAP).ensure(cap+TERMINAL_RESERVE)
    ledger.reserve(key,requests=1,body_bytes=cap,output_bytes=cap)
    count=0;response_headers={};began=time.monotonic()
    try:
        request=urllib.request.Request(url,headers={'User-Agent':'EnglishSLM-research-source-audit/1.0','Accept-Encoding':'identity'})
        opener=opener or urllib.request.build_opener(NoRedirect())
        with opener.open(request,timeout=20) as response,partial.open('xb') as output:
            if not same_url(response.geturl(),url):raise ValueError('Unpinned response URL')
            if response.headers.get('Content-Encoding') not in (None,'identity'):raise ValueError('Unexpected body encoding')
            content_length=response.headers.get('Content-Length')
            if content_length is not None and (int(content_length)<0 or int(content_length)>=cap):raise ValueError('Response length reaches cap')
            mime=response.headers.get('Content-Type','').split(';')[0].strip().lower()
            allowed={'application/json','text/plain','application/octet-stream'} if kind=='metadata' else {'application/epub+zip','application/octet-stream','application/zip','application/x-zip-compressed'}
            if mime not in allowed:raise ValueError('Unexpected MIME type')
            response_headers={k:response.headers.get(k) for k in ['Content-Type','Content-Length','ETag','Last-Modified']}
            while count<cap:
                if time.monotonic()-started>=WALL:raise TimeoutError('Global worker deadline')
                ledger.check_time()
                if shutil.disk_usage(ROOT).free<headroom['protected_bytes']+65536:raise ValueError('Protected disk floor reached')
                chunk=response.read(min(65536,cap-count))
                if not chunk:break
                OutputBudget(DEST if path.resolve().is_relative_to(DEST.resolve()) else path.parent,PROCESSED_CAP).ensure(len(chunk)+TERMINAL_RESERVE)
                count+=len(chunk);output.write(chunk);output.flush()
            if count>=cap:raise ValueError('Response hit cap; refused without unreserved EOF probe')
            if content_length is not None and count!=int(content_length):raise ValueError('Truncated response')
            output.flush();os.fsync(output.fileno())
        raw=partial.read_bytes()
        if kind=='metadata':json.loads(raw)
        elif not raw.startswith(b'PK\x03\x04'):raise ValueError('EPUB ZIP signature missing')
        # Small per-file caps allow ordinary ledger completion, no custom DB updates.
        ledger.finish(key,raw=raw)
        os.rename(partial,path)
        directory_fd=os.open(path.parent,os.O_RDONLY)
        try:os.fsync(directory_fd)
        finally:os.close(directory_fd)
        return {'key':key,'url':url,'file':str(path),'body_bytes':count,'body_sha256':hashlib.sha256(raw).hexdigest(),'response_headers':response_headers,'elapsed_seconds':time.monotonic()-began,'body_reservation':cap,'storage_preflight':headroom}
    except BaseException as error:
        row=ledger.db.execute('SELECT state FROM attempts WHERE key=?',(key,)).fetchone()
        if row and row[0]=='pending':ledger.finish(key,raw=None)
        write(path.with_name(path.name+'.failure.json'),{'status':'FAILED_NO_RETRY','url':url,'key':key,'received_body_bytes':count,'reserved_body_bytes':cap,'error_type':type(error).__name__,'error':str(error),'partial_path':str(partial),'response_headers':response_headers})
        raise

def validate_metadata(record,item):
    row,reasons=evaluate(record)
    if row is None:raise ValueError('Metadata candidate refused: '+','.join(reasons))
    if row['work_id']!=item['work_id'] or row['family']!=item['doi'].lower() or row['epub_url']!=item['native_epub_url_observed_in_primary_locations']:raise ValueError('Pinned UUID/DOI/native EPUB differs')
    if license_key(record['license'])!=license_key(item['observed_work_license']):raise ValueError('Pinned work license differs')
    if record.get('publicationDate')!=item['publication_date']:raise ValueError('Pinned publication date differs')
    if norm(record.get('copyrightHolder',''))!=norm('; '.join(item['authors'])):raise ValueError('Pinned copyright holder differs')
    epubs=[p for p in record['publications'] if p.get('publicationType')=='EPUB']
    if len(epubs)!=1 or epubs[0].get('isbn')!=item['epub_isbn']:raise ValueError('Pinned EPUB ISBN differs')
    generated=record.get('jsonGeneratedAt')
    if not generated:raise ValueError('Export generation timestamp required')
    stamp=datetime.datetime.fromisoformat(generated.replace('Z','+00:00'))
    if stamp.tzinfo is None or stamp>datetime.datetime.now(datetime.timezone.utc):raise ValueError('Invalid export version timestamp')
    return {'work_uuid':row['work_id'],'doi':row['doi'],'edition':record.get('edition'),'export_generated_at':generated,'publication_date':record.get('publicationDate'),'license':record['license'],'copyright_holder':record['copyrightHolder'],'canonical_epub':row['epub_url'],'epub_isbn':epubs[0]['isbn'],'work_license_is_not_artifact_or_chapter_clearance':True}

def worker():
    if os.getppid()!=int(os.environ['OBP_DISCOVERY_PARENT_PID']):raise ValueError('Supervisor mismatch')
    plan=json.loads((HERE/'preparation.json').read_text());items=plan['initial_discovery']
    if len(items)!=3:raise ValueError('Exactly3fixed discovery works required')
    started=time.monotonic();spent=0;receipts=[];inspection_failures=[];ledger=None
    try:
        preflight=storage(TOTAL_CAP+PROCESSED_CAP)
        ledger=IntakeLedger(ROOT/'charges',CONTRACT)
        write(DEST/'preflight.json',{'status':'DISCOVERY_PREFLIGHT','local_response_body_cap':TOTAL_CAP,'planned_response_body_reservations':len(items)*(META_CAP+EPUB_CAP),'metadata_cap_each':META_CAP,'epub_cap_each':EPUB_CAP,'attempts_each':1,'storage':preflight,'global_ledger_before':ledger.totals(),'preparation_sha256':sha(HERE/'preparation.json'),'code_sha256':{name:sha(HERE/name) for name in ['download_discovery.py','inspect_epub.py','prepare_frame.py']},'trained_or_admitted':False})
        for item in items:
            stem=item['doi'].rsplit('.',1)[1].lower();prefix='obp-native-discovery-v1-'+stem
            meta=transfer(ledger,prefix+'-metadata',item['json_export_url'],DEST/(stem+'.metadata.json'),META_CAP,'metadata',started,spent);spent+=META_CAP;receipts.append(meta)
            record=json.loads(Path(meta['file']).read_bytes());binding=validate_metadata(record,item)
            write(DEST/(stem+'.metadata-binding.json'),binding)
            epub=transfer(ledger,prefix+'-epub',binding['canonical_epub'],DEST/(stem+'.epub'),EPUB_CAP,'epub',started,spent);spent+=EPUB_CAP;receipts.append(epub)
            expected={'doi':item['doi'],'authors':item['authors'],'license':binding['license'],'epub_isbn':item['epub_isbn'],'metadata_sha256':meta['body_sha256'],'metadata_generated_at':binding['export_generated_at'],'work_id':item['work_id']}
            try:
                inspection=inspect(epub['file'],DEST/(stem+'-inspection'),expected,budget_root=DEST,budget_cap=PROCESSED_CAP-TERMINAL_RESERVE)
            except (ValueError,KeyError,zipfile.BadZipFile,ET.ParseError) as error:
                failure={'work':item['doi'],'status':'ARCHIVE_INSPECTION_REFUSED_RETAIN_RAW','error_type':type(error).__name__,'error':str(error),'epub_sha256':epub['body_sha256'],'new_admitted_tokens':0,'retry':False}
                write(DEST/(stem+'.inspection-failure.json'),failure);inspection_failures.append(failure)
                print(json.dumps(failure),flush=True)
                continue
            if sum(p.stat().st_size for p in DEST.rglob('*') if p.is_file())>PROCESSED_CAP:raise ValueError('Discovery output ceiling')
            print(json.dumps({'work':item['doi'],'downloaded_bytes':sum(r['body_bytes'] for r in receipts),'spine_items':len(inspection['spine_order']),'manual_review_flags':inspection['review_flags'],'admitted':False}),flush=True)
        write(DEST/'result.json',{'status':'DISCOVERY_TRANSFERS_COMPLETE_INSPECTION_REFUSALS' if inspection_failures else 'THREE_DISCOVERY_ARCHIVES_INSPECTED_REVIEW_PENDING','inspection_failures':inspection_failures,'transfers':receipts,'actual_successful_body_bytes':sum(x['body_bytes'] for x in receipts),'local_reserved_body_bytes':spent,'global_ledger_after':ledger.totals(),'global_actual_successful_body_bytes':ledger.db.execute('SELECT coalesce(sum(actual_bytes),0) FROM attempts').fetchone()[0],'elapsed_seconds':time.monotonic()-started,'training_started':False,'new_admitted_documents':0,'new_admitted_tokens':0,'scope':'No text quality/rights acceptance; full original XML/HTML preserved for discovery review.'})
    except BaseException as error:
        write(DEST/'failure.json',{'status':'FAILED_NO_RETRY','error_type':type(error).__name__,'error':str(error),'successful_transfers':receipts,'worker_elapsed_seconds':time.monotonic()-started,'ledger_after':ledger.totals() if ledger else None,'new_admitted_tokens':0})
        raise
    finally:
        if ledger:ledger.close()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    if not args.execute:
        print(json.dumps({'status':'OFFLINE_READY_NOT_EXECUTED','output_dir':str(DEST),'response_body_cap':TOTAL_CAP,'require_parent_dispatch_after_ledger_available':True}));return
    DEST.mkdir(exist_ok=False)
    environment=dict(os.environ,OBP_DISCOVERY_PARENT_PID=str(os.getpid()))
    child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--worker'],env=environment,start_new_session=True)
    write(DEST/'supervisor-start.json',{'pid':child.pid,'parent_pid':os.getpid(),'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'worker_max_seconds':WALL,'external_seconds':WALL+30,'retry':False})
    timeout=False;began=time.monotonic()
    try:code=child.wait(timeout=WALL+30)
    except subprocess.TimeoutExpired:
        timeout=True;os.killpg(child.pid,signal.SIGTERM)
        try:code=child.wait(timeout=5)
        except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);code=child.wait()
    write(DEST/'supervisor-result.json',{'status':'COMPLETE' if code==0 else 'FAILED','exit_code':code,'external_timeout':timeout,'elapsed_seconds':time.monotonic()-began,'partial_files':[{'path':str(p),'bytes':p.stat().st_size} for p in DEST.glob('*.partial')],'pending_ledger_charges_remain_conservative':True,'automatic_retry':False})
    raise SystemExit(code if code>=0 else 1)

if __name__=='__main__':
    worker() if sys.argv[1:]==['--worker'] else main()

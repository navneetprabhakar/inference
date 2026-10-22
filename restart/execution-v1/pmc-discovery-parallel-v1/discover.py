"""Bounded native PMC OAI/JATS discovery; no admission or model operations.
Import/offline mode performs no network and does not open the global ledger.
"""
import argparse,datetime,hashlib,importlib.util,json,os,re,shutil,signal,subprocess,sys,time,zlib
from pathlib import Path
from urllib.parse import urlencode,urlsplit
import urllib.request
from lxml import etree

HERE=Path(__file__).resolve().parent;EXEC=HERE.parent;REPO=EXEC.parents[1]
sys.path.insert(0,str(REPO/'src'));sys.path.insert(0,str(EXEC))
from acquire_sources import ROOT,CONTRACT,IntakeLedger
PREP=EXEC/'pmc-preparation-parallel-v1/prepare.py'
spec=importlib.util.spec_from_file_location('frozen_pmc_preparation',PREP);pmc=importlib.util.module_from_spec(spec);spec.loader.exec_module(pmc)
OBP=ROOT/'obp-preparation-parallel-v1';sys.path.insert(0,str(OBP))
from inspect_epub import OutputBudget
BASE='https://pmc.ncbi.nlm.nih.gov/api/oai/v1/mh/'
DEST=ROOT/'pmc-native-discovery-pilot-v1'
BODY_CAP=20000000;RESPONSE_CAP=4000000;DECODED_CAP=8*1024**2
OUTPUT_CAP=100000000;TERMINAL_RESERVE=1000000
MAX_PAGES=5;MAX_RECORDS=100;WORKER_SECONDS=570;EXTERNAL_SECONDS=600
SCOPE={'from':'2026-01-01','until':'2026-01-03'}

def sha(data):return hashlib.sha256(data).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc)
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise ValueError('No implicit redirect or extra HTTP request')

def save(path,data,reserve=0):
    path=Path(path);payload=data if isinstance(data,bytes) else (json.dumps(data,indent=2,ensure_ascii=False)+'\n').encode()
    budget=OutputBudget(DEST,OUTPUT_CAP);budget.ensure(len(payload)+reserve)
    budget.write(path,payload)

def check_time(started):
    if time.monotonic()-started>=WORKER_SECONDS:raise TimeoutError('Discovery worker deadline')

def storage(additional):
    policy=json.loads((EXEC/'disk-budget.json').read_text());footprint=0
    for base,dirs,files in os.walk(ROOT):
        for name in dirs+files:
            if (Path(base)/name).is_symlink():raise ValueError('Intake symlink')
        footprint+=sum((Path(base)/name).stat().st_size for name in files)
    if footprint+additional>min(policy['raw_download_cap_bytes'],policy['processed_data_cap_bytes']):raise ValueError('Conservative combined storage ceiling')
    protected=policy['free_disk_floor_bytes']+policy['weights_checkpoints_reserved_bytes']+policy['scratch_cap_bytes']
    free=shutil.disk_usage(ROOT).free
    if free<protected+additional:raise ValueError('Weights/scratch/free floor reservation')
    return {'free_bytes':free,'protected_bytes':protected,'all_intake_bytes':footprint,'policy_sha256':sha((EXEC/'disk-budget.json').read_bytes())}

def decode(wire,encoding,limit=DECODED_CAP):
    if encoding in (None,'','identity'):
        if len(wire)>limit:raise ValueError('Decoded response cap')
        return wire
    if encoding not in {'gzip','deflate'}:raise ValueError('Unsupported response encoding')
    decoder=zlib.decompressobj(31 if encoding=='gzip' else 15)
    plain=decoder.decompress(wire,limit+1)
    if len(plain)>limit or decoder.unconsumed_tail:raise ValueError('Decoded response cap')
    if not decoder.eof or decoder.unused_data:raise ValueError('Incomplete or concatenated compressed stream')
    return plain

def fetch(ledger,guard,q,index,started,charged,opener=None):
    if charged+RESPONSE_CAP>BODY_CAP:raise ValueError('Local20MBresponse cap')
    if pmc.query(BASE+'?'+urlencode(q))!=q:raise ValueError('Request query mismatch')
    check_time(started);headroom=storage(RESPONSE_CAP+OUTPUT_CAP)
    budget=OutputBudget(DEST,OUTPUT_CAP);budget.ensure(RESPONSE_CAP+TERMINAL_RESERVE)
    # Serial spacing covers all attempts, including eventual failures.
    if guard.last_start is not None:
        delay=max(0.0,1.0-(time.monotonic()-guard.last_start))
        if delay:time.sleep(delay)
    request_state=guard.start(time.monotonic(),now());key=f'pmc-native-oai-discovery-v1-page-{index:03d}'
    ledger.reserve(key,requests=1,body_bytes=RESPONSE_CAP,rows=10,output_bytes=OUTPUT_CAP if index==0 else 0)
    save(DEST/f'request-{index:03d}.json',{'key':key,'url':BASE+'?'+urlencode(q),'query':q,'guard':request_state,'reserved_response_body_bytes':RESPONSE_CAP,'local_scope':SCOPE,'charged_before_io':True},TERMINAL_RESERVE)
    wire=bytearray();partial=DEST/f'response-{index:03d}.body.partial';headers={}
    try:
        opener=opener or urllib.request.build_opener(NoRedirect())
        request=urllib.request.Request(BASE+'?'+urlencode(q),headers={'User-Agent':'EnglishSLM-source-discovery/1.0','Accept-Encoding':'gzip, deflate'})
        with opener.open(request,timeout=20) as response,partial.open('xb') as handle:
            if response.geturl()!=request.full_url:raise ValueError('Unpinned response URL')
            mime=response.headers.get('Content-Type','').split(';')[0].lower().strip()
            if mime not in {'text/xml','application/xml','application/oai-pmh+xml'}:raise ValueError('NonXML response or access block')
            length=response.headers.get('Content-Length')
            if length is not None and (int(length)<0 or int(length)>=RESPONSE_CAP):raise ValueError('Response ContentLength reaches bound')
            headers={k:response.headers.get(k) for k in ['Content-Type','Content-Length','Content-Encoding','ETag','Last-Modified']}
            while len(wire)<RESPONSE_CAP:
                check_time(started);ledger.check_time()
                if shutil.disk_usage(ROOT).free<headroom['protected_bytes']+65536:raise ValueError('Protected disk floor')
                chunk=response.read(min(65536,RESPONSE_CAP-len(wire)))
                if not chunk:break
                budget.ensure(len(chunk)+TERMINAL_RESERVE);wire.extend(chunk);handle.write(chunk);handle.flush()
            if len(wire)>=RESPONSE_CAP:raise ValueError('Response hits cap, no unreserved EOF probe')
            if length is not None and int(length)!=len(wire):raise ValueError('Truncated response')
            handle.flush();os.fsync(handle.fileno())
        raw=bytes(wire);ledger.finish(key,raw=raw)
        rawpath=DEST/f'response-{index:03d}.body';os.rename(partial,rawpath)
        plain=decode(raw,headers.get('Content-Encoding'));save(DEST/f'response-{index:03d}.xml',plain,TERMINAL_RESERVE)
        receipt={'key':key,'request_url':request.full_url,'query':q,'body_bytes':len(raw),'body_sha256':sha(raw),'decoded_bytes':len(plain),'decoded_sha256':sha(plain),'headers':headers,'response_file':str(rawpath),'decoded_file':str(DEST/f'response-{index:03d}.xml'),'guard':request_state}
        save(DEST/f'response-{index:03d}.receipt.json',receipt,TERMINAL_RESERVE)
        return plain,receipt
    except BaseException as error:
        row=ledger.db.execute('SELECT state FROM attempts WHERE key=?',(key,)).fetchone()
        if row and row[0]=='pending':ledger.finish(key,raw=None)
        save(DEST/f'response-{index:03d}.failure.json',{'status':'FAILED_NO_RETRY','key':key,'query':q,'received_body_bytes':len(wire),'body_cap_charge':RESPONSE_CAP,'headers':headers,'error_type':type(error).__name__,'error':str(error)})
        raise
    finally:guard.finish()

def parse(plain,q,index):
    if b'\x00' in plain or re.search(br'<!\s*(?:DOCTYPE|ENTITY)',plain,re.I):raise ValueError('XML entities,DTD,UTF16/32 refused')
    rows,token,response_date=pmc.parse_response(plain,f'response-{index:03d}.xml',q)
    if len(rows)>10:raise ValueError('Unexpected OAI page cardinality')
    if len(token)>4096:raise ValueError('Unbounded cursor')
    parser=etree.XMLParser(resolve_entities=False,no_network=True,load_dtd=False,huge_tree=False)
    root=etree.fromstring(plain,parser);listing=root.find('{'+pmc.OAI+'}ListRecords')
    records=listing.findall('{'+pmc.OAI+'}record')
    extras=[]
    for row,record in zip(rows,records):
        if not SCOPE['from']<=row['oai_datestamp'][:10]<=SCOPE['until']:raise ValueError('OAI datestamp outside frozen interval')
        md=record.find('{'+pmc.OAI+'}metadata');articles=[] if md is None else [x for x in md if pmc.local(x)=='article']
        if not articles:
            row['metadata_filter_eligible']=False
            row['holds']=sorted(set(row.get('holds',[])+['no_full_JATS_article_held']))
            row['eligibility_scope']='PRE_LOCAL_FAMILY_CHECKS_HELD_NO_ARTICLE'
            row['raw_fulltext_not_admitted']=True
            extras.append(None);continue
        article=articles[0];front=pmc.one(article,'front');meta=pmc.one(front,'article-meta');bodies=pmc.children(article,'body')
        author_names=[]
        for contrib in pmc.descendants(meta,'contrib'):
            if contrib.get('contrib-type')!='author':continue
            author_names += [pmc.text(x) for x in contrib if pmc.local(x) in {'name','string-name'} and pmc.text(x)]
        if not author_names:row['holds'].append('no_named_person_author_metadata')
        for license_url in row['permission_review']['observed_license_uris']:
            u=urlsplit(license_url)
            if u.username or u.password or u.port:row['holds'].append('ambiguous_license_uri_credentials_or_port')
        if re.match(r'(?i)^(?:retraction|withdrawal|correction|erratum|expression of concern)\b',row.get('title','')):row['holds'].append('title_correction_or_retraction_requires_review')
        if len(bodies)!=1:row['holds'].append('missing_or_multiple_full_article_bodies')
        dependencies=[pmc.local(n) for n in article.iter() if pmc.local(n) in {'fig','table-wrap','disp-formula','inline-formula','supplementary-material','sub-article'}]
        body_text=pmc.text(bodies[0]) if len(bodies)==1 else ''
        row.update({'named_author_metadata':author_names,'authorship_scope':'Publisher named-person authorship metadata only; human composition and AI assistance history are not independently certified.','fulltext_body_characters':len(body_text),'structured_dependency_counts':{name:dependencies.count(name) for name in sorted(set(dependencies))},'retraction_status':'Only observed JATS article-type,related-links and frozen-frame connected risk checked; outside-frame updates/retractions remain unresolved.','body_readability_review':'PENDING_FULL_DOCUMENT_REVIEW','rights_scope':'Article and object permission fields inspected by metadata filter, but separately attributed quotations/objects and fulltext exceptions remain review gates.','metadata_filter_eligible':not row['holds'],'eligibility_scope':'PRE_LOCAL_FAMILY_CHECKS_NOT_FINAL','source_original_decoded_response_sha256':sha(plain),'article_serialization_is_derivative_not_original_response':True,'raw_fulltext_not_admitted':True})
        # Diagnostic rendering only, never a candidate training document.
        preview='[DISCOVERY DIAGNOSTIC: flattened JATS body; figures/math/tables require original XML review; NOT TRAINING DATA]\n'+row.get('title','')+'\n\n'+body_text+'\n'
        extras.append({'article_xml':etree.tostring(article,encoding='utf-8'),'diagnostic_preview':preview.encode()})
    return rows,extras,token,response_date

def finalize(rows):
    pmc.family_assign(rows)
    for row in rows:
        row['metadata_filter_eligible']=not row.get('holds',[])
        row['eligibility_scope']='POST_OBSERVED_LOCAL_FAMILY_CHECKS_NO_EXTERNAL_STATUS_CLEARANCE'
    return rows

def pins():
    ready=json.loads((HERE/'ready.json').read_text())
    for path,expected in ready['input_code_sha256'].items():
        if sha(Path(path).read_bytes())!=expected:raise ValueError('Pinned code or policy changed')
    return ready

def worker():
    if os.getppid()!=int(os.environ['PMC_DISCOVERY_PARENT_PID']):raise ValueError('Supervisor parent mismatch')
    ready=pins();started=time.monotonic();ledger=None;rows=[];sources=[];seen=set();token=None;charged=0
    try:
        disk=storage(BODY_CAP+OUTPUT_CAP);ledger=IntakeLedger(ROOT/'charges',CONTRACT)
        guard=pmc.SerialRequestGuard(planned_requests=MAX_PAGES)
        save(DEST/'preflight.json',{'status':'PINNED_LOCAL_DISCOVERY_ONLY','ready_sha256':sha((HERE/'ready.json').read_bytes()),'source_protocol_evidence':ready['official_sources'],'scope':SCOPE,'limits':ready['limits'],'storage':disk,'global_reserved_before':ledger.totals(),'no_admission':True})
        q={'verb':'ListRecords','metadataPrefix':'pmc','set':'pmc-open',**SCOPE}
        for index in range(MAX_PAGES):
            plain,source=fetch(ledger,guard,q,index,started,charged);charged+=RESPONSE_CAP;sources.append(source)
            new,extras,token,response_date=parse(plain,q,index)
            for row in new:
                if row['pmcid'] in seen:raise ValueError('Duplicate or moving OAI record requires reconciliation')
                seen.add(row['pmcid'])
            if len(rows)+len(new)>MAX_RECORDS:raise ValueError('100record cap')
            payloads=[]
            for row,extra in zip(new,extras):
                if extra:
                    row['serialized_article_sha256']=sha(extra['article_xml'])
                    payloads.extend([(DEST/f"PMC{row['pmcid']}.article.xml",extra['article_xml']),(DEST/f"PMC{row['pmcid']}.diagnostic.txt",extra['diagnostic_preview'])])
            OutputBudget(DEST,OUTPUT_CAP).ensure(sum(len(raw) for _,raw in payloads)+TERMINAL_RESERVE)
            for path,raw in payloads:save(path,raw,TERMINAL_RESERVE)
            rows+=new
            save(DEST/f'page-{index:03d}.records.json',{'response_date':response_date,'rows':new,'resumption_token':token,'records_seen':len(rows),'frame_complete_for_interval':not token,'eligibility_scope':'PRE_CROSSRECORD_LOCAL_FAMILY_CHECKS; records.jsonl is final authority','no_admission':True},TERMINAL_RESERVE)
            print(json.dumps({'page':index,'records':len(rows),'metadata_eligible_before_crossrecord_family_checks':sum(r['metadata_filter_eligible'] for r in rows),'cursor_remaining':bool(token),'successful_wire_bytes':sum(x['body_bytes'] for x in sources)}),flush=True)
            if not token:break
            q={'verb':'ListRecords','resumptionToken':token}
        finalize(rows)
        save(DEST/'records.jsonl',(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in rows)).encode(),TERMINAL_RESERVE)
        save(DEST/'result.json',{'status':'BOUNDED_NATIVE_JATS_DISCOVERY_NO_ADMISSION','scope':SCOPE,'records_observed':len(rows),'metadata_filter_eligible_after_local_family_checks':sum(r['metadata_filter_eligible'] for r in rows),'source_responses':sources,'resumption_token_remaining':token,'frame_complete_for_declared_interval':not token,'incomplete_prefix_is_not_sampling_frame':bool(token),'sourcewide_or_statistical_quality_claim':False,'successful_body_bytes':sum(x['body_bytes'] for x in sources),'reserved_body_bytes':charged,'request_count':guard.count,'global_reserved_after':ledger.totals(),'global_successful_body_bytes':ledger.db.execute('SELECT coalesce(sum(actual_bytes),0) FROM attempts').fetchone()[0],'new_admitted_documents':0,'new_admitted_tokens':0,'models_initialized':0,'elapsed_seconds':time.monotonic()-started,'pending':['Full representative semantic review from a complete frozen frame','Fulltext/object/quotation rights and attribution review','External correction/retraction status reconciliation','Human-authorship/synthetic ancestry investigation','language/dedup/protected/family/split/token gates']})
    except BaseException as error:
        save(DEST/'failure.json',{'status':'TERMINAL_FAILED_NO_RETRY','error_type':type(error).__name__,'error':str(error),'successful_responses':sources,'records_observed_before_failure':len(rows),'global_reserved_after':ledger.totals() if ledger else None,'elapsed_seconds':time.monotonic()-started,'new_admitted_tokens':0})
        raise
    finally:
        if ledger:ledger.close()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true');args=parser.parse_args();ready=pins()
    if not args.execute:print(json.dumps({'status':'READY_NOT_EXECUTED','limits':ready['limits'],'output':str(DEST)}));return
    DEST.mkdir(exist_ok=False);env=dict(os.environ,PMC_DISCOVERY_PARENT_PID=str(os.getpid()))
    child=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--worker'],env=env,start_new_session=True)
    save(DEST/'supervisor-start.json',{'pid':child.pid,'parent_pid':os.getpid(),'utc':now().isoformat(),'external_timeout_seconds':EXTERNAL_SECONDS,'worker_seconds':WORKER_SECONDS,'no_retry':True})
    timed_out=False;started=time.monotonic()
    try:code=child.wait(timeout=EXTERNAL_SECONDS)
    except subprocess.TimeoutExpired:
        timed_out=True;os.killpg(child.pid,signal.SIGTERM)
        try:code=child.wait(timeout=5)
        except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);code=child.wait()
    save(DEST/'supervisor-result.json',{'status':'COMPLETE' if code==0 else 'FAILED','worker_exit_code':code,'external_timeout':timed_out,'elapsed_seconds':time.monotonic()-started,'pending_charges_remain_conservative':True,'retry':False})
    raise SystemExit(code if code>=0 else 1)
if __name__=='__main__':worker() if sys.argv[1:]==['--worker'] else main()

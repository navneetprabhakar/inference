"""Serial, explicit-hop HTTPS transport. Signed query strings never persisted."""
import hashlib
import json
import os
from pathlib import Path
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

HOSTS={'huggingface.co','us.aws.cdn.hf.co','us.gcp.cdn.hf.co','cdn-lfs-us-1.hf.co',
       'cdn-lfs-eu-1.hf.co','cas-bridge.xethub.hf.co'}
CHUNK=1048576
HEADER=65536


class Fault(ValueError):
    """Only developer-authored fixed codes; never pass external exception text."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


def clock():return time.clock_gettime(time.CLOCK_MONOTONIC)


def url(value):
    try:
        if not isinstance(value,str) or len(value)>32768 or any(c.isspace() or unicodedata.category(c) in {'Cc','Cf'} for c in value):
            raise Fault('URL_characters_or_length')
        u=urllib.parse.urlsplit(value)
        if u.scheme!='https' or u.hostname not in HOSTS or u.port not in (None,443) or u.username is not None or u.password is not None or u.fragment:
            raise Fault('URL_HTTPS_exact_host_port_no_credentials_fragment')
        return u
    except Fault:raise
    except Exception:raise Fault('URL_parse_invalid') from None


def redact(value):
    # Even refused credential-bearing URLs are never returned verbatim.
    try:
        u=urllib.parse.urlsplit(value)
        return {'scheme':u.scheme,'host':u.hostname,'path_SHA256':hashlib.sha256(u.path.encode()).hexdigest(),
                'query_present':bool(u.query),'URL_SHA256':hashlib.sha256(value.encode()).hexdigest(),
                'userinfo_present':u.username is not None or u.password is not None,'query_retained':False}
    except Exception:return {'invalid_URL_redacted':True}


def safe_error(error):
    return str(error) if type(error) is Fault else type(error).__name__


def headers(response,item):
    raw=b''.join((k+': '+v+'\r\n').encode('latin1') for k,v in response.headers.items())
    h=response.headers
    receipt={'status':response.code,'header_bytes':len(raw),'headers_SHA256':hashlib.sha256(raw).hexdigest(),
             'effective_URL':redact(response.geturl()),'Content_Length':None,'raw_headers_retained':False,
             'reason':'Signed Location/cookies/unknown values redacted; exact whole-header hash retained.',
             'repo_commit_header_present':bool(h.get_all('X-Repo-Commit',[])),
             'linked_hash_header_present':bool(h.get_all('X-Linked-Etag',[]))}
    try:
        if len(raw)>HEADER:raise Fault('aggregate_header_cap')
        length=h.get_all('Content-Length',[])
        if length:
            if len(length)!=1 or not length[0].isascii() or not length[0].isdigit() or len(length[0])>20:raise Fault('ContentLength_invalid_or_duplicate')
            receipt['Content_Length']=int(length[0])
        for name,expected in [('X-Repo-Commit',item['revision']),('X-Linked-Etag',item['expected_sha256'])]:
            values=h.get_all(name,[])
            if values and (len(values)!=1 or values[0] not in [expected,'"'+expected+'"']):
                raise Fault('repository_commit_or_linked_hash_mismatch')
        if h.get_all('Content-Encoding',[]) not in [[],['identity']] or h.get_all('Transfer-Encoding',[]):
            raise Fault('nonidentity_encoding_or_transfer_encoding')
        return receipt
    except Fault as e:
        e.headers_evidence=receipt
        raise


def acquire(item,destination,ledger,body_key,hop_keys,opener,check,save,state,arm_io):
    """Body charged once, requests once per physical GET; no implicit hops/retry.

    save receives only redacted metadata. Caller owns timeout/output/ledger and
    settles exact pending keys after any failure. No external exception string
    escapes into receipts or logs. One bounded EOF probe remains charged.
    """
    current=item['url'];path=Path(destination);response=None;n=0;digest=hashlib.sha256()
    receipt={'source_ordinal':item['ordinal'],'expected_bytes':item['expected_bytes'],
        'expected_SHA256':item['expected_sha256'],'body_key':body_key,'hops':[],
        'status':'PARTIAL_FILE_NO_RETRY','partial_bytes':0,'no_decompression':True}
    ledger.reserve(body_key,body_bytes=item['expected_bytes']+1,requests=0,output_bytes=0)
    try:
        for hop in range(3):
            check();url(current)
            while state['last_start'] is not None:
                check()
                remaining=1-(clock()-state['last_start'])
                if remaining<=0:break
                time.sleep(min(.05,remaining))
            check();key=hop_keys[hop];ledger.reserve(key,requests=1,body_bytes=0,output_bytes=0)
            record={'hop':hop,'key':key,'request_URL':redact(current),'request_precharged':True,
                    'status':'PENDING_PHYSICAL_GET','body_read':False}
            receipt['hops'].append(record);save('current-attempt.json',receipt,True)
            timeout=arm_io();state['last_start']=clock();record['start_monotonic']=state['last_start'];state['requests']+=1
            request=urllib.request.Request(current,headers={'Accept-Encoding':'identity','User-Agent':'EnglishSLM-research-source-audit/1.0'})
            try:response=opener.open(request,timeout=timeout)
            except urllib.error.HTTPError as e:response=e
            try:ev=headers(response,item)
            except Fault as e:
                record['headers']=getattr(e,'headers_evidence',{})
                raise
            record['headers']=ev
            if response.geturl()!=current:raise Fault('implicit_or_effective_URL_change')
            if response.code in (301,302,303,307,308):
                locations=response.headers.get_all('Location',[])
                if len(locations)!=1 or hop==2:raise Fault('redirect_count_or_location')
                next_url=urllib.parse.urljoin(current,locations[0]);record['redirect_target']=redact(next_url)
                url(next_url)
                response.close();response=None
                record.update(status='REDIRECT_HEADERS_ONLY_BODY_NOT_CONSUMED');ledger.finish(key,raw=b'')
                save(f'hop-{item["ordinal"]:03}-{hop}.json',record,False);current=next_url
                continue
            if response.code!=200:raise Fault('final_status_not200')
            if ev['Content_Length'] is not None and ev['Content_Length']!=item['expected_bytes']:
                raise Fault('final_declared_length_not_exact')
            path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('xb') as output:
                try:
                    while n<=item['expected_bytes']:
                        check();timeout=arm_io()
                        chunk=response.read1(min(CHUNK,item['expected_bytes']+1-n))
                        if not chunk:break
                        if len(chunk)>min(CHUNK,item['expected_bytes']+1-n):raise Fault('reader_return_overrequest')
                        if output.write(chunk)!=len(chunk):raise Fault('short_local_file_write')
                        n+=len(chunk);digest.update(chunk);receipt['partial_bytes']=n;receipt['partial_SHA256']=digest.hexdigest();record['body_read']=True
                        if n>item['expected_bytes']:raise Fault('extra_EOF_probe_byte_retained')
                finally:output.flush();os.fsync(output.fileno())
            response.close();response=None
            if n!=item['expected_bytes']:raise Fault('short_response_body')
            if digest.hexdigest()!=item['expected_sha256']:raise Fault('publisher_SHA256_mismatch')
            ledger.finish(key,raw=b'');record['status']='COMPLETE_EXACT200_FILE_RESPONSE'
            save(f'hop-{item["ordinal"]:03}-{hop}.json',record,False)
            receipt.update(status='COMPLETE_EXACT_BYTES_SHA256_RAW_FILE',bytes=n,SHA256=digest.hexdigest())
            return receipt
        raise Fault('unreachable_redirect_bound')
    except BaseException as error:
        receipt['error']=safe_error(error);receipt['partial_bytes']=n;receipt['partial_SHA256']=digest.hexdigest()
        save('current-attempt.json',receipt,True)
        raise Fault('file_attempt_terminal_no_retry') from None
    finally:
        if response is not None:response.close()

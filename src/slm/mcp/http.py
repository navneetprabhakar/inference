"""Bounded, endpoint-pinned Streamable HTTP for the official SDK session engine."""
from contextlib import asynccontextmanager,suppress
import hashlib
import ipaddress
import json
import math
import os
import re
import ssl
import anyio
import httpx2
from mcp.client.streamable_http import streamable_http_client
from slm.data.schema import digest
from slm.mcp.transport import wire_json


class HTTPBoundary(ValueError):pass


def endpoint(value,allow_loopback_http=False):
    if type(allow_loopback_http) is not bool:raise ValueError('Loopback HTTP requires a boolean opt-in')
    if not isinstance(value,str) or len(value)>2048 or any(ord(v)<33 for v in value):raise ValueError('Explicit bounded endpoint URL required')
    url=httpx2.URL(value)
    if url.username or url.password or url.query or url.fragment or not url.host:raise ValueError('Endpoint cannot embed credentials, query or fragment')
    if url.scheme=='http':
        try:local=ipaddress.ip_address(url.host).is_loopback
        except ValueError:local=False
        if not allow_loopback_http or not local:raise ValueError('Plain HTTP requires explicit numeric-loopback opt-in')
    elif url.scheme!='https':raise ValueError('HTTPS endpoint required outside explicit loopback fixtures')
    return url


class _Body(httpx2.AsyncByteStream):
    def __init__(self,owner,response,sse=False):
        self.owner=owner;self.response=response;self.sse=sse;self.buffer=bytearray();self.data=[];self.event='message';self.closed=False;self.received=0
    def _sse_check(self,chunk):
        self.buffer.extend(chunk)
        while (end:=self.buffer.find(b'\n'))>=0:
            line=bytes(self.buffer[:end]).rstrip(b'\r');del self.buffer[:end+1]
            if not line:
                if self.data:
                    payload=b'\n'.join(self.data)
                    if payload:wire_json(payload)
                    self.owner.stats['sse_events']+=1
                self.data=[];self.event='message'
            elif line.startswith(b'data:'):self.data.append(line[5:].removeprefix(b' '))
            elif line.startswith(b'event:'):self.event=line[6:].strip().decode('utf-8')
        if len(self.buffer)>self.owner.max_response_bytes:raise HTTPBoundary('SSE line exceeds byte budget')
    async def __aiter__(self):
        try:
            async for chunk in self.response.stream:
                self.received+=len(chunk);self.owner.stats['received_bytes']+=len(chunk)
                if self.received>self.owner.max_response_bytes or self.owner.stats['received_bytes']>self.owner.max_received_bytes:
                    raise HTTPBoundary('HTTP response/connection byte budget exceeded')
                if self.sse:self._sse_check(chunk)
                yield chunk
            if self.sse and (self.buffer or self.data):raise HTTPBoundary('Truncated SSE event')
        except BaseException as exc:
            if isinstance(exc,Exception):self.owner.fail(type(exc).__name__)
            raise
        finally:await self.aclose()
    async def aclose(self):
        if not self.closed:
            self.closed=True
            with anyio.CancelScope(shield=True):
                with anyio.move_on_after(1):await self.response.aclose()
            self.owner.stats['open_responses']-=1


class _Network(httpx2.AsyncBaseTransport):
    def __init__(self,owner):
        self.owner=owner
        self.inner=httpx2.AsyncHTTPTransport(verify=owner._verify,trust_env=False,retries=0,
            limits=httpx2.Limits(max_connections=4,max_keepalive_connections=2))
    async def handle_async_request(self,request):
        o=self.owner
        if o._failed:
            o.stats['blocked_requests']+=1
            raise HTTPBoundary('HTTP connection invalidated; explicit reopen required')
        if request.url!=o.url or request.method not in ('POST','GET','DELETE'):
            o.stats['blocked_requests']+=1;o.fail('endpoint_or_method');raise HTTPBoundary('Request would leave configured endpoint/method profile')
        if 'last-event-id' in request.headers or (request.method=='GET' and request.headers.get('mcp-protocol-version','').startswith('2026')):
            o.stats['blocked_requests']+=1;o.fail('resumption');raise HTTPBoundary('SSE replay/resumption is disabled')
        if o.stats['requests_forwarded']>=o.max_requests:o.fail('request_budget');raise HTTPBoundary('HTTP request budget exceeded')
        if request.method=='POST':
            body=request.content
            if len(body)>o.max_response_bytes:o.fail('request_bytes');raise HTTPBoundary('HTTP request exceeds byte budget')
            msg=wire_json(body).message
            if getattr(msg,'method',None)=='tools/call':
                id_=msg.id;key=(type(id_).__name__,id_)
                if key in o._tool_ids:o.fail('tool_replay');raise HTTPBoundary('Repeated tool POST ID refused')
                o._tool_ids.add(key);o.stats['tool_posts_forwarded']+=1
        o.stats['requests_forwarded']+=1
        o.stats['methods'][request.method]=o.stats['methods'].get(request.method,0)+1
        try:response=await self.inner.handle_async_request(request)
        except BaseException as exc:
            if isinstance(exc,Exception):o.fail(type(exc).__name__)
            raise
        o.stats['last_status']=response.status_code
        headers=sum(len(k)+len(v) for k,v in response.headers.raw)
        try:
            if headers>16384:raise HTTPBoundary('HTTP response header budget exceeded')
            if 300<=response.status_code<400:o.fail('redirect');raise HTTPBoundary('Redirects are disabled; configure the final endpoint explicitly')
            if response.status_code in (401,403):o.fail('authorization');raise HTTPBoundary('Configured HTTP authorization was rejected')
            if response.headers.get('content-encoding','identity').lower() not in ('','identity'):
                o.fail('compression');raise HTTPBoundary('Compressed MCP responses are not supported by the bounded reference')
            length=response.headers.get('content-length')
            if length is not None and int(length)>o.max_response_bytes:raise HTTPBoundary('Declared HTTP body exceeds byte budget')
            content_type=response.headers.get('content-type','').partition(';')[0].lower().strip()
            sse=content_type=='text/event-stream';o.stats['open_responses']+=1
            stream=_Body(o,response,sse)
            if content_type=='application/json':
                parts=[]
                async for part in stream:parts.append(part)
                body=b''.join(parts)
                if 200<=response.status_code<300 and body:wire_json(body)
                return httpx2.Response(response.status_code,headers=response.headers,content=body,extensions=response.extensions)
            return httpx2.Response(response.status_code,headers=response.headers,stream=stream,extensions=response.extensions)
        except BaseException as exc:
            if isinstance(exc,Exception):o.fail(type(exc).__name__)
            with anyio.CancelScope(shield=True):
                with anyio.move_on_after(1):await response.aclose()
            raise
    async def aclose(self):
        await self.inner.aclose();self.owner.stats['network_closed']=True


class BoundedHTTP:
    def __init__(self,url,*,allow_loopback_http=False,bearer_token_env=None,headers_env=None,ca_file=None,
                 timeout=5,max_response_bytes=131072,max_received_bytes=1048576,max_requests=256):
        if type(timeout) not in (int,float) or not math.isfinite(timeout) or not .1<=timeout<=30:raise ValueError('Bounded HTTP timeout required')
        self.url=endpoint(url,allow_loopback_http);self.timeout=timeout;self.ca_file=ca_file
        for v,low,high in [(max_response_bytes,1024,1048576),(max_received_bytes,1024,16777216),(max_requests,8,4096)]:
            if type(v) is not int or not low<=v<=high:raise ValueError('Invalid HTTP transport bounds')
        self.max_response_bytes=max_response_bytes;self.max_received_bytes=max_received_bytes;self.max_requests=max_requests
        self.headers={'Accept-Encoding':'identity'}
        if headers_env is not None and (not isinstance(headers_env,dict) or len(headers_env)>16):raise ValueError('Bounded header/environment mapping required')
        for key,var in (headers_env or {}).items():
            if (not isinstance(key,str) or not re.fullmatch('[A-Za-z][A-Za-z0-9-]{0,63}',key)
                or key.lower() in ('host','content-length','accept','accept-encoding','content-type','connection','cookie')
                or key.lower().startswith('mcp-')):raise ValueError('Host/protocol headers cannot be overridden')
            self.headers[key]=self._secret(var)
        if bearer_token_env:
            if any(k.lower()=='authorization' for k in self.headers):raise ValueError('Configure one authorization mechanism')
            self.headers['Authorization']='Bearer '+self._secret(bearer_token_env)
        if len({k.lower() for k in self.headers})!=len(self.headers):raise ValueError('Duplicate HTTP header names')
        if ca_file is not None and (not isinstance(ca_file,(str,os.PathLike)) or not os.path.isfile(ca_file)):raise ValueError('Explicit CA bundle file required')
        ca_hash=None;self._verify=True
        if ca_file is not None:
            with open(ca_file,'rb') as f:ca_bytes=f.read(4*1024*1024+1)
            if len(ca_bytes)>4*1024*1024:raise ValueError('CA bundle exceeds explicit byte limit')
            ca_hash=hashlib.sha256(ca_bytes).hexdigest()
            self._verify=ssl.create_default_context(cadata=ca_bytes.decode('ascii') if ca_bytes.startswith(b'-----BEGIN') else ca_bytes)
        self.identity_hash=digest({'url':str(self.url),'header_names':sorted(self.headers),'ca_bundle_sha256':ca_hash})
        self._failed=False;self._entered=False;self._tool_ids=set()
        self.stats={'kind':'streamable_http','endpoint_hash':self.identity_hash,'requests_forwarded':0,'tool_posts_forwarded':0,
            'received_bytes':0,'sse_events':0,'blocked_requests':0,'methods':{},'open_responses':0,'last_status':None,
            'failure':None,'network_closed':False,'http_client_closed':False,'header_names':sorted(self.headers),'tls_verification':self.url.scheme=='https','ca_bundle_sha256':ca_hash}
    @staticmethod
    def _secret(var):
        if not isinstance(var,str) or not re.fullmatch('[A-Za-z_][A-Za-z0-9_]{0,127}',var):raise ValueError('Explicit credential environment-variable name required')
        value=os.environ.get(var)
        if not value or len(value)>8192 or any(ord(v)<32 or ord(v)>126 for v in value):raise ValueError('Configured credential variable is missing or invalid')
        return value
    def fail(self,reason):
        self._failed=True
        if self.stats['failure'] is None:self.stats['failure']=reason
    def __call__(self):return self.connect()
    @asynccontextmanager
    async def connect(self):
        if self._entered:raise ValueError('HTTP transport cannot be reused')
        self._entered=True;network=_Network(self)
        client=httpx2.AsyncClient(transport=network,headers=self.headers,trust_env=False,follow_redirects=False,
            timeout=httpx2.Timeout(self.timeout),limits=httpx2.Limits(max_connections=4,max_keepalive_connections=2))
        try:
            async with streamable_http_client(str(self.url),http_client=client,max_sse_event_size=self.max_response_bytes) as streams:
                yield streams
        finally:
            with anyio.CancelScope(shield=True):
                with anyio.move_on_after(1):await client.aclose()
            self.stats['http_client_closed']=client.is_closed

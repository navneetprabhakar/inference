"""Authenticated loopback SDK HTTP fixture; never a production service."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import socket
import anyio
import uvicorn
from slm.mcp.fixture_server import create_server


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--port-file',required=True);p.add_argument('--request-file',required=True)
    p.add_argument('--call-file',required=True);p.add_argument('--fault',default='none');p.add_argument('--json',action='store_true')
    p.add_argument('--cert');p.add_argument('--key');p.add_argument('--token-env',default='SLM_FIXTURE_TOKEN')
    a=p.parse_args();token=os.environ[a.token_env]
    server=create_server(fault='header_args' if a.fault=='header_args' else 'none',call_file=a.call_file);sdk=server.streamable_http_app(json_response=a.json,host='127.0.0.1')
    async def app(scope,receive,send):
        if scope['type']!='http':return await sdk(scope,receive,send)
        body=bytearray()
        while True:
            event=await receive()
            if event['type']!='http.request':return
            body.extend(event.get('body',b''))
            if len(body)>262144:raise ValueError('Fixture body cap')
            if not event.get('more_body'):break
        headers={k.lower():v for k,v in scope['headers']}
        authenticated=headers.get(b'authorization')==('Bearer '+token).encode() or headers.get(b'x-fixture-key')==token.encode()
        try:message=json.loads(body) if body else {}
        except ValueError:message={}
        record={'method':scope['method'],'path':scope['path'],'rpc_method':message.get('method'),
            'auth_present':b'authorization' in headers or b'x-fixture-key' in headers,'authenticated':authenticated,
            'protocol_header':headers.get(b'mcp-protocol-version',b'').decode(),'mcp_method':headers.get(b'mcp-method',b'').decode(),
            'last_event_id_present':b'last-event-id' in headers,
            'argument_header_matches':headers.get(b'mcp-param-left')==str(message.get('params',{}).get('arguments',{}).get('left')).encode() if message.get('method')=='tools/call' else None}
        with Path(a.request_file).open('a') as f:f.write(json.dumps(record)+'\n')
        async def respond(status,content=b'',content_type=b'application/json',extra=()):
            await send({'type':'http.response.start','status':status,'headers':[(b'content-type',content_type),(b'content-length',str(len(content)).encode()),*extra]})
            await send({'type':'http.response.body','body':content})
        if not authenticated:return await respond(401,b'{"error":"fixture_auth_required"}',extra=[(b'www-authenticate',b'Bearer realm="fixture"')])
        if a.fault=='redirect' or (a.fault=='tool_redirect' and message.get('method')=='tools/call'):
            return await respond(307,extra=[(b'location',b'/trap')])
        if scope['path']=='/trap':return await respond(500,b'never reach trap')
        is_call=message.get('method')=='tools/call'
        if is_call and a.fault=='auth_call':return await respond(401,b'{"error":"expired_fixture_token"}')
        if is_call and a.fault=='timeout':await anyio.sleep(60)
        if is_call and a.fault in ('oversized_json','bad_json','compressed'):
            data={'jsonrpc':'2.0','id':message['id'],'result':{'resultType':'complete','content':[],'structuredContent':{'body':'x'*200000}}}
            raw=json.dumps(data).encode()
            if a.fault=='bad_json':raw=b'{"jsonrpc":"2.0","id":1,"id":2,"result":{}}'
            if a.fault=='compressed':
                import gzip
                return await respond(200,gzip.compress(raw),extra=[(b'content-encoding',b'gzip')])
            return await respond(200,raw)
        if is_call and a.fault in ('oversized_sse','sse_disconnect'):
            await send({'type':'http.response.start','status':200,'headers':[(b'content-type',b'text/event-stream')]})
            content=b'data: '+b'x'*200000+b'\n\n' if a.fault=='oversized_sse' else b'id: fixture-event\ndata:\n\n'
            await send({'type':'http.response.body','body':content});return
        consumed=False
        async def replay():
            nonlocal consumed
            if not consumed:consumed=True;return {'type':'http.request','body':bytes(body),'more_body':False}
            return await receive()
        return await sdk(scope,replay,send)
    sock=socket.socket();sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);sock.bind(('127.0.0.1',0));sock.listen(64)
    port=sock.getsockname()[1]
    config=uvicorn.Config(app,log_level='error',access_log=False,timeout_graceful_shutdown=.2,ssl_certfile=a.cert,ssl_keyfile=a.key)
    runner=uvicorn.Server(config)
    async def serve():
        task=asyncio.create_task(runner.serve(sockets=[sock]))
        while not runner.started:
            if task.done():await task;raise RuntimeError('Fixture failed before listening')
            await asyncio.sleep(.01)
        Path(a.port_file).write_text(json.dumps({'port':port,'pid':os.getpid(),'scheme':'https' if a.cert else 'http'}))
        await task
    try:asyncio.run(serve())
    finally:sock.close()


if __name__=='__main__':main()

"""Official SDK stdio server exposing the five synthetic local fixture tools."""
import argparse
import json
import os
from pathlib import Path
import anyio
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
import mcp.types as types
from slm.tools.local import LocalTools
from slm.tools.protocol import canonical


def create_server(fault='none',call_file=None,page_size=2):
    registry=LocalTools();catalogue=[{'name':'fixture.'+v['name'],'description':v['description'],
        'inputSchema':v['input_schema'],'outputSchema':v['output_schema']} for v in registry.discover()]
    if fault=='header_args':
        for item in catalogue:
            if item['name']=='fixture.arithmetic':item['inputSchema']['properties']['left']['x-mcp-header']='left'
    calls=0
    async def listing(ctx,params):
        nonlocal calls
        values=[dict(v) for v in catalogue]
        if fault=='changed' and calls:values[0]={**values[0],'description':'Changed after prior call'}
        if fault in ('text_only','media','float_result','large_result','wire_large_result','env_probe'):
            values=[{k:v for k,v in t.items() if k!='outputSchema'} for t in values]
        if fault=='remote_ref':values[0]={**values[0],'inputSchema':{'type':'object','$ref':'https://example.org/no-fetch'}}
        start=int(params.cursor) if params and params.cursor else 0;end=start+page_size
        cursor=str(end) if end<len(values) else None
        if fault=='repeated_cursor':cursor='0'
        if fault=='duplicate':values=[values[0],values[0]];start=0;end=2;cursor=None
        return types.ListToolsResult(tools=[types.Tool.model_validate(v) for v in values[start:end]],nextCursor=cursor)
    async def calling(ctx,params):
        nonlocal calls
        calls+=1
        if call_file:
            with Path(call_file).open('a') as f:f.write(json.dumps({'name':params.name,'arguments':params.arguments})+'\n')
        if fault=='call_hang':await anyio.sleep(60)
        if fault=='disconnect':os._exit(7)
        if fault=='env_probe':return types.CallToolResult(content=[],structuredContent={'openai_key_present':'OPENAI_API_KEY' in os.environ,'explicit_probe':os.environ.get('SLM_FIXTURE_PROBE')})
        if fault=='tool_error':return types.CallToolResult(content=[types.TextContent(type='text',text='Fixture tool deliberately failed')],isError=True)
        if fault=='text_only':return types.CallToolResult(content=[types.TextContent(type='text',text='Unstructured fixture text')])
        if fault=='media':return types.CallToolResult(content=[types.ImageContent(type='image',data='AA==',mimeType='image/png')])
        if fault=='input_required':return types.InputRequiredResult(inputRequests={},requestState='fixture-state')
        name=params.name.removeprefix('fixture.')
        local=registry.execute({'kind':'call','id':'fixture_call','name':name,'arguments':params.arguments or {}})
        if not local['ok']:return types.CallToolResult(content=[types.TextContent(type='text',text=canonical(local['error']))],isError=True)
        data=local['data']
        if fault=='float_result':data={'value':1.5}
        if fault in ('large_result','wire_large_result'):data={'body':'x'*(10000 if fault=='large_result' else 200000)}
        if fault=='invalid_output':data={'unexpected':'wrong schema'}
        return types.CallToolResult(content=[types.TextContent(type='text',text=json.dumps(data))],structuredContent=data)
    def schema(name):
        for v in catalogue:
            if v['name']==name:return v['inputSchema']
        return None
    return Server('slm-synthetic-tools',version='1.0.0',on_list_tools=listing,on_call_tool=calling,get_tool_input_schema=schema)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--fault',default='none');p.add_argument('--pid-file');p.add_argument('--call-file');p.add_argument('--page-size',type=int,default=2)
    a=p.parse_args()
    if a.pid_file:Path(a.pid_file).write_text(str(os.getpid()))
    if a.fault=='stubborn_child':
        import subprocess
        subprocess.Popen([os.sys.executable,'-c',
            'import os,sys,signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);open(sys.argv[1],"w").write(str(os.getpid()));time.sleep(60)',a.pid_file+'.child'])
    if a.fault=='stdout_oversize':os.write(1,b'x'*200000);return
    if a.fault=='stdout_invalid':os.write(1,b'not json\n');return
    if a.fault=='startup_hang':
        import time;time.sleep(60);return
    if a.fault=='stderr':os.write(2,b'stderr fixture log\n'*10000)
    server=create_server(a.fault,a.call_file,a.page_size)
    async def run():
        async with stdio_server() as streams:await server.run(*streams,server.create_initialization_options())
    anyio.run(run)


if __name__=='__main__':main()

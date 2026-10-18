"""Pinned MCP discovery mapped to student-safe aliases and synchronous tool calls."""
from copy import deepcopy
from importlib.metadata import version
import hashlib
import json
import math
from pathlib import Path
import re
import threading
import anyio
from anyio.from_thread import start_blocking_portal
from jsonschema import Draft202012Validator
from referencing import Registry
from mcp import Client
from mcp.types import CallToolResult
from slm.data.schema import digest
from slm.tools.protocol import decision,tool_result,canonical
from slm.tools.local import InvalidArguments,ExecutionRefused
from slm.mcp.transport import BoundedStdio


class MCPFailure(RuntimeError):pass
class MCPTimeout(MCPFailure):pass


def schema_validator(schema):
    if not isinstance(schema,dict):raise ValueError('Object JSON schema required')
    encoded=json.dumps(schema,ensure_ascii=False,allow_nan=False)
    if len(encoded.encode())>8192:raise ValueError('Tool schema byte limit exceeded')
    def visit(v,depth=0):
        if depth>24:raise ValueError('Tool schema nesting limit exceeded')
        if isinstance(v,dict):
            if '$id' in v or '$dynamicRef' in v:raise ValueError('Schema identifiers/dynamic references unsupported')
            if '$ref' in v and (not isinstance(v['$ref'],str) or not v['$ref'].startswith('#/')):raise ValueError('Only local JSON-pointer schema references supported')
            for x in v.values():visit(x,depth+1)
        elif isinstance(v,list):
            for x in v:visit(x,depth+1)
    visit(schema)
    if schema.get('$schema','https://json-schema.org/draft/2020-12/schema')!='https://json-schema.org/draft/2020-12/schema':raise ValueError('Reference supports JSON Schema 2020-12')
    Draft202012Validator.check_schema(schema)
    def deny(uri):raise ValueError('External schema retrieval prohibited')
    return Draft202012Validator(schema,registry=Registry(retrieve=deny))


class MCPRegistry:
    def __init__(self,command,*,namespace='tools',selected=None,cwd=None,env=None,timeout=5.,mode='auto',
                 max_tools=16,max_pages=16,max_discovery_bytes=65536,transport_limits=None):
        sdk_version=version('mcp')
        if sdk_version!='2.3.0':raise ValueError('This reference requires mcp==2.3.0')
        if not isinstance(namespace,str) or not re.fullmatch('[A-Za-z][A-Za-z0-9_]{0,15}',namespace):raise ValueError('Bounded host namespace required')
        if mode not in ('auto','legacy'):raise ValueError('Explicit supported protocol negotiation mode required')
        if type(timeout) not in (int,float) or not math.isfinite(timeout) or not .1<=timeout<=30:raise ValueError('Bounded MCP timeout required')
        for v,limit in ((max_tools,64),(max_pages,32),(max_discovery_bytes,262144)):
            if type(v) is not int or not 1<=v<=limit:raise ValueError('Invalid discovery bound')
        if selected is not None and (not selected or len(set(selected))!=len(selected) or any(not isinstance(v,str) or not v for v in selected)):raise ValueError('Explicit selected remote names required')
        self.transport=BoundedStdio(command,cwd=cwd,env=env,**(transport_limits or {}));self.namespace=namespace
        self.selected=tuple(selected) if selected is not None else None;self.timeout=timeout;self.mode=mode
        self.max_tools=max_tools;self.max_pages=max_pages;self.max_discovery_bytes=max_discovery_bytes
        self.context_note='Tools come from a host-configured MCP connection; do not invent missing result fields.'
        self._lock=threading.RLock();self._closed=False;self._broken=False;self._portal=None;self._client=None;self._specs={}
        self.metrics={'tool_requests_submitted':0,'tool_results_received':0,'unknown_tool_outcomes':0,'list_requests':0,'connection_closed':False,
            'protocol_version':None,'mcp_sdk':sdk_version,'endpoint_command_hash':digest({'command':list(command),'cwd':str(cwd),'env_keys':sorted(env or {})})}
    def __enter__(self):
        if self._portal is not None or self._closed:raise ValueError('MCP registry cannot be reused')
        self._portal_cm=start_blocking_portal(name='slm-mcp-'+self.namespace);self._portal=self._portal_cm.__enter__()
        try:
            self._lifetime,self._catalog=self._portal.start_task(self._serve)
            self._install(self._catalog)
            return self
        except BaseException:
            self.close();raise
    async def _serve(self,*,task_status=anyio.TASK_STATUS_IGNORED):
        self._stop=anyio.Event()
        try:
            with anyio.CancelScope(deadline=anyio.current_time()+self.timeout) as startup:
                async with Client(self.transport(),read_timeout_seconds=self.timeout,mode=self.mode,cache=None,input_required_max_rounds=0) as client:
                    self._client=client;self.metrics['protocol_version']=client.protocol_version
                    catalogue=await self._list_all()
                    startup.deadline=math.inf
                    task_status.started(catalogue)
                    await self._stop.wait()
            if startup.cancelled_caught:raise MCPTimeout('MCP startup deadline exceeded')
        finally:self.metrics['connection_closed']=True;self._client=None
    async def _list_all(self):
        catalogue=[];cursor=None;seen_names=set();seen_cursors=set();size=0
        with anyio.fail_after(self.timeout):
            for _ in range(self.max_pages):
                self.metrics['list_requests']+=1
                result=await self._client.list_tools(cursor=cursor,cache_mode='bypass')
                for tool in result.tools:
                    value=tool.model_dump(mode='json',by_alias=True,exclude_none=True)
                    size+=len(json.dumps(value,ensure_ascii=False,allow_nan=False).encode())
                    if len(catalogue)>=self.max_tools or size>self.max_discovery_bytes:raise ValueError('MCP discovery exceeds explicit bounds')
                    if not isinstance(tool.name,str) or not 1<=len(tool.name)<=128 or tool.name in seen_names:raise ValueError('Duplicate/invalid remote tool name')
                    seen_names.add(tool.name);catalogue.append(value)
                cursor=result.next_cursor
                if cursor is None:return sorted(catalogue,key=lambda v:v['name'])
                if not isinstance(cursor,str) or not cursor or len(cursor)>1024 or cursor in seen_cursors:raise ValueError('Invalid/repeated pagination cursor')
                seen_cursors.add(cursor)
            raise ValueError('MCP discovery page limit exceeded')
    def _install(self,catalogue):
        self._catalog_hash=digest(catalogue);names={v['name'] for v in catalogue}
        if self.selected is not None and not set(self.selected)<=names:raise ValueError('Selected MCP tools absent')
        for tool in catalogue:
            if self.selected is not None and tool['name'] not in self.selected:continue
            name=tool['name'];alias='mcp_'+self.namespace+'_'+hashlib.sha256(name.encode()).hexdigest()[:16]
            if alias in self._specs:raise ValueError('Tool alias collision')
            input_=tool['inputSchema'];output=tool.get('outputSchema')
            validator=schema_validator(input_)
            if input_.get('type')!='object':raise ValueError('Tool arguments must have an object schema')
            if output is not None:schema_validator(output)
            description=tool.get('description','')
            if not isinstance(description,str) or len(description.encode())>2048:raise ValueError('Tool description exceeds bound')
            self._specs[alias]={'name':alias,'description':name+': '+description,'input_schema':deepcopy(input_),
                'output_schema':deepcopy(output),'remote_name':name,'validator':validator}
        if not self._specs:raise ValueError('No selected MCP tools')
    def _guard(self):
        if self._closed or self._broken or self._client is None:raise ExecutionRefused('MCP connection is closed or invalidated')
    def discover(self):
        self._guard();return [{k:deepcopy(v[k]) for k in ('name','description','input_schema','output_schema')} for _,v in sorted(self._specs.items())]
    @property
    def fingerprint(self):return digest({'catalog_hash':self._catalog_hash,'namespace':self.namespace,'tools':self.discover()})
    def alias_for(self,remote_name):
        self._guard()
        for alias,v in self._specs.items():
            if v['remote_name']==remote_name:return alias
        raise ValueError('Remote tool is not selected')
    def validate(self,call):
        self._guard();decision(call)
        if call['kind']!='call' or call['name'] not in self._specs:raise InvalidArguments('Unknown selected MCP alias')
        try:errors=list(self._specs[call['name']]['validator'].iter_errors(call['arguments']))
        except Exception as exc:raise InvalidArguments('Argument schema could not be evaluated') from exc
        if errors:raise InvalidArguments('MCP arguments violate pinned schema')
    async def _execute(self,call):
        try:
            if digest(await self._list_all())!=self._catalog_hash:raise ExecutionRefused('Remote tool catalogue changed; reopen explicitly')
            with anyio.fail_after(self.timeout):
                self.metrics['tool_requests_submitted']+=1
                # Low-level call deliberately avoids high-level refresh/input-required retries.
                result=await self._client.session.call_tool(self._specs[call['name']]['remote_name'],call['arguments'],read_timeout_seconds=self.timeout*2)
                self.metrics['tool_results_received']+=1
            if not isinstance(result,CallToolResult):raise ValueError('Unsupported MCP result shape')
            return result
        except TimeoutError as exc:
            self.metrics['unknown_tool_outcomes']=self.metrics['tool_requests_submitted']-self.metrics['tool_results_received']
            self._broken=True;self._stop.set();raise MCPTimeout('MCP deadline exceeded; no automatic retry') from exc
        except BaseException:
            self.metrics['unknown_tool_outcomes']=self.metrics['tool_requests_submitted']-self.metrics['tool_results_received']
            self._broken=True;self._stop.set();raise
    def execute(self,call):
        with self._lock:
            self.validate(call)
            try:result=self._portal.call(self._execute,deepcopy(call))
            except (ExecutionRefused,MCPTimeout):raise
            except Exception as exc:
                self._broken=True;raise MCPFailure('MCP transport/protocol call failed; no automatic retry') from exc
            try:
                raw=result.model_dump(mode='json',by_alias=True,exclude_none=True);self.metrics['last_result_hash']=digest(raw)
                if any(v.type!='text' for v in result.content):raise ValueError('Text student cannot consume non-text MCP content')
                if result.is_error:
                    text='\n'.join(v.text for v in result.content)
                    error={'code':'mcp_tool_error','message':text[:256] or 'MCP tool reported an error'};data=None
                else:
                    data=result.structured_content
                    if data is None and 'structured_content' not in result.model_fields_set:data={'content':[{'type':'text','text':v.text} for v in result.content]}
                    elif not isinstance(data,dict):data={'value':data}
                    error=None
                return tool_result({'id':call['id'],'name':call['name'],'ok':not result.is_error,'data':data,'error':error})
            except ValueError:
                return tool_result({'id':call['id'],'name':call['name'],'ok':False,'data':None,
                    'error':{'code':'unsupported_mcp_result','message':'Result exceeds the supported bounded text/integer JSON contract'}})
    def close(self):
        if self._closed:return
        self._closed=True
        if self._portal is not None:
            try:
                if hasattr(self,'_stop'):self._portal.call(self._stop.set)
                if hasattr(self,'_lifetime'):
                    try:self._lifetime.result(timeout=5)
                    except Exception as exc:self.metrics['lifecycle_error']=type(exc).__name__
            finally:self._portal_cm.__exit__(None,None,None);self._portal=None
    @property
    def tool_submission_count(self):return self.metrics['tool_requests_submitted']
    def audit(self):return {'connection':deepcopy(self.metrics),'transport':deepcopy(self.transport.stats)}
    def __exit__(self,*args):self.close()

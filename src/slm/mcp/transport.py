"""Bounded POSIX stdio transport for the pinned official MCP session engine."""
from contextlib import asynccontextmanager,suppress
import hashlib
import json
import math
import os
import signal
import re
import anyio
import mcp.types as types
from mcp.client.stdio import get_default_environment
from mcp.shared.message import SessionMessage


class TransportLimit(ValueError):pass


def wire_json(line):
    def pairs(items):
        value={}
        for k,v in items:
            if k in value:raise TransportLimit('Duplicate JSON-RPC key')
            value[k]=v
        return value
    def invalid(v):raise TransportLimit('Nonfinite JSON-RPC value')
    def number(text):
        value=float(text)
        if not math.isfinite(value):raise TransportLimit('Nonfinite JSON-RPC number')
        return value
    try:value=json.loads(line.decode('utf-8'),object_pairs_hook=pairs,parse_constant=invalid,parse_float=number)
    except (UnicodeError,json.JSONDecodeError,RecursionError) as exc:raise TransportLimit('Invalid UTF8 JSON-RPC message') from exc
    nodes=0
    def check(v,depth=0):
        nonlocal nodes
        nodes+=1
        if depth>32 or nodes>16384:raise TransportLimit('JSON-RPC structure limit exceeded')
        if isinstance(v,dict):
            for x in v.values():check(x,depth+1)
        elif isinstance(v,list):
            for x in v:check(x,depth+1)
    check(value)
    return SessionMessage(types.jsonrpc_message_adapter.validate_python(value,by_name=False))


class BoundedStdio:
    def __init__(self,command,*,cwd=None,env=None,max_line_bytes=131072,max_received_bytes=1048576,max_messages=256):
        if os.name!='posix':raise ValueError('Reference process-group transport requires POSIX')
        if (not isinstance(command,(list,tuple)) or not 1<=len(command)<=32
            or any(not isinstance(v,str) or not v or '\x00' in v or len(v)>4096 for v in command)):
            raise ValueError('Explicit bounded executable/argv required; no shell parsing')
        for value,low,high in [(max_line_bytes,1024,1048576),(max_received_bytes,1024,16777216),(max_messages,8,4096)]:
            if type(value) is not int or not low<=value<=high:raise ValueError('Invalid transport bounds')
        if env is not None and (not isinstance(env,dict) or len(env)>32 or any(not isinstance(k,str) or re.fullmatch('[A-Za-z_][A-Za-z0-9_]{0,127}',k) is None or not isinstance(v,str) or len(v)>8192 or '\x00' in v for k,v in env.items())):raise ValueError('Bounded explicit string environment required')
        if cwd is not None and (not isinstance(cwd,(str,os.PathLike)) or '\x00' in str(cwd)):raise ValueError('Explicit valid working directory required')
        self.command=list(command);self.cwd=cwd;self.env=dict(env or {});self.max_line_bytes=max_line_bytes
        self.max_received_bytes=max_received_bytes;self.max_messages=max_messages
        self.stats={'pid':None,'received_bytes':0,'received_messages':0,'stderr_bytes':0,'stderr_sha256':None,
            'stdin_closed':False,'parent_reaped':False,'returncode':None,'signals':[],'limit_error':None}
        self._stderr=hashlib.sha256();self._entered=False
    def __call__(self):return self.connect()
    async def _cleanup(self,process):
        async def wait(seconds):
            with anyio.move_on_after(seconds):await process.wait()
        with anyio.CancelScope(shield=True):
            with suppress(Exception):await process.stdin.aclose()
            self.stats['stdin_closed']=True
            await wait(.5)
            for sig in (signal.SIGTERM,signal.SIGKILL):
                try:os.killpg(process.pid,sig);self.stats['signals'].append(sig.name)
                except ProcessLookupError:break
                await wait(.5)
            self.stats['returncode']=process.returncode;self.stats['parent_reaped']=process.returncode is not None
            for stream in (process.stdout,process.stderr):
                with suppress(Exception):await stream.aclose()
            with anyio.move_on_after(.5):await process.aclose()
            self.stats['stderr_sha256']=self._stderr.hexdigest()
    @asynccontextmanager
    async def connect(self):
        if self._entered:raise ValueError('Transport cannot be reused')
        self._entered=True
        process=await anyio.open_process(self.command,cwd=self.cwd,env=get_default_environment()|self.env,start_new_session=True)
        self.stats['pid']=process.pid
        send,read=anyio.create_memory_object_stream(0);write,receive=anyio.create_memory_object_stream(0)
        async def stdout():
            buffer=bytearray()
            try:
                while True:
                    chunk=await process.stdout.receive(16384);self.stats['received_bytes']+=len(chunk)
                    if self.stats['received_bytes']>self.max_received_bytes:raise TransportLimit('Connection byte budget exceeded')
                    buffer.extend(chunk)
                    while (end:=buffer.find(b'\n'))>=0:
                        if end>self.max_line_bytes:raise TransportLimit('JSON-RPC line exceeds byte limit')
                        line=bytes(buffer[:end]);del buffer[:end+1]
                        self.stats['received_messages']+=1
                        if self.stats['received_messages']>self.max_messages:raise TransportLimit('Connection message budget exceeded')
                        await send.send(wire_json(line))
                    if len(buffer)>self.max_line_bytes:raise TransportLimit('Unterminated JSON-RPC line exceeds byte limit')
            except anyio.EndOfStream:
                if buffer:raise TransportLimit('Truncated JSON-RPC line')
            except (anyio.ClosedResourceError,anyio.BrokenResourceError):pass
            except Exception as exc:
                self.stats['limit_error']=type(exc).__name__;raise
            finally:await send.aclose()
        async def stderr():
            try:
                while True:
                    chunk=await process.stderr.receive(16384);self.stats['stderr_bytes']+=len(chunk);self._stderr.update(chunk)
            except (anyio.EndOfStream,anyio.ClosedResourceError,anyio.BrokenResourceError):pass
        async def stdin():
            try:
                async for item in receive:
                    data=(item.message.model_dump_json(by_alias=True,exclude_unset=True)+'\n').encode('utf-8')
                    if len(data)>self.max_line_bytes+1:raise TransportLimit('Outgoing JSON-RPC line exceeds byte limit')
                    await process.stdin.send(data)
            except (anyio.ClosedResourceError,anyio.BrokenResourceError):pass
        # The lifecycle task owns the task group's cancellation scopes and all cleanup.
        async with anyio.create_task_group() as group:
            group.start_soon(stdout);group.start_soon(stderr);group.start_soon(stdin)
            try:yield read,write
            finally:
                await self._cleanup(process)
                group.cancel_scope.cancel()
        self.stats['stderr_sha256']=self._stderr.hexdigest()

#!/usr/bin/env python3
"""Loopback-only inspection UI for the frozen local student checkpoints.

This is deliberately a small stdlib server.  It neither trains nor writes model
artifacts, and it uses the same local decoder and deterministic fixtures as the
frozen evaluator.  The reserve guard is checked before weights are loaded.
"""
import argparse
import contextlib
import fcntl
import hashlib
import re
import json
import os
import shutil
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/approved-next-three-v1"
RESERVE_BYTES = 15 * 1024 ** 3
MAX_BODY = 64 * 1024
MAX_MESSAGE = 8_000
MAX_MESSAGES = 24
MAX_TURNS = 6
MAX_OUTPUT_TOKENS = 96

MODELS = {
    "baseline": {
        "label": "Baseline (selected default)",
        "path": "runs/sft-v3/repair-lr3/milestones/2000000",
        "sha256": "93bb235b29c8bdff5efe4e14bac223b92b5bc70fecc3023a22d8ed2d9b6fd781",
        "provenance": "V3 repair-lr3 milestone, 2,000,000 training input slots; selected after Stage 2.",
    },
    "partial_candidate": {
        "label": "Experimental partial candidate (not promoted)",
        "path": "runs/approved-next-three-v1/training/checkpoint-000000441999-1793553999251485000",
        "sha256": "96a57b77bca3b1df16947a38b793a772e38fc9511eba85d31013517c6a1b1567",
        "provenance": "Stopped at 441,999 non-padding tokens / 220,283 supervised assistant tokens; baseline remains default.",
    },
}

def model_registry():
    models = {key: dict(value) for key, value in MODELS.items()}
    default = "baseline"
    selection = ROOT / "runs/eight-hour-improvement-v1/ui-selection.json"
    if selection.exists():
        data = json.loads(selection.read_text())
        for key, value in data["models"].items():
            if not re.fullmatch(r"[a-z0-9_]+", key): raise RuntimeError("invalid model registry key")
            if not all(isinstance(value.get(k), str) for k in ["label", "path", "sha256", "provenance"]): raise RuntimeError("invalid model registry descriptor")
            if not re.fullmatch(r"[0-9a-f]{64}", value["sha256"]): raise RuntimeError("invalid checkpoint digest")
            if not (ROOT / value["path"]).resolve().is_relative_to(ROOT.resolve()): raise RuntimeError("checkpoint outside workspace")
            models[key] = dict(value)
        default = data["default_model"]
        if default not in models: raise RuntimeError("selected model missing")
        if default != "baseline": models["baseline"]["label"] = "Baseline reference"
    return models, default

HTML = r'''<!doctype html><html><head><meta charset="utf-8"><title>Local Student Inspector</title><style>
body{max-width:940px;margin:28px auto;font:15px system-ui;color:#17212b;background:#fafafa}textarea,select,button{font:inherit}textarea{width:100%;height:100px;padding:10px;box-sizing:border-box}button,select{padding:8px 10px;margin:6px 5px 6px 0}.notice{padding:10px;background:#fff4d6;border:1px solid #d7ad51}.status{padding:8px;background:#eaf1f7}.msg{white-space:pre-wrap;padding:10px;margin:8px 0;border-left:4px solid #789;background:white}.user{border-color:#437}.assistant{border-color:#285}.trace{background:#111;color:#d9f7e3;padding:12px;overflow:auto;white-space:pre-wrap}.small{color:#58636e;font-size:13px}</style></head><body>
<h1>Local Student Inspector</h1><p class="notice">Experimental local model. Outputs may be incorrect. Tool mode runs only deterministic local fixtures; it cannot take real actions.</p>
<label>Model <select id="model"></select></label><label><input id="tools" type="checkbox"> Tool mode</label><button onclick="reset()">Reset</button><span id="state" class="small"></span>
<div id="meta" class="small"></div><div id="history"></div><textarea id="prompt" maxlength="8000" placeholder="Write a message…"></textarea><br><button id="send" onclick="send()">Send</button><button onclick="cancel()">Cancel active request</button>
<h3>Inspectable trace</h3><pre id="trace" class="trace">No request yet.</pre><script>
let history=[], active=null; const $=id=>document.getElementById(id);
let registry={}; async function info(){let x=await fetch('/api/info').then(r=>r.json()); registry=x.models; $('state').textContent=x.ready? 'Ready for local inference':'Inference unavailable: '+x.reason; $('model').replaceChildren(...Object.entries(x.models).map(([k,v])=>new Option(v.label,k))); $('model').value=x.default_model; $('meta').textContent=registry[$('model').value].provenance+' Disk free: '+x.disk_free_gib+' GiB; reserve: 15 GiB.'} $('model').onchange=()=>{reset();$('meta').textContent=registry[$('model').value].provenance}
function render(){ $('history').innerHTML=history.map(m=>`<div class="msg ${m.role}"><b>${m.role}</b>\n${escape(m.content)}</div>`).join('')}; function escape(s){let d=document.createElement('div');d.textContent=s;return d.innerHTML}
function reset(){history=[];active=null;render();$('trace').textContent='Conversation reset.'}
async function send(){let text=$('prompt').value.trim();if(!text||active)return;$('prompt').value='';history.push({role:'user',content:text});render();$('send').disabled=true;let c=new AbortController(), id=crypto.randomUUID();active={c,id};try{let r=await fetch('/api/chat',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({request_id:id,model:$('model').value,tool_mode:$('tools').checked,messages:history}),signal:c.signal});let x=await r.json();if(!r.ok)throw Error(x.error||'request failed');history=x.messages;$('state').textContent=x.notice||'Reply generated locally';$('trace').textContent=JSON.stringify({checkpoint_sha256:x.checkpoint_sha256,trace:x.trace},null,2);render()}catch(e){$('trace').textContent='Request not completed: '+e.message}finally{active=null;$('send').disabled=false}}
function cancel(){if(active){fetch('/api/cancel',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({request_id:active.id})});active.c.abort()}}; info();</script></body></html>'''

class Engine:
    def __init__(self):
        self.lock = threading.Lock()
        self.model = None
        self.tokenizer = None
        self.loaded_key = None
        self.loaded_signature = None
        self.health_baseline = None

    @contextlib.contextmanager
    def gpu_guard(self):
        path = ROOT / "runs/eight-hour-improvement-v1/.training.lock"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError("GPU guard: training or evaluation is using the laptop; try again after it finishes") from None
            yield

    def availability(self):
        free = shutil.disk_usage(ROOT).free
        if free < RESERVE_BYTES:
            return False, f"disk reserve guard: {free / 1024**3:.1f} GiB free, requires at least 15 GiB"
        try:
            with self.gpu_guard(): pass
        except RuntimeError as exc:
            return False, str(exc)
        return True, ""

    def resource_guard(self):
        from train_local import health
        from sft_common import memory_stats
        from inference_guard import violation
        current = {**health(), **memory_stats()}
        if self.health_baseline is None: self.health_baseline = current
        reason = violation(current, self.health_baseline)
        if reason: raise RuntimeError("resource guard: " + reason)

    def load(self, key):
        models, _ = model_registry()
        descriptor = models[key]
        signature = (key, descriptor["path"], descriptor["sha256"])
        if self.loaded_signature == signature: return
        path = (ROOT / descriptor["path"]).resolve()
        weights = path / "model.safetensors"
        if not path.is_relative_to(ROOT.resolve()) or not weights.is_file(): raise RuntimeError("selected checkpoint is unavailable")
        h = hashlib.sha256()
        with weights.open("rb") as f:
            for block in iter(lambda: f.read(4 * 1024 * 1024), b""): h.update(block)
        if h.hexdigest() != descriptor["sha256"]: raise RuntimeError("checkpoint provenance guard: model digest differs from selection")
        import mlx.core as mx
        from tokenizers import Tokenizer
        from benchmark_mlx import Model
        from sft_common import configure_memory
        configure_memory()
        self.model = None
        mx.clear_cache()
        self.tokenizer = Tokenizer.from_file(str(ROOT / "data/sft-v3/tokenizer.json"))
        self.model = Model(768, 12, 16384)
        self.model.load_weights(str(weights))
        self.model.set_dtype(mx.bfloat16)
        mx.eval(self.model.parameters())
        self.loaded_key = key
        self.loaded_signature = signature

    def chat(self, key, messages, tool_mode, cancelled):
        with self.lock, self.gpu_guard():
            self.resource_guard()
            self.load(key)
            self.resource_guard()
            from sft_common import generate, parse_call, execute, system
            context = [dict(message) for message in messages]
            working = ([{"role": "system", "content": system()}] if tool_mode else []) + list(context)
            trace = []
            final = ""
            notice = None
            for turn in range(MAX_TURNS):
                if cancelled.is_set(): raise RuntimeError("cancelled before next generation")
                self.resource_guard()
                g = generate(self.model, self.tokenizer, working, penalty=1.2, mode="greedy", seed=20261101, cap=MAX_OUTPUT_TOKENS)
                if cancelled.is_set(): raise RuntimeError("cancelled after generation")
                text = g["output"]
                item = {"turn": turn + 1, "generation": g, "raw_output": text}
                if g["stop"] == "context_overflow":
                    item["kind"] = "context_limit"
                    trace.append(item)
                    notice = "This conversation exceeds the 512-token context limit. Reset or shorten it; older messages were not dropped."
                    break
                assistant = {"role": "assistant", "content": text}
                context.append(assistant)
                working.append(assistant)
                final = text
                if not tool_mode or not text.strip().startswith("<|tool_call|>"):
                    item["kind"] = "final_answer"
                    trace.append(item)
                    break
                try:
                    call = parse_call(text)
                    result = execute(call)
                    item.update(kind="tool_call", call=call, fixture_result=result, executed=True)
                    trace.append(item)
                    tool = {"role": "tool", "content": json.dumps(result, separators=(",", ":"))}
                    working.append(tool)
                    context.append(tool)
                except Exception as exc:
                    item.update(kind="invalid_tool_call", rejected=True, error=type(exc).__name__, detail=str(exc))
                    trace.append(item)
                    notice = "The model emitted an invalid tool call; no tool was run."
                    break
            else:
                notice = "Stopped after the bounded tool-turn limit without a final answer."
            return {"reply": final, "trace": trace, "messages": context, "model": key,
                    "checkpoint_sha256": self.loaded_signature[2], "notice": notice}

ENGINE = Engine()
CANCELS = {}
CANCELS_LOCK = threading.Lock()
def valid_messages(value):
    if not isinstance(value, list) or not value or len(value) > MAX_MESSAGES: raise ValueError("messages must be a nonempty list of at most 24 entries")
    allowed = {"user", "assistant", "tool"}; out = []
    for m in value:
        if not isinstance(m, dict) or m.get("role") not in allowed or not isinstance(m.get("content"), str) or len(m["content"]) > MAX_MESSAGE: raise ValueError("invalid message")
        out.append({"role":m["role"],"content":m["content"]})
    if out[-1]["role"] != "user": raise ValueError("last message must be user")
    return out

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass
    def reply(self, code, obj):
        raw=json.dumps(obj).encode(); self.send_response(code); self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def do_GET(self):
        if urlparse(self.path).path == "/":
            raw=HTML.encode(); self.send_response(200); self.send_header("Content-Type","text/html; charset=utf-8"); self.send_header("Content-Length",str(len(raw))); self.end_headers(); self.wfile.write(raw); return
        if urlparse(self.path).path == "/api/info":
            ok,reason=ENGINE.availability(); self.reply(200,{"ready":ok,"reason":reason,"models":model_registry()[0],"default_model":model_registry()[1],"disk_free_gib":round(shutil.disk_usage(ROOT).free/1024**3,2),"limits":{"max_turns":MAX_TURNS,"max_output_tokens":MAX_OUTPUT_TOKENS,"context":"512 tokens; older turns are not silently dropped—overlong contexts return an explicit model limit."}}); return
        self.reply(404,{"error":"not found"})
    def do_POST(self):
        endpoint=urlparse(self.path).path
        if endpoint not in {"/api/chat", "/api/cancel"}: self.reply(404,{"error":"not found"}); return
        try:
            n=int(self.headers.get("Content-Length","0"));
            if n <= 0 or n > MAX_BODY: raise ValueError("request body must be 1..65536 bytes")
            data=json.loads(self.rfile.read(n)); request_id=data.get("request_id")
            if not isinstance(request_id,str) or not (1 <= len(request_id) <= 128): raise ValueError("request_id is required")
            if endpoint == "/api/cancel":
                with CANCELS_LOCK:
                    event=CANCELS.get(request_id)
                    if event: event.set()
                self.reply(200,{"cancelled":bool(event)}); return
            models,default_model=model_registry()
            key=data.get("model",default_model)
            if key not in models: raise ValueError("unknown model")
            messages=valid_messages(data.get("messages")); cancelled=threading.Event()
            with CANCELS_LOCK: CANCELS[request_id]=cancelled
            result=ENGINE.chat(key,messages,bool(data.get("tool_mode")),cancelled)
            with CANCELS_LOCK: CANCELS.pop(request_id,None)
            self.reply(200,result)
        except Exception as exc:
            if 'request_id' in locals():
                with CANCELS_LOCK: CANCELS.pop(request_id,None)
            self.reply(503 if "guard" in str(exc) else 400,{"error":str(exc)})

def main():
    p=argparse.ArgumentParser(); p.add_argument("--port",type=int,default=8765); a=p.parse_args()
    if not (1024 <= a.port <= 65535): p.error("port must be 1024..65535")
    httpd=ThreadingHTTPServer(("127.0.0.1",a.port),Handler); print(f"http://127.0.0.1:{a.port}",flush=True); httpd.serve_forever()
if __name__ == "__main__": main()

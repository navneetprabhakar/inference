"""Loopback chat page/API for the exact own-model bundle and bounded broker."""
import argparse
from collections import OrderedDict
from dataclasses import dataclass, field
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import secrets
import threading
import uuid
import torch

from cloud_training.nano_serve import BrokerChat, generate_action, load_own_bundle

ROOT = Path(__file__).resolve().parents[1]
MAX_SESSIONS = 16
MAX_TURNS = 64
MAX_BODY = 32 * 1024
MAX_MESSAGE = 8 * 1024


class RequestError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


@dataclass
class Session:
    chat: object
    model_info: dict = field(default_factory=dict)
    turns: dict = field(default_factory=dict)
    host_failed: bool = False


class Sessions:
    def __init__(self, factory, model_info, *, watch=None):
        self.watch = watch
        self.factory = factory
        self.model_info = model_info
        self.sessions = OrderedDict()
        self.lock = threading.Lock()

    def lookup(self, token):
        if not isinstance(token, str) or token not in self.sessions:
            raise RequestError(404, "This conversation has expired. Start a new chat.")
        self.sessions.move_to_end(token)
        return self.sessions[token]

    def open(self, token=None):
        with self.lock:
            if token is None:
                token = secrets.token_urlsafe(32)
                self.sessions[token] = self.watch.open() if self.watch else Session(self.factory(), self.model_info)
                if len(self.sessions) > MAX_SESSIONS:
                    self.sessions.popitem(last=False)
            session = self.lookup(token)
            return dict(session=token, model=session.model_info, turns=list(session.turns.values()))

    def turn(self, token, turn_id, message, permit_calls):
        if not isinstance(message, str) or not message.strip() or len(message.encode("utf-8")) > MAX_MESSAGE:
            raise RequestError(400, "Enter a message of 1 to 8,192 UTF-8 bytes.")
        if type(permit_calls) is not bool:
            raise RequestError(400, "The tools setting must be true or false.")
        if not isinstance(turn_id, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", turn_id):
            raise RequestError(400, "Invalid turn ID.")
        with self.lock:
            session = self.lookup(token)
            if turn_id in session.turns:
                old = session.turns[turn_id]
                if old["message"] != message or old["permit_calls"] != permit_calls:
                    raise RequestError(409, "This turn ID was already used for a different request.")
                return old
            if session.host_failed:
                raise RequestError(409, "Start a new chat after the host failure.")
            if len(session.turns) >= MAX_TURNS:
                raise RequestError(409, "This conversation reached 64 turns. Start a new chat.")
            host_session = getattr(session.chat, "session", None)
            offset = len(getattr(host_session, "trace", []))
            try:
                with torch.inference_mode():
                    result = session.chat.turn(message, permit_calls=permit_calls)
                record = {k: result[k] for k in ("answer", "frames", "trace", "failure")}
                record["selected_path"] = result.get("selected_path", "own-model/raw")
                record["frame_origins"] = result.get("frame_origins", ["own-model/raw"] * len(record["frames"]))
            except Exception as error:
                session.host_failed = True
                record = dict(
                    answer=None,
                    frames=[],
                    trace=getattr(host_session, "trace", [])[offset:],
                    failure=f"Host failure: {error}. Start a new chat to continue.",
                )
            record.update(id=turn_id, message=message, permit_calls=permit_calls)
            session.turns[turn_id] = record
            return record


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def log_message(self, *_args):
        pass

    def origin_allowed(self):
        port = self.server.server_port
        allowed = {f"127.0.0.1:{port}", f"localhost:{port}"}
        authority = self.headers.get("Host", "")
        origin = self.headers.get("Origin")
        return authority in allowed and (origin is None or origin == f"http://{authority}")

    def reply(self, status, body, content_type="application/json; charset=utf-8"):
        if isinstance(body, bytes):
            data = body
        else:
            data = json.dumps(body, ensure_ascii=True, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; script-src 'unsafe-inline'; "
            "style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'",
        )
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if not self.origin_allowed():
            return self.reply(403, {"error": "Loopback origin required."})
        if self.path == "/":
            return self.reply(200, (ROOT / "cloud_training/own-chat.html").read_bytes(), "text/html; charset=utf-8")
        self.reply(404, {"error": "Unknown path."})

    def do_POST(self):
        if not self.origin_allowed():
            return self.reply(403, {"error": "Loopback origin required."})
        try:
            if self.headers.get_content_type() != "application/json":
                raise RequestError(415, "Expected application/json.")
            length = self.headers.get("Content-Length", "")
            if not length.isascii() or not length.isdecimal() or len(length) > 6 or int(length) > MAX_BODY:
                raise RequestError(413, "Invalid or oversized request.")
            body = json.loads(self.rfile.read(int(length)))
            if not isinstance(body, dict):
                raise RequestError(400, "Expected a JSON object.")
            if self.path == "/api/session" and body.keys() <= {"session"}:
                result = self.server.sessions.open(body.get("session"))
            elif self.path == "/api/turn" and body.keys() == {"session", "id", "message", "permit_calls"}:
                result = self.server.sessions.turn(body["session"], body["id"], body["message"], body["permit_calls"])
            elif self.path in {"/api/session", "/api/turn"}:
                raise RequestError(400, "Unexpected or missing request fields.")
            else:
                raise RequestError(404, "Unknown path.")
            self.reply(200, result)
        except RequestError as error:
            self.reply(error.status, {"error": str(error)})
        except (ValueError, UnicodeError, RecursionError):
            self.reply(400, {"error": "Invalid JSON or UTF-8."})


class WebChat:
    def __init__(self, chat):
        self.chat = chat

    @property
    def session(self):
        return self.chat.broker

    def turn(self, message, *, permit_calls):
        result = self.chat.turn(message, policy={
            'permit_calls':permit_calls,
            'allowed_names':['calculate','convert'] if permit_calls else []})
        return {
            'answer':result['assistant_text'],
            'frames':[event['parsed'] for event in result['events'] if event['kind'] == 'model_action'],
            'trace':[event['record'] for event in result['events']
                     if event['kind'] == 'broker_decision' and event['decision']['dispatched']],
            'failure':None if result['status'] == 'complete' else
                result['error_code']+': '+result['detail']+
                (' Start a new chat.' if result['reset_required'] else ''),
            'selected_path':'own-model/raw',
            'frame_origins':['own-model/raw' for event in result['events'] if event['kind'] == 'model_action'],
        }


class OwnHandler(Handler):
    def do_POST(self):
        if self.path != '/api/chat':
            return super().do_POST()
        if not self.origin_allowed():
            return self.reply(403, {'error':'Loopback origin required.'})
        try:
            if self.headers.get_content_type() != 'application/json':
                raise RequestError(415, 'Expected application/json.')
            length = self.headers.get('Content-Length', '')
            if not length.isascii() or not length.isdecimal() or len(length) > 6 or int(length) > MAX_BODY:
                raise RequestError(413, 'Invalid or oversized request.')
            body = json.loads(self.rfile.read(int(length)))
            if not isinstance(body, dict) or 'message' not in body or not body.keys() <= {'message','session','id','permit_calls'}:
                raise RequestError(400, 'Expected message and optional session, id, permit_calls.')
            token = self.server.sessions.open(body.get('session'))['session']
            result = self.server.sessions.turn(token, body.get('id', uuid.uuid4().hex),
                                               body['message'], body.get('permit_calls', False))
            return self.reply(200, {'session':token, **result})
        except RequestError as error:
            return self.reply(error.status, {'error':str(error)})
        except (ValueError, UnicodeError, RecursionError, TypeError):
            return self.reply(400, {'error':'Invalid JSON or request fields.'})

    def do_GET(self):
        if not self.origin_allowed():
            return self.reply(403, {'error':'Loopback origin required.'})
        if self.path == '/':
            return self.reply(200, (ROOT/'cloud_training/own-chat.html').read_bytes(), 'text/html; charset=utf-8')
        if self.path == '/api/health':
            return self.reply(200, {'status':'ready', 'model':self.server.sessions.model_info})
        return self.reply(404, {'error':'Unknown path.'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--device', choices=['mps','cpu','cuda'], default='mps')
    parser.add_argument('--reply-budget', type=int, default=192)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535 or not 1 <= args.reply_budget <= 512:
        parser.error('Invalid port or reply budget')
    import torch
    torch.set_num_threads(4)
    checkpoint = args.checkpoint.expanduser().resolve()
    model, tokenizer, metadata = load_own_bundle(
        ROOT/'runs/nanochat-source', checkpoint, ROOT/'runs/ownbase-v2-data/tokenizer',
        tokenizer_sha256='ad777bb448ea8fcf115835548596f9303f3ee5e85a014b0bb315567091080cc5',
        device=args.device)
    info = {'name':'Own 537M · experimental', 'parameters':sum(p.numel() for p in model.parameters()),
            'device':args.device, 'checkpoint':str(checkpoint.relative_to(ROOT)) if checkpoint.is_relative_to(ROOT) else str(checkpoint),
            'sha256':hashlib.sha256((checkpoint/'manifest.json').read_bytes()).hexdigest(),
            'context_tokens':model.config.sequence_len, 'reply_budget':args.reply_budget,
            'repetition_penalty':1.0, 'step':metadata['step'],
            'tools':['calculate','convert (m/cm/mm/km)'], 'automatic_promotion':False}
    factory = lambda: WebChat(BrokerChat(tokenizer,
        lambda ids,n:generate_action(model,tokenizer,ids,n,repetition_penalty=1.0),
        context=model.config.sequence_len, reply_budget=args.reply_budget))
    server = ThreadingHTTPServer(('127.0.0.1', args.port), OwnHandler)
    server.sessions = Sessions(factory, info)
    print(json.dumps({'url':f'http://127.0.0.1:{args.port}', 'model':info}), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()

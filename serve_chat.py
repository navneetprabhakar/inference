"""Serve a hash-pinned GPT-2 student on loopback, or chat in the terminal."""
import argparse
from collections import OrderedDict
from dataclasses import dataclass, field
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import secrets
import sys
import threading
import uuid

import torch

from gpt2 import GPT2
from guards import Guard, ResourceStop
from tokenizer import load

ROOT = Path(__file__).resolve().parent
DEFAULT_PIN = ROOT / "reports/working-chat/selected.json"
MAX_SESSIONS = 16
MAX_TURNS = 64
MAX_BODY = 32 * 1024
MAX_MESSAGE = 8 * 1024


class RequestError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def resolve_weights(weights, sha, pin):
    if weights is None:
        pin = (pin or DEFAULT_PIN).resolve()
        spec = json.loads(pin.read_text())
        weights, sha = Path(spec["weights"]).expanduser(), spec["sha256"]
        if not weights.is_absolute():
            local = pin.parent / weights
            weights = local if local.is_file() else ROOT / weights
    if not isinstance(sha, str) or not re.fullmatch("[0-9a-fA-F]{64}", sha):
        raise ValueError("Provide the full 64-character SHA-256 for the checkpoint.")
    return weights.resolve(), sha.lower()


def load_student(weights, sha, device):
    # Hash and load from the same descriptor so replacing a pathname between
    # verification and deserialization cannot silently select different weights.
    with weights.open("rb") as stream:
        observed = hashlib.file_digest(stream, "sha256").hexdigest()
        if observed != sha:
            raise ValueError(f"Checkpoint SHA-256 mismatch: expected {sha}, observed {observed}")
        stream.seek(0)
        state = torch.load(stream, weights_only=True, map_location="cpu")
    with torch.device("meta"):
        model = GPT2()
    model.load_state_dict(state, strict=True, assign=True)
    return model.to(device).eval()


class CPUGuard:
    def check(self):
        if (ROOT / "runs/STOP").is_file():
            raise ResourceStop("Serving stopped by runs/STOP")


@dataclass
class Session:
    chat: object
    turns: dict = field(default_factory=dict)
    host_failed: bool = False


class Sessions:
    def __init__(self, factory, model_info):
        self.factory = factory
        self.model_info = model_info
        self.sessions = OrderedDict()
        # One inference at a time. A user's follow-up sees the completed prior turn.
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
                self.sessions[token] = Session(self.factory())
                if len(self.sessions) > MAX_SESSIONS:
                    self.sessions.popitem(last=False)
            session = self.lookup(token)
            return dict(session=token, model=self.model_info, turns=list(session.turns.values()))

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
                record["selected_path"] = result.get("selected_path", "gpt2/dialogue")
                record["frame_origins"] = result.get("frame_origins", ["gpt2/dialogue"]*len(record["frames"]))
            except Exception as error:
                # The adapter may already have run when generation failed. Show its
                # actual records and close this uncertain history to further execution.
                session.host_failed = True
                record = dict(answer=None, frames=[], trace=getattr(host_session, "trace", [])[offset:],
                              failure=f"Host failure: {error}. Start a new chat to continue.")
            record.update(id=turn_id, message=message, permit_calls=permit_calls)
            session.turns[turn_id] = record
            return record


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, port, sessions):
        self.sessions = sessions
        super().__init__(("127.0.0.1", port), Handler)


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def log_message(self, *_args):
        pass  # Chats and session identifiers are kept in memory only.

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
        self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'unsafe-inline'; "
                         "style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if not self.origin_allowed():
            return self.reply(403, {"error": "Loopback origin required."})
        if self.path == "/":
            return self.reply(200, (ROOT / "chat.html").read_bytes(), "text/html; charset=utf-8")
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


def print_turn(record, as_json):
    if as_json:
        print(json.dumps(record, ensure_ascii=True))
        return
    for event in record["trace"]:
        print("Offline tool:", json.dumps(event, ensure_ascii=True))
    if record["answer"] is not None:
        print("Model:", record["answer"])
    if record["failure"]:
        print("Failure:", record["failure"])
        print("Generated frames:", json.dumps(record["frames"], ensure_ascii=True))


def terminal(sessions, prompt, permit_calls, as_json):
    token = sessions.open()["session"]
    if prompt is not None:
        record = sessions.turn(token, uuid.uuid4().hex, prompt, permit_calls)
        print_turn(record, as_json)
        return 1 if record["failure"] else 0
    print("Commands: /new, /tools on, /tools off, /quit", file=sys.stderr)
    while True:
        try:
            message = input("You> ")
        except EOFError:
            return 0
        if message == "/quit":
            return 0
        if message == "/new":
            token = sessions.open()["session"]
            continue
        if message in ("/tools on", "/tools off"):
            permit_calls = message == "/tools on"
            print("Offline tools enabled." if permit_calls else "Offline tools disabled.", file=sys.stderr)
            continue
        if message.strip():
            try:
                print_turn(sessions.turn(token, uuid.uuid4().hex, message, permit_calls), as_json)
            except RequestError as error:
                print(error, file=sys.stderr)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    select = parser.add_mutually_exclusive_group()
    select.add_argument("--pin", type=Path, help="JSON with weights path and SHA-256 (defaults to reports/working-chat/selected.json)")
    select.add_argument("--weights", type=Path, help="Bare GPT-2 state dict, requires --sha256")
    parser.add_argument("--sha256", help="Expected digest for --weights")
    parser.add_argument("--device", choices=("cpu", "mps"), default="cpu")
    parser.add_argument("--runtime",choices=("raw","structured","product","product-v2"),help="Override the runtime named in the pin")
    parser.add_argument("--port", type=int, default=8765, help="Loopback web port (default 8765)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--cli", action="store_true", help="Interactive terminal")
    mode.add_argument("--prompt", help="Run one terminal turn and exit")
    parser.add_argument("--tools", action="store_true", help="Enable offline tools for terminal messages")
    parser.add_argument("--json", action="store_true", help="Print terminal turn records as JSON")
    args = parser.parse_args(argv)
    if bool(args.weights) != bool(args.sha256):
        parser.error("--weights and --sha256 must be supplied together")
    if not 0 <= args.port <= 65535:
        parser.error("--port must be between 0 and 65535")
    if (args.tools or args.json) and not (args.cli or args.prompt is not None):
        parser.error("--tools and --json apply to --cli or --prompt")
    guard = None
    try:
        weights, sha = resolve_weights(args.weights, args.sha256, args.pin)
        guard = Guard(ROOT / "runs" / ("serve-" + uuid.uuid4().hex), 12 * 3600) if args.device == "mps" else CPUGuard()
        guard.check()
        pin_info = json.loads((args.pin or DEFAULT_PIN).read_text()) if args.weights is None else {}
        runtime = args.runtime or pin_info.get("runtime","raw")
        if runtime in ("product","product-v2"):
            from product_chat import reader_identity
            if runtime == "product-v2":
                from followon_product_chat import Chat
                route_params = json.loads((ROOT/"reports/working-chat/head-v2.json").read_text())["parameters"]
            else:
                from product_chat import Chat
                route_params = 56566
            parameters = 124439808 + route_params + reader_identity()["parameters"]
        elif runtime == "structured":
            from fallback_chat import Chat
            parameters = 124439808 + 56566
        elif runtime == "raw":
            from local_chat import Chat
            parameters = 124439808
        else:
            raise ValueError("unknown chat runtime")
        if args.device == "cpu":
            torch.set_num_threads(1)
        tokenizer = load()
        model = load_student(weights, sha, args.device)
        info = dict(name=f"GPT-2 small · {runtime} · {pin_info.get('status','local')}", runtime=runtime, parameters=parameters, checkpoint=weights.name, sha256=sha, device=args.device)
        sessions = Sessions(lambda: Chat(model, tokenizer, guard), info)
        if args.cli or args.prompt is not None:
            print(f"GPT-2 small · {args.device.upper()} · SHA-256 {sha}", file=sys.stderr)
            return terminal(sessions, args.prompt, args.tools, args.json)
        with LocalServer(args.port, sessions) as server:
            print(f"Local chat: http://127.0.0.1:{server.server_port}/  SHA-256 {sha}", flush=True)
            server.serve_forever()
    except KeyboardInterrupt:
        return 0
    except (OSError, ValueError, RuntimeError, KeyError, ImportError, RequestError) as error:
        print(f"Local chat: {error}", file=sys.stderr)
        return 1
    finally:
        if isinstance(guard, Guard):
            guard.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

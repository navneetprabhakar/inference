"""Loopback chat page/API for the exact own-model bundle and bounded broker."""
import argparse
import hashlib
import json
from pathlib import Path
import uuid

from serve_chat import Handler, Sessions, ThreadingHTTPServer, RequestError, MAX_BODY
from cloud_training.nano_serve import BrokerChat, generate_action, load_own_bundle

ROOT = Path(__file__).resolve().parents[1]


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
            return self.reply(200, (ROOT/'own-chat.html').read_bytes(), 'text/html; charset=utf-8')
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

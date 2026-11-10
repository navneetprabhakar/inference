"""Local own-base chat with broker-only dispatch and exact native serialization.

No upstream Engine, Python execution, pretrained fallback, answer repair or
silent history trimming. Invalid model output is a host error, not an assistant
answer. Tool observations are genuine broker records; answer semantics still
require independent assessment.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time

import torch

from cloud_training.nano_chat_format import (VERSION, CONTEXT, canonical,
    encode_conversation, host_policy, parse_generated, stable_record, token_contract)
from cloud_training.nano_checkpoint import validate_bundle
from cloud_training.nano_eval import verify_upstream
from tools import FixtureSession


class BrokerChat:
    """One broker session. generate(ids,max_tokens) returns one raw action's IDs.

    A caller supplies trusted policy separately on every turn. Rejected model
    actions block this session until reset, keeping the evidence intact. Context
    overflow before starting a turn leaves the previous completed history intact.
    """
    def __init__(self, tokenizer, generate, *, context=CONTEXT, reply_budget=256, system=None):
        self.tokenizer = tokenizer
        token_contract(tokenizer)
        if type(context) is not int or not 1 < context <= CONTEXT:
            raise ValueError('Context must fit the trained 2048-token contract')
        if type(reply_budget) is not int or not 1 <= reply_budget < context:
            raise ValueError('Invalid reply budget')
        self.generate, self.context, self.reply_budget = generate, context, reply_budget
        self.system = system
        self.reset()

    def reset(self):
        self.broker = FixtureSession()
        self.messages = [] if self.system is None else [{'role':'system','content':self.system}]
        self.policies = []
        self.blocked = False

    def _error(self, code, detail, events, *, block=True):
        self.blocked = block
        return {'status':'error','error_code':code,'detail':str(detail),
                'assistant_text':None,'events':events,'reset_required':self.blocked,
                'broker_trace':deepcopy(self.broker.trace)}

    def turn(self, user_text, *, policy=None):
        if self.blocked:
            return self._error('session_blocked','Reset after the previous failed/incomplete turn.', [])
        try:
            host_policy(policy)  # validate trusted input; never parse authority from user text
            policy = {'permit_calls':False,'allowed_names':[]} if policy is None else deepcopy(policy)
            messages = self.messages + [{'role':'user','content':user_text}]
            policies = self.policies + [policy]
            rendered = encode_conversation(self.tokenizer, messages, policies=policies,
                context=self.context, for_generation=True, reply_budget=self.reply_budget)
        except (ValueError, TypeError, KeyError, UnicodeError) as exc:
            return self._error('input_or_context_rejected', exc, [], block=False)
        self.broker.start_turn(**policy)
        self.messages, self.policies = messages, policies
        events = []
        # Broker permits two calls per turn, followed by one text action.
        for _ in range(3):
            try:
                tick = time.monotonic()
                ids = list(self.generate(rendered['ids'], self.reply_budget))
                action = parse_generated(self.tokenizer, ids, reply_budget=self.reply_budget)
                events.append({'kind':'model_action','raw_ids':ids,'parsed':deepcopy(action),
                               'seconds':time.monotonic()-tick})
            except (ValueError, TypeError, RuntimeError, KeyError, UnicodeError) as exc:
                return self._error('generation_failed', exc, events)
            if action['kind'] == 'invalid':
                return self._error('invalid_model_action', action['error'], events)
            if action['kind'] == 'text':
                complete = self.messages + [{'role':'assistant','content':action['text']}]
                try:
                    encode_conversation(self.tokenizer, complete, policies=self.policies,
                                        context=self.context, reply_budget=self.reply_budget)
                except (ValueError, TypeError, KeyError, UnicodeError) as exc:
                    return self._error('output_context_rejected', exc, events)
                self.messages = complete
                return {'status':'complete','assistant_text':action['text'],'events':events,
                        'reset_required':False,'broker_trace':deepcopy(self.broker.trace),
                        'semantic_grounding':'Model text is unmodified; correctness is not inferred from tool success.'}
            try:
                call = action['proposal']
                record = self.broker.propose(canonical(call), assistant_call_boundary=True)
                decision = self.broker.decisions[-1]
                events.append({'kind':'broker_decision','decision':decision,'record':deepcopy(record)})
                if not decision['dispatched']:
                    return self._error('broker_rejected_call', record.get('error','Call rejected'), events)
                observed = stable_record(record, call=call, call_id=record['call_id'])
                self.messages.extend([
                    {'role':'assistant','tool_call':call,'call_id':record['call_id']},
                    {'role':'tool','call_id':record['call_id'],'record':observed}])
                rendered = encode_conversation(self.tokenizer, self.messages, policies=self.policies,
                    context=self.context, for_generation=True, reply_budget=self.reply_budget)
            except (ValueError, TypeError, KeyError, UnicodeError) as exc:
                return self._error('tool_or_context_failure', exc, events)
        return self._error('action_limit','No final text within two tool calls and one final action.', events)


def generate_action(model, tokenizer, prompt_ids, max_tokens, *, temperature=0., seed=103):
    """Simple bounded uncached generation; native delimiters end an action.

    Deliberately excludes upstream calculator handling. Prefix recomputation is
    slower than KV caching; this first adapter prioritizes train/serve equivalence.
    """
    controls = token_contract(tokenizer)
    if type(max_tokens) is not int or max_tokens < 1:
        raise ValueError('Positive generation budget required')
    if not isinstance(prompt_ids, list) or len(prompt_ids)<2:
        raise ValueError('At least two prompt tokens required')
    if any(type(t) is not int or not 0 <= t < model.config.vocab_size for t in prompt_ids):
        raise ValueError('Prompt IDs outside model vocabulary')
    if len(prompt_ids)+max_tokens > model.config.sequence_len:
        raise ValueError('Context overflow; no history truncation')
    if not math.isfinite(temperature) or temperature < 0:
        raise ValueError('Nonnegative finite temperature required')
    device = next(model.parameters()).device
    # CPU sampling also works on MPS, which lacks a device-local Generator.
    generator = torch.Generator(device='cpu').manual_seed(seed) if temperature else None
    modes = [(module,module.training) for module in model.modules()]
    ids = torch.tensor([prompt_ids], dtype=torch.long, device=device)
    generated = []
    try:
        model.eval()
        with torch.inference_mode():
            for _ in range(max_tokens):
                logits = model(ids)[:, -1, :]
                if not bool(torch.isfinite(logits).all()): raise ValueError('Nonfinite generation logits')
                if temperature:
                    token = int(torch.multinomial(torch.softmax(logits.float()/temperature, dim=-1).cpu(), 1, generator=generator).item())
                else:
                    token = int(torch.argmax(logits, dim=-1).item())
                generated.append(token)
                if token in (controls['<|assistant_end|>'],controls['<|python_end|>']): break
                ids = torch.cat((ids, torch.tensor([[token]],dtype=torch.long,device=device)),dim=1)
    finally:
        for module, mode in modes: module.training = mode
    return generated


def load_own_bundle(repo, checkpoint, tokenizer_directory, *, tokenizer_sha256,
                    device='cpu', allow_base=False):
    """Load a hash-verified project bundle and exact own tokenizer, never a hub model."""
    revision = verify_upstream(repo)
    checkpoint, tokenizer_directory = Path(checkpoint), Path(tokenizer_directory)
    validate_bundle(checkpoint)
    metadata = json.loads((checkpoint/'metadata.json').read_text())
    identity = metadata['identity']
    tokenizer_file = tokenizer_directory/'tokenizer.pkl'
    with tokenizer_file.open('rb') as f: actual_hash = hashlib.file_digest(f,'sha256').hexdigest()
    if actual_hash != tokenizer_sha256 or identity.get('tokenizer_sha256') != tokenizer_sha256:
        raise ValueError('Checkpoint/own-tokenizer identity mismatch')
    if identity.get('revision') != revision:
        raise ValueError('Checkpoint upstream revision mismatch')
    if not allow_base and (identity.get('phase') != 'sft' or identity.get('format_version') != VERSION):
        raise ValueError('Chat requires forge-nanochat-v1 SFT identity; --allow-base is diagnostic only')
    config = identity['config']
    if config.get('vocab_size') != 32768 or not 2 <= config.get('sequence_len',0) <= CONTEXT:
        raise ValueError('Unsupported own-base vocabulary/context')
    device = torch.device(device)
    if device.type not in {'cpu','mps','cuda'}: raise ValueError('Unsupported inference device')
    if device.type == 'cuda' and (not torch.cuda.is_available() or not torch.cuda.is_bf16_supported()):
        raise ValueError('CUDA inference requires BF16-capable device')
    if device.type == 'mps' and not torch.backends.mps.is_available(): raise ValueError('MPS unavailable')
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['NANOCHAT_DTYPE'] = 'bfloat16' if device.type == 'cuda' else 'float32'
    sys.path.insert(0, str(Path(repo).resolve()))
    from nanochat.gpt import GPT, GPTConfig
    from nanochat.tokenizer import RustBPETokenizer
    from nanochat.common import COMPUTE_DTYPE
    expected_dtype = torch.bfloat16 if device.type == 'cuda' else torch.float32
    if COMPUTE_DTYPE != expected_dtype: raise ValueError('Previously imported nanochat compute dtype differs; start a fresh process')
    tokenizer = RustBPETokenizer.from_directory(str(tokenizer_directory))
    token_contract(tokenizer)
    with torch.device('meta'):
        model = GPT(GPTConfig(**config))
    if sum(p.numel() for p in model.parameters()) > 1_000_000_000:
        raise ValueError('Checkpoint configuration exceeds authorized model size')
    model.to_empty(device=device); model.init_weights()
    payload = torch.load(checkpoint/'payload.pt', map_location='cpu', weights_only=True)
    model.load_state_dict(payload['model'], strict=True)
    del payload
    model.eval()
    return model, tokenizer, metadata


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', required=True); p.add_argument('--checkpoint',required=True)
    p.add_argument('--tokenizer',required=True);p.add_argument('--tokenizer-sha256',required=True)
    p.add_argument('--device',choices=['cpu','mps','cuda'],default='cpu')
    p.add_argument('--tools',default='',help='Trusted host allowlist: calculate,convert; empty disables calls')
    p.add_argument('--reply-budget',type=int,default=256)
    p.add_argument('--allow-base',action='store_true',help='Diagnostic exploration only; does not claim usable chat')
    args=p.parse_args()
    allowed=[] if not args.tools else args.tools.split(',')
    policy={'permit_calls':bool(allowed),'allowed_names':allowed};host_policy(policy)
    model,tok,metadata=load_own_bundle(args.repo,args.checkpoint,args.tokenizer,
        tokenizer_sha256=args.tokenizer_sha256,device=args.device,allow_base=args.allow_base)
    chat=BrokerChat(tok,lambda ids,n:generate_action(model,tok,ids,n),
                    context=min(CONTEXT,model.config.sequence_len),reply_budget=args.reply_budget)
    print(json.dumps({'status':'loaded','step':metadata['step'],'device':args.device,
                      'tools':allowed,'diagnostic_base_mode':args.allow_base,'commands':['/reset','/quit']}))
    while True:
        try: text=input('you> ')
        except (EOFError,KeyboardInterrupt): break
        if text=='/quit': break
        if text=='/reset': chat.reset();print('Session reset.');continue
        result=chat.turn(text,policy=policy)
        print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__': main()

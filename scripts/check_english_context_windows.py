"""Local diagnostic: raw English chat and counterfactual recall across context lengths."""
import argparse
import json
from pathlib import Path
import sys

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cloud_training.ganesh_sft_repair import encode_conversation_repaired
from cloud_training.nano_chat_format import encode_conversation, token_contract
from cloud_training.nano_package import TOKENIZER_SHA, sha
from cloud_training.nano_serve import load_own_bundle


def run(label, path, write, budget, live_only, short_answers):
    model, tok, meta = load_own_bundle(ROOT / 'runs/nanochat-source', path,
        ROOT / 'runs/ownbase-v2-data/tokenizer', tokenizer_sha256=TOKENIZER_SHA,
        device='mps', allow_base=label == 'Base10B')
    from nanochat.engine import KVCache
    c = token_contract(tok)
    render = encode_conversation_repaired if label == 'Base10B' else encode_conversation
    def frame(user):
        return render(tok, [dict(role='user', content=user)], for_generation=True)['ids']
    def scripted(history, question, answer):
        return history + frame(question)[bool(history):] + tok.encode(answer) + [c['<|assistant_end|>']]

    for window in [2048, 4096, 8192]:
        model.config.sequence_len = window
        model.window_sizes = model._compute_window_sizes(model.config)
        def reply(prefix, budget):
            assert len(prefix) + budget <= window <= model.cos.shape[1]
            cfg = model.config
            cache = KVCache(1, cfg.n_kv_head, len(prefix)+budget, cfg.n_embd//cfg.n_head,
                            cfg.n_layer, 'mps', torch.float32)
            ids = []
            inputs = prefix
            for _ in range(budget):
                logits = model(torch.tensor([inputs], device='mps'), kv_cache=cache)[0,-1]
                if not torch.isfinite(logits).all():
                    raise ValueError('Nonfinite logits')
                token = int(logits.argmax().item())
                ids.append(token)
                if token in c.values():
                    break
                inputs = [token]
            text = tok.decode(ids[:-1] if ids[-1] in c.values() else ids)
            status = ('complete' if ids[-1] == c['<|assistant_end|>'] and text.strip()
                      else 'invalid_frame' if ids[-1] in c.values() else 'budget_exhausted')
            return dict(input_tokens=len(prefix), ids=ids, text=text, status=status)
        def record(kind, **result):
            write(dict(model=label, step=meta['step'], manifest=sha(path/'manifest.json'),
                       window=window, kind=kind, reply_budget=budget if kind == 'live' else 16, **result))
        history = []
        blocked = False
        questions = ["Hi! I'm Mira. I'm packing for a picnic. What is one easy thing I can bring?",
                     "My bag is small. Could you suggest something that fits?",
                     "By the way, what is my name?", "What was I packing for?"]
        if short_answers:
            questions = ["Hi, my name is Mira. What's my name?",
                         "I have a blue bag. What colour is my bag?",
                         "Actually, my bag is green now. What colour is it now?",
                         "What is my name, and what colour is my bag now?"]
        for user in questions:
            if blocked:
                record('live', user=user, status='blocked')
                continue
            prefix = history + frame(user)[bool(history):]
            r = reply(prefix, budget)
            record('live', user=user, **r)
            blocked = r['status'] != 'complete'
            history = prefix + r['ids']
        if live_only:
            continue
        for name in ['Mira','Nora']:
            history = scripted([], f"Hi, my name is {name}. I am planning a picnic.", "That sounds nice.")
            question = frame("What is my name? Reply with just my first name.")[1:]
            # Supply complete exchanges as a separate controlled retrieval task.
            filler = [
                ('What could we put in the basket?', 'Some fruit and a loaf of bread would fit.'),
                ('What if the grass is damp?', 'Bring a folded blanket to sit on.'),
                ('How should we pack the cups?', 'Wrap them in a clean towel.'),
                ('What can we do after lunch?', 'A short walk by the pond sounds pleasant.')]
            i = 0
            while True:
                candidate = scripted(history, *filler[i % len(filler)])
                if len(candidate) + len(question) + 16 > window:
                    break
                history = candidate
                i += 1
            prefix = history + question
            r = reply(prefix, 16)
            correct = r['status'] == 'complete' and r['text'].strip(' .!\n').casefold()==name.casefold()
            record('supplied_history', expected=name, filler_turns=i, exact=correct, **r)
        print(label,window,'done',flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--live-budget', type=int, choices=[64, 256], default=64)
    parser.add_argument('--live-only', action='store_true')
    parser.add_argument('--short-answers', action='store_true')
    args = parser.parse_args()
    with args.output.open('x') as stream, torch.inference_mode():
        def write(row):
            stream.write(json.dumps(row, ensure_ascii=False)+'\n')
            stream.flush()
        run('SFT194', ROOT/'runs/ownbase-budget50-v1/local-candidates/new-base-2k-8epochs',
            write, args.live_budget, args.live_only, args.short_answers)

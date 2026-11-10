"""Fixed qualitative base completions, never chat/tool acceptance or optimization criteria."""
from pathlib import Path
import time

FINAL_TOKENIZER_SHA256='ad777bb448ea8fcf115835548596f9303f3ee5e85a014b0bb315567091080cc5'
PROMPTS=(
    'The rain stopped just before sunrise. When Mira opened the window,',
    'A library lends books to readers. Readers return the books so that',
    'The blue notebook belongs to Arun. The green notebook belongs to Leela. Arun picked up his',
    'On Monday the parcel was in Pune. On Tuesday it arrived in Kochi. Its most recent location was',
)
MAX_NEW_TOKENS=32


def configuration(enabled):
    return {'enabled':bool(enabled),'version':1,'prompts':list(PROMPTS),
            'max_new_tokens_per_prompt':MAX_NEW_TOKENS,'max_total_new_tokens':128,
            'decoding':'greedy raw, no repetition penalty',
            'purpose':'qualitative base diagnostics only; not chat/tool acceptance or optimization criterion'}


def load_tokenizer(directory,expected_sha256):
    from cloud_training.nano_data import sha256_file
    if expected_sha256!=FINAL_TOKENIZER_SHA256 or sha256_file(Path(directory)/'tokenizer.pkl')!=expected_sha256:
        raise ValueError('Probes require the frozen final own tokenizer')
    from nanochat.tokenizer import RustBPETokenizer
    return RustBPETokenizer.from_directory(str(directory))


def run_probes(model,tokenizer,*,should_stop=lambda:False):
    import torch
    from cloud_training.nano_checkpoint import capture_rng,restore_rng_state
    rng=capture_rng();modes=[(m,m.training) for m in model.modules()]
    tick=time.monotonic();results=[]
    device=next(model.parameters()).device
    try:
        model.eval()
        with torch.inference_mode():
            for prompt in PROMPTS:
                if should_stop():break
                start=time.monotonic()
                prompt_ids=list(tokenizer.encode(prompt,prepend=tokenizer.get_bos_token_id()))
                if not prompt_ids or len(prompt_ids)+MAX_NEW_TOKENS>model.config.sequence_len:
                    raise ValueError('Complete probe exceeds model context; no truncation permitted')
                ids=torch.tensor([prompt_ids],dtype=torch.long,device=device);generated=[]
                for _ in range(MAX_NEW_TOKENS):
                    if should_stop():break
                    logits=model(ids)[:,-1,:]
                    if not bool(torch.isfinite(logits).all()):raise ValueError('Nonfinite probe logits')
                    token=int(logits.argmax(dim=-1).item());generated.append(token)
                    ids=torch.cat((ids,ids.new_tensor([[token]])),dim=1)
                results.append({'prompt':prompt,'prompt_ids':prompt_ids,'generated_ids':generated,
                    'raw_completion':tokenizer.decode(generated),'seconds':time.monotonic()-start,
                    'complete':len(generated)==MAX_NEW_TOKENS})
        return {'configuration':configuration(True),'results':results,'seconds':time.monotonic()-tick,
                'generated_tokens':sum(len(r['generated_ids']) for r in results),
                'complete':len(results)==len(PROMPTS) and all(r['complete'] for r in results)}
    finally:
        for module,mode in modes:module.training=mode
        restore_rng_state(rng)

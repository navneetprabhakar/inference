#!/usr/bin/env python3
"""Freeze the local pilot BPE and prepare all admitted foundation train tokens."""
# Creator: Navneet Prabhakar
import json
import time
from pathlib import Path
from slm.common.config import Config
from slm.common.tokenizer import BPE
from slm.data.tokenized import build_shards,sha


def main():
    root=Path('data/iteration-two-foundation-prepared-v1')
    if root.exists():raise FileExistsError(root)
    release=Path('data/iteration-two-foundation-research-v1');tokenizers=Path('data/iteration-two-foundation-tokenizers-v1')
    comparison=Path('reports/milestone-forty-seven-tokenizer-comparison.json')
    measurements=json.loads(comparison.read_text());tokenizer=tokenizers/'vocab-16384';bpe=BPE.load(tokenizer)
    config=Config(**json.loads(Path('configs/target-81m.json').read_text()))
    if bpe.vocab_size!=config.vocab_size:raise ValueError('Actual full pilot vocabulary required')
    candidates={c['training']['actual_vocab_size']:c for c in measurements['candidates']}
    if any(c['training']['release_manifest_sha256']!=sha(release/'manifest.json') for c in candidates.values()):raise ValueError('Tokenizer comparison release differs')
    root.mkdir();started=time.monotonic()
    freeze=dict(version=1,creator='Navneet Prabhakar',scope='local_iteration_two_foundation_pilot',production_frozen=False,
        release_manifest_sha256=sha(release/'manifest.json'),comparison_file_sha256=sha(comparison),
        tokenizer_manifest_sha256=sha(tokenizer/'manifest.json'),selected_vocab_size=bpe.vocab_size,
        config=config.to_dict(),parameters=config.parameter_count,
        initialization='New canonical random chain required: IDs differ from iteration one. No reused embeddings or optimizer state.',
        selection='Select 16K for the laptop experiment: 24K saves 3.53 percent of serialized validation positions but adds 4194304 parameters and a 50 percent larger vocabulary dimension. No measured latency or memory-speed tradeoff is claimed. Heldout token counts and development byte round-trips are sizing evidence, not language-quality selection.',
        limitations='Train-only fitting, with validation and test token-sizing metrics reported separately. Exact-message token counts do not establish substring or semantic uniqueness. This is a pilot-specific freeze; broader language/styles/content/tools and production selection remain open.')
    (root/'tokenizer-freeze.json').write_text(json.dumps(freeze,indent=2,sort_keys=True)+'\n')
    prepared=build_shards(release,tokenizer,root/'tokens','foundation',context_length=1024,max_positions=12000000)
    report=dict(creator='Navneet Prabhakar',freeze=freeze,token_preparation=prepared,elapsed_seconds=time.monotonic()-started,
        script_sha256=sha(__file__),tokenizer_freeze_sha256=sha(root/'tokenizer-freeze.json'),new_neural_updates=0,
        scope='All admitted train rows prepared once, without truncation. Preparation ceiling is not a training allowance. Optimizer comparison, cumulative physical budget, main schedule and validation protocol still must be frozen before launch.')
    (root/'preparation.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    with Path('reports/milestone-forty-seven-token-preparation.json').open('x') as out:out.write(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':main()

"""Run the proof-gated uniform main stage, or its exact MLX return assessment."""
# Creator: Navneet Prabhakar
import os
os.environ['NVIDIA_TF32_OVERRIDE']='0'
import importlib.util,json,sys
from pathlib import Path
import numpy as np
from slm.data.stream_hash import sha
from slm.data.english_foundation_adapter import CurriculumBatches
from slm.common.curriculum import CurriculumTrainer
from slm.common.tokenizer import BPE
from slm.data.english_corpus import lines,save
from slm.eval.portability import compare
ROOT=Path('data/english-uniform-main-run-v3');CORPUS=Path('data/english-recovery-corpus-v1')
TOK=Path('data/iteration-two-foundation-tokenizers-v1/vocab-16384')


def main():
    p=json.loads((ROOT/'plan.json').read_text())
    for name,h in p['inputs'].items():
        if sha(name)!=h:raise ValueError('Frozen uniform-main dependency differs: '+name)
    if sys.argv[1]=='language':
        import torch
        torch.set_num_threads(4);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
        if not torch.cuda.is_available() or torch.cuda.device_count()!=1 or 'L4' not in torch.cuda.get_device_name(0):
            raise ValueError('Actual single authorized L4 required')
        from slm.english_main_v3 import run
        run(p,ROOT,CORPUS,TOK,sha(ROOT/'plan.json'));return
    if sys.argv[1]!='return-assess':raise ValueError('Explicit uniform-main or return assessment action required')
    spec=importlib.util.spec_from_file_location('_exact_return_helpers','scripts/run-english-learning-v2.py')
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    docs=list(lines(CORPUS/'development.jsonl'));bpe=BPE.load(TOK);origin=ROOT/'language/terminal'
    with CurriculumBatches(ROOT/'curriculum',p['curriculum_bindings'],TOK,p['curriculum_sha256']) as data:
        t=CurriculumTrainer.resume(origin,data,'mlx','default',sha(TOK/'manifest.json'))
        exact=helper.exact_import(t,origin);helper.snapshot(t,bpe,docs,ROOT/'language/returned-mlx-inference.npz')
        metrics=compare(dict(np.load(ROOT/'language/returned-mlx-inference.npz',allow_pickle=False)),
                        dict(np.load(ROOT/'language/terminal-inference.npz',allow_pickle=False)),
                        policy='full_depth_fp32_v1',config=t.config)
        save(ROOT/'language/return-inference.json',dict(creator='Navneet Prabhakar',passed=True,exact_import=exact,metrics=metrics))
    del t
    from slm.english_language_stage import conversations
    conversations(origin/'model',TOK,ROOT/'language/conversation-100-mlx','mlx','default')


if __name__=='__main__':main()

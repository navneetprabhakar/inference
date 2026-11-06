"""Freeze the prospective own-base tranche after corpus and benchmark verification."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from checkpoint import checksum
from pretrained_base import continuation_parent
from gpt2 import Config

REPORT=Path(__file__).resolve().parent
DATA=ROOT/'data/base-foundation-100m'

def main():
    output=REPORT/'budget.json'
    if output.exists():raise FileExistsError('Do not replace a frozen budget')
    verification=json.loads((DATA/'verification.json').read_text())
    assert verification['state']=='passed'
    benchmark_path=ROOT/'runs/base-layout-benchmark-512/status.json'
    benchmark=json.loads(benchmark_path.read_text())
    assert benchmark['state']=='passed' and benchmark['selected']=='bf16-b2-t512'
    assert benchmark['comparison']['passed'] and benchmark['checkpoint_roundtrip'].startswith('exact logits')
    diagnostic=REPORT/'diagnostics.json'
    assert checksum(diagnostic)=='82ad6c3d7ddf2fba301ac1ecc68d77c3ad815bcee6608dbc21140782f91be03b'
    manifest=json.loads((DATA/'manifest.json').read_text())
    assert manifest['shards']['fineweb-train']['tokens']>=120_000_000
    assert manifest['shards']['fineweb-validation']['tokens']>=2_000_000
    result=dict(budget_name='own-base-foundation-100m-v1',
                parent_checkpoint=dict(path='runs/astra-candidate-01/step-000600-f029b7d3cf7921b72911697c38a6a697608af3646c2d9f8fe7d6ed90eda734a4.pt',sha256='f029b7d3cf7921b72911697c38a6a697608af3646c2d9f8fe7d6ed90eda734a4'),
                corpus=str(DATA),manifest_sha256=checksum(DATA/'manifest.json'),
                validation_blocks_sha256=checksum(DATA/'validation-blocks.json'),
                diagnostics=str(diagnostic),diagnostics_sha256=checksum(diagnostic),
                seed=20261106,length=512,microbatch=2,targets_per_update=8192,target_tokens=99_999_744,bf16=True,
                scheduler=dict(peak_lr=6e-5,warmup_tokens=1_000_000,decay_start_tokens=80_000_000,
                               horizon_tokens=99_999_744,end_fraction=.1),
                active_seconds=36*3600,calendar_seconds=7*86400,lease_seconds=4*3600,
                protocol_sha256=checksum(REPORT/'PROTOCOL.md'),
                benchmark=dict(path=str(benchmark_path),sha256=checksum(benchmark_path)),
                verification_sha256=checksum(DATA/'verification.json'),
                code_sha256={name:checksum(ROOT/name) for name in
                             ('base_train.py','base_run_control.py','base_supervise.py','gpt2.py','train.py',
                              'guards.py','checkpoint.py','tokenizer.py','pretrained_base.py','pretrain.py')},
                optimizer_initialization='Fresh AdamW moments on verified own pre-SFT weights; full-state resumes thereafter',
                quality_policy='Prospective fixed-window loss and text/context diagnostics; numerical/resource failures stop; two successive material regressions versus best trigger reproducibility check and stop; plateau is review-only',
                authorization='User authorized hands-off local execution and corpus acquisition, then explicitly reaffirmed own base model objective; no pretrained weights and no paid compute')
    parent=continuation_parent(result,Config())
    assert checksum(Path(parent['path']))==parent['sha256']
    with output.open('x') as stream:stream.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(budget=str(output),sha256=checksum(output),parent=parent['sha256'],target_tokens=result['target_tokens']),indent=2))

if __name__=='__main__':main()

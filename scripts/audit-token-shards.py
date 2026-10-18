#!/usr/bin/env python3
"""Synthetic test-fixture reader audit; mock reviews are never real source clearance."""
# Creator: Navneet Prabhakar
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from slm.common.tokenizer import train_core
from slm.data.tokenized import build_shards
from slm.data.review import prepare,release


def audit(output,repeat_words=50000):
    output=Path(output)
    if output.exists():raise FileExistsError(output)
    if type(repeat_words) is not int or not 1<=repeat_words<=100000:raise ValueError('Bounded synthetic fixture size required')
    # Reuse the explicitly synthetic review fixtures. No public packet is modified.
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
    from test_review import fixture_snapshot,approved_packet
    with tempfile.TemporaryDirectory(prefix='slm-shard-fixture-') as name:
        root=Path(name)
        fixture_snapshot(root/'raw',kind='prose',repeat_words=repeat_words)
        prepare(root/'raw',root/'mock-review.json',30);approved_packet(root/'mock-review.json')
        release(root/'raw',root/'mock-review.json',root/'mock-reviewed')
        tokenizer=train_core([' '.join(f'word{i}' for i in range(30))]*20,512)
        tokenizer.save(root/'tokenizer',{'scope':'Synthetic repeated-word mechanics; not a selected production tokenizer'})
        build=build_shards(root/'mock-reviewed',root/'tokenizer',root/'tokens','foundation')
        subprocess.run([sys.executable,'-m','slm.eval.dataio','--dataset',str(root/'tokens'),
            '--tokenizer',str(root/'tokenizer'),'--output',str(root/'reader.json')],check=True,stdout=subprocess.DEVNULL)
        reader=json.loads((root/'reader.json').read_text())
    report={'scope':'Synthetic repeated-word fixture and simulated review state only; no real human/source approval, no language quality or pretraining claim',
        'repeat_words_per_fixture_record':repeat_words,'fixture_records_before_filtering':30,
        'real_human_approvals':0,'public_training_examples_used':0,'neural_updates':0,
        'temporary_fixture_removed':True,'build':build,'fresh_process_reader':reader}
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x') as handle:handle.write(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);p.add_argument('--repeat-words',type=int,default=50000)
    a=p.parse_args();print(json.dumps(audit(a.output,a.repeat_words),indent=2))

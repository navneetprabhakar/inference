#!/usr/bin/env python3
"""Scripted local runtime controls plus actual random-student negatives; no training."""
# Creator: Navneet Prabhakar
from copy import deepcopy
import argparse
import json
from pathlib import Path
import tempfile
import numpy as np
from slm.common.config import Config,initialize
from slm.common.checkpoint import save
from slm.common.tokenizer import train_core
from slm.data.tokenized import sha
from slm.eval.conversation import write_new
from slm.eval.tool_cases import tool_cases
from slm.eval.tools import score_task
from slm.inference.tools import ToolModel,run_turn
from slm.tools.local import LocalTools


class ScriptedControl:
    identity={'source':'scripted_oracle_control','student':False}
    def __init__(self,actions):self.actions=deepcopy(actions)
    def generate_decision(self,history,max_new_tokens):return {'source':'scripted_control_not_student'},self.actions.pop(0)


def run(output,artifacts,backend='mlx',device='cpu'):
    output,artifacts=Path(output),Path(artifacts)
    if output.exists() or artifacts.exists():raise FileExistsError('Fresh audit destinations required')
    artifacts.mkdir(parents=True);registry=LocalTools();cases=tool_cases();positive=[];negative=[]
    for case in cases:
        actions=[case['expected_action']]+([case['expected_final']] if case['expected_action']['kind']=='call' else [])
        report=run_turn(ScriptedControl(actions),case['history'],registry);scored=score_task(case,report)
        if not scored['structured_task_passed']:raise AssertionError('Scripted positive control failed')
        positive.append({'scenario':case,'report':report,'score':scored})
    wrong=deepcopy(cases[0]['expected_action']);wrong['arguments']['right']=3
    wrong_final={'kind':'answer','text':'The synthetic total is 3750 minor units.','facts':{'total_minor':3750}}
    fault=run_turn(ScriptedControl([wrong,wrong_final]),cases[0]['history'],registry);fault_score=score_task(cases[0],fault)
    if fault_score['structured_task_passed'] or not fault_score['checks']['execution_success']:raise AssertionError('Semantic negative control is ineffective')
    write_new(artifacts/'scripted-controls.json',positive);write_new(artifacts/'wrong-quantity.json',{'report':fault,'score':fault_score})
    rng=np.random.default_rng(1801);words=[''.join(rng.choice(list('abcdefghijklmnopqrstuvwxyz'),12)) for _ in range(1000)]
    with tempfile.TemporaryDirectory(prefix='slm-tool-negative-') as temp:
        root=Path(temp);bpe=train_core([' '.join(words)]*2,512,min_frequency=1);bpe.save(root/'tokenizer',{'scope':'Independent random-word mechanics tokenizer'})
        c=Config(vocab_size=bpe.vocab_size,max_seq_len=4096);save(root/'model',c,initialize(c,1703))
        model=ToolModel(root/'model',root/'tokenizer',backend,device,expected_tokenizer_hash=sha(root/'tokenizer/manifest.json'))
        for case in cases:
            report=run_turn(model,case['history'],registry,max_new_tokens=8);scored=score_task(case,report)
            if scored['structured_task_passed'] or report['executed_calls']:raise AssertionError('Random negative unexpectedly passed or executed; inspect before acceptance')
            negative.append({'scenario_id':case['scenario_id'],'report':report,'score':scored})
        identity=deepcopy(model.identity)
    write_new(artifacts/'random-student.json',negative)
    report={'creator':'Navneet Prabhakar','registry_hash':registry.fingerprint,'tool_names':[t['name'] for t in registry.discover()],
        'scripted_positive_controls':{'cases':len(positive),'structured_passes':len(positive),'student':False,'free_text_verified':False},
        'wrong_quantity_control':fault_score,'actual_random_student':{'parameters':c.parameter_count,'cases':len(negative),
            'structured_passes':0,'executed_calls':0,'statuses':[r['report']['status'] for r in negative],'identity':identity},
        'new_training_updates':0,'new_teacher_calls':0,'new_cloud_jobs':0,'production_accepted':False,
        'artifact_sha256':{str(p):sha(p) for p in sorted(artifacts.iterdir())},
        'source_sha256':{str(p):sha(p) for p in [Path('scripts/audit-tools.py'),*sorted(Path('src/slm/tools').glob('*.py')),Path('src/slm/inference/tools.py'),Path('src/slm/inference/greedy.py'),Path('src/slm/common/tool_serialization.py'),Path('src/slm/eval/tools.py'),Path('src/slm/eval/tool_cases.py')]},
        'scope':'Pure synthetic local runtime/serializer controls, no learned tool capability, free-text meaning/style judgment, MCP transport or production data approval'}
    write_new(output,report);return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);p.add_argument('--artifacts',required=True);p.add_argument('--backend',choices=['mlx','torch'],default='mlx');p.add_argument('--device',default='cpu')
    a=p.parse_args();r=run(a.output,a.artifacts,a.backend,a.device);print(json.dumps({k:r[k] for k in ('tool_names','scripted_positive_controls','new_training_updates','production_accepted')},indent=2))


if __name__=='__main__':main()

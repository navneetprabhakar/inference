#!/usr/bin/env python3
"""Actual MCP process controls and random student negatives, no remote service or training."""
# Creator: Navneet Prabhakar
from copy import deepcopy
from importlib.metadata import version
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import numpy as np
from slm.mcp.registry import MCPRegistry,MCPFailure
from slm.common.config import Config,initialize
from slm.common.checkpoint import save
from slm.common.tokenizer import train_core
from slm.data.tokenized import sha
from slm.eval.conversation import write_new
from slm.eval.tool_cases import tool_cases
from slm.eval.tools import score_task
from slm.inference.tools import ToolModel,run_turn
from slm.tools.local import ExecutionRefused


class Scripted:
    identity={'source':'scripted_oracle_control','student':False}
    def __init__(self,actions):self.actions=deepcopy(actions)
    def generate_decision(self,messages,max_new_tokens):return {'source':'scripted_control_not_student'},self.actions.pop(0)


def absent(pid):
    try:os.kill(pid,0);return False
    except ProcessLookupError:return True


def run(output,artifacts,backend='mlx',device='cpu'):
    output,artifacts=Path(output),Path(artifacts)
    if output.exists() or artifacts.exists():raise FileExistsError('Fresh audit destinations required')
    artifacts.mkdir(parents=True);positives=[];negatives=[];probes=[]
    with tempfile.TemporaryDirectory(prefix='slm-mcp-audit-') as temp:
        root=Path(temp)
        def connection(tag,fault='none',**kwargs):
            return MCPRegistry([sys.executable,'-m','slm.mcp.fixture_server','--fault',fault,'--pid-file',str(root/(tag+'.pid')),
                '--call-file',str(root/(tag+'.calls'))],namespace='fixture',timeout=kwargs.pop('timeout',3),**kwargs)
        registry=connection('positive')
        with registry:
            catalogue=registry.discover();catalogue_hash=registry.fingerprint
            for original in tool_cases():
                case=deepcopy(original)
                if case['expected_action']['kind']=='call':case['expected_action']['name']=registry.alias_for('fixture.'+case['expected_action']['name'])
                model=Scripted([case['expected_action']]+([case['expected_final']] if case['expected_action']['kind']=='call' else []))
                trace=run_turn(model,case['history'],registry);score=score_task(case,trace)
                if not score['structured_task_passed']:raise AssertionError('Scripted MCP control failed')
                positives.append({'scenario':case,'trace':trace,'score':score})
        peer_calls=[json.loads(v) for v in (root/'positive.calls').read_text().splitlines()]
        if len(peer_calls)!=5 or not absent(registry.transport.stats['pid']):raise AssertionError('MCP controls or cleanup incomplete')
        positive_audit=registry.audit();positive_audit['parent_absent_verified']=True
        write_new(artifacts/'positive-traces.json',positives);write_new(artifacts/'peer-calls.json',peer_calls)
        for tag in ('legacy','call_hang','changed','stdout_oversize','stubborn_child'):
            r=connection(tag,'none' if tag=='legacy' else tag,mode='legacy' if tag=='legacy' else 'auto',timeout=1 if tag=='call_hang' else 3)
            event={'probe':tag,'expected_failure_observed':False}
            try:
                with r:
                    action={'kind':'call','id':'c1','name':r.alias_for('fixture.arithmetic'),'arguments':{'operation':'multiply','left':1250,'right':2}}
                    result=r.execute(action)
                    if tag=='changed':
                        action['id']='c2';r.execute(action)
                    if tag in ('call_hang','changed','stdout_oversize'):raise AssertionError('Expected refusal was not observed')
                    if result['data']!={'value':2500}:raise AssertionError('Probe result differs')
            except (MCPFailure,ExecutionRefused,ExceptionGroup) as exc:
                event['expected_failure_observed']=True;event['failure_type']=type(exc).__name__
            event['audit']=r.audit();event['parent_absent_verified']=absent(r.transport.stats['pid'])
            if not event['parent_absent_verified'] or not r.transport.stats['parent_reaped']:raise AssertionError('MCP probe process remains')
            if tag=='stubborn_child':
                pid=int(Path(str(root/(tag+'.pid'))+'.child').read_text())
                state=subprocess.run(['ps','-o','stat=','-p',str(pid)],capture_output=True,text=True).stdout.strip()
                event['child_ps_state']=state;event['child_not_running_verified']=not state or state.startswith('Z')
                if not event['child_not_running_verified']:raise AssertionError('Descendant still running')
            probes.append(event)
        # Independent random-word tokenizer; no candidate prompts/references used as training text.
        rng=np.random.default_rng(1901);words=[''.join(rng.choice(list('abcdefghijklmnopqrstuvwxyz'),12)) for _ in range(1000)]
        bpe=train_core([' '.join(words)]*2,512,min_frequency=1);bpe.save(root/'tokenizer',{'scope':'Independent random mechanics tokenizer'})
        config=Config(vocab_size=bpe.vocab_size,max_seq_len=4096);save(root/'model',config,initialize(config,1703))
        model=ToolModel(root/'model',root/'tokenizer',backend,device,expected_tokenizer_hash=sha(root/'tokenizer/manifest.json'))
        negative=connection('negative')
        with negative:
            for original in tool_cases():
                case=deepcopy(original)
                if case['expected_action']['kind']=='call':case['expected_action']['name']=negative.alias_for('fixture.'+case['expected_action']['name'])
                trace=run_turn(model,case['history'],negative,max_new_tokens=8);score=score_task(case,trace)
                if score['structured_task_passed'] or trace['executed_calls']:raise AssertionError('Random control unexpectedly passed or submitted a tool')
                negatives.append({'scenario_id':case['scenario_id'],'trace':trace,'score':score})
        if negative.metrics['tool_requests_submitted'] or not absent(negative.transport.stats['pid']):raise AssertionError('Negative control submitted or leaked')
        negative_audit=negative.audit();negative_audit['parent_absent_verified']=True
        write_new(artifacts/'negative-traces.json',negatives);write_new(artifacts/'lifecycle-probes.json',probes)
        report={'creator':'Navneet Prabhakar','mcp_sdk':version('mcp'),'catalogue_hash':catalogue_hash,'tools':catalogue,
            'scripted_controls':{'cases':7,'structured_passes':7,'student':False,'free_text_verified':False,
                'actual_peer_tool_calls':len(peer_calls),'audit':positive_audit},
            'random_student':{'parameters':config.parameter_count,'cases':7,'structured_passes':0,'tool_submissions':0,
                'statuses':[v['trace']['status'] for v in negatives],'identity':model.identity,'audit':negative_audit},
            'lifecycle_probes':probes,'runtime_audit_training_updates':0,'new_teacher_calls':0,'new_cloud_jobs':0,'production_accepted':False,
            'artifact_sha256':{str(p):sha(p) for p in sorted(artifacts.iterdir())},
            'source_sha256':{str(p):sha(p) for p in [Path('scripts/audit-mcp.py'),*sorted(Path('src/slm/mcp').glob('*.py')),
                Path('src/slm/inference/tools.py'),Path('src/slm/tools/local.py'),Path('requirements-mcp-reference.lock')]},
            'scope':'Actual local stdio SDK interoperability and bounded lifecycle controls on this host, not real-service authorization, HTTP, learned capability or actual CUDA MCP validation'}
    write_new(output,report);return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);p.add_argument('--artifacts',required=True);p.add_argument('--backend',choices=['mlx','torch'],default='mlx');p.add_argument('--device',default='cpu')
    a=p.parse_args();r=run(a.output,a.artifacts,a.backend,a.device)
    print(json.dumps({'sdk':r['mcp_sdk'],'scripted_passes':r['scripted_controls']['structured_passes'],'actual_peer_calls':r['scripted_controls']['actual_peer_tool_calls'],
        'random_passes':r['random_student']['structured_passes'],'production_accepted':False},indent=2))


if __name__=='__main__':main()

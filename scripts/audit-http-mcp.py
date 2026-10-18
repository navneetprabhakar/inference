#!/usr/bin/env python3
"""Local HTTP/TLS MCP evidence, scripted controls and an actual random student."""
# Creator: Navneet Prabhakar
from copy import deepcopy
from importlib.metadata import version
import argparse
import json
from pathlib import Path
import socket
import sys
import tempfile
from urllib.parse import urlsplit
import numpy as np
import pytest
from slm.common.config import Config,initialize
from slm.common.checkpoint import save
from slm.common.tokenizer import train_core
from slm.data.tokenized import sha
from slm.eval.conversation import write_new
from slm.eval.tool_cases import tool_cases
from slm.eval.tools import score_task
from slm.inference.tools import ToolModel,run_turn
from slm.mcp.registry import MCPFailure

# Reuse only the development fixture owner and TLS generator, not task assertions.
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
from test_mcp_http import http_server,tls_files,connection,rows,call


class Scripted:
    identity={'source':'scripted_oracle_control','student':False}
    def __init__(self,actions):self.actions=deepcopy(actions)
    def generate_decision(self,messages,max_new_tokens):return {'source':'scripted_control_not_student'},self.actions.pop(0)


def closed(registry):
    audit=registry.audit();t=audit['transport']
    if not (audit['connection']['connection_closed'] and t['http_client_closed'] and t['network_closed'] and t['open_responses']==0):
        raise AssertionError('HTTP client resources remain open')
    return audit


def owner_closed(server):
    if server['process'].poll() is None:raise AssertionError('Fixture owner did not reap server')
    url=urlsplit(server['url'])
    with socket.socket() as client:
        client.settimeout(.5)
        if client.connect_ex((url.hostname,url.port))==0:raise AssertionError('Fixture listener remains open')
    return {'server_reaped':True,'listener_closed':True}


def run(output,artifacts,backend='mlx',device='cpu'):
    output,artifacts=Path(output),Path(artifacts)
    if output.exists() or artifacts.exists():raise FileExistsError('Fresh evidence destinations required')
    artifacts.mkdir(parents=True);positives=[];negatives=[];probes=[];secrets=[]
    with tempfile.TemporaryDirectory(prefix='slm-http-audit-') as temp,pytest.MonkeyPatch.context() as patch:
        root=Path(temp)
        with http_server(root/'positive',json_response=False) as server:
            secrets.append(server['token']);registry=connection(server,patch)
            with registry:
                catalogue=registry.discover();catalogue_hash=registry.fingerprint
                for original in tool_cases():
                    case=deepcopy(original)
                    if case['expected_action']['kind']=='call':case['expected_action']['name']=registry.alias_for('fixture.'+case['expected_action']['name'])
                    actions=[case['expected_action']]+([case['expected_final']] if case['expected_action']['kind']=='call' else [])
                    trace=run_turn(Scripted(actions),case['history'],registry);score=score_task(case,trace)
                    if not score['structured_task_passed']:raise AssertionError('Scripted HTTP control failed')
                    positives.append({'scenario':case,'trace':trace,'score':score})
            positive_audit=closed(registry)
            peer=rows(server['root']/'calls.jsonl');requests=rows(server['root']/'requests.jsonl')
            if len(peer)!=5 or registry.tool_submission_count!=5:raise AssertionError('Peer calls differ')
            if server['process'].poll() is not None:raise AssertionError('Client must not stop a separately owned server')
            positive_audit['server_alive_after_client_close']=True
        positive_audit['fixture_owner_cleanup']=owner_closed(server)
        write_new(artifacts/'positive-traces.json',positives);write_new(artifacts/'positive-peer-calls.json',peer)
        write_new(artifacts/'positive-requests.json',requests)
        cert,key=tls_files(root/'tls')
        for tag,options in [('json',{}),('legacy_json',{'mode':'legacy'}),('legacy_sse',{'mode':'legacy','sse':True}),
                            ('trusted_tls',{'tls':True}),('redirect',{}),('auth_call',{}),('oversized_sse',{}),('sse_disconnect',{}),('timeout',{})]:
            failure=tag in ('redirect','auth_call','oversized_sse','sse_disconnect','timeout')
            with http_server(root/tag,fault=tag if failure else 'none',json_response=not options.get('sse',False),
                             cert=cert if options.get('tls') else None,key=key if options.get('tls') else None) as server:
                secrets.append(server['token']);r=connection(server,patch,mode=options.get('mode','auto'),
                    ca_file=cert if options.get('tls') else None,timeout=1.5 if tag in ('timeout','sse_disconnect') else 3)
                event={'probe':tag,'expected_failure_observed':False}
                try:
                    with r:
                        result=r.execute(call(r))
                        if result['data']!={'value':2500}:raise AssertionError('Unexpected arithmetic result')
                except (MCPFailure,ExceptionGroup) as exc:
                    if not failure:raise
                    event.update(expected_failure_observed=True,failure_type=type(exc).__name__)
                if failure!=event['expected_failure_observed']:raise AssertionError('Fault control did not fail')
                event['audit']=closed(r);received=rows(server['root']/'requests.jsonl')
                posts=sum(v['rpc_method']=='tools/call' for v in received)
                if posts!=(0 if tag=='redirect' else 1):raise AssertionError('Tool POST was retried or omitted')
                if any(v['path']=='/trap' or v['last_event_id_present'] for v in received):raise AssertionError('Redirect or replay reached peer')
                event['peer_tool_posts']=posts
                write_new(artifacts/(tag+'-requests.json'),received)
            event['fixture_owner_cleanup']=owner_closed(server);probes.append(event)
        rng=np.random.default_rng(1901);words=[''.join(rng.choice(list('abcdefghijklmnopqrstuvwxyz'),12)) for _ in range(1000)]
        bpe=train_core([' '.join(words)]*2,512,min_frequency=1);bpe.save(root/'tokenizer',{'scope':'Independent random mechanics tokenizer'})
        config=Config(vocab_size=bpe.vocab_size,max_seq_len=4096);save(root/'model',config,initialize(config,1703))
        model=ToolModel(root/'model',root/'tokenizer',backend,device,expected_tokenizer_hash=sha(root/'tokenizer/manifest.json'))
        with http_server(root/'negative') as server:
            secrets.append(server['token']);negative=connection(server,patch)
            with negative:
                for original in tool_cases():
                    case=deepcopy(original)
                    if case['expected_action']['kind']=='call':case['expected_action']['name']=negative.alias_for('fixture.'+case['expected_action']['name'])
                    trace=run_turn(model,case['history'],negative,max_new_tokens=8);score=score_task(case,trace)
                    if score['structured_task_passed'] or trace['executed_calls']:raise AssertionError('Random control passed or submitted')
                    negatives.append({'scenario_id':case['scenario_id'],'trace':trace,'score':score})
            negative_audit=closed(negative)
            if negative.tool_submission_count or rows(server['root']/'calls.jsonl'):raise AssertionError('Random student called tools')
        negative_audit['fixture_owner_cleanup']=owner_closed(server)
        write_new(artifacts/'negative-traces.json',negatives);write_new(artifacts/'lifecycle-probes.json',probes)
        report={'creator':'Navneet Prabhakar','mcp_sdk':version('mcp'),'catalogue_hash':catalogue_hash,'tools':catalogue,
            'scripted_controls':{'cases':7,'structured_passes':7,'student':False,'free_text_verified':False,'actual_peer_tool_calls':len(peer),'audit':positive_audit},
            'random_student':{'parameters':config.parameter_count,'cases':7,'structured_passes':0,'tool_submissions':0,
                'statuses':[v['trace']['status'] for v in negatives],'identity':model.identity,'audit':negative_audit},
            'lifecycle_probes':probes,'runtime_audit_training_updates':0,'new_teacher_calls':0,'new_cloud_jobs':0,'production_accepted':False,
            'source_sha256':{str(p):sha(p) for p in [Path(__file__).relative_to(Path.cwd()),*sorted(Path('src/slm/mcp').glob('*.py')),
                Path('tests/test_mcp_http.py'),Path('src/slm/inference/tools.py'),Path('src/slm/tools/local.py'),Path('requirements-mcp-reference.lock')]},
            'scope':'Local official-SDK HTTP/TLS interoperability, static credentials and bounded lifecycle; no OAuth, real-service authorization, learned capability or CUDA validation'}
        if any(secret in json.dumps(report) for secret in secrets):raise AssertionError('Audit discloses credential')
        for path in artifacts.iterdir():
            if any(secret in path.read_text() for secret in secrets):raise AssertionError('Artifact discloses credential')
        report['artifact_sha256']={str(p):sha(p) for p in sorted(artifacts.iterdir())}
    write_new(output,report);return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);p.add_argument('--artifacts',required=True)
    p.add_argument('--backend',choices=['mlx','torch'],default='mlx');p.add_argument('--device',default='cpu');a=p.parse_args();r=run(a.output,a.artifacts,a.backend,a.device)
    print(json.dumps({'scripted_passes':r['scripted_controls']['structured_passes'],'peer_calls':r['scripted_controls']['actual_peer_tool_calls'],
        'random_passes':r['random_student']['structured_passes'],'lifecycle_probes':len(r['lifecycle_probes']),'production_accepted':False},indent=2))


if __name__=='__main__':main()

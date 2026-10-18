"""Real SDK subprocess transport controls, never learned student tool competence."""
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
import threading
import time
import pytest
pytest.importorskip('mcp');pytest.importorskip('tokenizers')
from slm.mcp.registry import MCPRegistry,MCPFailure,MCPTimeout,schema_validator
from slm.mcp.transport import TransportLimit,wire_json
from slm.tools.local import Session,InvalidArguments,ExecutionRefused
from slm.eval.tool_cases import tool_cases
from slm.eval.tools import score_task
from slm.inference.tools import run_turn
from test_tool_runtime import Script


def server(tmp_path,fault='none',**kwargs):
    return MCPRegistry([sys.executable,'-m','slm.mcp.fixture_server','--fault',fault,'--pid-file',str(tmp_path/'pid'),
        '--call-file',str(tmp_path/'calls')],timeout=kwargs.pop('timeout',3),**kwargs)


def call(registry,name='arithmetic',args=None,id='c1'):
    return {'kind':'call','id':id,'name':registry.alias_for('fixture.'+name),
        'arguments':args or {'operation':'multiply','left':1250,'right':2}}


def assert_closed(registry):
    audit=registry.audit();pid=audit['transport']['pid']
    assert audit['connection']['connection_closed'] and audit['transport']['parent_reaped']
    assert audit['transport']['stdin_closed']
    with pytest.raises(ProcessLookupError):os.kill(pid,0)
    assert not any(t.name=='slm-mcp-'+registry.namespace for t in threading.enumerate())


@pytest.mark.parametrize('mode',['auto','legacy'])
def test_official_sdk_stdio_discovery_pages_calls_aliases_and_cleanup(tmp_path,mode):
    registry=server(tmp_path,mode=mode)
    with registry:
        assert len(registry.discover())==5
        assert registry.metrics['protocol_version']==('2026-07-28' if mode=='auto' else '2025-11-25')
        assert all(v['name'].startswith('mcp_tools_') and '.' not in v['name'] for v in registry.discover())
        fingerprint=registry.fingerprint;view=registry.discover();view[0]['description']='mutation'
        assert registry.fingerprint==fingerprint
        session=Session(registry);result=session.call(call(registry))
        assert result['ok'] and result['data']=={'value':2500}
        assert registry.metrics['list_requests']==6 and registry.metrics['tool_requests_submitted']==1
    assert_closed(registry)
    assert len((tmp_path/'calls').read_text().splitlines())==1
    with pytest.raises(ExecutionRefused):registry.discover()
    with pytest.raises(ValueError):registry.__enter__()


def test_selected_remote_tools_are_explicit_and_aliases_are_stable(tmp_path):
    with server(tmp_path,selected=['fixture.arithmetic'],namespace='math') as a:
        assert len(a.discover())==1;alias=a.alias_for('fixture.arithmetic')
        with pytest.raises(ValueError):a.alias_for('fixture.product_lookup')
        bad=call(a);bad['arguments']['left']=True
        with pytest.raises(InvalidArguments):Session(a).call(bad)
        assert a.metrics['tool_requests_submitted']==0
    with server(tmp_path,selected=['fixture.arithmetic'],namespace='math') as b:assert b.alias_for('fixture.arithmetic')==alias
    assert_closed(a);assert_closed(b)


@pytest.mark.parametrize('fault',['duplicate','remote_ref','repeated_cursor','stdout_invalid','stdout_oversize','startup_hang'])
def test_startup_protocol_limits_and_discovery_failures_reap_child(tmp_path,fault):
    registry=server(tmp_path,fault,timeout=.5 if fault=='startup_hang' else 3)
    started=time.monotonic()
    with pytest.raises(Exception):
        with registry:pass
    assert time.monotonic()-started<6
    assert_closed(registry)
    assert not (tmp_path/'calls').exists()


@pytest.mark.parametrize('fault',['call_hang','disconnect','invalid_output'])
def test_ambiguous_or_invalid_call_never_retries_and_invalidates_connection(tmp_path,fault):
    registry=server(tmp_path,fault,timeout=1)
    with registry:
        action=call(registry);started=time.monotonic()
        with pytest.raises(MCPFailure):registry.execute(action)
        assert time.monotonic()-started<5
        assert registry.metrics['tool_requests_submitted']==1 and registry.metrics['unknown_tool_outcomes']==1
        with pytest.raises(ExecutionRefused):registry.execute(action)
    assert_closed(registry)
    assert len((tmp_path/'calls').read_text().splitlines())==1


def test_catalog_change_is_detected_before_second_tool_submission(tmp_path):
    registry=server(tmp_path,'changed')
    with registry:
        action=call(registry);assert registry.execute(action)['ok']
        action['id']='c2'
        with pytest.raises(ExecutionRefused,match='catalogue changed'):registry.execute(action)
        assert registry.metrics['tool_requests_submitted']==1
    assert_closed(registry)
    assert len((tmp_path/'calls').read_text().splitlines())==1


def test_tool_errors_and_stderr_are_data_and_do_not_trigger_retries(tmp_path):
    registry=server(tmp_path,'tool_error')
    with registry:
        r=registry.execute(call(registry));assert not r['ok'] and r['error']['code']=='mcp_tool_error'
        assert registry.metrics['tool_requests_submitted']==registry.metrics['tool_results_received']==1
    assert_closed(registry)
    registry=server(tmp_path,'stderr')
    with registry:assert registry.execute(call(registry))['ok']
    assert_closed(registry)
    assert registry.audit()['transport']['stderr_bytes']>160000
    assert len(registry.audit()['transport']['stderr_sha256'])==64


def test_local_schema_references_work_without_external_retrieval():
    schema={'type':'object','properties':{'value':{'$ref':'#/$defs/count'}},'required':['value'],
        'additionalProperties':False,'$defs':{'count':{'type':'integer','minimum':1}}}
    validate=schema_validator(schema)
    assert not list(validate.iter_errors({'value':2})) and list(validate.iter_errors({'value':False}))
    for bad in [{'type':'object','$ref':'https://example.org/no-network'},{'type':'object','$id':'https://example.org/base'},{'$schema':'bad'}]:
        with pytest.raises(ValueError):schema_validator(bad)


@pytest.mark.parametrize('payload',[b'{"jsonrpc":"2.0","id":1,"id":2,"result":{}}',b'not JSON',b'\xff',b'{"value":NaN}',b'{"value":1e999}',b'['*40+b'0'+b']'*40])
def test_wire_parser_refuses_duplicates_invalid_utf8_and_nonfinite_or_deep_json(payload):
    with pytest.raises((ValueError,TransportLimit)):wire_json(payload)


def test_seven_scripted_runtime_tasks_use_actual_mcp_calls_with_same_semantic_oracles(tmp_path):
    registry=server(tmp_path)
    with registry:
        for original in tool_cases():
            case=deepcopy(original)
            if case['expected_action']['kind']=='call':case['expected_action']['name']=registry.alias_for('fixture.'+case['expected_action']['name'])
            actions=[case['expected_action']]+([case['expected_final']] if case['expected_action']['kind']=='call' else [])
            report=run_turn(Script(actions),case['history'],registry)
            assert score_task(case,report)['structured_task_passed'] and report['repair_attempts']==0
        assert registry.metrics['tool_requests_submitted']==5
    assert_closed(registry)
    assert len((tmp_path/'calls').read_text().splitlines())==5


@pytest.mark.parametrize('fault',['text_only','media','float_result','large_result'])
def test_mcp_results_are_preserved_as_text_or_rejected_without_silent_coercion(tmp_path,fault):
    registry=server(tmp_path,fault)
    with registry:
        result=registry.execute(call(registry))
        if fault=='text_only':assert result['ok'] and result['data']=={'content':[{'type':'text','text':'Unstructured fixture text'}]}
        else:assert not result['ok'] and result['error']['code']=='unsupported_mcp_result'
        assert registry.metrics['tool_requests_submitted']==registry.metrics['tool_results_received']==1
    assert_closed(registry)


@pytest.mark.parametrize('fault',['wire_large_result','input_required'])
def test_unsupported_wire_or_input_round_does_not_retry_server_action(tmp_path,fault):
    registry=server(tmp_path,fault)
    with registry:
        with pytest.raises(MCPFailure):registry.execute(call(registry))
        assert registry.metrics['tool_requests_submitted']==1
        assert registry.metrics['unknown_tool_outcomes']==1
    assert_closed(registry)
    assert len((tmp_path/'calls').read_text().splitlines())==1


def test_cleanup_terminates_same_group_descendant_even_after_parent_exits(tmp_path):
    registry=server(tmp_path,'stubborn_child')
    with registry:
        assert registry.execute(call(registry))['ok']
        child=Path(str(tmp_path/'pid')+'.child')
        assert child.exists()
        pid=int(child.read_text())
    assert_closed(registry)
    assert 'SIGKILL' in registry.audit()['transport']['signals']
    # Reaping adopted children belongs to the OS. A zombie is terminated, not running.
    import subprocess
    state=subprocess.run(['ps','-o','stat=','-p',str(pid)],capture_output=True,text=True).stdout.strip()
    assert not state or state.startswith('Z')


def test_mcp_submission_count_differs_from_preflight_handler_dispatch(tmp_path):
    registry=server(tmp_path,'changed')
    with registry:
        action=call(registry);registry.execute(action)
        final={'kind':'answer','text':'Fixture value.','facts':{'value':2500}}
        report=run_turn(Script([action,final]),[{'role':'user','content':'Try again.'}],registry)
        assert report['handler_dispatches']==1 and report['executed_calls']==0
        assert registry.metrics['tool_requests_submitted']==1
    assert_closed(registry)


def test_mcp_cli_discovery_and_actual_student_run_close_processes(tmp_path):
    import subprocess
    from slm.common.config import Config,initialize
    from slm.common.tokenizer import train_core
    from slm.common.checkpoint import save
    from slm.data.tokenized import sha
    config={'transport':'stdio','command':[sys.executable,'-m','slm.mcp.fixture_server'],'namespace':'fixture','selected':['fixture.arithmetic']}
    path=tmp_path/'config.json';path.write_text(json.dumps(config))
    base=[sys.executable,'-m','slm.mcp.cli']
    subprocess.run([*base,'discover','--config',str(path),'--output',str(tmp_path/'discovery.json')],check=True,capture_output=True)
    discovery=json.loads((tmp_path/'discovery.json').read_text());assert len(discovery['tools'])==1
    assert discovery['mcp_audit']['transport']['parent_reaped']
    bpe=train_core(['Independent random-word tokenizer fixture.']*3,512);bpe.save(tmp_path/'tok',{'scope':'MCP CLI test only'})
    c=Config(vocab_size=bpe.vocab_size,max_seq_len=4096);save(tmp_path/'model',c,initialize(c,1703))
    (tmp_path/'history.json').write_text(json.dumps([{'role':'user','content':'Multiply 2 by 1250.'}]))
    subprocess.run([*base,'run','--config',str(path),'--model',str(tmp_path/'model'),'--tokenizer',str(tmp_path/'tok'),
        '--tokenizer-hash',sha(tmp_path/'tok/manifest.json'),'--history',str(tmp_path/'history.json'),'--max-new-tokens','4','--output',str(tmp_path/'run.json')],check=True,capture_output=True)
    r=json.loads((tmp_path/'run.json').read_text());assert r['status']=='invalid_decision' and r['executed_calls']==0
    assert r['mcp_audit']['connection']['tool_requests_submitted']==0 and r['mcp_audit']['transport']['parent_reaped']


def test_configuration_is_explicit_and_does_not_accept_model_selected_shell(tmp_path):
    from slm.mcp.cli import configuration
    p=tmp_path/'config.json'
    for value in [{'transport':'http','command':['x']},{'transport':'stdio','command':['x'],'shell':True}]:
        p.write_text(json.dumps(value))
        with pytest.raises(ValueError):configuration(p)
    with pytest.raises(ValueError):MCPRegistry('python -m slm.mcp.fixture_server')


def test_credentials_are_explicit_not_inherited_or_disclosed_in_model_descriptors(tmp_path,monkeypatch):
    from slm.mcp.transport import BoundedStdio
    with pytest.raises(ValueError):BoundedStdio([sys.executable],env={'BAD':True})
    monkeypatch.setenv('OPENAI_API_KEY','fixture-key-must-not-leak')
    # Fixture descriptors contain no environment values; MCP session stores only env key names in its endpoint hash.
    with server(tmp_path,'env_probe',env={'SLM_FIXTURE_PROBE':'fixture-only'}) as registry:
        probe=registry.execute(call(registry))
        assert probe['data']=={'openai_key_present':False,'explicit_probe':'fixture-only'}
        assert 'fixture-key-must-not-leak' not in json.dumps(registry.discover())
        assert registry.transport.env=={'SLM_FIXTURE_PROBE':'fixture-only'}
    assert_closed(registry)


def test_pinned_sdk_version_is_checked_before_spawning(monkeypatch,tmp_path):
    import slm.mcp.registry as module
    monkeypatch.setattr(module,'version',lambda name:'different')
    with pytest.raises(ValueError,match='mcp==2.3.0'):server(tmp_path)
    assert not (tmp_path/'pid').exists()


def test_host_schema_injection_does_not_turn_heldout_tasks_into_training_data():
    from slm.data.holdout import check_training_context
    for history in [tool_cases()[0]['history'],__import__('slm.eval.cases',fromlist=['candidate_suite']).candidate_suite()['cases'][0]['messages']]:
        changed=[{'role':'system','content':'New host schemas and style'},*(history[1:] if history[0]['role']=='system' else history)]
        with pytest.raises(ValueError,match='held-out'):check_training_context(changed)

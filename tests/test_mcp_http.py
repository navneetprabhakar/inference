"""Actual loopback HTTP/TLS SDK controls; no remote service or model skill claims."""
from contextlib import contextmanager
from copy import deepcopy
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid
import pytest
pytest.importorskip('mcp');pytest.importorskip('tokenizers')
from mcp.client.stdio import get_default_environment
from slm.mcp.registry import MCPRegistry,MCPFailure
from slm.mcp.http import BoundedHTTP,endpoint
from slm.eval.tool_cases import tool_cases
from slm.eval.tools import score_task
from slm.inference.tools import run_turn
from test_tool_runtime import Script


def rows(path):return [json.loads(v) for v in Path(path).read_text().splitlines()] if Path(path).exists() else []


@contextmanager
def http_server(root,*,fault='none',json_response=True,cert=None,key=None):
    root.mkdir();token='fixture-'+uuid.uuid4().hex
    command=[sys.executable,'-m','slm.mcp.http_fixture','--port-file',str(root/'port.json'),
        '--request-file',str(root/'requests.jsonl'),'--call-file',str(root/'calls.jsonl'),'--fault',fault]
    if json_response:command.append('--json')
    if cert:command.extend(['--cert',str(cert),'--key',str(key)])
    process=subprocess.Popen(command,env=get_default_environment()|{'SLM_FIXTURE_TOKEN':token},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    try:
        deadline=time.monotonic()+5
        while not (root/'port.json').exists():
            if process.poll() is not None or time.monotonic()>deadline:raise AssertionError('HTTP fixture failed to start')
            time.sleep(.01)
        info=json.loads((root/'port.json').read_text());yield {'url':f"{info['scheme']}://127.0.0.1:{info['port']}/mcp",'token':token,'process':process,'root':root}
    finally:
        if process.poll() is None:
            os.killpg(process.pid,signal.SIGTERM)
            try:process.wait(timeout=2)
            except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=2)
        assert process.returncode is not None


def connection(server,monkeypatch,**kwargs):
    monkeypatch.setenv('SLM_MCP_TEST_AUTH',server['token'])
    return MCPRegistry(url=server['url'],allow_loopback_http=True,bearer_token_env='SLM_MCP_TEST_AUTH',timeout=kwargs.pop('timeout',3),**kwargs)


def call(registry):return {'kind':'call','id':'c1','name':registry.alias_for('fixture.arithmetic'),'arguments':{'operation':'multiply','left':1250,'right':2}}


def assert_closed(registry):
    r=registry.audit();assert r['connection']['connection_closed']
    assert r['transport']['http_client_closed'] and r['transport']['network_closed'] and r['transport']['open_responses']==0


@pytest.mark.parametrize('mode',['auto','legacy'])
@pytest.mark.parametrize('json_response',[True,False],ids=['json','sse'])
def test_real_http_sdk_negotiates_calls_and_closes_without_stopping_server(tmp_path,monkeypatch,mode,json_response):
    with http_server(tmp_path/'server',json_response=json_response) as server:
        registry=connection(server,monkeypatch,mode=mode)
        with registry:
            assert registry.metrics['protocol_version']==('2026-07-28' if mode=='auto' else '2025-11-25')
            assert registry.execute(call(registry))['data']=={'value':2500}
        assert_closed(registry);assert server['process'].poll() is None
        received=rows(server['root']/'requests.jsonl');assert all(v['authenticated'] for v in received)
        assert len(rows(server['root']/'calls.jsonl'))==1
        assert len([v for v in received if v['rpc_method']=='tools/call'])==1
        if mode=='legacy':assert any(v['method']=='DELETE' for v in received)


@pytest.mark.parametrize('fault',['redirect','tool_redirect','auth_call','oversized_json','oversized_sse','bad_json','compressed','timeout','sse_disconnect'])
def test_http_faults_never_repeat_tool_posts_and_always_release_client(tmp_path,monkeypatch,fault):
    with http_server(tmp_path/'server',fault=fault) as server:
        registry=connection(server,monkeypatch,timeout=1.5 if fault in ('timeout','sse_disconnect') else 3)
        if fault=='redirect':
            with pytest.raises(Exception):
                with registry:pass
        else:
            with registry:
                with pytest.raises(MCPFailure):registry.execute(call(registry))
                assert registry.metrics['tool_requests_submitted']==1
        assert_closed(registry)
        received=rows(server['root']/'requests.jsonl')
        assert not any(v['path']=='/trap' or v['last_event_id_present'] for v in received)
        assert len([v for v in received if v['rpc_method']=='tools/call'])==(0 if fault=='redirect' else 1)


def test_missing_and_rejected_credentials_never_trigger_authorization_flows(tmp_path,monkeypatch):
    with http_server(tmp_path/'server') as server:
        monkeypatch.delenv('SLM_MCP_MISSING_AUTH',raising=False)
        with pytest.raises(ValueError,match='missing'):MCPRegistry(url=server['url'],allow_loopback_http=True,bearer_token_env='SLM_MCP_MISSING_AUTH')
        assert rows(server['root']/'requests.jsonl')==[]
        monkeypatch.setenv('SLM_MCP_BAD_AUTH','fixture-wrong')
        registry=MCPRegistry(url=server['url'],allow_loopback_http=True,bearer_token_env='SLM_MCP_BAD_AUTH')
        with pytest.raises(Exception):
            with registry:pass
        assert_closed(registry);assert len(rows(server['root']/'requests.jsonl'))==1
        assert registry.audit()['transport']['failure']=='authorization'


@pytest.mark.parametrize('url',['http://example.org/mcp','http://192.168.1.1/mcp','file:///tmp/mcp','https://user:password@example.org/mcp','https://example.org/mcp?token=secret','https://example.org/mcp#fragment'])
def test_endpoint_is_explicit_and_cannot_embed_credentials_or_unapproved_plaintext(url):
    with pytest.raises(ValueError):endpoint(url,True)


def test_proxy_environment_is_ignored_and_credentials_not_in_descriptors_or_audits(tmp_path,monkeypatch):
    monkeypatch.setenv('HTTP_PROXY','http://127.0.0.1:1');monkeypatch.setenv('ALL_PROXY','http://127.0.0.1:1');monkeypatch.setenv('NO_PROXY','')
    with http_server(tmp_path/'server') as server:
        registry=connection(server,monkeypatch)
        with registry:
            assert registry.execute(call(registry))['ok']
            assert server['token'] not in json.dumps(registry.discover())
        assert_closed(registry);assert server['token'] not in json.dumps(registry.audit())


def test_seven_scenarios_use_actual_http_calls_and_existing_independent_semantic_oracles(tmp_path,monkeypatch):
    with http_server(tmp_path/'server',json_response=False) as server:
        registry=connection(server,monkeypatch)
        with registry:
            for original in tool_cases():
                case=deepcopy(original)
                if case['expected_action']['kind']=='call':case['expected_action']['name']=registry.alias_for('fixture.'+case['expected_action']['name'])
                actions=[case['expected_action']]+([case['expected_final']] if case['expected_action']['kind']=='call' else [])
                report=run_turn(Script(actions),case['history'],registry);assert score_task(case,report)['structured_task_passed']
            assert registry.metrics['tool_requests_submitted']==5
        assert_closed(registry);assert len(rows(server['root']/'calls.jsonl'))==5


def tls_files(root,matching_host=True):
    import datetime
    import ipaddress
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes,serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    root.mkdir();key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'slm-local-fixture')]);now=datetime.datetime.now(datetime.timezone.utc)
    san=x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address('127.0.0.1'))] if matching_host else [x509.DNSName('wrong.invalid')])
    cert=(x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now-datetime.timedelta(days=1)).not_valid_after(now+datetime.timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True,path_length=None),critical=True).add_extension(san,critical=False).sign(key,hashes.SHA256()))
    cert_path=root/'cert.pem';key_path=root/'key.pem'
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()));key_path.chmod(0o600)
    return cert_path,key_path


def test_actual_https_verifies_explicit_ca_and_keeps_auth_outside_model_context(tmp_path,monkeypatch):
    cert,key=tls_files(tmp_path/'tls')
    with http_server(tmp_path/'server',cert=cert,key=key) as server:
        registry=connection(server,monkeypatch,ca_file=cert)
        with registry:assert registry.execute(call(registry))['data']=={'value':2500}
        assert_closed(registry);audit=registry.audit()['transport']
        assert audit['tls_verification'] and len(audit['ca_bundle_sha256'])==64
        assert server['token'] not in json.dumps(registry.audit())


@pytest.mark.parametrize('failure',['untrusted_ca','wrong_hostname'])
def test_tls_failures_never_send_http_credentials_or_disable_certificate_checks(tmp_path,monkeypatch,failure):
    cert,key=tls_files(tmp_path/'tls',matching_host=failure!='wrong_hostname')
    with http_server(tmp_path/'server',cert=cert,key=key) as server:
        registry=connection(server,monkeypatch,ca_file=cert if failure=='wrong_hostname' else None,timeout=1.5)
        with pytest.raises(Exception):
            with registry:pass
        assert_closed(registry)
        assert rows(server['root']/'requests.jsonl')==[]
        assert registry.audit()['transport']['tls_verification']


def test_explicit_api_header_works_and_invalid_protocol_headers_or_control_characters_do_not(tmp_path,monkeypatch):
    with http_server(tmp_path/'server') as server:
        monkeypatch.setenv('SLM_MCP_TEST_AUTH',server['token'])
        registry=MCPRegistry(url=server['url'],allow_loopback_http=True,headers_env={'X-Fixture-Key':'SLM_MCP_TEST_AUTH'})
        with registry:assert registry.execute(call(registry))['ok']
        assert_closed(registry)
        for header in ('Host','Content-Length','MCP-Protocol-Version','Mcp-Param-foo'):
            with pytest.raises(ValueError):BoundedHTTP(server['url'],allow_loopback_http=True,headers_env={header:'SLM_MCP_TEST_AUTH'})
        monkeypatch.setenv('SLM_MCP_BAD_HEADER','value\r\nHost: other')
        with pytest.raises(ValueError):BoundedHTTP(server['url'],allow_loopback_http=True,headers_env={'Authorization':'SLM_MCP_BAD_HEADER'})


def test_http_byte_budget_is_applied_before_unbounded_json_body_read(tmp_path,monkeypatch):
    with http_server(tmp_path/'server',fault='oversized_json') as server:
        registry=connection(server,monkeypatch,transport_limits={'max_response_bytes':16384,'max_received_bytes':65536})
        with registry:
            with pytest.raises(MCPFailure):registry.execute(call(registry))
            assert registry.transport.stats['received_bytes']<65536
        assert_closed(registry)


def test_explicit_ca_bytes_are_pinned_at_configuration_time(tmp_path,monkeypatch):
    import hashlib
    cert,key=tls_files(tmp_path/'tls');original=cert.read_bytes()
    with http_server(tmp_path/'server',cert=cert,key=key) as server:
        registry=connection(server,monkeypatch,ca_file=cert)
        cert.write_bytes(b'changed after configuration')
        with registry:assert registry.execute(call(registry))['ok']
        assert registry.audit()['transport']['ca_bundle_sha256']==hashlib.sha256(original).hexdigest()
        assert_closed(registry)


def test_sdk_mirrors_declared_argument_headers_and_current_protocol_metadata(tmp_path,monkeypatch):
    with http_server(tmp_path/'server',fault='header_args') as server:
        registry=connection(server,monkeypatch)
        with registry:assert registry.execute(call(registry))['ok']
        assert_closed(registry)
        requests=rows(server['root']/'requests.jsonl')
        tools=[v for v in requests if v['rpc_method']=='tools/call']
        assert len(tools)==1 and tools[0]['argument_header_matches']
        assert all(v['protocol_header']=='2026-07-28' and v['mcp_method']==v['rpc_method'] for v in requests if v['method']=='POST')


def test_actual_sdk_server_rejects_untrusted_browser_origin(tmp_path,monkeypatch):
    with http_server(tmp_path/'server') as server:
        monkeypatch.setenv('SLM_MCP_ORIGIN','http://untrusted.invalid')
        registry=connection(server,monkeypatch,headers_env={'Origin':'SLM_MCP_ORIGIN'})
        with pytest.raises(Exception):
            with registry:pass
        assert_closed(registry)
        assert registry.audit()['transport']['last_status']==403
        assert len(rows(server['root']/'requests.jsonl'))==1


def test_cli_runs_http_with_environment_credentials_and_does_not_write_them(tmp_path,monkeypatch):
    from slm.common.config import Config,initialize
    from slm.common.tokenizer import train_core
    from slm.common.checkpoint import save
    from slm.data.tokenized import sha
    with http_server(tmp_path/'server') as server:
        monkeypatch.setenv('SLM_MCP_CLI_TOKEN',server['token'])
        config={'transport':'streamable_http','url':server['url'],'allow_loopback_http':True,'bearer_token_env':'SLM_MCP_CLI_TOKEN','selected':['fixture.arithmetic']}
        (tmp_path/'config.json').write_text(json.dumps(config));base=[sys.executable,'-m','slm.mcp.cli']
        subprocess.run([*base,'discover','--config',str(tmp_path/'config.json'),'--output',str(tmp_path/'discovery.json')],check=True,capture_output=True)
        result=json.loads((tmp_path/'discovery.json').read_text());assert len(result['tools'])==1
        assert result['mcp_audit']['transport']['http_client_closed']
        bpe=__import__('slm.common.tokenizer',fromlist=['train_core']).train_core(['Independent tokenizer mechanics.']*5,512)
        bpe.save(tmp_path/'tok',{'scope':'HTTP CLI test'});c=Config(vocab_size=bpe.vocab_size,max_seq_len=4096);save(tmp_path/'model',c,initialize(c,1703))
        (tmp_path/'history.json').write_text(json.dumps([{'role':'user','content':'Multiply 1250 by 2.'}]))
        subprocess.run([*base,'run','--config',str(tmp_path/'config.json'),'--model',str(tmp_path/'model'),'--tokenizer',str(tmp_path/'tok'),
            '--tokenizer-hash',sha(tmp_path/'tok/manifest.json'),'--history',str(tmp_path/'history.json'),'--max-new-tokens','4','--output',str(tmp_path/'run.json')],check=True,capture_output=True)
        r=json.loads((tmp_path/'run.json').read_text());assert r['status']=='invalid_decision' and r['executed_calls']==0
        assert r['mcp_audit']['transport']['http_client_closed'] and server['token'] not in (tmp_path/'run.json').read_text()

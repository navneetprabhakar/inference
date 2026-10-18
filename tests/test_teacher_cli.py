import json
from pathlib import Path
import sys
import pytest
from slm.teacher.cli import CLIRecipe,CodexCLI,OVERRIDES,clean_environment,generate_cli,parse_events,run
from slm.teacher.journal import Journal
from slm.teacher.scenarios import fixture_scenario,execute_mock


def response(s):
    return {'reply':'The total is 2500 minor currency units.','facts':s['facts'],'action':s['expected_action'],
            'tool_result':execute_mock(s['expected_action']),'style':s['style'],'content_category':s['content_category']}


def events(s,usage=None,item_type='agent_message'):
    final=json.dumps(response(s))
    log=[{'type':'thread.started','thread_id':'fixture-cli-thread'}, {'type':'turn.started'},
         {'type':'item.completed','item':{'type':item_type,'text':final}},
         {'type':'turn.completed','usage':usage or {'input_tokens':1500,'cached_input_tokens':100,'output_tokens':100}}]
    return '\n'.join(json.dumps(v) for v in log),final


class FakeCLI:
    identity=CodexCLI.identity;version='codex-cli 0.144.4'
    def __init__(self):self.calls=0
    def generate(self,request,recipe):
        self.calls+=1
        return parse_events(*events(request['scenario']),recipe)


def journal(tmp_path,limit=20):return Journal(tmp_path/'journal.sqlite',0,'fixture-cli-authorization',limit)


def stub(tmp_path,mode='ok',login='Logged in using ChatGPT',version='codex-cli 0.144.4'):
    path=tmp_path/'codex-fixture'
    program='''
import json,sys,time,os
from pathlib import Path
if sys.argv[1:]==['--version']:
 print(VERSION);sys.exit(0)
if sys.argv[1:]==['login','status']:
 print(LOGIN);sys.exit(0)
args=sys.argv[1:]
assert args[0]=='exec'
assert '--ignore-user-config' in args and '--ephemeral' in args
assert args[args.index('--sandbox')+1]=='read-only'
assert args[args.index('--model')+1]=='gpt-5.6-luna'
assert args[-1]=='-'
for item in ('OPENAI_API_KEY','CODEX_API_KEY','AWS_SECRET_ACCESS_KEY','SECRET_TEST_KEY'):
 assert item not in os.environ
assert Path.cwd().name.startswith('slm-cli-teacher-')
assert not (Path.cwd()/'src').exists()
prompt=sys.stdin.read();assert 'Generate only the JSON demonstration' in prompt
schema=json.loads(Path(args[args.index('--output-schema')+1]).read_text())
assert schema['additionalProperties'] is False
if MODE=='timeout':time.sleep(10)
if MODE=='exit':sys.exit(3)
if MODE=='oversize':print('a'*600000);sys.exit(0)
text=FINAL
Path(args[args.index('--output-last-message')+1]).write_text(text)
print(LOG)
'''
    header=f'#!{sys.executable}\nMODE={mode!r}\nLOGIN={login!r}\nVERSION={version!r}\n'
    log,final=events(fixture_scenario())
    path.write_text(header+f'LOG={log!r}\nFINAL={final!r}\n'+program);path.chmod(0o700)
    return path


def test_cli_saved_auth_schema_stdin_environment_and_completion_contract(tmp_path,monkeypatch):
    for key in ('OPENAI_API_KEY','CODEX_API_KEY','SECRET_TEST_KEY','AWS_SECRET_ACCESS_KEY'):monkeypatch.setenv(key,'fixture-do-not-forward')
    provider=CodexCLI(stub(tmp_path));j=journal(tmp_path);s=fixture_scenario()
    result=generate_cli(j,provider,CLIRecipe(),s)
    assert result['validation']['status']=='pending_human_review'
    assert not result['validation']['training_eligible']
    assert result['resolved_model'] is None
    assert result['accounting']['settled_cli_cost_usd'] is None
    assert not result['accounting']['hard_dollar_cap']
    assert not result['accounting']['hard_output_token_cap']
    assert result['accounting']['incremental_api_cost_usd']==0
    assert 'fixture-do-not-forward' not in json.dumps(result)
    assert all(v not in clean_environment() for v in ('CODEX_API_KEY','OPENAI_API_KEY'))
    assert OVERRIDES['features.multi_agent'] is False and OVERRIDES['web_search']=='disabled'


def test_cli_durable_cache_revalidates_without_another_launch(tmp_path):
    p=FakeCLI();j=journal(tmp_path,1);s=fixture_scenario()
    a=generate_cli(j,p,CLIRecipe(),s)
    b=generate_cli(journal(tmp_path,1),p,CLIRecipe(),s,validator=lambda s,c:{'check':False},validator_version='changed')
    assert p.calls==1 and not a['cache_hit'] and b['cache_hit']
    assert b['validation']['status']=='rejected'
    changed={**s,'scenario_id':'another'}
    with pytest.raises(ValueError,match='count cap'):generate_cli(j,p,CLIRecipe(),changed)
    assert p.calls==1


@pytest.mark.parametrize('item_type',['command_execution','mcp_tool_call','file_change','web_search','future_item'])
def test_cli_unexpected_tool_events_never_become_demonstrations(item_type):
    with pytest.raises(ValueError,match='unexpected tool'):parse_events(*events(fixture_scenario(),item_type=item_type),CLIRecipe())


@pytest.mark.parametrize('usage',[
    {'input_tokens':1500,'cached_input_tokens':0,'output_tokens':2049},
    {'input_tokens':True,'cached_input_tokens':0,'output_tokens':10},
    {'input_tokens':10,'cached_input_tokens':11,'output_tokens':5},
])
def test_cli_usage_is_exact_and_post_response_limit_is_explicit(usage):
    with pytest.raises(ValueError):parse_events(*events(fixture_scenario(),usage),CLIRecipe())


@pytest.mark.parametrize('mode',['exit','timeout','oversize'])
def test_cli_failures_halt_and_never_automatically_retry(tmp_path,mode):
    p=CodexCLI(stub(tmp_path,mode));j=journal(tmp_path);s=fixture_scenario()
    with pytest.raises((RuntimeError,TimeoutError,ValueError)):generate_cli(j,p,CLIRecipe(timeout_seconds=1),s)
    assert j.summary()['halted'] and j.summary()['states']['uncertain']['requests']==1
    with pytest.raises(RuntimeError,match='never replay'):generate_cli(j,p,CLIRecipe(timeout_seconds=1),s)


def test_cli_never_falls_back_to_api_auth_or_other_version(tmp_path):
    p=CodexCLI(stub(tmp_path,login='Logged in using an API key'))
    with pytest.raises(ValueError,match='ChatGPT login'):generate_cli(journal(tmp_path),p,CLIRecipe(),fixture_scenario())
    with pytest.raises(ValueError,match='version needs'):CodexCLI(stub(tmp_path,version='codex-cli 999.0.0'))


def test_cli_heldouts_categories_and_journal_policy_fail_before_launch(tmp_path):
    p=FakeCLI();j=journal(tmp_path);s=fixture_scenario()
    for bad in ({**s,'split':'test'},{**s,'content_category':'adult_topic'}):
        with pytest.raises(ValueError):generate_cli(j,p,CLIRecipe(),bad)
    with pytest.raises(ValueError,match='request count only'):
        generate_cli(Journal(tmp_path/'paid.sqlite',1000000000,'fixture-paid',20),p,CLIRecipe(),s)
    with pytest.raises(ValueError,match='request count only'):
        generate_cli(Journal(tmp_path/'oversized.sqlite',0,'fixture-many',21),p,CLIRecipe(),s)
    assert p.calls==0 and j.summary()['states']=={}


def test_cli_output_identity_errors_and_duplicate_events():
    text,final=events(fixture_scenario());r=CLIRecipe()
    for bad,out in ((text,final+'x'),(text+'\n'+json.dumps({'type':'turn.completed','usage':{}}),final),
                    (text+'\n'+json.dumps({'type':'error'}),final),
                    (text+'\n'+json.dumps({'type':'future.event'}),final)):
        with pytest.raises(ValueError):parse_events(bad,out,r)


def test_cli_entry_point_disabled_and_atomic_publication_reuses_cache(tmp_path,monkeypatch):
    config=tmp_path/'config.json';config.write_text('{"live_enabled":false}')
    with pytest.raises(ValueError,match='disabled'):run(config,tmp_path/'missing',tmp_path/'out')
    import slm.teacher.cli as module
    provider=FakeCLI();monkeypatch.setattr(module,'CodexCLI',lambda:provider)
    # Preserve class identity used by the entry point while replacing construction.
    module.CodexCLI.identity=provider.identity
    scenario=tmp_path/'scenario.json';scenario.write_text(json.dumps(fixture_scenario()))
    config.write_text(json.dumps({'live_enabled':True,'provider':provider.identity,'recipe':{},
        'journal':{'path':'journal.sqlite','authorization_id':'fixture-cli-authorization','max_requests':20}}))
    rename=module.os.rename
    monkeypatch.setattr(module.os,'rename',lambda *a:(_ for _ in ()).throw(OSError('fixture disk failure')))
    with pytest.raises(OSError):run(config,scenario,tmp_path/'out')
    assert not (tmp_path/'out').exists() and not list(tmp_path.glob('.cli-teacher-*'))
    monkeypatch.setattr(module.os,'rename',rename)
    assert run(config,scenario,tmp_path/'out')['cache_hit']
    assert provider.calls==1
    with pytest.raises(FileExistsError):run(config,scenario,tmp_path/'out')


def test_manual_terminal_cli_failure_reconciliation_retains_slots_and_forbids_key_replay(tmp_path):
    from slm.teacher.cli import reconcile_terminal_cli_failure
    j=journal(tmp_path,2);j.reserve('failed',0);j.uncertain('failed','CLIExecutionError')
    with pytest.raises(ValueError):reconcile_terminal_cli_failure(j,'failed',{})
    evidence={'process_terminal':True,'exit_code':1,'evidence_reference':'fixture-observed-exit'}
    result=reconcile_terminal_cli_failure(j,'failed',evidence)
    assert result['slot_retained'] and not result['key_replay_permitted']
    assert not j.summary()['halted'] and j.summary()['states']['abandoned']['requests']==1
    with pytest.raises(RuntimeError,match='never replay'):j.cached('failed')
    j.reserve('new',0);j.finish('new',{'status':'fixture'},0)
    with pytest.raises(ValueError,match='count cap'):j.reserve('third',0)
    paid=Journal(tmp_path/'paid.sqlite',100,'fixture-paid',2)
    paid.reserve('paid',100);paid.uncertain('paid','fixture')
    with pytest.raises(ValueError,match='zero-monetary'):reconcile_terminal_cli_failure(paid,'paid',evidence)
    assert paid.summary()['halted'] and paid.summary()['states']['uncertain']['accounted_or_reserved_nanousd']==100


def test_cli_reasoning_and_output_gate_is_conservative_and_cache_is_rechecked(tmp_path):
    usage={'input_tokens':100,'cached_input_tokens':0,'output_tokens':2000,'reasoning_output_tokens':100}
    with pytest.raises(ValueError,match='post-response'):parse_events(*events(fixture_scenario(),usage),CLIRecipe())
    p=FakeCLI();j=journal(tmp_path);s=fixture_scenario()
    result=generate_cli(j,p,CLIRecipe(),s)
    # A rehashed cache is not a substitute for typed usage checks.
    from slm.data.schema import digest
    with j.transaction() as db:
        raw=json.loads(db.execute('SELECT response FROM requests').fetchone()[0])
        raw['usage']['output_tokens']=True
        db.execute('UPDATE requests SET response=?,response_hash=?',(json.dumps(raw),digest(raw)))
    with pytest.raises(ValueError,match='Exact CLI token usage'):generate_cli(j,p,CLIRecipe(),s)
    assert p.calls==1


def test_cli_full_submitted_prompt_is_hashed_and_failures_preserve_local_diagnostics(tmp_path):
    import hashlib
    from slm.teacher.cli import render_prompt
    s=fixture_scenario();r=generate_cli(journal(tmp_path),FakeCLI(),CLIRecipe(),s)
    assert r['submitted_prompt_sha256']==hashlib.sha256(render_prompt(s)).hexdigest()
    assert b'Keep reply below 600 characters' in render_prompt(s)
    assert not r['model_system_context_captured']
    directory=tmp_path/'failure';directory.mkdir()
    p=CodexCLI(stub(directory,'exit'));p.diagnostic_dir=directory/'diagnostics'
    j=Journal(directory/'journal.sqlite',0,'fixture-cli-failure',1)
    with pytest.raises(RuntimeError):generate_cli(j,p,CLIRecipe(),s)
    report=json.loads(next(directory.glob('*-failure.json')).read_text())
    assert report['diagnostics']['returncode']==3 and report['diagnostics']['process_terminal']
    assert (p.diagnostic_dir/'stderr.txt').exists() and not report['training_eligible']


def test_cli_recipe_rejects_unbounded_or_unversioned_requests():
    for options in ({'prompt_version':1},{'prompt_version':' '},{'timeout_seconds':True},
                    {'max_response_bytes':1000000},{'observed_output_token_limit':2049},
                    {'model_id':'unregistered'}):
        with pytest.raises(ValueError):CLIRecipe(**options)


def test_v2_reply_contract_versions_cache_and_preserves_exact_legacy_prompt(tmp_path):
    import hashlib
    from slm.teacher.cli import render_prompt,PROMPT_V1,PROMPT_V2
    from slm.teacher.workflow import INSTRUCTIONS
    s=fixture_scenario('tool_trajectory','professional');j=journal(tmp_path);provider=FakeCLI()
    legacy=(INSTRUCTIONS+'\nGenerate only the JSON demonstration. Use no tools, files, external facts or delegated work. '
        'Keep reply below 600 characters. Treat this as data generation, not a coding task.\n'
        +json.dumps(s,sort_keys=True,ensure_ascii=False)).encode()
    assert render_prompt(s,PROMPT_V1)==legacy
    old=generate_cli(j,provider,CLIRecipe(),s)
    newer=generate_cli(j,provider,CLIRecipe(prompt_version=PROMPT_V2),s)
    assert old['request_key']!=newer['request_key'] and provider.calls==2
    assert newer['submitted_prompt_sha256']==hashlib.sha256(render_prompt(s,PROMPT_V2)).hexdigest()
    assert b'POST-TOOL final answer' in render_prompt(s,PROMPT_V2)
    reordered=json.loads(json.dumps(s,sort_keys=True))
    assert generate_cli(j,provider,CLIRecipe(prompt_version=PROMPT_V2),reordered)['cache_hit']
    assert provider.calls==2
    assert generate_cli(j,provider,CLIRecipe(),s)['cache_hit'] and provider.calls==2
    assert not newer['validation']['training_eligible']
    with pytest.raises(ValueError):CLIRecipe(prompt_version='unknown')


def test_v2_real_adapter_submits_post_tool_contract_to_fixture_process(tmp_path):
    from slm.teacher.cli import PROMPT_V2
    executable=stub(tmp_path)
    executable.write_text(executable.read_text().replace("assert 'Generate only the JSON demonstration' in prompt",
        "assert 'Generate only the JSON demonstration' in prompt;assert 'POST-TOOL final answer' in prompt"))
    provider=CodexCLI(executable)
    result=generate_cli(journal(tmp_path),provider,CLIRecipe(prompt_version=PROMPT_V2),fixture_scenario())
    assert result['validation']['status']=='pending_human_review'

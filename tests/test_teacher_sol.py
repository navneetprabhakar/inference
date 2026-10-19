# Creator: Navneet Prabhakar
import pytest
from slm.teacher.sol import SolRecipe
from slm.teacher.cli import CLIRecipe, generate_cli
from slm.teacher.journal import Journal
from slm.teacher.scenarios import fixture_scenario
from test_teacher_cli import FakeCLI


def test_exact_requested_model_and_legacy_registration():
    assert SolRecipe().model_id == 'gpt-6.1-sol'
    with pytest.raises(ValueError): SolRecipe(model_id='gpt-6-luna')
    with pytest.raises(ValueError): CLIRecipe(model_id='gpt-6.1-sol')
    with pytest.raises(ValueError): SolRecipe(timeout_seconds=1000)


def test_sol_uses_existing_bounded_cli_journal_and_cache(tmp_path):
    journal = Journal(tmp_path/'journal.sqlite', 0, 'fixture-existing-budget', 1)
    provider = FakeCLI()
    first = generate_cli(journal, provider, SolRecipe(), fixture_scenario())
    second = generate_cli(journal, provider, SolRecipe(), fixture_scenario())
    assert first['requested_model'] == 'gpt-6.1-sol'
    assert second['cache_hit'] and provider.calls == 1
    assert first['resolved_model'] is None
    assert not first['validation']['training_eligible']


def test_disabled_entrypoint_never_reads_scenario_or_credentials(tmp_path):
    import json
    from slm.teacher.sol import run
    config = tmp_path/'config.json'
    config.write_text(json.dumps({'live_enabled': False}))
    with pytest.raises(ValueError, match='disabled'):
        run(config, tmp_path/'missing-scenario', tmp_path/'out')


def test_entrypoint_refuses_new_journal_before_login(tmp_path):
    import json
    from slm.teacher.sol import run
    config = tmp_path/'config.json'
    config.write_text(json.dumps(dict(live_enabled=True, provider='codex-cli-chatgpt-v1', recipe={},
        journal=dict(path='new.sqlite', authorization_id='fixture', max_requests=1))))
    scenario = tmp_path/'scenario.json'
    scenario.write_text(json.dumps(fixture_scenario()))
    with pytest.raises(ValueError, match='Existing pilot journal'):
        run(config, scenario, tmp_path/'out')
    assert not (tmp_path/'new.sqlite').exists()


def test_entrypoint_uses_existing_journal_and_publishes_cached_exact_model(tmp_path, monkeypatch):
    import json
    import slm.teacher.sol as transport
    from slm.teacher.sol import run
    journal_path = tmp_path/'existing.sqlite'
    Journal(journal_path, 0, 'fixture-existing', 1)
    provider = FakeCLI()
    monkeypatch.setattr(transport, 'SolCodexCLI', lambda executable: provider)
    config = tmp_path/'config.json'
    config.write_text(json.dumps(dict(live_enabled=True, provider=provider.identity, recipe={}, cli_executable='fixture',
        journal=dict(path=str(journal_path), authorization_id='fixture-existing', max_requests=1))))
    scenario = tmp_path/'scenario.json'
    scenario.write_text(json.dumps(fixture_scenario()))
    assert run(config, scenario, tmp_path/'first')['requested_model'] == 'gpt-6.1-sol'
    assert run(config, scenario, tmp_path/'second')['cache_hit']
    assert provider.calls == 1
    assert not json.loads((tmp_path/'second/record.json').read_text())['validation']['training_eligible']


def test_modern_client_is_separately_pinned_and_uses_same_safe_transport(tmp_path):
    from slm.teacher.sol import SolCodexCLI
    from test_teacher_cli import stub
    path = stub(tmp_path, version='codex-cli 0.163.0')
    path.write_text(path.read_text().replace("=='gpt-5.6-luna'", "=='gpt-6.1-sol'").replace("startswith('slm-cli-teacher-')", "startswith('sol-attempt-')"))
    provider = SolCodexCLI(path)
    provider.diagnostic_dir = tmp_path/'diagnostics'
    result = generate_cli(Journal(tmp_path/'modern.sqlite', 0, 'fixture-modern', 1), provider,
                          SolRecipe(), fixture_scenario())
    assert result['requested_model'] == 'gpt-6.1-sol'
    assert result['cli_version'] == 'codex-cli 0.163.0'
    assert len(list(provider.diagnostic_dir.glob('*/process-terminal.json'))) == 1
    with pytest.raises(ValueError, match='reviewed'):
        SolCodexCLI(stub(tmp_path, version='codex-cli 0.144.4'))


def test_rejected_modern_events_are_retained_and_never_marked_eligible(tmp_path):
    import json
    from slm.teacher.sol import SolCodexCLI
    from test_teacher_cli import stub, events
    path = stub(tmp_path, version='codex-cli 0.163.0')
    original, final = events(fixture_scenario())
    rejected, _ = events(fixture_scenario(), item_type='mcp_tool_call')
    text = path.read_text().replace(repr(original), repr(rejected))
    path.write_text(text.replace("=='gpt-5.6-luna'", "=='gpt-6.1-sol'").replace("startswith('slm-cli-teacher-')", "startswith('sol-attempt-')"))
    provider = SolCodexCLI(path)
    provider.diagnostic_dir = tmp_path/'diagnostics'
    journal = Journal(tmp_path/'journal.sqlite', 0, 'fixture', 1)
    with pytest.raises(ValueError, match='unexpected tool'):
        generate_cli(journal, provider, SolRecipe(), fixture_scenario())
    assert journal.summary()['halted']
    roots = list(provider.diagnostic_dir.iterdir())
    assert len(roots) == 1
    assert (roots[0]/'events.jsonl').read_text().strip() == rejected.strip()
    assert (roots[0]/'last.json').read_text() == final
    assert json.loads((roots[0]/'process-terminal.json').read_text())['returncode'] == 0


def test_only_exact_reviewed_client_notices_can_be_separated_from_actions():
    import json
    from slm.teacher.sol import KNOWN_CLIENT_NOTICES, parse_sol_events
    from test_teacher_cli import events
    text, final = events(fixture_scenario())
    for notice in KNOWN_CLIENT_NOTICES:
        warning = json.dumps(dict(type='item.completed', item=dict(id='notice-1', type='error', message=notice)))
        result = parse_sol_events(warning+'\n'+text, final, SolRecipe())
        assert result['client_notices'] == [notice]
        bad = warning.replace(notice[:15], 'unknown notice')
        with pytest.raises(ValueError, match='Unrecognized'):
            parse_sol_events(bad+'\n'+text, final, SolRecipe())
    for item_type in ['mcp_tool_call', 'command_execution', 'file_change', 'web_search', 'collab_tool_call', 'todo_list']:
        log, final = events(fixture_scenario(), item_type=item_type)
        with pytest.raises(ValueError, match='unexpected tool'):
            parse_sol_events(log, final, SolRecipe())

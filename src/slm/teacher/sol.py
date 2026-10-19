"""Explicit GPT-6.1 Sol registration without changing historical Luna cache contracts."""
# Creator: Navneet Prabhakar
from dataclasses import dataclass
from slm.teacher.cli import CLIRecipe, PROMPT_V3, CodexCLI


KNOWN_CLIENT_NOTICES = frozenset({
    'Codex is ignoring 1 unrecognized configuration setting. Check for typos or deprecated settings.\n  session-flags: `tools.view_image` is ignored.',
    'Code Mode is unavailable because code-mode host is disabled. Code mode will fail closed; enable `features.code_mode_host` and install `codex-code-mode-host`.',
})


def parse_sol_events(text, response, recipe):
    """Separate exact known client notices from model actions; reject other error items."""
    import json
    from slm.teacher.cli import parse_events
    from slm.teacher.workflow import parse_json
    filtered, notices = [], []
    for line in text.splitlines():
        event = parse_json(line)
        item = event.get('item', {})
        if event.get('type') == 'item.completed' and item.get('type') == 'error':
            if set(item) != {'id', 'type', 'message'} or item['message'] not in KNOWN_CLIENT_NOTICES:
                raise ValueError('Unrecognized modern client error item; no acceptance')
            notices.append(item['message'])
        else:
            filtered.append(json.dumps(event))
    raw = parse_events('\n'.join(filtered), response, recipe)
    raw['client_notices'] = notices
    raw['event_parser'] = 'sol-exact-client-notice-parser-v1'
    return raw


class SolCodexCLI(CodexCLI):
    """Separately pinned modern client; historical CLI/cache contracts remain unchanged."""
    def __init__(self, executable):
        from pathlib import Path
        import subprocess
        from slm.teacher.cli import clean_environment
        self.executable = str(Path(executable).resolve())
        self.env = clean_environment()
        probe = subprocess.run([self.executable, '--version'], env=self.env, capture_output=True,
                               text=True, timeout=10, check=True)
        self.version = probe.stdout.strip()
        if self.version != 'codex-cli 0.163.0':
            raise ValueError('Sol client requires reviewed codex-cli 0.163.0')

    def generate(self, request, recipe):
        """Retain bounded raw modern-client events even when validation rejects them."""
        import json
        import os
        from pathlib import Path
        import signal
        import subprocess
        import tempfile
        import time
        from slm.teacher.cli import OVERRIDES, CLIExecutionError, render_prompt
        status = subprocess.run([self.executable, 'login', 'status'], env=self.env,
                                capture_output=True, text=True, timeout=10, check=True)
        if (status.stdout+status.stderr).strip() != 'Logged in using ChatGPT':
            raise ValueError('Saved ChatGPT login required; no API authentication')
        base = Path(self.diagnostic_dir)
        base.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix='sol-attempt-', dir=base)).resolve()
        schema, last = root/'schema.json', root/'last.json'
        schema.write_text(json.dumps(request['schema'], sort_keys=True))
        (root/'prompt.txt').write_bytes(render_prompt(request['scenario'], recipe.prompt_version))
        argv = [self.executable, 'exec', '--ignore-user-config', '--ephemeral', '--skip-git-repo-check',
                '--sandbox', 'read-only', '--cd', str(root), '--model', recipe.model_id, '--json',
                '--color', 'never', '--output-schema', str(schema), '--output-last-message', str(last)]
        for key, value in OVERRIDES.items(): argv += ['-c', key+'='+json.dumps(value)]
        argv += ['-']
        with (root/'events.jsonl').open('w+b') as events, (root/'stderr.txt').open('w+b') as errors, (root/'prompt.txt').open('rb') as incoming:
            process = subprocess.Popen(argv, stdin=incoming, stdout=events, stderr=errors,
                                       env=self.env, cwd=root, start_new_session=True)
            try:
                deadline = time.monotonic()+recipe.timeout_seconds
                while process.poll() is None:
                    if time.monotonic() >= deadline: raise TimeoutError('Sol teacher deadline exceeded')
                    if events.tell() > 512*1024 or errors.tell() > 128*1024 or (last.exists() and last.stat().st_size > recipe.max_response_bytes):
                        raise ValueError('Sol teacher output budget exceeded')
                    time.sleep(.05)
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                (root/'process-terminal.json').write_text(json.dumps(dict(process_terminal=True, returncode=process.returncode)))
            events.seek(0); errors.seek(0)
            event_bytes, error_bytes = events.read(512*1024+1), errors.read(128*1024+1)
        if len(event_bytes) > 512*1024 or len(error_bytes) > 128*1024:
            raise ValueError('Sol teacher terminal output budget exceeded')
        if process.returncode: raise CLIExecutionError(process.returncode, event_bytes, error_bytes)
        if not last.exists() or not 0 < last.stat().st_size <= recipe.max_response_bytes:
            raise ValueError('Missing or oversized Sol final response')
        # Raw evidence remains private whether this strict parser succeeds or fails.
        return parse_sol_events(event_bytes.decode('utf-8'), last.read_text(), recipe)


@dataclass(frozen=True)
class SolRecipe:
    model_id: str = 'gpt-6.1-sol'
    prompt_version: str = PROMPT_V3
    timeout_seconds: int = 120
    max_response_bytes: int = 16384
    observed_output_token_limit: int = 2048
    transport_contract: str = 'sol-persistent-cli-v1'

    def __post_init__(self):
        if self.model_id != 'gpt-6.1-sol' or self.transport_contract != 'sol-persistent-cli-v1':
            raise ValueError('Exact requested GPT-6.1 Sol identifier required; no substitution')
        # Reuse bounded transport validation; historical registration stays unchanged.
        CLIRecipe(model_id='gpt-5.6-luna', prompt_version=self.prompt_version,
                  timeout_seconds=self.timeout_seconds, max_response_bytes=self.max_response_bytes,
                  observed_output_token_limit=self.observed_output_token_limit)


def run(config_file, scenario_file, output):
    """Use an existing request journal only; no budget reset or provider fallback."""
    import json
    import os
    from pathlib import Path
    import shutil
    import tempfile
    from slm.teacher.cli import generate_cli
    from slm.teacher.journal import Journal
    from slm.teacher.workflow import check_scenario, parse_json

    config_file = Path(config_file)
    config = parse_json(config_file.read_text())
    if config.get('live_enabled') is not True:
        raise ValueError('Sol teacher disabled until exact-model account access is resolved')
    if config.get('provider') != CodexCLI.identity:
        raise ValueError('Saved-auth CLI only; no API or provider fallback')
    recipe = SolRecipe(**config['recipe'])
    scenario = parse_json(Path(scenario_file).read_text())
    check_scenario(scenario)
    if scenario['content_category'] != 'sfw': raise ValueError('Initial English pilot is SFW only')
    output = Path(output)
    if output.exists(): raise FileExistsError(output)
    settings = config['journal']
    path = Path(settings['path'])
    if not path.is_absolute(): path = config_file.resolve().parent/path
    if not path.is_file(): raise ValueError('Existing pilot journal required; no new allowance')
    journal = Journal(path, 0, settings['authorization_id'], settings['max_requests'])
    executable = Path(config['cli_executable'])
    if not executable.is_absolute(): executable = config_file.resolve().parent/executable
    provider = SolCodexCLI(executable)
    provider.diagnostic_dir = path.parent/'sol-diagnostics'
    result = generate_cli(journal, provider, recipe, scenario)
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix='.sol-teacher-', dir=output.parent))
    try:
        (temp/'record.json').write_text(json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2)+'\n')
        os.rename(temp, output)
    except BaseException:
        shutil.rmtree(temp, ignore_errors=True)
        raise
    return dict(requested_model=result['requested_model'], resolved_model=result['resolved_model'],
                cache_hit=result['cache_hit'], training_eligible=False, usage=result['usage'])


def main():
    import argparse
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--scenario', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.config, args.scenario, args.output), indent=2))


if __name__ == '__main__': main()

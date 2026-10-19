"""Bounded CLI English demonstrations and checked continuation-only candidates."""
# Creator: Navneet Prabhakar
from dataclasses import dataclass, asdict
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
from jsonschema import Draft202012Validator
from slm.data.schema import digest
from slm.data.stream_hash import sha
from slm.teacher.cli import OVERRIDES, CLIExecutionError, check_raw
from slm.teacher.journal import Journal
from slm.teacher.scenarios import output_schema, validate
from slm.teacher.sol import SolCodexCLI, SolRecipe, parse_sol_events
from slm.teacher.styles import instructions as style_instructions
from slm.teacher.workflow import check_scenario, check_schema, parse_json

INSTRUCTIONS = ('Produce English conversation training demonstrations. Each supplied scenario is independent. '
    'For EACH scenario, write only the final assistant continuation after its complete context. '
    'Return one JSON object keyed by scenario_id, following the supplied schema. '
    'Copy its facts, expected_action as action, style and content_category exactly; tool_result is null. '
    'Facts are supplied evidence, not a request to invent details. Preserve corrections, negation and constraints. '
    'When facts contains expected_reply, reply must equal that exact string. '
    'Use natural concise English, normally one or two sentences, at most240 characters per reply. '
    'Do not rewrite history or train a previous assistant mistake as a correct answer. '
    'Use no tools, files, browsing, external facts, delegated work or hidden reasoning. '
    'The structured facts are checked separately; they cannot substitute for a correct useful reply. ')


@dataclass(frozen=True)
class EnglishRecipe:
    model_id: str = 'gpt-6.1-sol'
    prompt_version: str = 'english-final-continuation-batch-v1'
    timeout_seconds: int = 120
    max_response_bytes: int = 16384
    observed_output_token_limit: int = 2048

    def __post_init__(self):
        if self.prompt_version != 'english-final-continuation-batch-v1': raise ValueError('Unregistered English recipe')
        SolRecipe(model_id=self.model_id, timeout_seconds=self.timeout_seconds,
                  max_response_bytes=self.max_response_bytes,
                  observed_output_token_limit=self.observed_output_token_limit)


def checked_batch(batch, exclusions):
    if not isinstance(batch, list) or not 1 <= len(batch) <= 10: raise ValueError('One to ten independent scenarios required')
    if len({s['scenario_id'] for s in batch}) != len(batch): raise ValueError('Duplicate scenario IDs')
    for scenario in batch:
        check_scenario(scenario)
        if (scenario['content_category'] != 'sfw' or scenario['expected_action']['kind'] not in ('answer', 'clarify')
                or scenario['expected_action']['name'] is not None or scenario['expected_action']['arguments']
                or not 1 <= len(scenario['context']) <= 5 or scenario['context'][-1]['role'] != 'user'
                or any(m['role'] not in ('user', 'assistant') for m in scenario['context'])):
            raise ValueError('Bounded SFW conversation continuations only; no tool trajectories')
        if exclusions.matches('\n'.join(m['content'] for m in scenario['context'])):
            raise ValueError('Protected evaluation text in teacher input')
    return json.loads(json.dumps(batch, sort_keys=True))


def schema_for(batch):
    schema = dict(type='object', properties={s['scenario_id']: output_schema(s) for s in batch},
                  required=[s['scenario_id'] for s in batch], additionalProperties=False)
    check_schema(schema)
    return schema


class EnglishBatchCLI(SolCodexCLI):
    identity = 'codex-cli-chatgpt-english-batch-v1'

    def generate(self, request, recipe):
        status = subprocess.run([self.executable, 'login', 'status'], env=self.env,
                                capture_output=True, text=True, timeout=10, check=True)
        if (status.stdout+status.stderr).strip() != 'Logged in using ChatGPT': raise ValueError('Saved ChatGPT login required')
        base = Path(self.diagnostic_dir); base.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix='english-attempt-', dir=base)).resolve()
        (root/'schema.json').write_text(json.dumps(request['schema'], sort_keys=True))
        prompt = request['instructions']+'\nSCENARIOS:\n'+json.dumps(request['batch'], sort_keys=True, ensure_ascii=False)
        (root/'prompt.txt').write_text(prompt)
        argv = [self.executable, 'exec', '--ignore-user-config', '--ephemeral', '--skip-git-repo-check',
                '--sandbox', 'read-only', '--cd', str(root), '--model', recipe.model_id, '--json',
                '--color', 'never', '--output-schema', str(root/'schema.json'),
                '--output-last-message', str(root/'last.json')]
        for key, value in OVERRIDES.items(): argv += ['-c', key+'='+json.dumps(value)]
        argv += ['-']
        with (root/'events.jsonl').open('w+b') as events, (root/'stderr.txt').open('w+b') as errors, (root/'prompt.txt').open('rb') as incoming:
            process = subprocess.Popen(argv, stdin=incoming, stdout=events, stderr=errors, env=self.env,
                                       cwd=root, start_new_session=True)
            try:
                deadline = time.monotonic()+recipe.timeout_seconds
                while process.poll() is None:
                    if time.monotonic() >= deadline: raise TimeoutError('English teacher deadline exceeded')
                    if events.tell() > 512*1024 or errors.tell() > 128*1024 or ((root/'last.json').exists() and (root/'last.json').stat().st_size > recipe.max_response_bytes):
                        raise ValueError('English teacher output bound exceeded')
                    time.sleep(.05)
            finally:
                if process.poll() is None: os.killpg(process.pid, signal.SIGKILL); process.wait()
                (root/'process-terminal.json').write_text(json.dumps(dict(process_terminal=True, returncode=process.returncode)))
        with (root/'events.jsonl').open('rb') as stream: events = stream.read(512*1024+1)
        with (root/'stderr.txt').open('rb') as stream: errors = stream.read(128*1024+1)
        if len(events) > 512*1024 or len(errors) > 128*1024: raise ValueError('Terminal event bound exceeded')
        if process.returncode: raise CLIExecutionError(process.returncode, events, errors)
        last = root/'last.json'
        if not last.is_file() or not 0 < last.stat().st_size <= recipe.max_response_bytes: raise ValueError('Missing or oversized final response')
        raw = parse_sol_events(events.decode(), last.read_text(), recipe)
        raw['capture'] = dict(root=str(root), files={p.name:sha(p) for p in root.iterdir() if p.is_file()})
        return raw


def evaluate(batch, raw, exclusions):
    text = raw['output'][0]['content'][0]['text']; candidate = parse_json(text)
    Draft202012Validator(schema_for(batch)).validate(candidate)
    values = []
    for scenario in batch:
        answer = candidate[scenario['scenario_id']]; reply = answer['reply']
        checks = validate(scenario, answer)
        checks['bounded_nonempty_reply'] = isinstance(reply, str) and bool(reply.strip()) and len(reply) <= 240
        checks['evaluation_exclusion'] = not exclusions.matches(reply)
        if 'expected_reply' in scenario['facts']: checks['exact_reply_oracle'] = reply == scenario['facts']['expected_reply']
        values.append(dict(scenario_id=scenario['scenario_id'], family_id=scenario['family_id'],
                           checks=checks, automated_passed=all(checks.values()), reply=reply,
                           human_attestation=False, training_approved=False))
    return values


def generate_batch(journal, provider, recipe, batch, exclusions):
    if journal.summary()['cap_nanousd'] != 0 or journal.summary()['max_requests'] != 20:
        raise ValueError('Exactly the separately authorized20-call CLI envelope required')
    batch = checked_batch(batch, exclusions)
    request = dict(batch=batch, schema=schema_for(batch), recipe=asdict(recipe),
                   instructions=INSTRUCTIONS+'\n'+style_instructions(), provider=provider.identity,
                   cli_version=provider.version, controls=OVERRIDES,
                   evaluation_inventory_sha256=exclusions.expected_sha256)
    if len(json.dumps(request, ensure_ascii=False).encode()) > 65536: raise ValueError('Bounded teacher request exceeded')
    key = digest(request); raw = journal.cached(key); cached = raw is not None
    if not cached:
        journal.reserve(key, 0)
        try:
            raw = provider.generate(request, recipe)
            check_raw(raw, recipe)
            if len(json.dumps(raw).encode()) > 65536: raise ValueError('Normalized response bound exceeded')
            journal.finish(key, raw, 0)
        except BaseException as error:
            journal.uncertain(key, type(error).__name__)
            raise
    check_raw(raw, recipe)
    results = evaluate(batch, raw, exclusions)
    return dict(creator='Navneet Prabhakar', version=1, request_key=key, request=request,
                cache_hit=cached, raw_response_sha256=digest(raw), usage=raw['usage'],
                results=results, training_approved=False, resolved_model=raw['resolved_model'],
                scope='English continuation candidates only; structured facts do not verify prose meaning/style')


def continuations(record, journal, exclusions):
    """Reconstruct exact candidate contexts; earlier assistant turns remain input only."""
    if digest(record['request']) != record['request_key']: raise ValueError('Request identity changed')
    raw = journal.cached(record['request_key'])
    if raw is None or digest(raw) != record['raw_response_sha256']: raise ValueError('Completed raw cache required')
    batch = checked_batch(record['request']['batch'], exclusions)
    recipe = EnglishRecipe(**record['request']['recipe']); check_raw(raw, recipe)
    result = evaluate(batch, raw, exclusions)
    if result != record['results']: raise ValueError('Recorded validation changed')
    return [dict(creator='Navneet Prabhakar', scenario_id=s['scenario_id'], family_id=s['family_id'],
                 messages=s['context']+[dict(role='assistant', content=r['reply'])],
                 supervision='last-user-turn-v1', prior_assistant_context_is_input_only=True,
                 teacher_request_key=record['request_key'], teacher_response_sha256=record['raw_response_sha256'],
                 automated_passed=r['automated_passed'], human_attestation=False, training_approved=False)
            for s,r in zip(batch,result,strict=True)]

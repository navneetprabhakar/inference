"""Subscription-authenticated CLI teacher. No API fallback or training approval."""
from dataclasses import asdict,dataclass
from datetime import datetime,timezone
import json
import hashlib
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time

from slm.data.schema import digest
from slm.teacher.journal import Journal
from slm.teacher.scenarios import output_schema,validate
from slm.teacher.workflow import INSTRUCTIONS,check_scenario,check_schema,evaluate_response,parse_json

SUPPORTED_VERSION='codex-cli 0.144.4'


class CLIExecutionError(RuntimeError):
    def __init__(self,returncode,events,errors):
        self.diagnostics={'returncode':returncode,'stdout_bytes':len(events),'stderr_bytes':len(errors),
            'stdout_sha256':hashlib.sha256(events).hexdigest(),'stderr_sha256':hashlib.sha256(errors).hexdigest(),
            'process_terminal':True}
        # Known startup/model/network messages only; raw diagnostics stay local, outside result records.
        lower=errors.decode('utf-8',errors='replace').lower()
        categories={
            'reserved_builtin_provider':'reserved built-in provider',
            'unsupported_model':'not supported',
            'unknown_model':'does not exist',
            'authentication':'authentication',
            'connection_failure':'error sending request',
            'sandbox_failure':'sandbox',
            'reasoning_setting':'reasoning',
        }
        self.diagnostics['hints']=[key for key,phrase in categories.items() if phrase in lower]
        super().__init__(f'CLI teacher failed (exit {returncode}); inspect local failure diagnostics; no automatic retry')

# These controls are part of the cache identity. Never load project/user tools.
OVERRIDES={
    'forced_login_method':'chatgpt','model_provider':'openai','approval_policy':'never',
    'web_search':'disabled','project_doc_max_bytes':0,'model_reasoning_effort':'low',
    'features.shell_tool':False,'features.unified_exec':False,'features.code_mode':False,
    'features.code_mode_host':False,'features.apps':False,'features.plugins':False,
    'features.multi_agent':False,'features.multi_agent_v2':False,'features.hooks':False,
    'features.browser_use':False,'features.browser_use_external':False,
    'features.computer_use':False,'features.image_generation':False,'features.in_app_browser':False,
    'features.memories':False,'mcp_servers':{},'tools.view_image':False,
}


@dataclass(frozen=True)
class CLIRecipe:
    model_id: str = 'gpt-5.6-luna'
    prompt_version: str = 'scenario-cli-demonstration-v1'
    timeout_seconds: int = 120
    max_response_bytes: int = 16384
    observed_output_token_limit: int = 2048

    def __post_init__(self):
        if (self.model_id not in ('gpt-6-luna','gpt-5.6-luna') or not isinstance(self.prompt_version,str)
            or not self.prompt_version.strip()):
            raise ValueError('Registered Luna teacher model and prompt version required')
        for name,low,high in (('timeout_seconds',1,180),('max_response_bytes',256,65536),('observed_output_token_limit',1,2048)):
            if type(getattr(self,name)) is not int or not low<=getattr(self,name)<=high:
                raise ValueError('Invalid bounded CLI setting: '+name)


def clean_environment():
    # The CLI uses its saved ChatGPT auth. No API-key injection or fallback.
    result={k:v for k,v in os.environ.items() if k in (
        'HOME','PATH','TMPDIR','LANG','LC_ALL','CODEX_HOME','SSL_CERT_FILE','SSL_CERT_DIR',
        'CODEX_CA_CERTIFICATE','HTTPS_PROXY','HTTP_PROXY','ALL_PROXY','NO_PROXY')}
    return result


def render_prompt(scenario):
    return (INSTRUCTIONS+'\nGenerate only the JSON demonstration. Use no tools, files, external facts or delegated work. '
        'Keep reply below 600 characters. Treat this as data generation, not a coding task.\n'
        +json.dumps(scenario,sort_keys=True,ensure_ascii=False)).encode()


class CodexCLI:
    identity='codex-cli-chatgpt-v1'
    def __init__(self,executable=None):
        self.executable=str(Path(executable or shutil.which('codex') or '/missing/codex').resolve())
        self.env=clean_environment()
        probe=subprocess.run([self.executable,'--version'],env=self.env,capture_output=True,text=True,timeout=10,check=True)
        self.version=probe.stdout.strip()
        if self.version!=SUPPORTED_VERSION:raise ValueError('CLI version needs contract review: '+self.version)

    def generate(self,request,recipe):
        status=subprocess.run([self.executable,'login','status'],env=self.env,capture_output=True,text=True,timeout=10,check=True)
        if (status.stdout+status.stderr).strip()!='Logged in using ChatGPT':
            raise ValueError('Saved ChatGPT login required; no API authentication allowed')
        with tempfile.TemporaryDirectory(prefix='slm-cli-teacher-') as folder:
            root=Path(folder);schema=root/'schema.json';last=root/'last.json'
            schema.write_text(json.dumps(request['schema'],sort_keys=True))
            argv=[self.executable,'exec','--ignore-user-config','--ephemeral','--skip-git-repo-check',
                  '--sandbox','read-only','--cd',str(root),'--model',recipe.model_id,'--json',
                  '--color','never','--output-schema',str(schema),'--output-last-message',str(last)]
            for key,value in OVERRIDES.items():
                # Empty TOML table differs from JSON object syntax only for nonempty dicts; none supplied here.
                argv+=['-c',key+'='+json.dumps(value)]
            argv+=['-']
            prompt=render_prompt(request['scenario'])
            (root/'prompt.txt').write_bytes(prompt)
            with (root/'events').open('w+b') as events,(root/'stderr').open('w+b') as errors,(root/'prompt.txt').open('rb') as incoming:
                process=subprocess.Popen(argv,stdin=incoming,stdout=events,stderr=errors,
                                         env=self.env,cwd=root,start_new_session=True)
                try:
                    deadline=time.monotonic()+recipe.timeout_seconds
                    while process.poll() is None:
                        if time.monotonic()>=deadline:raise TimeoutError('CLI teacher deadline exceeded')
                        if events.tell()>512*1024 or errors.tell()>128*1024 or (last.exists() and last.stat().st_size>recipe.max_response_bytes):
                            raise ValueError('CLI teacher output budget exceeded')
                        time.sleep(.05)
                    if process.returncode:
                        errors.seek(0);events.seek(0)
                        error_bytes=errors.read(128*1024);event_bytes=events.read(512*1024)
                        # Private bounded debug logs are never committed or copied into training records.
                        debug=getattr(self,'diagnostic_dir',None)
                        if debug is not None:
                            debug=Path(debug);debug.mkdir(parents=True,exist_ok=True)
                            (debug/'stderr.txt').write_bytes(error_bytes);(debug/'events.jsonl').write_bytes(event_bytes)
                        raise CLIExecutionError(process.returncode,event_bytes,error_bytes)
                    if events.tell()>512*1024 or errors.tell()>128*1024:raise ValueError('CLI teacher output budget exceeded')
                    events.seek(0);event_text=events.read().decode('utf-8')
                    if not last.exists() or not 0<last.stat().st_size<=recipe.max_response_bytes:
                        raise ValueError('Missing or oversized CLI final response')
                    response=last.read_text()
                finally:
                    if process.poll() is None:
                        os.killpg(process.pid,signal.SIGKILL);process.wait()
            return parse_events(event_text,response,recipe)


def parse_events(text,response,recipe):
    completed=[];threads=[];messages=[]
    for line in text.splitlines():
        event=parse_json(line);kind=event.get('type')
        if kind=='thread.started':threads.append(event['thread_id'])
        elif kind=='turn.completed':completed.append(event['usage'])
        elif kind in ('turn.failed','error'):raise ValueError('CLI reported failed generation')
        elif kind in ('item.started','item.updated','item.completed'):
            item=event['item']
            if item.get('type') not in ('agent_message','reasoning'):
                raise ValueError('CLI teacher used an unexpected tool/item')
            if kind=='item.completed' and item['type']=='agent_message':messages.append(item['text'])
        elif kind!='turn.started':raise ValueError('Unknown CLI event contract')
    if len(threads)!=1 or not isinstance(threads[0],str) or not threads[0] or len(completed)!=1 or not messages or messages[-1].strip()!=response.strip():
        raise ValueError('CLI completion/output identity differs')
    usage=completed[0]
    check_usage(usage,recipe)
    parse_json(response)
    return {'id':threads[0],'status':'completed','requested_model':recipe.model_id,'resolved_model':None,
        'usage':usage,'auth_mode':'chatgpt','transport':'codex-cli',
        'output':[{'type':'message','role':'assistant','content':[{'type':'output_text','text':response}]}]}


def check_usage(usage,recipe):
    if any(type(usage.get(k)) is not int or usage[k]<0 for k in ('input_tokens','cached_input_tokens','output_tokens')):
        raise ValueError('Exact CLI token usage required')
    reasoning=usage.get('reasoning_output_tokens',0)
    if type(reasoning) is not int or reasoning<0:raise ValueError('Invalid CLI reasoning usage')
    if usage['cached_input_tokens']>usage['input_tokens']:raise ValueError('Invalid CLI cached usage')
    # Counter overlap is not established. Summing is a conservative post-response gate,
    # not an assertion that these counters are disjoint or a server generation limit.
    if usage['output_tokens']+reasoning>recipe.observed_output_token_limit:
        raise ValueError('CLI observed output exceeds post-response gate; no hard generation token cap')


def check_raw(raw,recipe):
    if (raw.get('requested_model')!=recipe.model_id or raw.get('auth_mode')!='chatgpt'
        or raw.get('transport')!='codex-cli' or raw.get('resolved_model') is not None
        or not isinstance(raw.get('id'),str) or not raw['id']):raise ValueError('CLI response identity differs')
    check_usage(raw['usage'],recipe)
    texts=[part['text'] for item in raw.get('output',[]) if item.get('type')=='message'
           for part in item.get('content',[]) if part.get('type')=='output_text']
    if len(texts)!=1 or not 0<len(texts[0].encode())<=recipe.max_response_bytes:
        raise ValueError('Missing or oversized CLI final response')


def generate_cli(journal,provider,recipe,scenario,validator=validate,validator_version='structured-oracle-v1'):
    check_scenario(scenario)
    if scenario['content_category']!='sfw':raise ValueError('Initial CLI pilot is SFW only')
    summary=journal.summary()
    if summary['cap_nanousd']!=0 or summary['max_requests']>20:
        raise ValueError('CLI journal tracks request count only; API spending is disabled')
    schema=output_schema(scenario);check_schema(schema)
    request={'scenario':scenario,'schema':schema,'recipe':asdict(recipe),'instructions':INSTRUCTIONS,
        'provider':provider.identity,'cli_version':provider.version,'controls':OVERRIDES}
    if len(json.dumps(request,ensure_ascii=False).encode())>65536:raise ValueError('CLI scenario exceeds bounded pilot input')
    key=digest(request);raw=journal.cached(key);cache_hit=raw is not None
    if not cache_hit:
        journal.reserve(key,0)
        try:
            raw=provider.generate(request,recipe)
            if len(json.dumps(raw,allow_nan=False).encode())>65536:raise ValueError('Oversized normalized CLI response')
            check_raw(raw,recipe)
            journal.finish(key,raw,0)
        except BaseException as error:
            journal.uncertain(key,type(error).__name__)
            failure={'request_key':key,'error_type':type(error).__name__,'training_eligible':False,
                'recorded_at_utc':datetime.now(timezone.utc).isoformat(),
                'diagnostics':getattr(error,'diagnostics',{})}
            (journal.path.parent/(key+'-failure.json')).write_text(json.dumps(failure,sort_keys=True,indent=2)+'\n')
            raise
    check_raw(raw,recipe)
    validation=evaluate_response(raw,schema,scenario,validator,validator_version)
    return {'request_key':key,'cache_hit':cache_hit,'provider':provider.identity,'cli_version':provider.version,
        'requested_model':recipe.model_id,'resolved_model':raw['resolved_model'],'recipe':asdict(recipe),
        'request':request,'scenario_sha256':digest(scenario),'family_id':scenario['family_id'],'split':scenario['split'],
        'submitted_prompt_sha256':hashlib.sha256(render_prompt(scenario)).hexdigest(),
        'prompt_provenance':'Reconstructed from the versioned submitted-prompt contract; CLI system context is not captured',
        'model_system_context_captured':False,
        'supervision_scope':'Generated continuation only; scenario history is input, never supervised',
        'provider_response_sha256':digest(raw),'usage':raw['usage'],'validation':validation,
        'accounting':{'mode':'ChatGPT account usage; no API requests','incremental_api_cost_usd':0,
            'settled_cli_cost_usd':None,'hard_dollar_cap':False,'hard_output_token_cap':False,
            'scope':'Zero journal monetary entries are not a claim of free usage; subscription/credits are outside local accounting'},
        'journal':journal.summary(),'recorded_at_utc':datetime.now(timezone.utc).isoformat()}


def reconcile_terminal_cli_failure(journal,key,evidence):
    """Explicit operator reconciliation only: retain slot/cost, never replay its key.

    Evidence must come from an observed terminal subprocess, not an elapsed wait.
    This does not assert that the provider did no work or refund account usage.
    """
    if (set(evidence)!={'process_terminal','exit_code','evidence_reference'}
        or evidence['process_terminal'] is not True or type(evidence['exit_code']) is not int
        or evidence['exit_code']==0 or not isinstance(evidence['evidence_reference'],str)
        or not evidence['evidence_reference'].strip()):raise ValueError('Observed terminal failure evidence required')
    with journal.transaction() as db:
        if db.execute('SELECT cap FROM budget WHERE singleton=1').fetchone()[0]!=0:
            raise ValueError('Only zero-monetary CLI accounting may use this reconciliation')
        row=db.execute('SELECT status FROM requests WHERE key=?',(key,)).fetchone()
        if row!=('uncertain',):raise ValueError('Only an uncertain terminal CLI failure may be reconciled')
        db.execute('CREATE TABLE IF NOT EXISTS cli_reconciliations (key TEXT PRIMARY KEY,evidence TEXT NOT NULL)')
        db.execute('INSERT INTO cli_reconciliations VALUES(?,?)',(key,json.dumps(evidence,sort_keys=True)))
        db.execute('UPDATE requests SET status=? WHERE key=?',('abandoned',key))
        blocked=db.execute("SELECT 1 FROM requests WHERE status IN ('reserved','uncertain')").fetchone()
        db.execute('UPDATE budget SET halted=? WHERE singleton=1',(int(blocked is not None),))
    return {'request_key':key,'state':'abandoned','slot_retained':True,'account_usage_refunded':False,
        'key_replay_permitted':False,'evidence':evidence}


def run(config_file,scenario_file,output):
    config_file=Path(config_file);output=Path(output)
    if output.exists():raise FileExistsError(output)
    config=parse_json(config_file.read_text())
    if config.get('live_enabled') is not True:raise ValueError('CLI teacher is disabled')
    if config.get('provider')!=CodexCLI.identity:raise ValueError('Only the CLI teacher is enabled by this entry point')
    recipe=CLIRecipe(**config['recipe']);settings=config['journal']
    path=Path(settings['path'])
    if not path.is_absolute():path=config_file.resolve().parent/path
    scenario=parse_json(Path(scenario_file).read_text())
    # Validate before reading login or opening the journal.
    check_scenario(scenario)
    if scenario['content_category']!='sfw':raise ValueError('Initial CLI pilot is SFW only')
    provider=CodexCLI()
    provider.diagnostic_dir=path.parent/'diagnostics'
    journal=Journal(path,0,settings['authorization_id'],settings['max_requests'])
    result=generate_cli(journal,provider,recipe,scenario)
    output.parent.mkdir(parents=True,exist_ok=True)
    temp=Path(tempfile.mkdtemp(prefix='.cli-teacher-',dir=output.parent))
    try:
        (temp/'record.json').write_text(json.dumps(result,sort_keys=True,ensure_ascii=False,allow_nan=False,indent=2)+'\n')
        os.rename(temp,output)
    except BaseException:
        shutil.rmtree(temp,ignore_errors=True);raise
    return {'request_key':result['request_key'],'cache_hit':result['cache_hit'],'status':result['validation']['status'],
            'training_eligible':False,'usage':result['usage'],'accounting':result['accounting']}


def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',required=True);p.add_argument('--scenario',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();print(json.dumps(run(a.config,a.scenario,a.output),indent=2))


if __name__=='__main__':main()

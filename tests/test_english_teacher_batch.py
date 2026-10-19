# Creator: Navneet Prabhakar
from copy import deepcopy
import json
import pytest
from slm.data.schema import digest
from slm.teacher.english_batch import EnglishRecipe, checked_batch, generate_batch, continuations, evaluate
from slm.teacher.english_seeds import batches
from slm.teacher.journal import Journal
from slm.teacher.sol import parse_sol_events


class Guard:
    expected_sha256 = 'fixture-exclusions'
    def matches(self, text): return ['protected'] if 'heldoutmarker' in text else []


class Provider:
    identity = 'codex-cli-chatgpt-english-batch-v1'
    version = 'codex-cli 0.163.0'
    def __init__(self, wrong=False, fail=False): self.calls=0; self.wrong=wrong; self.fail=fail
    def generate(self, request, recipe):
        self.calls += 1
        if self.fail: raise TimeoutError('fixture uncertain generation')
        output={}
        for s in request['batch']:
            output[s['scenario_id']]=dict(reply='Wrong.' if self.wrong else s['facts'].get('expected_reply','A concise response.'),
                facts=s['facts'], action=s['expected_action'], tool_result=None, style=s['style'], content_category=s['content_category'])
        text=json.dumps(output)
        events=[dict(type='thread.started',thread_id='fixture'),dict(type='turn.started'),
                dict(type='item.completed',item=dict(type='agent_message',text=text)),
                dict(type='turn.completed',usage=dict(input_tokens=1000,cached_input_tokens=0,output_tokens=200))]
        return parse_sol_events('\n'.join(json.dumps(e) for e in events),text,recipe)


def test_all_182_own_training_seeds_have_bounded_complete_contexts():
    packets=batches(); assert len(packets)==20 and sum(map(len,packets))==182
    assert len({s['family_id'] for p in packets for s in p})==20
    for p in packets: checked_batch(p,Guard())
    with pytest.raises(ValueError): checked_batch(packets[2]+packets[3],Guard())
    bad=deepcopy(packets[0]);bad[0]['context'][0]['content']='heldoutmarker'
    with pytest.raises(ValueError,match='Protected'):checked_batch(bad,Guard())
    bad=deepcopy(packets[0]);bad[0]['split']='test'
    with pytest.raises(ValueError):checked_batch(bad,Guard())


def test_batch_cache_and_checked_final_continuation_mask(tmp_path):
    from slm.common.tokenizer import train_core
    journal=Journal(tmp_path/'journal.sqlite',0,'fixture-new20',20);provider=Provider()
    packet=batches()[13][:1]
    result=generate_batch(journal,provider,EnglishRecipe(),packet,Guard())
    assert generate_batch(journal,provider,EnglishRecipe(),packet,Guard())['cache_hit']
    assert provider.calls==1 and result['results'][0]['automated_passed']
    candidates=continuations(result,journal,Guard());assert len(candidates)==1
    row=candidates[0];assert not row['training_approved'] and row['prior_assistant_context_is_input_only']
    bpe=train_core([m['content'] for m in row['messages']],512,min_frequency=1)
    x,y,mask=bpe.serialize(row['messages'],supervision=row['supervision'])
    assert sum(mask)==len(bpe.encode(row['messages'][-1]['content']))+2
    altered=deepcopy(result);altered['results'][0]['reply']='forged'
    with pytest.raises(ValueError,match='validation changed'): continuations(altered,journal,Guard())


def test_wrong_prose_does_not_pass_by_copying_correct_facts(tmp_path):
    journal=Journal(tmp_path/'journal.sqlite',0,'fixture-new20',20)
    record=generate_batch(journal,Provider(wrong=True),EnglishRecipe(),batches()[2][:1],Guard())
    checks=record['results'][0]['checks']
    assert checks['structured_facts_match'] and not checks['exact_reply_oracle']
    assert not record['results'][0]['automated_passed'] and not record['training_approved']


def test_failure_retains_slot_halts_and_never_replays(tmp_path):
    journal=Journal(tmp_path/'journal.sqlite',0,'fixture-new20',20);provider=Provider(fail=True)
    with pytest.raises(TimeoutError):generate_batch(journal,provider,EnglishRecipe(),batches()[0],Guard())
    with pytest.raises(RuntimeError,match='never replay'):generate_batch(journal,provider,EnglishRecipe(),batches()[0],Guard())
    assert provider.calls==1 and journal.summary()['halted']
    assert journal.summary()['states']['uncertain']['requests']==1


def test_historical_or_larger_journal_cannot_replace_new20_allowance(tmp_path):
    for count in (19,21,200):
        journal=Journal(tmp_path/f'{count}.sqlite',0,'fixture',count);provider=Provider()
        with pytest.raises(ValueError,match='20-call'):generate_batch(journal,provider,EnglishRecipe(),batches()[0],Guard())
        assert provider.calls==0


def test_protected_output_rejected_and_cache_identity_tampering_refused(tmp_path):
    journal=Journal(tmp_path/'journal.sqlite',0,'fixture-new20',20);provider=Provider()
    result=generate_batch(journal,provider,EnglishRecipe(),batches()[0],Guard())
    raw=journal.cached(result['request_key']);bad=deepcopy(raw)
    candidate=json.loads(bad['output'][0]['content'][0]['text']);candidate[next(iter(candidate))]['reply']='heldoutmarker'
    bad['output'][0]['content'][0]['text']=json.dumps(candidate)
    assert not evaluate(result['request']['batch'],bad,Guard())[0]['automated_passed']
    result['request']['batch'][0]['facts']['forged']=True
    with pytest.raises(ValueError,match='identity changed'):continuations(result,journal,Guard())


def test_real_subprocess_batch_contract_captures_complete_raw_provenance(tmp_path,monkeypatch):
    import sys
    from slm.teacher.english_batch import EnglishBatchCLI
    for key in ('OPENAI_API_KEY','CODEX_API_KEY'):monkeypatch.setenv(key,'fixture-secret-not-forwarded')
    program='''
import sys,json,os
from pathlib import Path
if sys.argv[1:]==['--version']:print('codex-cli 0.163.0');sys.exit(0)
if sys.argv[1:]==['login','status']:print('Logged in using ChatGPT');sys.exit(0)
assert 'OPENAI_API_KEY' not in os.environ and 'CODEX_API_KEY' not in os.environ
a=sys.argv[1:];assert a[0]=='exec' and '--ignore-user-config' in a and '--ephemeral' in a
assert a[a.index('--model')+1]=='gpt-6.1-sol'
assert a[a.index('--sandbox')+1]=='read-only' and a[-1]=='-'
assert Path.cwd().name.startswith('english-attempt-')
prompt=sys.stdin.read();assert 'Use no tools' in prompt
batch=json.loads(prompt.split('\\nSCENARIOS:\\n',1)[1]);out={}
schema=json.loads(Path(a[a.index('--output-schema')+1]).read_text())
assert set(schema['required'])=={s['scenario_id'] for s in batch}
for s in batch:out[s['scenario_id']]=dict(reply=s['facts'].get('expected_reply','A concise reply.'),facts=s['facts'],action=s['expected_action'],tool_result=None,style=s['style'],content_category=s['content_category'])
text=json.dumps(out);Path(a[a.index('--output-last-message')+1]).write_text(text)
for event in [dict(type='thread.started',thread_id='fixture'),dict(type='turn.started'),dict(type='item.completed',item=dict(type='agent_message',text=text)),dict(type='turn.completed',usage=dict(input_tokens=1000,cached_input_tokens=0,output_tokens=100))]:print(json.dumps(event))
'''
    exe=tmp_path/'codex';exe.write_text(f'#!{sys.executable}\n'+program);exe.chmod(0o700)
    provider=EnglishBatchCLI(exe);provider.diagnostic_dir=tmp_path/'captures'
    journal=Journal(tmp_path/'journal.sqlite',0,'fixture',20)
    record=generate_batch(journal,provider,EnglishRecipe(),batches()[2][:2],Guard())
    raw=journal.cached(record['request_key'])
    capture=raw['capture'];assert capture['files'].keys()=={'schema.json','prompt.txt','last.json','events.jsonl','stderr.txt','process-terminal.json'}
    assert all(r['automated_passed'] for r in record['results'])
    from slm.data.stream_hash import sha
    from pathlib import Path
    assert all(sha(Path(capture['root'])/name)==want for name,want in capture['files'].items())

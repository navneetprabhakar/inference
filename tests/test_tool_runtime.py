"""Scripted positive/fault controls and actual random student negative inference."""
from copy import deepcopy
import pytest
pytest.importorskip('tokenizers');pytest.importorskip('jsonschema')
from slm.tools.local import LocalTools
from slm.tools.protocol import parse,canonical,InvalidDecision
from slm.inference.tools import run_turn,ToolModel
from slm.eval.tool_cases import tool_cases
from slm.eval.tools import score_task
from test_tools import call


class Script:
    def __init__(self,actions):self.actions=deepcopy(actions);self.histories=[]
    def generate_decision(self,history,max_new_tokens):
        self.histories.append(deepcopy(history));action=self.actions.pop(0)
        if isinstance(action,Exception):raise action
        return {'source':'scripted-test-control-not-student'},action


@pytest.mark.parametrize('case',tool_cases(),ids=lambda c:c['scenario_id'])
def test_seven_scripted_first_attempt_control_tasks_execute_with_no_repair(case):
    actions=[case['expected_action']]
    if actions[0]['kind']=='call':actions.append(case['expected_final'])
    model=Script(actions);r=run_turn(model,case['history'],LocalTools());score=score_task(case,r)
    assert score['structured_task_passed'] and not score['free_text_quality_verified']
    assert r['repair_attempts']==0 and r['executed_calls']==int(case['expected_action']['kind']=='call')
    assert 'expected_action' not in canonical(model.histories)
    if r['executed_calls']:
        tool=parse(model.histories[1][-1]['content']);assert model.histories[1][-1]['role']=='tool' and tool['ok']


def test_valid_schema_wrong_quantity_is_semantic_failure_even_with_consistent_result_summary():
    case=tool_cases()[0];action=deepcopy(case['expected_action']);action['arguments']['right']=3
    final={'kind':'answer','text':'The total is 3750.','facts':{'total_minor':3750}}
    r=run_turn(Script([action,final]),case['history'],LocalTools());s=score_task(case,r)
    assert s['checks']['protocol_valid_first'] and s['checks']['execution_success']
    assert s['checks']['tool_name_correct'] and not s['checks']['arguments_exact'] and not s['structured_task_passed']
    assert not s['checks']['tool_result_data_exact'] and not s['checks']['final_metadata_exact']


def test_metadata_does_not_establish_truth_of_response_text():
    case=tool_cases()[0];final=deepcopy(case['expected_final']);final['text']='The total is 999999. This deliberately contradicts the metadata.'
    r=run_turn(Script([case['expected_action'],final]),case['history'],LocalTools());s=score_task(case,r)
    assert s['structured_task_passed'] and s['free_text_quality_verified'] is False


@pytest.mark.parametrize('defect',['invalid_args','unknown_tool','repeat_id','budget','step_limit','handler_failure','invalid_output','raw_parse'])
def test_bounded_runtime_failure_paths_never_retry_or_conceal_execution(defect,monkeypatch):
    registry=LocalTools();case=tool_cases()[0];action=deepcopy(case['expected_action']);steps=2
    if defect=='invalid_args':action['arguments']['right']=True;actions=[action]
    elif defect=='unknown_tool':action['name']='arbitrary_shell';actions=[action]
    elif defect=='repeat_id':actions=[action,action]
    elif defect=='budget':other=deepcopy(action);other['id']='c2';actions=[action,other]
    elif defect=='step_limit':actions=[action];steps=1
    elif defect=='handler_failure':
        def fail(*args):raise RuntimeError('private implementation detail')
        monkeypatch.setattr(registry,'_execute',fail);actions=[action]
    elif defect=='invalid_output':monkeypatch.setattr(registry,'_execute',lambda *args:{'unexpected':1});actions=[action]
    else:actions=[InvalidDecision('Malformed generated JSON',{'token_ids':[8,99],'stop_reason':'length'})]
    r=run_turn(Script(actions),case['history'],registry,max_steps=steps,max_calls=2 if defect=='repeat_id' else 1)
    assert r['repair_attempts']==0 and r['final_decision'] is None
    if defect in ('invalid_args','unknown_tool'):assert r['status']=='invalid_arguments' and r['call_attempts']==1 and r['executed_calls']==0
    elif defect in ('repeat_id','budget'):assert r['status']=='execution_refused' and r['executed_calls']==1
    elif defect in ('handler_failure','invalid_output'):assert r['status']=='execution_error' and r['executed_calls']==1
    elif defect=='raw_parse':assert r['status']=='invalid_decision' and r['trace'][0]['raw']['token_ids']==[8,99] and r['executed_calls']==0
    else:assert r['status']=='step_limit' and r['executed_calls']==1


def test_hostile_document_stays_data_and_does_not_dispatch_another_tool():
    action=call('document_lookup',{'document_id':'D003'});final={'kind':'answer','text':'The document contains hostile instructions.','facts':{'document_id':'D003'}}
    script=Script([action,final]);r=run_turn(script,[{'role':'user','content':'Read fixture D003.'}],LocalTools())
    assert r['executed_calls']==1 and 'ignore the user' in script.histories[1][-1]['content']
    assert r['status']=='answer'


@pytest.mark.parametrize('backend',['torch','mlx'])
def test_actual_random_student_invalid_structural_output_is_retained_without_execution(tmp_path,backend):
    if backend=='mlx':pytest.importorskip('mlx.core')
    from slm.common.tokenizer import train_core
    from slm.common.config import Config,initialize
    from slm.common.checkpoint import save
    from slm.data.tokenized import sha
    bpe=train_core(['Synthetic tokenizer letters numbers and punctuation.']*10,512);bpe.save(tmp_path/'tok',{'scope':'Random negative fixture'})
    c=Config(vocab_size=bpe.vocab_size,max_seq_len=4096);save(tmp_path/'model',c,initialize(c,1703))
    m=ToolModel(tmp_path/'model',tmp_path/'tok',backend,expected_tokenizer_hash=sha(tmp_path/'tok/manifest.json'))
    r=run_turn(m,[{'role':'user','content':'Find the total of two times 1250.'}],LocalTools(),max_new_tokens=4)
    assert r['status']=='invalid_decision' and r['executed_calls']==0
    assert r['trace'][0]['raw'] is not None


@pytest.mark.parametrize('backend,device',[('torch','cpu'),('mlx','cpu'),('torch','cuda')])
def test_raw_model_decodes_structural_call_frame_without_masking_logits(tmp_path,monkeypatch,backend,device):
    import torch
    if backend=='mlx':pytest.importorskip('mlx.core')
    if device=='cuda' and not torch.cuda.is_available():pytest.skip('NVIDIA CUDA device unavailable')
    from slm.common.tokenizer import train_core
    from slm.common.config import Config,initialize
    from slm.common.checkpoint import save
    from slm.data.tokenized import sha
    bpe=train_core(['Synthetic JSON arithmetic add left right 1 2.']*10,512);bpe.save(tmp_path/'tok',{'scope':'Scripted-logit transport fixture'})
    c=Config(vocab_size=bpe.vocab_size,max_seq_len=512);save(tmp_path/'model',c,initialize(c))
    m=ToolModel(tmp_path/'model',tmp_path/'tok',backend,device,expected_tokenizer_hash=sha(tmp_path/'tok/manifest.json'))
    action=call('arithmetic',{'operation':'add','left':1,'right':2});tokens=[8,*bpe.encode(canonical(action)),9,3];seen=[];original=m.impl.forward
    def scripted(*args,**kwargs):
        logits,cache,traces=original(*args,**kwargs)
        if backend=='mlx':
            import mlx.core as mx
            mx.eval(logits,cache,traces);out=mx.full(logits.shape,-100,dtype=logits.dtype)
        else:out=torch.full_like(logits,-100)
        out[0,-1,tokens[len(seen)]]=100;seen.append(1);return out,cache,traces
    monkeypatch.setattr(m.impl,'forward',scripted)
    raw,decoded=m.generate_decision([{'role':'user','content':'Add 1 and 2.'}],max_new_tokens=len(tokens))
    assert raw['token_ids']==tokens and decoded==action and raw['stop_reason']=='message_end'


def test_new_tool_evaluation_families_and_exact_histories_remain_held_out():
    from slm.data.holdout import check_training_context
    for case in tool_cases():
        with pytest.raises(ValueError,match='held-out'):check_training_context(case['history'])
        with pytest.raises(ValueError,match='Reserved'):check_training_context([{'role':'user','content':'Different'}],(case['family_id'],))


def test_runtime_cli_lists_schemas_and_rejects_untrained_model_output(tmp_path):
    import subprocess,sys,json
    from slm.common.tokenizer import train_core
    from slm.common.config import Config,initialize
    from slm.common.checkpoint import save
    from slm.data.tokenized import sha
    subprocess.run([sys.executable,'-m','slm.inference.tools','list','--output',str(tmp_path/'tools.json')],check=True,capture_output=True)
    assert len(json.loads((tmp_path/'tools.json').read_text())['tools'])==5
    bpe=train_core(['Independent synthetic tokenizer.']*5,512);bpe.save(tmp_path/'tok',{'scope':'Runtime CLI fixture'})
    c=Config(vocab_size=bpe.vocab_size,max_seq_len=4096);save(tmp_path/'model',c,initialize(c,1703))
    (tmp_path/'history.json').write_text(json.dumps([{'role':'user','content':'Add 1 and 2.'}]))
    subprocess.run([sys.executable,'-m','slm.inference.tools','run','--model',str(tmp_path/'model'),'--tokenizer',str(tmp_path/'tok'),
        '--tokenizer-hash',sha(tmp_path/'tok/manifest.json'),'--history',str(tmp_path/'history.json'),'--max-new-tokens','4','--output',str(tmp_path/'trace.json')],check=True,capture_output=True)
    r=json.loads((tmp_path/'trace.json').read_text());assert r['status']=='invalid_decision' and r['executed_calls']==0
    assert r['trace'][0]['raw'] is not None


def test_completed_turns_preserve_user_history_without_duplicate_discovery_context():
    from slm.tools.protocol import validate_messages
    registry=LocalTools();case=tool_cases()[0]
    history=[{'role':'system','content':'Use professional SFW language.'},*case['history']]
    first=run_turn(Script([case['expected_action'],case['expected_final']]),history,registry)
    validate_messages(first['messages'])
    assert first['messages'][0]==history[0] and first['messages'][-1]['role']=='assistant'
    second_case=tool_cases()[2];next_history=[*first['messages'],*second_case['history']]
    new=deepcopy(second_case['expected_action']);new['id']='c2'
    model=Script([new,second_case['expected_final']]);second=run_turn(model,next_history,registry)
    validate_messages(second['messages'])
    assert second['messages'][0]==history[0] and second['status']=='answer'
    assert model.histories[0][0]['content'].count('Available tools: ')==1
    assert history==[{'role':'system','content':'Use professional SFW language.'},*case['history']]


def test_schema_valid_wrong_tool_data_does_not_pass_executable_semantics(monkeypatch):
    registry=LocalTools();case=tool_cases()[2];original=registry._execute
    monkeypatch.setattr(registry,'_execute',lambda name,args:original('product_lookup',{'product_id':'P002'}))
    result=run_turn(Script([case['expected_action'],case['expected_final']]),case['history'],registry)
    scored=score_task(case,result)
    assert scored['checks']['arguments_exact'] and scored['checks']['execution_success']
    assert not scored['checks']['tool_result_data_exact'] and not scored['structured_task_passed']


def test_history_reserves_room_for_declared_tool_results_before_any_execution():
    history=[]
    for i in range(31):history.extend([{'role':'user','content':f'Hello {i}.'},{'role':'assistant','content':canonical({'kind':'answer','text':'Hello.','facts':{}})}])
    history.append({'role':'user','content':'Add 1 and 2.'});model=Script([])
    with pytest.raises(ValueError,match='History cannot fit'):run_turn(model,history,LocalTools())
    assert model.histories==[]

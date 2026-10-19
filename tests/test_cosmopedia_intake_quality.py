"""Check complete-window screening and preserve raw acquisition payloads."""
# Creator: Navneet Prabhakar
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
from slm.data.evaluation_exclusions import compile_inventory,EvaluationExclusions
from slm.data.tokenized import sha

spec=importlib.util.spec_from_file_location('cosmo_intake',Path('scripts/intake-cosmopedia-candidates.py'))
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
REQUEST='Remember the purple cup and return its original color only.'


def setup(tmp_path,monkeypatch,foreign=False):
    p=tmp_path/'inventory.json';p.write_text(json.dumps(compile_inventory([dict(kind='request',text=REQUEST,origin='fixture')],{'fixture':'0'*64})))
    guard=EvaluationExclusions(p,sha(p))
    def predict(binary,model,inp,out,limits):
        lines=inp.read_text().splitlines();results=['__label__en 0.99 __label__es 0.01']*len(lines)
        if foreign:results[-1]='__label__es 0.99 __label__en 0.01'
        out.write_text('\n'.join(results)+'\n')
    monkeypatch.setattr(module,'predict',predict)
    plan=dict(fields=['prompt','text','audience','format','seed_data','token_length'],string_fields=['prompt','text','audience','format','seed_data'],nonapproval_prompt_families=[],nonapproval_seed_families=[],detector=dict(binary='unused',model='unused'))
    seed=' '.join('source'+str(i) for i in range(70))
    row=dict(prompt='Here is an extract from a webpage:\n"'+seed+'"\n\nWrite an explanatory article.',text=' '.join('word'+str(i) for i in range(300)),audience='middle_school_students',format='textbook',seed_data='fineweb',token_length=400)
    return guard,plan,row


def test_exact_seed_full_windows_and_original_payload(tmp_path,monkeypatch):
    guard,plan,row=setup(tmp_path,monkeypatch);before=deepcopy(row)
    result=module.quality([row],guard,plan,tmp_path)[0]
    assert not result['reasons'] and result['seed'] and len(result['windows'])>1
    assert row==before and all('scores' in w for w in result['windows'])


def test_foreign_tail_is_rejected(tmp_path,monkeypatch):
    guard,plan,row=setup(tmp_path,monkeypatch,foreign=True)
    assert 'window_english_signal' in module.quality([row],guard,plan,tmp_path)[0]['reasons']


def test_prompt_privacy_and_body_request_are_blocked(tmp_path,monkeypatch):
    guard,plan,row=setup(tmp_path,monkeypatch);row['text']+=' '+REQUEST;row['prompt']+=' Contact test@example.org.'
    result=module.quality([row],guard,plan,tmp_path)[0]
    assert 'protected_evaluation_text' in result['reasons'] and 'privacy_or_credential_signal' in result['reasons']


def test_unsupported_and_known_nonapproval_seed_never_pass(tmp_path,monkeypatch):
    guard,plan,row=setup(tmp_path,monkeypatch);row['seed_data']='ultrachat'
    assert 'unsupported_seed_constituent' in module.quality([row],guard,plan,tmp_path)[0]['reasons']
    row['seed_data']='fineweb';seed=module.extract(row);plan['nonapproval_seed_families']=[seed['proposed_exact_seed_family']]
    assert 'known_seed_nonapproval' in module.quality([row],guard,plan,tmp_path)[0]['reasons']

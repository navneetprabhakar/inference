"""Controlled style/meaning diagnostics never assert human approval."""
from copy import deepcopy
import hashlib
import json
import pytest
from slm.teacher.styles import GUIDES,assess,compare,surface
from slm.teacher.cli import CLIRecipe,PROMPT_V1,PROMPT_V2,PROMPT_V3,render_prompt,generate_cli,REPLY_CONTRACT
from slm.teacher.workflow import INSTRUCTIONS
from slm.teacher.scenarios import fixture_scenario
from slm.teacher.bridge import normalize
from test_teacher_cli import FakeCLI,journal,response,stub


@pytest.mark.parametrize('style',sorted(GUIDES))
def test_v3_guides_bind_prompt_cache_and_remain_pending(tmp_path,style):
    s=fixture_scenario('tool_trajectory',style);j=journal(tmp_path);provider=FakeCLI();recipe=CLIRecipe(prompt_version=PROMPT_V3)
    r=generate_cli(j,provider,recipe,s)
    prompt=render_prompt(s,PROMPT_V3)
    for guide in GUIDES.values():assert guide.encode() in prompt
    assert b'POST-TOOL final answer' in prompt and b'Style must change diction or syntax' in prompt
    assert r['submitted_prompt_sha256']==hashlib.sha256(prompt).hexdigest()
    assert 'five-styles-v1' in r['request']['instructions']
    assert generate_cli(j,provider,recipe,json.loads(json.dumps(s,sort_keys=True)))['cache_hit'] and provider.calls==1
    assert normalize(r,j.path)['proof']['prompt_version']==PROMPT_V3
    assert not normalize(r,j.path)['training_eligible']
    # Guidance edits cannot re-use a v3 request key silently, even if a version bump was forgotten.
    from unittest.mock import patch
    with patch('slm.teacher.styles.instructions',return_value='Altered fixture guide'):
        changed=generate_cli(j,provider,recipe,s)
    assert changed['request_key']!=r['request_key'] and provider.calls==2


def test_legacy_v1_v2_prompt_bytes_and_request_instructions_are_unchanged(tmp_path):
    s=fixture_scenario();suffix=('\nGenerate only the JSON demonstration. Use no tools, files, external facts or delegated work. '
        'Keep reply below 600 characters. Treat this as data generation, not a coding task.\n'+json.dumps(s,sort_keys=True,ensure_ascii=False))
    assert render_prompt(s,PROMPT_V1)==(INSTRUCTIONS+suffix).encode()
    assert render_prompt(s,PROMPT_V2)==(INSTRUCTIONS+'\n'+REPLY_CONTRACT+suffix).encode()
    p=FakeCLI();j=journal(tmp_path)
    versions=[generate_cli(j,p,CLIRecipe(prompt_version=v),s) for v in (PROMPT_V1,PROMPT_V2,PROMPT_V3)]
    assert len({v['request_key'] for v in versions})==3
    assert all(v['request']['instructions']==INSTRUCTIONS for v in versions[:2])
    assert all(generate_cli(j,p,CLIRecipe(prompt_version=v),s)['cache_hit'] for v in (PROMPT_V1,PROMPT_V2,PROMPT_V3))
    assert p.calls==3


@pytest.mark.parametrize('text,expected',[('Total 2,625.','total 2625.'),('  Total is 2,625 minor units.  ','total is 2625 minor units.'),
    ('1,2 are list items','1,2 are list items'),('1,234.50 decimal','1,234.50 decimal'),('Word123,456','word123,456')])
def test_numeric_formatting_normalization_does_not_erase_other_text(text,expected):
    assert surface(text)==expected


@pytest.mark.parametrize('reply,extra,negation',[
 ('Total is 2,500 minor units.',[],False),('Total 2500.',[],False),
 ('The total is not 2500 minor units.',[],True),
 ('The total is 5000 minor units.',[5000],False),
 ('Not 5000: total 2500 minor units.',[5000],True),
 ('The total is 2500 dollars.',[],False),
 ('The total is two thousand five hundred minor units.',[],False)])
def test_meaning_diagnostics_never_approve_wrong_negated_units_or_unparsed_words(reply,extra,negation):
    s=fixture_scenario();candidate=response(s);candidate['reply']=reply;r=assess(s,candidate)
    assert r['structured_passed'] and r['surface_observations']['integer_literals_outside_oracle']==extra
    assert r['surface_observations']['negation_marker_present']==negation
    assert not r['meaning_verified'] and not r['style_verified'] and not r['training_eligible']
    # Correct metadata survives even when prose is wrong: it must not be reported as prose truth.
    assert r['human_attestation'] is False


def test_same_reply_or_punctuation_difference_exposes_nonseparation_without_approving_other_pairs():
    a=fixture_scenario(style='professional');b=fixture_scenario(style='caveman');x=deepcopy(response(a));y=deepcopy(response(b))
    x['reply']='The total is 2,500 minor units.';y['reply']='The total is 2500 minor units.'
    r=compare(a,x,b,y)
    assert r['structured_fields_equal'] and r['style_nonseparation_cue']
    assert not r['meaning_equivalence_verified'] and not r['style_separation_verified']
    y['reply']='Two cups. Each 1250. Total 2500 minor units.';r=compare(a,x,b,y)
    assert not r['style_nonseparation_cue']
    assert not r['style_separation_verified'] and not r['training_eligible']
    y['facts']['quantity']=3;r=compare(a,x,b,y)
    assert not r['right']['structured_passed'] and not r['structured_fields_equal']


def test_mismatched_context_or_family_and_same_style_cannot_be_compared():
    a=fixture_scenario(style='professional');b=fixture_scenario(style='caveman')
    for field,value in [('family_id','other-family'),('task','correction'),('context',[{'role':'user','content':'Different task.'}])]:
        bad=deepcopy(b);bad[field]=value
        with pytest.raises(ValueError,match='same context'):compare(a,response(a),bad,response(bad))
    with pytest.raises(ValueError,match='different requested styles'):compare(a,response(a),a,response(a))


def test_invalid_candidate_is_separate_structured_failure():
    s=fixture_scenario();c=response(s);c['extra']='invalid';r=assess(s,c)
    assert not r['schema_passed'] and not r['structured_passed'] and not r['training_eligible']


def test_actual_fixture_process_receives_v3_guide(tmp_path):
    from slm.teacher.cli import CodexCLI
    executable=stub(tmp_path)
    executable.write_text(executable.read_text().replace("assert 'Generate only the JSON demonstration' in prompt",
        "assert 'Generate only the JSON demonstration' in prompt;assert 'five-styles-v1' in prompt;assert 'telegraphic English' in prompt"))
    r=generate_cli(journal(tmp_path),CodexCLI(executable),CLIRecipe(prompt_version=PROMPT_V3),fixture_scenario())
    assert not r['validation']['training_eligible']

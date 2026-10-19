"""Reference-only derivation must not smuggle targets or weaken heldouts."""
# Creator: Navneet Prabhakar
from copy import deepcopy
import json
from pathlib import Path
import pytest
from slm.data.context import derive,checked_policy,prepare
from slm.data.schema import digest
from slm.data.staging import stage
from slm.data.tokenized import sha
from slm.data.review import training_examples
from test_staging import setup,spec,LIMITS,item,read


def policy():return json.loads(Path('configs/context-prose-candidate-v1.json').read_text())


TEXT=('The archive is in a large building and has a collection of books. '
      'Its visitors can read the records with a guide from the local library. '
      'These pages describe the history of the town and the design of its bridges. ')*3


def record():
    return dict(example_id='source:row',source=policy()['source'],source_revision='a'*40,license_record='b'*64,
        parent_group_id='family:parent',split='test',official_split='train',task='conversation',style='unlabeled',
        content_category='unreviewed',language='unknown',lineage=[],upstream_references=[],
        messages=[dict(role='user',content='What is this?\n\nContext:\n'+TEXT.strip()),
                  dict(role='assistant',content='An unsupported and deliberately wrong answer.')],
        validation_results={'split_group':'c'*64})


def test_exact_passage_and_parent_proof_without_answer_supervision():
    raw=record();saved=deepcopy(raw);out,reason=derive(raw,policy())
    assert reason is None and raw==saved
    assert out['messages']==[dict(role='text',content=TEXT.strip())]
    assert 'deliberately wrong' not in json.dumps(out)
    assert out['official_split']==out['split']=='test'
    proof=out['validation_results']['context_derivation']
    assert proof['parent_record_sha256']==digest(raw) and proof['parent_split_group']=='c'*64
    assert out['language']=='unknown' and out['content_category']=='unreviewed'


@pytest.mark.parametrize('addition,reason',[
    ('\n\nContext:\nAnother purported passage.','missing_or_ambiguous_context'),
    ('\ncontact: person@example.org','privacy_attention'),
    ('\nphone: +1 555 123 4567','privacy_attention'),
    ('\nThe medication dosage is described here.','scope_attention'),
    ('\n[citation needed]','boilerplate_attention'),
    ('\nReferences','boilerplate_attention'),
    ('\ufffd','noncanonical_context'),
    ('\x00','controls'),
])
def test_unsafe_or_ambiguous_context_is_excluded_not_rewritten(addition,reason):
    raw=record();raw['messages'][0]['content']+=addition
    out,why=derive(raw,policy());assert out is None and why==reason


def test_missing_long_non_latin_and_non_english_proxy_contexts_are_not_silently_shortened():
    for text,reason in [('short','word_count'),(TEXT*100,'word_count'),
                        ('中文内容 '*100,'script_proxy'),('randomword '*100,'function_word_proxy')]:
        raw=record();raw['messages'][0]['content']='Question\n\nContext:\n'+text.strip()
        assert derive(raw,policy())==(None,reason)
    raw=record();raw['messages'][0]['content']='Question without reference'
    assert derive(raw,policy())==(None,'missing_or_ambiguous_context')


def test_context_reprocessing_reunites_equal_passages_and_keeps_heldout_precedence(tmp_path):
    src=setup(tmp_path);first=record();second=record();second.update(example_id='source:other',parent_group_id='family:other',split='train')
    rows=[derive(r,policy())[0] for r in (first,second)]
    # Isolate the independent grouping contract with the registered test source.
    for r in rows:r.update(source=src.source_id,source_revision=src.revision,license_record=digest(src.__dict__))
    from slm.data.schema import Example
    out=tmp_path/'regroup';stage([spec(tmp_path,[Example(**r) for r in rows])],out,limits=LIMITS)
    got=read(out)
    assert len(got)==1 and got[0]['split']=='test' and got[0]['messages'][0]['content']==TEXT.strip()
    with pytest.raises(ValueError,match='sample-only'):list(training_examples(out))


def test_policy_must_stay_nonadmitting_and_bound_to_parent():
    for key,value in [('status','training'),('source','arbitrary'),('maximum_words',0),('minimum_latin_letter_fraction',float('nan'))]:
        bad=policy();bad[key]=value
        with pytest.raises(ValueError):checked_policy(bad)

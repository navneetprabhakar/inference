# Creator: Navneet Prabhakar
import importlib.util
import json
from pathlib import Path
import pytest
from slm.teacher.journal import Journal
from slm.data.stream_hash import sha
from test_english_teacher_batch import Guard, Provider


def controller(tmp_path,monkeypatch):
    spec=importlib.util.spec_from_file_location('english_controller','scripts/run-english-teacher-pilot.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    historical=[]
    for n in (1,19):
        p=tmp_path/f'old{n}.sqlite';j=Journal(p,0,f'fixture{n}',n)
        for i in range(n):j.reserve(str(i),0);j.finish(str(i),{'fixture':i},0)
        historical.append(str(p))
    cfg=tmp_path/'authorization.json';cfg.write_text(json.dumps(dict(authorized=True,maximum_additional_launches=20,
        historical_journals=historical,authorization_id='fixture-new20',cli_executable='fixture')))
    source=tmp_path/'source.txt';source.write_text('fixture source')
    monkeypatch.setattr(mod,'ROOT',tmp_path/'run');monkeypatch.setattr(mod,'CONFIG',cfg)
    monkeypatch.setattr(mod,'SOURCES',[str(source)])
    monkeypatch.setattr(mod,'EvaluationExclusions',lambda *args:Guard())
    provider=Provider();monkeypatch.setattr(mod,'EnglishBatchCLI',lambda *args:provider)
    return mod,provider


def test_frozen_controller_requires_two_actual_reviewed_single_calls_before_batches(tmp_path,monkeypatch):
    mod,p=controller(tmp_path,monkeypatch);mod.freeze();mod.next_call();mod.next_call()
    assert p.calls==2
    with pytest.raises(FileNotFoundError):mod.next_call()
    assert p.calls==2
    review=dict(passed=True,record_sha256=[sha(mod.ROOT/'records'/f'{i:02d}.json') for i in range(2)])
    (mod.ROOT/'initial-direct-review.json').write_text(json.dumps(review))
    mod.next_call();assert p.calls==3
    record=json.loads((mod.ROOT/'records/02.json').read_text());assert len(record['results'])==10
    record['continuation_candidates'][0]['messages'][-1]['content']='forged'
    (mod.ROOT/'records/02.json').write_text(json.dumps(record))
    with pytest.raises(ValueError,match='identity changed'):mod.next_call()
    assert p.calls==3


def test_authorization_source_and_original_deadline_cannot_reset(tmp_path,monkeypatch):
    mod,p=controller(tmp_path,monkeypatch);mod.freeze()
    with pytest.raises(FileExistsError):mod.freeze()
    deadline=mod.read(mod.ROOT/'plan.json')['deadline_epoch']
    monkeypatch.setattr(mod.time,'time',lambda:deadline)
    with pytest.raises(TimeoutError):mod.next_call()
    assert p.calls==0

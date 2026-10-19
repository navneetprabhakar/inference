# Creator: Navneet Prabhakar
from copy import deepcopy
import json
from pathlib import Path
import pytest
from slm.common.tokenizer import train_core
from slm.data.schema import digest
from slm.data.stream_hash import sha
from slm.teacher.english_batch import generate_batch, EnglishRecipe
from slm.teacher.english_continuations import compose
from slm.teacher.english_seeds import batches
from slm.teacher.journal import Journal
from test_english_teacher_batch import Provider,Guard


def captured(tmp_path):
    journal=Journal(tmp_path/'journal.sqlite',0,'fixture',20)
    record=generate_batch(journal,Provider(),EnglishRecipe(),batches()[13][:1],Guard())
    raw=journal.cached(record['request_key']);text=raw['output'][0]['content'][0]['text']
    base=tmp_path/'captures';root=base/'english-attempt-fixture';root.mkdir(parents=True)
    request=record['request']
    events=[dict(type='thread.started',thread_id='fixture'),dict(type='turn.started'),
        dict(type='item.completed',item=dict(type='agent_message',text=text)),
        dict(type='turn.completed',usage=raw['usage'])]
    (root/'events.jsonl').write_text('\n'.join(json.dumps(e) for e in events))
    (root/'last.json').write_text(text);(root/'stderr.txt').write_text('')
    (root/'schema.json').write_text(json.dumps(request['schema']))
    (root/'prompt.txt').write_text(request['instructions']+'\nSCENARIOS:\n'+json.dumps(request['batch'],sort_keys=True,ensure_ascii=False))
    (root/'process-terminal.json').write_text(json.dumps(dict(process_terminal=True,returncode=0)))
    raw['capture']=dict(root=str(root),files={p.name:sha(p) for p in root.iterdir()})
    with journal.transaction() as db:db.execute('UPDATE requests SET response=?,response_hash=? WHERE key=?',(json.dumps(raw),digest(raw),record['request_key']))
    record['raw_response_sha256']=digest(raw)
    bpe=train_core(['A complete prior conversation with corrected owner information.'],512,min_frequency=1)
    return record,journal,bpe,base,root


def test_style_is_in_student_context_and_only_final_continuation_is_supervised(tmp_path):
    record,journal,bpe,base,root=captured(tmp_path)
    rows=compose(record,journal,Guard(),bpe,tokenizer_sha256='fixture',capture_base=base)
    row=rows[0]
    assert row['messages'][0]==dict(role='system',content='Response style: terse. Content setting: sfw.')
    assert row['messages'][1:-1]==record['request']['batch'][0]['context']
    assert row['assistant_targets']==len(bpe.encode(row['messages'][-1]['content']))+2
    assert not row['training_release_approved'] and not row['source_evidence_complete']


def test_modified_capture_cannot_pass_merely_by_rehashing_final_file(tmp_path):
    record,journal,bpe,base,root=captured(tmp_path)
    (root/'last.json').write_text('{}')
    with pytest.raises(ValueError,match='capture changed'):compose(record,journal,Guard(),bpe,tokenizer_sha256='fixture',capture_base=base)
    raw=journal.cached(record['request_key']);raw['capture']['files']['last.json']=sha(root/'last.json')
    with journal.transaction() as db:db.execute('UPDATE requests SET response=?,response_hash=? WHERE key=?',(json.dumps(raw),digest(raw),record['request_key']))
    record['raw_response_sha256']=digest(raw)
    with pytest.raises(ValueError):compose(record,journal,Guard(),bpe,tokenizer_sha256='fixture',capture_base=base)


def test_capture_location_context_length_and_extra_files_are_guarded(tmp_path):
    record,journal,bpe,base,root=captured(tmp_path)
    with pytest.raises(ValueError,match='location'):compose(record,journal,Guard(),bpe,tokenizer_sha256='fixture',capture_base=tmp_path)
    with pytest.raises(ValueError,match='context'):compose(record,journal,Guard(),bpe,tokenizer_sha256='fixture',capture_base=base,max_length=1)
    (root/'extra').write_text('unexpected')
    with pytest.raises(ValueError,match='Exact bounded'):compose(record,journal,Guard(),bpe,tokenizer_sha256='fixture',capture_base=base)

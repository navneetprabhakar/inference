# Creator: Navneet Prabhakar
import hashlib
import pytest
from slm.data.story_segments import segments, DELIMITER as D


def test_exact_offsets_and_final_eof():
    raw=b'\nOne story.\n'+D+b'\nTwo stories.\n'
    rows=segments(raw,0,len(raw))
    assert [r['text'] for r in rows]==['\nOne story.\n','\nTwo stories.\n']
    for r in rows:
        assert raw[r['start']:r['end']]==r['text'].encode()
        assert hashlib.sha256(r['text'].encode()).hexdigest()==r['raw_text_sha256']


def test_sparse_partial_edges_are_discarded_without_utf8_repair():
    raw=b'\x80fragment'+D+b'\nWhole story.\n'+D+b'partial\xc3'
    rows=segments(raw,37,1000)
    assert len(rows)==1 and rows[0]['text']=='\nWhole story.\n'
    assert rows[0]['start']==37+raw.index(b'\nWhole')


def test_complete_story_invalid_utf8_refused():
    with pytest.raises(UnicodeDecodeError):segments(b'bad\x80'+D,0,100)


def test_missing_delimiter_and_caps_refused():
    with pytest.raises(ValueError):segments(b'no marker',0,9)
    with pytest.raises(ValueError):segments(b'big'+D,0,100,max_story_bytes=2)
    with pytest.raises(ValueError):segments(b'a'+D+b'b'+D,0,100,max_records=1)


def test_no_false_record_from_delimiter_or_whitespace():
    assert segments(D+b'\n'+D,0,len(D)*2+1)==[]

"""Failure and extraction checks for finite Parquet range intake."""
# Creator: Navneet Prabhakar
from dataclasses import replace
import io
import urllib.error
from email.message import Message

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from slm.data.parquet_ranges import BoundedParquet, CoveredFile, ExactRanges, Limits


class Response(io.BytesIO):
    status = 206

    def __init__(self, raw, start, length, total, **changes):
        super().__init__(raw)
        self.headers = Message()
        for key, value in {'Content-Range': f'bytes {start}-{start + length - 1}/{total}',
                           'Content-Length': str(length), 'ETag': '"fixture"', **changes}.items():
            self.headers[key] = value


def fixture():
    sink = pa.BufferOutputStream()
    pq.write_table(pa.table({'text': ['one', 'two', 'three', 'four'], 'id': [1, 2, 3, 4]}),
                   sink, row_group_size=2)
    raw = sink.getvalue().to_pybytes()
    calls = []

    def open_range(request, timeout):
        start, stop = map(int, request.get_header('Range').split('=')[1].split('-'))
        assert request.get_header('If-match') == '"fixture"'
        assert timeout == 45
        calls.append((start, stop))
        return Response(raw[start:stop + 1], start, stop - start + 1, len(raw))
    return raw, calls, open_range


def test_exact_groups_and_gap_refusal():
    raw, calls, opener = fixture()
    transport = ExactRanges('https://example.invalid/pinned', len(raw), '"fixture"', opener=opener)
    reader = BoundedParquet(transport)
    assert reader.read_group(1).to_pydict() == {'text': ['three', 'four'], 'id': [3, 4]}
    assert len(calls) == 4 and sum(c['bytes'] + 1 for c in transport.receipts) == transport.reserved_bytes
    with pytest.raises(ValueError, match='Repeated'):
        reader.read_group(1)
    view = CoveredFile(100, [(0, b'1234'), (90, b'abcdefghij')])
    with pytest.raises(ValueError, match='unretained'):
        view.read(100)
    assert view.tell() == 0
    view.seek(-3, 2)
    assert view.read(3) == b'hij'


@pytest.mark.parametrize('defect', ['status', 'etag', 'range', 'encoding', 'short', 'long', 'length'])
def test_transport_refusals_precharged_no_retry(defect):
    calls = []

    def opener(request, timeout):
        calls.append(request)
        changes = {'ETag': '"changed"'} if defect == 'etag' else {}
        if defect == 'range': changes['Content-Range'] = 'bytes 1-4/100'
        if defect == 'encoding': changes['Content-Encoding'] = 'gzip'
        if defect == 'length': changes['Content-Length'] = '100'
        body = b'abc' if defect == 'short' else b'abcde' if defect == 'long' else b'abcd'
        response = Response(body, 0, 4, 100, **changes)
        if defect == 'status': response.status = 200
        return response
    transport = ExactRanges('https://example.invalid/pinned', 100, '"fixture"',
                            limits=replace(Limits(), requests=1), opener=opener)
    with pytest.raises(ValueError): transport.get(0, 4)
    assert len(calls) == 1 and transport.reserved_bytes == 5 and not transport.receipts
    with pytest.raises(ValueError, match='budget'): transport.get(0, 4)
    assert len(calls) == 1


def test_declared_size_limits_before_payload():
    raw, calls, opener = fixture()
    reader = BoundedParquet(ExactRanges('https://example.invalid/pinned', len(raw), '"fixture"',
                            limits=replace(Limits(), group_declared_uncompressed_bytes=1), opener=opener))
    with pytest.raises(ValueError, match='Declared'): reader.read_group(0)
    assert len(calls) == 3


def test_footer_and_network_caps_before_extra_fetch():
    raw, calls, opener = fixture()
    with pytest.raises(ValueError, match='Footer'):
        BoundedParquet(ExactRanges('https://example.invalid/pinned', len(raw), '"fixture"',
                                  limits=replace(Limits(), footer_bytes=1), opener=opener))
    assert len(calls) == 2
    transport = ExactRanges('https://example.invalid/pinned', len(raw), '"fixture"',
                            limits=replace(Limits(), network_bytes=4), opener=opener)
    with pytest.raises(ValueError, match='budget'): transport.get(0, 4)
    assert transport.attempts == 0


def test_actual_decoded_size_checked():
    raw, calls, opener = fixture()
    reader = BoundedParquet(ExactRanges('https://example.invalid/pinned', len(raw), '"fixture"',
                            limits=replace(Limits(), group_decoded_bytes=1), opener=opener))
    with pytest.raises(ValueError, match='Actual decoded'): reader.read_group(0)
    assert len(calls) == 4 and reader.completed_groups == {0}


def test_ignored_range_never_reads_full_file_body():
    class IgnoredRange(Response):
        status = 200

        def read(self, *args):
            pytest.fail('Must refuse HTTP 200 before reading any body')
    transport = ExactRanges('https://example.invalid/pinned', 100, '"fixture"',
                            opener=lambda *args, **kwargs: IgnoredRange(b'', 0, 4, 100))
    with pytest.raises(ValueError, match='honor exact'): transport.get(0, 4)


def test_transport_exception_hides_signed_url_and_is_not_retried():
    calls = []

    def opener(*args, **kwargs):
        calls.append(1)
        raise urllib.error.URLError('https://temporary.invalid/?secret=example')
    transport = ExactRanges('https://example.invalid/pinned', 100, '"fixture"', opener=opener)
    with pytest.raises(ValueError, match='no automatic retry') as caught:
        transport.get(0, 4)
    assert 'secret' not in str(caught.value) and len(calls) == 1
    assert transport.attempts == 1 and transport.reserved_bytes == 5

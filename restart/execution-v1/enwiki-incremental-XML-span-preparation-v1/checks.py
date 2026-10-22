"""Synthetic-only independent byte-slice/hash oracle and hostile XML cases."""
import hashlib
import json
import random
import resource
import time
from spans import PageSpans

HEADER = b'<?xml version="1.0" encoding="UTF-8"?><mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/"><siteinfo/>'
TAIL = b'</mediawiki>'
PAGES = [
    '<page><title>caf\u00e9 \u6f22\U0001f30f</title><text>A&amp;B&lt;/page&gt;\r\nC</text></page>'.encode(),
    b'<page a="quoted &gt; value"><text><![CDATA[</page> & literal]]></text><!-- </page> --></page>',
    b'<page/>', b'<page ><text /></page  >',
    b'<page><text>&#x1F30F;&#13;Z</text><?test page?></page>',
]
WIRE = HEADER + b'\n'.join(PAGES) + TAIL


def run_chunks(wire, chunks, **kwargs):
    rows = []
    p = PageSpans(rows.append, **kwargs)
    for part in chunks:
        p.feed(part)
    result = p.finish()
    for row in rows:
        raw = wire[row['start']:row['end']]
        assert row['bytes'] == len(raw)
        assert row['SHA256'] == hashlib.sha256(raw).hexdigest()
    return p, rows, result


def pieces(wire, sizes):
    pos = 0
    for n in sizes:
        if pos >= len(wire):
            break
        yield wire[pos:pos+n]
        pos += n
    if pos < len(wire):
        yield wire[pos:]


def refused(wire, **kwargs):
    p = PageSpans(lambda r: None, **kwargs)
    try:
        for i in range(0, len(wire), 17):
            p.feed(wire[i:i+17])
        p.finish()
    except Exception as error:
        # An actual parser/source failure is terminal; no recovery continuation.
        assert p.failed
        try:
            p.finish()
        except ValueError:
            return type(error).__name__
        raise AssertionError('failed_parser_reused')
    raise AssertionError('hostile_source_accepted')


def main():
    start = time.monotonic()
    count = 0
    for size in [1, 2, 3, 4, 7, 16, 17, 31, 64, 127, 65536]:
        p, rows, result = run_chunks(WIRE, (WIRE[i:i+size] for i in range(0, len(WIRE), size)))
        assert len(rows) == len(PAGES)
        assert [WIRE[r['start']:r['end']] for r in rows] == PAGES
        assert result['actual_root_closed']
        count += 1
    # Every possible two-feed boundary probes split UTF8, entity, CDATA, empty
    # page, closing tags and original newline spellings against byte slices.
    for cut in range(1, len(WIRE)):
        _, rows, _ = run_chunks(WIRE, [WIRE[:cut], WIRE[cut:]])
        assert [WIRE[r['start']:r['end']] for r in rows] == PAGES
        count += 1
    rng = random.Random(9371)
    for _ in range(100):
        _, rows, _ = run_chunks(WIRE, pieces(WIRE, [rng.randrange(1, 40) for _ in range(len(WIRE))]))
        assert [WIRE[r['start']:r['end']] for r in rows] == PAGES
        count += 1
    # A large ordinary text page must not retain page-sized XML or strings.
    rows = []
    p = PageSpans(rows.append)
    beginning, ending = b'<page><text>', b'</text></page>'
    h = hashlib.sha256(beginning)
    p.feed(HEADER + beginning)
    text = ('abc\u00e9\u6f22\U0001f30f&amp;'.encode()) * 2048
    size = len(beginning) + len(ending)
    for _ in range(1024):
        p.feed(text)
        h.update(text)
        size += len(text)
    h.update(ending)
    p.feed(ending + TAIL)
    summary = p.finish()
    assert len(rows) == 1 and rows[0]['SHA256'] == h.hexdigest() and rows[0]['bytes'] == size
    assert summary['max_retained_source_bytes'] < 131072
    count += 1
    failures = []
    for raw, opts in [
        (HEADER+b'<page><text>truncated', {}),
        (HEADER+b'<page></text></page>'+TAIL, {}),
        (HEADER+b'<page><text>&bad;</text></page>'+TAIL, {}),
        (b'<!DOCTYPE mediawiki SYSTEM "https://invalid.example/evil">'+HEADER, {}),
        (b'<!DOCTYPE mediawiki [<!ENTITY e "evil">]>'+HEADER, {}),
        (HEADER+b'<page xmlns="other"/>'+TAIL, {}),
        (WIRE+b'junk', {}),
        (WIRE, {'page_cap': 1}),
        (WIRE, {'decoded_cap': 100}),
        (HEADER+b'<page '+b'x'*300+b'="v"/>'+TAIL, {'token_cap': 128, 'feed_cap': 32}),
        (b'\xff\xfe<\0?\0x\0m\0l\0', {}),
        (b'<?xml version="1.0" encoding="ISO-8859-1"?>'+HEADER, {}),
    ]:
        failures.append(refused(raw, **opts))
        count += 1
    # Reuse after successful actual root closure also fails.
    try:
        p.feed(b' ')
        raise AssertionError('completed_parser_reused')
    except ValueError:
        count += 1
    return {'status': 'SYNTHETIC_RAW_XML_SPAN_CONTROLS_PASS', 'checks': count,
            'large_page_bytes': size, 'large_page_retained_source_peak': summary['max_retained_source_bytes'],
            'elapsed_seconds': time.monotonic()-start,
            'peak_RSS_platform_units': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            'hostile_cases_refused': len(failures), 'native_source_reads': 0,
            'scope': 'Original XML spans/hashes only. Not semantic parser/schema, index/group reconciliation, BZ2, archive reader, admission or production bounds.'}


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))

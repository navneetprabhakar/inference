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
    for pageparts in [[b'<page/>'], [b'<page><text/></page>'],
                      [b'<page/>', b'<page/>'], [b'<page a="quoted >"/>'],
                      [b'<page a="/>"><text/></page>', b'<page/>']]:
        wire = HEADER+b''.join(pageparts)+TAIL
        for cut in range(1, len(wire)):
            _, rows, _ = run_chunks(wire, [wire[:cut], wire[cut:]])
            assert [wire[r['start']:r['end']] for r in rows] == pageparts
            count += 1
        _, rows, _ = run_chunks(wire, (wire[i:i+1] for i in range(len(wire))))
        assert [wire[r['start']:r['end']] for r in rows] == pageparts
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
        (HEADER+b'<page>'+b'<x>'*255+b'</x>'*255+b'</page>'+TAIL, {'depth_cap': 256}),
    ]:
        failures.append(refused(raw, **opts))
        count += 1
    # Reuse after successful actual root closure also fails.
    try:
        p.feed(b' ')
        raise AssertionError('completed_parser_reused')
    except ValueError:
        count += 1
    # Exactly the finite depth boundary is valid; one level beyond is refused.
    wire = HEADER+b'<page>'+b'<x>'*254+b'</x>'*254+b'</page>'+TAIL
    _, rows, _ = run_chunks(wire, [wire], depth_cap=256)
    assert len(rows) == 1
    count += 1
    for limit in [0, -1, True, 1.5]:
        try:
            PageSpans(lambda r: None, depth_cap=limit)
            raise AssertionError('invalid_depth_limit')
        except ValueError:
            count += 1
    # Prefix calibration has its own terminal trust class, never fake closure.
    prefix = HEADER+b'<page><text>complete unit</text></page>\n'
    p = PageSpans(lambda r: None)
    for i in range(0, len(prefix), 7):
        p.feed(prefix[i:i+7])
    pre = p.finish_prefix()
    assert pre['pages'] == 1 and not pre['actual_root_closed'] and not pre['global_XML_validity']
    try:
        p.feed(TAIL)
        raise AssertionError('prefix_parser_reused')
    except ValueError:
        count += 1
    for wire in [HEADER, HEADER+b'<page><text>x', HEADER+b'<page/><pa', WIRE]:
        p = PageSpans(lambda r: None)
        p.feed(wire)
        try:
            p.finish_prefix()
            raise AssertionError('invalid_prefix_boundary')
        except ValueError:
            assert p.failed
            count += 1
    return {'status': 'SYNTHETIC_RAW_XML_SPAN_CONTROLS_PASS', 'checks': count,
            'large_page_bytes': size, 'large_page_retained_source_peak': summary['max_retained_source_bytes'],
            'elapsed_seconds': time.monotonic()-start,
            'peak_RSS_platform_units': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            'hostile_cases_refused': len(failures), 'native_source_reads': 0,
            'scope': 'Original XML spans/hashes only. Not semantic parser/schema, index/group reconciliation, BZ2, archive reader, admission or production bounds.'}


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))

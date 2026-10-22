"""Synthetic group interruption, index reconciliation and occurrence checks."""
import ast
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
from sink import Sink, SCHEMA


def page(ordinal, ident, first=91, revs=1, **changes):
    d = dict(row_ordinal=ordinal, page_id=ident, first_revision_id=first,
             namespace=0, flags=0, model_code=1, revision_count=revs,
             main_text_bytes=3, group_decoded_start=0, raw_XML_bytes=20,
             raw_SHA256=hashlib.sha256(b'synthetic-page').digest())
    d.update(changes)
    return d


def counts(path):
    with sqlite3.connect('file:'+str(path)+'?mode=ro', uri=True) as db:
        return [db.execute('SELECT COUNT(*) FROM '+t).fetchone()[0]
                for t in ['groups', 'pages', 'revisions']]


def main():
    n = 0
    # Capacity evidence applies to exactly this schema; no hidden new indexes.
    measured = Path(__file__).resolve().parents[1]/'enwiki-native-compact-SQLite-capacity-v1/measure.py'
    schema = next(ast.literal_eval(x.value) for x in ast.parse(measured.read_text()).body
                  if isinstance(x, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'SCHEMA' for t in x.targets))
    assert SCHEMA == schema
    n += 1
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        p = root/'ok.sqlite'
        s = Sink(p)
        s.begin_group(1, 10, 20, [(1, 15, 'A: caf\u00e9'), (2, 16, 'B')])
        # Same revision ID within/across pages retains every occurrence.
        s.revision(91, 1, 1)
        s.revision(91, 1, 2)
        s.page(page(1, 15, revs=2), 'A: caf\u00e9')
        s.revision(91, 2, 1)
        s.page(page(2, 16), 'B')
        assert counts(p) == [0, 0, 0]  # uncommitted group invisible
        receipt = s.end_group(100, bytes(32))
        assert receipt == dict(durable_groups=1, durable_pages=2, durable_revision_occurrences=3)
        assert counts(p) == [1, 2, 3]
        n += 3
        s.begin_group(2, 20, 30, [(3, 17, 'no revision')])
        s.page(page(3, 17, first=None, revs=0, main_text_bytes=-1), 'no revision')
        s.end_group(100, bytes(32))
        assert s.db.execute('SELECT revision_id,page_ordinal,revision_ordinal FROM revisions ORDER BY 1,2,3').fetchall() == [(91, 1, 1), (91, 1, 2), (91, 2, 1)]
        assert s.db.execute('PRAGMA integrity_check').fetchall() == [('ok',)]
        assert s.db.execute('PRAGMA foreign_key_check').fetchall() == []
        n += 3
        s.close()
        assert counts(p) == [2, 3, 3]
        try:
            Sink(p)
            raise AssertionError('partial_existing_file_reopened')
        except FileExistsError:
            n += 1
        # Interruption before group close leaves the prior durable group exact.
        for stage in ['empty', 'revision', 'page']:
            p = root/(stage+'.sqlite')
            s = Sink(p)
            s.begin_group(1, 10, 20, [(1, 15, 'A')])
            if stage in ['revision', 'page']:
                s.revision(91, 1, 1)
            if stage == 'page':
                s.page(page(1, 15), 'A')
            s.close()
            assert counts(p) == [0, 0, 0]
            n += 1
        faults = {
            'wrong_title': lambda s: s.page(page(1, 15), 'a'),
            'wrong_ID': lambda s: s.page(page(1, 99), 'A'),
            'wrong_ordinal': lambda s: s.page(page(2, 15), 'A'),
            'wrong_revision_page': lambda s: s.revision(91, 2, 1),
            'wrong_revision_order': lambda s: s.revision(91, 1, 2),
            'missing_page': lambda s: s.end_group(100, bytes(32)),
            'bad_raw_hash': lambda s: s.page(page(1, 15, raw_SHA256=b'x'), 'A'),
            'missing_revision': lambda s: s.page(page(1, 15, revs=2), 'A'),
            'bool_ID': lambda s: s.revision(True, 1, 1),
            'int64_overflow': lambda s: s.revision(2**63, 1, 1),
            'namespace_overflow': lambda s: s.page(page(1, 15, namespace=2**31), 'A'),
        }
        for name, fault in faults.items():
            p = root/(name+'.sqlite')
            s = Sink(p)
            s.begin_group(1, 10, 20, [(1, 15, 'A')])
            try:
                fault(s)
                raise AssertionError('fault_accepted_'+name)
            except ValueError:
                assert s.failed
                assert counts(p) == [0, 0, 0]
                try:
                    s.begin_group(1, 10, 20, [(1, 15, 'A')])
                    raise AssertionError('failed_sink_reused')
                except ValueError:
                    pass
                n += 1
            finally:
                s.close()
        p = root/'cap.sqlite'
        s = Sink(p, revision_cap=1)
        s.begin_group(1, 10, 20, [(1, 15, 'A')])
        s.revision(91, 1, 1)
        try:
            s.revision(92, 1, 2)
            raise AssertionError('revision_cap_exceeded')
        except ValueError:
            assert s.failed and counts(p) == [0, 0, 0]
            n += 1
        s.close()
    return {'status': 'SYNTHETIC_COMPACT_SQLITE_SINK_CONTROLS_PASS', 'checks': n,
            'schema_matches_measured': True, 'retained_native_or_index_reads': 0,
            'scope': 'Group transaction/occurrence/index identity sink only. No semantic flag coding, source parsing, supervisor/resource aggregate or publication proof.'}


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))

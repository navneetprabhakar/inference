"""Synthetic-stage compact occurrence sink; no source reader/publication.

Caller owns source/index pins, SAX schema/flag coding, resources and supervisor.
Each group is one atomic transaction; any failure makes this instance terminal.
"""
import sqlite3
from pathlib import Path

SCHEMA = '''
CREATE TABLE pages(
 row_ordinal INTEGER PRIMARY KEY, page_id INTEGER NOT NULL,
 first_revision_id INTEGER, namespace INTEGER NOT NULL, flags INTEGER NOT NULL,
 model_code INTEGER NOT NULL, revision_count INTEGER NOT NULL,
 main_text_bytes INTEGER NOT NULL, group_decoded_start INTEGER NOT NULL,
 raw_XML_bytes INTEGER NOT NULL, raw_SHA256 BLOB NOT NULL CHECK(length(raw_SHA256)=32));
CREATE TABLE groups(
 group_ordinal INTEGER PRIMARY KEY, compressed_start INTEGER NOT NULL,
 compressed_end_exclusive INTEGER NOT NULL, decoded_bytes INTEGER NOT NULL,
 first_page_ordinal INTEGER UNIQUE NOT NULL, last_page_ordinal INTEGER NOT NULL,
 page_count INTEGER NOT NULL, raw_SHA256 BLOB NOT NULL CHECK(length(raw_SHA256)=32));
CREATE TABLE revisions(
 revision_id INTEGER NOT NULL, page_ordinal INTEGER NOT NULL, revision_ordinal INTEGER NOT NULL,
 PRIMARY KEY(revision_id,page_ordinal,revision_ordinal),
 FOREIGN KEY(page_ordinal) REFERENCES pages(row_ordinal)) WITHOUT ROWID;
'''
FIELDS = ('row_ordinal', 'page_id', 'first_revision_id', 'namespace', 'flags',
          'model_code', 'revision_count', 'main_text_bytes', 'group_decoded_start',
          'raw_XML_bytes', 'raw_SHA256')


def integer(value, minimum=0, maximum=2**63-1):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError('integer_outside_declared_domain')
    return value


def digest(value):
    if type(value) is not bytes or len(value) != 32:
        raise ValueError('raw_SHA256_requires32bytes')
    return value


class Sink:
    def __init__(self, path, *, DB_cap=3800000000, max_group_pages=100, revision_cap=30000000):
        self.path = Path(path)
        integer(DB_cap, 65536)
        self.max_group_pages = integer(max_group_pages, 1, 10000)
        self.revision_cap = integer(revision_cap, 1)
        # Exclusive creation; a previous partial is never reopened as a run.
        with self.path.open('xb'):
            pass
        self.db = sqlite3.connect(self.path)
        self.closed = self.failed = False
        self.group = None
        self.pages = self.revisions = self.groups = 0
        self.previous_compressed_end = None
        for pragma in ['page_size=4096', 'max_page_count='+str(DB_cap//4096),
                       'journal_mode=MEMORY', 'synchronous=FULL',
                       'cache_size=-32768', 'temp_store=MEMORY', 'mmap_size=0',
                       'foreign_keys=ON']:
            self.db.execute('PRAGMA '+pragma)
        self.db.executescript(SCHEMA)
        self.db.commit()

    def _ready(self):
        if self.failed or self.closed:
            raise ValueError('terminal_sink')

    def _abort(self):
        self.failed = True
        self.db.rollback()

    def begin_group(self, ordinal, start, end, expected_rows):
        self._ready()
        try:
            if self.group is not None:
                raise ValueError('previous_group_not_closed')
            integer(ordinal, 1)
            integer(start)
            integer(end, start+1)
            if ordinal != self.groups+1 or (self.previous_compressed_end is not None and start != self.previous_compressed_end):
                raise ValueError('noncontiguous_group')
            if type(expected_rows) not in (tuple, list) or not 1 <= len(expected_rows) <= self.max_group_pages:
                raise ValueError('bounded_expected_group_rows_required')
            expected = []
            for i, (row_ordinal, page_id, title) in enumerate(expected_rows):
                if integer(row_ordinal, 1) != self.pages+i+1 or type(title) is not str:
                    raise ValueError('noncontiguous_index_rows_or_title')
                expected.append((row_ordinal, integer(page_id, 1), title))
            self.db.execute('BEGIN')
            self.db.execute('PRAGMA defer_foreign_keys=ON')
            self.group = {'ordinal': ordinal, 'start': start, 'end': end,
                          'expected': expected, 'seen': 0, 'revs': 0,
                          'page_revs': 0, 'first_rev': None, 'max_page_end': 0}
        except BaseException:
            self._abort()
            raise

    def revision(self, revision_id, page_ordinal, revision_ordinal):
        self._ready()
        try:
            g = self.group
            if g is None or g['seen'] >= len(g['expected']):
                raise ValueError('revision_outside_active_page')
            if integer(page_ordinal, 1) != g['expected'][g['seen']][0] or integer(revision_ordinal, 1) != g['page_revs']+1:
                raise ValueError('revision_occurrence_order')
            integer(revision_id, 1)
            if self.revisions + g['revs'] >= self.revision_cap:
                raise ValueError('revision_occurrence_cap')
            self.db.execute('INSERT INTO revisions VALUES (?,?,?)',
                            (revision_id, page_ordinal, revision_ordinal))
            if not g['page_revs']:
                g['first_rev'] = revision_id
            g['page_revs'] += 1
            g['revs'] += 1
        except BaseException:
            self._abort()
            raise

    def page(self, record, exact_title):
        self._ready()
        try:
            g = self.group
            if g is None or g['seen'] >= len(g['expected']) or set(record) != set(FIELDS):
                raise ValueError('page_outside_group_or_wrong_fields')
            expected = g['expected'][g['seen']]
            if (record['row_ordinal'], record['page_id'], exact_title) != expected:
                raise ValueError('ordered_native_index_identity_mismatch')
            for name in FIELDS[:-1]:
                if name == 'first_revision_id' and record[name] is None:
                    continue
                integer(record[name], -2**31 if name == 'namespace' else -1 if name == 'main_text_bytes' else 0)
            integer(record['namespace'], -2**31, 2**31-1)
            integer(record['flags'], 0, 2**32-1)
            integer(record['model_code'], 0, 2**32-1)
            integer(record['raw_XML_bytes'], 1)
            digest(record['raw_SHA256'])
            if record['revision_count'] != g['page_revs'] or record['first_revision_id'] != g['first_rev']:
                raise ValueError('page_revision_occurrences_disagree')
            if record['group_decoded_start'] < g['max_page_end']:
                raise ValueError('page_spans_overlap_or_reordered')
            self.db.execute('INSERT INTO pages VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                            tuple(record[f] for f in FIELDS))
            g['max_page_end'] = max(g['max_page_end'], record['group_decoded_start']+record['raw_XML_bytes'])
            g['seen'] += 1
            g['page_revs'], g['first_rev'] = 0, None
        except BaseException:
            self._abort()
            raise

    def end_group(self, decoded_bytes, raw_SHA256):
        self._ready()
        try:
            g = self.group
            integer(decoded_bytes, 1)
            digest(raw_SHA256)
            if g is None or g['seen'] != len(g['expected']) or g['page_revs'] or g['max_page_end'] > decoded_bytes:
                raise ValueError('group_coverage_or_decoded_span_incomplete')
            self.db.execute('INSERT INTO groups VALUES (?,?,?,?,?,?,?,?)',
                            (g['ordinal'], g['start'], g['end'], decoded_bytes,
                             g['expected'][0][0], g['expected'][-1][0], g['seen'], raw_SHA256))
            self.db.commit()
            self.pages += g['seen']
            self.revisions += g['revs']
            self.groups += 1
            self.previous_compressed_end = g['end']
            self.group = None
            return {'durable_groups': self.groups, 'durable_pages': self.pages,
                    'durable_revision_occurrences': self.revisions}
        except BaseException:
            self._abort()
            raise

    def close(self):
        if self.closed:
            return
        if self.group is not None:
            self._abort()
        self.db.close()
        self.closed = True

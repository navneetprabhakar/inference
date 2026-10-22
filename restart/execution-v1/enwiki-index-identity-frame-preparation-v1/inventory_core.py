"""On-disk unique ID inventory through the frozen strict index assessor."""
import hashlib
import json
import sqlite3
from pathlib import Path

DB_BYTES = 3800000000
BATCH = 500


class Store:
    def __init__(self, path, *, db_cap=DB_BYTES, batch=BATCH):
        self.path = Path(path)
        if self.path.exists() or self.path.is_symlink():
            raise ValueError('existing_database_refused')
        self.db = sqlite3.connect(self.path)
        self.batch = batch
        self.rows = self.groups = self.committed = 0
        self.offset = self.first = self.group_rows = None
        self.db.execute('PRAGMA page_size=4096')
        self.db.execute('PRAGMA max_page_count=%d' % (db_cap // 4096))
        self.db.execute('PRAGMA journal_mode=MEMORY')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('PRAGMA cache_size=-32768')
        self.db.execute('PRAGMA temp_store=MEMORY')
        self.db.execute('PRAGMA mmap_size=0')
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''
        CREATE TABLE groups(group_ordinal INTEGER PRIMARY KEY, block_start INTEGER UNIQUE NOT NULL,
          block_end_exclusive INTEGER, first_row INTEGER NOT NULL, last_row INTEGER, row_count INTEGER);
        CREATE TABLE rows(row_ordinal INTEGER PRIMARY KEY, page_id INTEGER UNIQUE NOT NULL,
          group_ordinal INTEGER NOT NULL, title TEXT NOT NULL, raw_line_sha256 BLOB NOT NULL,
          raw_line_bytes INTEGER NOT NULL, line_ends_LF INTEGER NOT NULL,
          noncanonical_offset_ascii TEXT, noncanonical_page_ascii TEXT,
          FOREIGN KEY(group_ordinal) REFERENCES groups(group_ordinal));
        CREATE TABLE provenance(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        ''')
        self.db.commit()

    def end_group(self, end):
        if self.offset is None:
            return
        if end <= self.offset:
            raise ValueError('nonpositive_offset_group_range')
        self.db.execute('UPDATE groups SET block_end_exclusive=?,last_row=?,row_count=? WHERE group_ordinal=?',
                        (end, self.rows, self.group_rows, self.groups))

    def emit(self, raw, record):
        offset = record['compressed_XML_block_start']
        if self.offset is not None and offset < self.offset:
            raise ValueError('nonmonotonic_offsets_before_SQL_insert')
        if offset != self.offset:
            self.end_group(offset)
            self.groups += 1
            self.first = self.rows + 1
            self.group_rows = 0
            self.offset = offset
            self.db.execute('INSERT INTO groups(group_ordinal,block_start,first_row) VALUES (?,?,?)',
                            (self.groups, offset, self.first))
        if record['row_ordinal'] != self.rows + 1:
            raise ValueError('exact_one_based_row_ordinal')
        # Numeric lexemes are retained iff they differ from canonical decimal.
        # LF flag and UTF8 title reconstruct every original source line exactly.
        a = record['exact_offset_field_ascii']
        b = record['exact_page_ID_field_ascii']
        reconstructed = (a + ':' + b + ':' + record['title_observed']).encode('utf8') + (b'\n' if record['line_ends_LF'] else b'')
        if reconstructed != raw or hashlib.sha256(reconstructed).hexdigest() != record['raw_line_sha256']:
            raise ValueError('lossless_raw_line_reconstruction')
        self.db.execute('INSERT INTO rows VALUES (?,?,?,?,?,?,?,?,?)',
                        (record['row_ordinal'], record['page_ID_observed'], self.groups,
                         record['title_observed'], bytes.fromhex(record['raw_line_sha256']), len(raw),
                         int(record['line_ends_LF']), a if a != str(offset) else None,
                         b if b != str(record['page_ID_observed']) else None))
        self.rows += 1
        self.group_rows += 1
        if self.rows % self.batch == 0:
            self.db.commit()
            self.committed = self.rows

    def finish(self, end, result, expected):
        self.end_group(end)
        stats = result['stats']
        for key in ['rows', 'offset_groups', 'decoded_bytes', 'compressed_bytes', 'bzip2_members', 'unterminated_final_rows', 'empty_titles']:
            if stats[key] != expected[key]:
                raise ValueError('exact_prior_index_receipt_reconciliation:' + key)
        if self.rows != expected['rows'] or self.groups != expected['offset_groups']:
            raise ValueError('all_rows_groups_SQL_reconciliation')
        for key, value in {'source_SHA256': result['source_SHA256'], 'source_MD5': result['source_MD5'],
                           'source_SHA1': result['source_SHA1'], 'source_stats': stats,
                           'global_page_ID_uniqueness_proven': True,
                           'schema': 'lossless-index-identity-frame-v1'}.items():
            self.db.execute('INSERT INTO provenance VALUES (?,?)', (key, json.dumps(value)))
        self.db.commit()
        self.committed = self.rows
        if self.db.execute('SELECT COUNT(*),MIN(row_ordinal),MAX(row_ordinal) FROM rows').fetchone() != (expected['rows'], 1, expected['rows']):
            raise ValueError('SQL_exact_row_coverage')
        if self.db.execute('SELECT COUNT(*) FROM groups WHERE block_end_exclusive IS NULL OR last_row IS NULL OR row_count IS NULL').fetchone()[0]:
            raise ValueError('unclosed_SQL_offset_group')
        if self.db.execute('SELECT COUNT(*),SUM(row_count) FROM groups').fetchone() != (expected['offset_groups'], expected['rows']):
            raise ValueError('SQL_group_row_sum')
        if self.db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('SQLite_group_foreign_key_integrity')
        if self.db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
            raise ValueError('SQLite_integrity_check')

    def close(self):
        self.db.close()


def build(source, assessor, store, spec, check=lambda: None, progress=None):
    original_parse = assessor.parse
    def emit(raw, ordinal, xmlsize):
        record = original_parse(raw, ordinal, xmlsize)
        store.emit(raw, record)
        return record
    assessor.parse = emit
    caps = dict(assessor.CAPS)
    caps.update(decoded_bytes=spec['stats']['decoded_bytes'], rows=spec['stats']['rows'],
                sample_rows=1, line_bytes=spec['stats']['maximum_line_bytes'],
                group_rows=spec['stats']['maximum_group_rows'], group_raw_bytes=spec['stats']['maximum_group_raw_bytes'],
                worker_seconds=1200, external_seconds=1260)
    try:
        result = assessor.assess(source, spec['SHA256'], spec['MD5'], spec['SHA1'], spec['bytes'],
                                 spec['XML_bytes'], 'identity-inventory-no-new-sample', caps=caps,
                                 check=check, progress=progress)
        store.finish(spec['XML_bytes'], result, spec['stats'])
        result.pop('samples')  # Internal bounded assessor compatibility, not a new discovery cohort.
        result['global_page_ID_uniqueness_proven'] = True
        result['SQLite_rows'] = store.rows
        result['SQLite_groups'] = store.groups
        return result
    finally:
        assessor.parse = original_parse

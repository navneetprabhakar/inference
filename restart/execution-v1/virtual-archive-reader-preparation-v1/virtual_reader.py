"""Pinned COMPLETE-publication reader; bounded reads, no copy or implicit rehash."""
import bisect
import hashlib
import io
import json
import os
import stat
from pathlib import Path

MAX_READ = 1048576
MAX_METADATA = 1048576
MAX_COMPONENTS = 128
NAMES = ('virtual-archive-manifest.json', 'supervisor-result.json', 'worker-result.json')


def identity(st):
    return [st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns]


def digest(value, length=64):
    return isinstance(value, str) and len(value) == length and all(c in '0123456789abcdef' for c in value)


def plain_path(value):
    p = Path(value)
    if not p.is_absolute() or str(p) != str(value) or '..' in p.parts:
        raise ValueError('canonical_absolute_path_required')
    if any(q.is_symlink() for q in [p, *p.parents]):
        raise ValueError('symlink_path_refused')
    return p


def exact_object(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise ValueError('duplicate_JSON_key')
        result[k] = v
    return result


def metadata(path, expected):
    if not digest(expected):
        raise ValueError('external_publication_metadata_digest_required')
    p = plain_path(path)
    source_stat = p.stat()
    if not stat.S_ISREG(source_stat.st_mode):
        raise ValueError('regular_metadata_file_required')
    before = identity(source_stat)
    if before[2] > MAX_METADATA:
        raise ValueError('metadata_byte_cap')
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        if identity(os.fstat(fd)) != before:
            raise ValueError('metadata_descriptor_identity')
        raw = os.read(fd, MAX_METADATA + 1)
        if len(raw) != before[2] or os.read(fd, 1):
            raise ValueError('metadata_length')
        if identity(os.fstat(fd)) != before or identity(p.stat()) != before:
            raise ValueError('metadata_mutated')
    finally:
        os.close(fd)
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('external_publication_metadata_hash')
    return json.loads(raw, object_pairs_hook=exact_object), (p, before)


class VirtualArchive(io.RawIOBase):
    """Read-only file interface over externally pinned publication and components.

    Caller supplies frozen publication hashes and exact expected ordered path/size
    pairs. Per-component hashes are retained provenance, NOT implicitly rehashed.
    File descriptors/stat identities are checked on access and every seek/close.
    This is not a bz2/XML validator or a checksum substitute for the publisher.
    One reader instance is single-consumer, not thread safe.
    """

    def __init__(self, directory, publication_pins, expected, *, max_read=MAX_READ):
        super().__init__()
        self._fds = []
        self._components = []
        self._metadata = []
        self._position = 0
        self._starts = []
        if type(max_read) is not int or not 1 <= max_read <= MAX_READ:
            raise ValueError('bounded_positive_read_cap')
        self.max_read = max_read
        try:
            if set(publication_pins) != set(NAMES):
                raise ValueError('exact_three_external_publication_pins')
            directory = plain_path(directory)
            records = {}
            for name in NAMES:
                records[name], pin = metadata(directory / name, publication_pins[name])
                self._metadata.append(pin)
            m, s, w = (records[n] for n in NAMES)
            if set(expected) != {'URL', 'bytes', 'publisher_MD5', 'publisher_SHA1', 'components'}:
                raise ValueError('exact_expected_source_contract')
            if type(expected['bytes']) is not int or expected['bytes'] <= 0 or not digest(expected['publisher_MD5'], 32) or not digest(expected['publisher_SHA1'], 40):
                raise ValueError('expected_publisher_identity')
            if m['status'] != 'COMPLETE_VIRTUAL_ARCHIVE_WORKER_AND_INDEPENDENT_SUPERVISOR_VERIFIED' or s['status'] != 'COMPLETE_VIRTUAL_ARCHIVE_NO_ADMISSION' or w['status'] != 'COMPLETE_WORKER_VIRTUAL_CHECKSUMS_PENDING_INDEPENDENT_PUBLICATION':
                raise ValueError('complete_publication_only_no_candidate_or_partial')
            for key in ['URL', 'bytes', 'publisher_MD5', 'publisher_SHA1']:
                if m[key] != expected[key]:
                    raise ValueError('frozen_publisher_identity:' + key)
            if not digest(m['local_SHA256']) or m['no_concatenated_full_file_created'] is not True or m['no_decompression_or_usable_data_claim'] is not True:
                raise ValueError('publication_scope')
            if type(s['coordinator_exit_code']) is not int or s['coordinator_exit_code'] != 0 or s['coordinator_reaped'] is not True or s['all_charges_preserved'] is not True or s['virtual_manifest_SHA256'] != publication_pins[NAMES[0]]:
                raise ValueError('supervisor_publication_binding')
            if m['worker_receipt_SHA256'] != publication_pins[NAMES[2]]:
                raise ValueError('manifest_worker_binding')
            whole = {'bytes': m['bytes'], 'MD5': m['publisher_MD5'], 'SHA1': m['publisher_SHA1'], 'SHA256': m['local_SHA256']}
            if s['independent_checksums'] != whole or {'bytes': w['virtual_bytes'], **{k: w[k] for k in ['MD5', 'SHA1', 'SHA256']}} != whole:
                raise ValueError('two_independent_publication_checksum_receipts')
            components = m['ordered_components']
            if any(type(w[k]) is not int for k in ['parts', 'response_bytes', 'body_reserved', 'virtual_bytes']) or not 2 <= len(components) <= MAX_COMPONENTS or len(expected['components']) != len(components) or w['parts'] != len(components) - 1:
                raise ValueError('bounded_component_count')
            if w['response_bytes'] != sum(e['bytes'] for e in components[1:]) or w['body_reserved'] != w['response_bytes'] + w['parts']:
                raise ValueError('worker_tail_byte_reconciliation')
            count = 0
            paths = set()
            for e, allowed in zip(components, expected['components']):
                if set(e) != {'path', 'bytes', 'SHA256', 'stat'} or set(allowed) != {'path', 'bytes'} or (e['path'], e['bytes']) != (allowed['path'], allowed['bytes']):
                    raise ValueError('exact_ordered_component_path_length')
                if type(e['bytes']) is not int or e['bytes'] <= 0 or not digest(e['SHA256']) or len(e['stat']) != 5 or any(type(v) is not int or v < 0 for v in e['stat']) or e['stat'][2] != e['bytes']:
                    raise ValueError('component_receipt_schema')
                p = plain_path(e['path'])
                if p in paths:
                    raise ValueError('duplicate_component_path')
                paths.add(p)
                if not stat.S_ISREG(p.stat().st_mode):
                    raise ValueError('regular_component_file_required')
                self._starts.append(count)
                fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                self._fds.append(fd)
                self._components.append(dict(e))
                self._check_component(len(self._fds) - 1)
                count += e['bytes']
            if count != expected['bytes']:
                raise ValueError('component_total_reconciliation')
            self.length = count
            self.publication_SHA256 = publication_pins[NAMES[0]]
            self.publisher_verified_by_producer = whole
            self.component_hashes_not_recomputed_by_reader = True
            self._check_all()
        except BaseException:
            for fd in self._fds:
                os.close(fd)
            self._fds = []
            super().close()
            raise

    def _check_metadata(self):
        for p, st in self._metadata:
            if plain_path(p) != p or identity(p.stat()) != st:
                raise ValueError('publication_metadata_mutated')

    def _check_component(self, i):
        e = self._components[i]
        p = plain_path(e['path'])
        if not stat.S_ISREG(os.fstat(self._fds[i]).st_mode) or identity(os.fstat(self._fds[i])) != e['stat'] or identity(p.stat()) != e['stat']:
            raise ValueError('component_descriptor_or_path_mutated')

    def _check_all(self):
        self._check_metadata()
        for i in range(len(self._fds)):
            self._check_component(i)

    def readable(self):
        return not self.closed

    def seekable(self):
        return not self.closed

    def writable(self):
        return False

    def tell(self):
        self._checkClosed()
        self._check_metadata()
        return self._position

    def seek(self, offset, whence=os.SEEK_SET):
        self._checkClosed()
        if type(offset) is not int or type(whence) is not int or whence not in (0, 1, 2):
            raise ValueError('integer_seek_and_valid_whence_required')
        target = offset + (0 if whence == 0 else self._position if whence == 1 else self.length)
        if not 0 <= target <= self.length:
            raise ValueError('seek_outside_virtual_archive')
        self._check_all()
        self._position = target
        return target

    def read(self, size=-1):
        self._checkClosed()
        if type(size) is not int or not 0 <= size <= self.max_read:
            raise ValueError('explicit_bounded_nonnegative_read_required')
        self._check_metadata()
        left = min(size, self.length - self._position)
        if not left:
            self._check_all()
            return b''
        result = []
        while left:
            i = bisect.bisect_right(self._starts, self._position) - 1
            self._check_component(i)
            within = self._position - self._starts[i]
            n = min(left, self._components[i]['bytes'] - within)
            raw = os.pread(self._fds[i], n, within)
            if len(raw) != n:
                raise ValueError('short_component_read')
            self._check_component(i)
            result.append(raw)
            self._position += n
            left -= n
        return b''.join(result)

    def readinto(self, buffer):
        view = memoryview(buffer).cast('B')
        if view.readonly:
            raise ValueError('writable_readinto_buffer_required')
        data = self.read(len(view))
        view[:len(data)] = data
        return len(data)

    def close(self):
        if self.closed:
            return
        try:
            self._check_all()
        finally:
            for fd in self._fds:
                os.close(fd)
            self._fds = []
            super().close()

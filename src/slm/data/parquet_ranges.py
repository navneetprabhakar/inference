"""Pinned, finite public Parquet range reads. Acquisition is never admission.

Declared uncompressed limits are checked before decoding; actual table size is
checked afterwards. This is not a hostile-codec sandbox or a hard RSS bound.
"""
# Creator: Navneet Prabhakar
from dataclasses import dataclass
import hashlib
import io
import re
import urllib.error
import urllib.request

import pyarrow as pa
import pyarrow.parquet as pq


@dataclass(frozen=True)
class Limits:
    network_bytes: int = 16 * 1024**2
    requests: int = 8
    footer_bytes: int = 4 * 1024**2
    group_compressed_bytes: int = 8 * 1024**2
    group_declared_uncompressed_bytes: int = 32 * 1024**2
    group_decoded_bytes: int = 32 * 1024**2
    group_rows: int = 1000

    def __post_init__(self):
        if any(type(value) is not int or value <= 0 for value in vars(self).values()):
            raise ValueError('Positive integer limits required')


class ExactRanges:
    """No retry/fallback; precharge each request including one overread byte.

    The caller binds URL, file size and strong entity tag to a pinned inventory.
    Receipts intentionally omit redirect URLs and authorization headers.
    """
    def __init__(self, url, size, etag, limits=Limits(), opener=None):
        if not url.startswith('https://') or type(size) is not int or size < 12:
            raise ValueError('HTTPS URL and valid file size required')
        if not re.fullmatch(r'"[A-Za-z0-9_-]+"', etag):
            raise ValueError('Explicit strong entity tag required')
        self.url, self.size, self.etag, self.limits = url, size, etag, limits
        self.opener = opener or urllib.request.urlopen
        self.reserved_bytes = 0
        self.attempts = 0
        self.receipts = []

    def get(self, start, length):
        if type(start) is not int or type(length) is not int or start < 0 or length < 1 or start + length > self.size:
            raise ValueError('Invalid byte range')
        if self.attempts >= self.limits.requests or self.reserved_bytes + length + 1 > self.limits.network_bytes:
            raise ValueError('Finite request/byte budget exhausted')
        self.attempts += 1
        self.reserved_bytes += length + 1
        request = urllib.request.Request(self.url, headers={
            'Range': f'bytes={start}-{start + length - 1}', 'If-Match': self.etag,
            'Accept-Encoding': 'identity', 'User-Agent': 'portable-slm-bounded-parquet/1'})
        try:
            with self.opener(request, timeout=45) as response:
                if response.status != 206:
                    raise ValueError('Server did not honor exact range')
                headers = response.headers
                if headers.get('Content-Range') != f'bytes {start}-{start + length - 1}/{self.size}':
                    raise ValueError('Content range differs')
                if headers.get('ETag') != self.etag:
                    raise ValueError('Pinned entity tag differs')
                if headers.get('Content-Encoding', 'identity') != 'identity':
                    raise ValueError('Encoded range response refused')
                if headers.get('Content-Length') not in (None, str(length)):
                    raise ValueError('Response length header differs')
                raw = response.read(length + 1)
                if len(raw) != length:
                    raise ValueError('Truncated or excessive range body')
        except (urllib.error.URLError, TimeoutError, OSError):
            # urllib errors can include a temporary signed redirect URL.
            raise ValueError('Public range transport failed; no automatic retry') from None
        self.receipts.append(dict(start=start, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
        return raw


class CoveredFile(io.RawIOBase):
    """Seekable view of retained intervals; a gap never causes a network read."""
    def __init__(self, size, segments):
        super().__init__()
        self.size, self.position = size, 0
        self.segments = sorted(segments)
        end = 0
        for start, raw in self.segments:
            if start < end or start < 0 or start + len(raw) > size:
                raise ValueError('Overlapping/out-of-bounds retained intervals')
            end = start + len(raw)

    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self.position

    def seek(self, offset, whence=0):
        base = (0, self.position, self.size)[whence] if whence in (0, 1, 2) else None
        if base is None or not 0 <= base + offset <= self.size:
            raise ValueError('Invalid seek')
        self.position = base + offset
        return self.position

    def read(self, size=-1):
        stop = self.size if size is None or size < 0 else min(self.size, self.position + size)
        cursor, pieces = self.position, []
        for start, raw in self.segments:
            if cursor >= stop: break
            if start <= cursor < start + len(raw):
                end = min(stop, start + len(raw))
                pieces.append(raw[cursor - start:end - start])
                cursor = end
        if cursor != stop:
            raise ValueError('Parquet requested an unretained byte interval')
        self.position = stop
        return b''.join(pieces)


class BoundedParquet:
    def __init__(self, transport):
        self.transport = transport
        self.completed_groups = set()
        self.header = transport.get(0, 4)
        tail = transport.get(transport.size - 8, 8)
        if self.header != b'PAR1' or tail[-4:] != b'PAR1':
            raise ValueError('Parquet magic differs')
        n = int.from_bytes(tail[:4], 'little')
        if not 0 < n <= transport.limits.footer_bytes or n + 12 > transport.size:
            raise ValueError('Footer exceeds bounded metadata scope')
        self.footer_start = transport.size - 8 - n
        self.footer = transport.get(self.footer_start, n) + tail
        self.metadata = pq.ParquetFile(pa.BufferReader(self.header + self.footer),
                                      thrift_string_size_limit=8 * 1024**2,
                                      thrift_container_size_limit=1000000).metadata

    def read_group(self, index):
        if type(index) is not int or not 0 <= index < self.metadata.num_row_groups:
            raise ValueError('Invalid row-group index')
        if index in self.completed_groups:
            raise ValueError('Repeated row-group extraction refused')
        group = self.metadata.row_group(index)
        columns = [group.column(i) for i in range(group.num_columns)]
        if not columns or group.num_rows > self.transport.limits.group_rows:
            raise ValueError('Row-group count exceeds scope')
        uncompressed = sum(c.total_uncompressed_size for c in columns)
        if uncompressed < 0 or uncompressed > self.transport.limits.group_declared_uncompressed_bytes:
            raise ValueError('Declared row-group decoded size exceeds scope')
        spans = []
        for c in columns:
            if c.file_path or c.total_uncompressed_size < 0:
                raise ValueError('External or invalid column payload refused')
            start = c.dictionary_page_offset if c.has_dictionary_page else c.data_page_offset
            length = c.total_compressed_size
            if start < 4 or length <= 0 or start + length > self.footer_start:
                raise ValueError('Column payload outside allowed file body')
            spans.append((start, start + length))
        start, stop = min(s for s, _ in spans), max(e for _, e in spans)
        if stop - start > self.transport.limits.group_compressed_bytes:
            raise ValueError('Compressed row-group interval exceeds scope')
        raw = self.transport.get(start, stop - start)
        # Record before decode; failure does not silently enable repeated work.
        self.completed_groups.add(index)
        view = CoveredFile(self.transport.size, [(0, self.header), (start, raw), (self.footer_start, self.footer)])
        reader = pq.ParquetFile(view, metadata=self.metadata, pre_buffer=False,
                                thrift_string_size_limit=8 * 1024**2,
                                thrift_container_size_limit=1000000)
        table = reader.read_row_group(index, use_threads=False)
        if table.num_rows != group.num_rows or table.nbytes > self.transport.limits.group_decoded_bytes:
            raise ValueError('Actual decoded table exceeds scope or row count differs')
        return table

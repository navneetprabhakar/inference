"""Immutable prepacked rows for nanochat, with an exact, finite reader cursor.

The producer supplies T+1 rows (e.g. from pinned upstream BOS best-fit packing).
This module does not change packing, train a tokenizer, or admit a corpus. It
separates data order from asynchronous model execution: checkpoint the reader
state BEFORE fetching a batch if that batch has not yet been optimized.
"""
from __future__ import annotations

import argparse
import array
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Iterable


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _hash(value: str) -> bool:
    return isinstance(value, str) and bool(re.fullmatch('[0-9a-f]{64}', value))


def write_rows(directory: str | Path, rows: Iterable[Iterable[int]], *,
               sequence_length: int, vocab_size: int, tokenizer_sha256: str,
               split: str, source_manifest_sha256: str, packing: str,
               max_rows: int) -> dict:
    """Write a bounded immutable dataset; manifests publish only complete data.

    max_rows bounds accidental infinite upstream iterators. Caller is responsible
    for detecting source epoch wrap and accounting unique exposure/cropped tokens.
    Existing destinations are refused. A failed write leaves no admitted manifest.
    """
    if not 0 < sequence_length or not 1 < vocab_size <= 65536:
        raise ValueError('invalid sequence length/vocabulary')
    if split not in ('train', 'validation', 'test') or max_rows <= 0:
        raise ValueError('invalid split/row limit')
    if not _hash(tokenizer_sha256) or not _hash(source_manifest_sha256) or not packing:
        raise ValueError('tokenizer/source hashes and packing identity required')
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    part = directory / 'rows.u16.partial'
    count = 0
    try:
        with part.open('xb') as f:
            for row in rows:
                row = list(row)
                if len(row) != sequence_length + 1:
                    raise ValueError('row must contain exactly T+1 tokens')
                if any(type(t) is not int or not 0 <= t < vocab_size for t in row):
                    raise ValueError('token out of vocabulary or non-integer')
                values = array.array('H', row)
                if sys.byteorder != 'little':
                    values.byteswap()
                f.write(values.tobytes())
                count += 1
                if count == max_rows:
                    break
            f.flush()
            os.fsync(f.fileno())
        if not count:
            raise ValueError('empty dataset')
        final = directory / 'rows.u16'
        os.replace(part, final)
        manifest = dict(schema=1, format='uint16-le-fixed-T-plus-1',
                        file=final.name, sha256=sha256_file(final),
                        sequence_length=sequence_length, vocab_size=vocab_size,
                        tokenizer_sha256=tokenizer_sha256, split=split,
                        source_manifest_sha256=source_manifest_sha256,
                        packing=packing, rows=count, target_tokens=count*sequence_length,
                        bytes=final.stat().st_size,
                        training_admitted=False,
                        admission_note='Integrity only; source/license/leakage/packing admission required separately.')
        temp = directory / 'manifest.json.partial'
        with temp.open('x') as f:
            json.dump(manifest, f, indent=2)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, directory / 'manifest.json')
        return manifest
    except BaseException:
        part.unlink(missing_ok=True)
        raise


class PackedRows:
    """Finite sequential reader. No shuffle, hidden prefetch, wrap or padding."""
    def __init__(self, directory: str | Path, *, expected_tokenizer_sha256: str,
                 expected_split: str, verify_hash: bool = True):
        self.directory = Path(directory)
        manifest_path = self.directory / 'manifest.json'
        self.manifest_sha256 = sha256_file(manifest_path)
        self.manifest = json.loads(manifest_path.read_text())
        m = self.manifest
        if m.get('schema') != 1 or m.get('format') != 'uint16-le-fixed-T-plus-1':
            raise ValueError('unknown dataset format')
        if m.get('file') != 'rows.u16':
            raise ValueError('unexpected data path')
        if m.get('tokenizer_sha256') != expected_tokenizer_sha256 or not _hash(expected_tokenizer_sha256):
            raise ValueError('tokenizer mismatch')
        if m.get('split') != expected_split:
            raise ValueError('split mismatch')
        self.row_bytes = (m['sequence_length'] + 1)*2
        if m['rows'] <= 0 or m['bytes'] != self.row_bytes*m['rows']:
            raise ValueError('invalid row dimensions')
        self.path = self.directory / m['file']
        if self.path.stat().st_size != m['bytes']:
            raise ValueError('truncated or extended data file')
        if verify_hash and sha256_file(self.path) != m['sha256']:
            raise ValueError('corrupt data file')
        self.next_row = 0

    def state_dict(self) -> dict:
        return dict(schema=1, manifest_sha256=self.manifest_sha256, next_row=self.next_row)

    def load_state_dict(self, state: dict) -> None:
        if state.get('schema') != 1 or state.get('manifest_sha256') != self.manifest_sha256:
            raise ValueError('cursor belongs to a different dataset')
        row = state.get('next_row')
        if type(row) is not int or not 0 <= row <= self.manifest['rows']:
            raise ValueError('invalid cursor')
        self.next_row = row

    def read(self, batch_rows: int) -> tuple[list[list[int]], list[list[int]]]:
        if type(batch_rows) is not int or batch_rows <= 0:
            raise ValueError('batch_rows must be positive')
        if self.next_row + batch_rows > self.manifest['rows']:
            raise StopIteration('insufficient rows; automatic replay prohibited')
        with self.path.open('rb') as f:
            f.seek(self.next_row*self.row_bytes)
            raw = f.read(batch_rows*self.row_bytes)
        if len(raw) != batch_rows*self.row_bytes:
            raise ValueError('dataset changed after validation')
        values = array.array('H')
        values.frombytes(raw)
        if sys.byteorder != 'little':
            values.byteswap()
        width = self.manifest['sequence_length']+1
        rows = [values[i*width:(i+1)*width].tolist() for i in range(batch_rows)]
        self.next_row += batch_rows
        return [r[:-1] for r in rows], [r[1:] for r in rows]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory')
    parser.add_argument('--tokenizer-sha256', required=True)
    parser.add_argument('--split', choices=['train','validation','test'], required=True)
    args = parser.parse_args()
    reader = PackedRows(args.directory, expected_tokenizer_sha256=args.tokenizer_sha256,
                        expected_split=args.split)
    print(json.dumps(dict(integrity_verified=True, **reader.manifest), indent=2))


if __name__ == '__main__':
    main()

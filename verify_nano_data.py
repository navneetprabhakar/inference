"""Checks actual restart semantics and fail-closed data integrity."""
import json
from pathlib import Path
import tempfile
import unittest
from cloud_training.nano_data import PackedRows, write_rows

TOKENIZER = 'a'*64
SOURCE = 'b'*64

class DataTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def make(self, name='data', rows=None):
        target = self.root/name
        write_rows(target, rows if rows is not None else [[0,1,2,3],[4,5,6,7],[8,9,10,11]],
                   sequence_length=3, vocab_size=32, tokenizer_sha256=TOKENIZER,
                   split='train', source_manifest_sha256=SOURCE,
                   packing='test-fixture', max_rows=3)
        return target

    def reader(self, path):
        return PackedRows(path, expected_tokenizer_sha256=TOKENIZER, expected_split='train')

    def test_exact_restart_after_consumed_batch_and_before_prefetch(self):
        path=self.make(); r=self.reader(path)
        self.assertEqual(r.read(1), ([[0,1,2]], [[1,2,3]]))
        consumed = r.state_dict()
        expected = r.read(2)
        restored=self.reader(path);restored.load_state_dict(consumed)
        self.assertEqual(restored.read(2), expected)
        with self.assertRaises(StopIteration): restored.read(1)
        self.assertEqual(restored.state_dict()['next_row'],3)

    def test_no_partial_batch_or_wrap(self):
        r=self.reader(self.make());r.read(2)
        with self.assertRaises(StopIteration):r.read(2)
        self.assertEqual(r.state_dict()['next_row'],2)
        self.assertEqual(r.read(1)[0],[[8,9,10]])

    def test_reject_corruption_and_wrong_tokenizer(self):
        path=self.make()
        with self.assertRaises(ValueError):
            PackedRows(path,expected_tokenizer_sha256='c'*64,expected_split='train')
        with self.assertRaises(ValueError):
            PackedRows(path,expected_tokenizer_sha256=TOKENIZER,expected_split='validation')
        with (path/'rows.u16').open('r+b') as f:f.write(b'\x03\x00')
        with self.assertRaises(ValueError):self.reader(path)

    def test_foreign_cursor_rejected(self):
        first=self.reader(self.make())
        second=self.reader(self.make('different',[[1,2,3,4]]))
        with self.assertRaises(ValueError):second.load_state_dict(first.state_dict())
        with self.assertRaises(ValueError):first.load_state_dict(dict(first.state_dict(),next_row=-1))

    def test_invalid_rows_never_publish_manifest(self):
        for i, rows in enumerate(([[1,2]], [[1,2,3,32]], [[1,2,3,True]], [])):
            path=self.root/str(i)
            with self.assertRaises(ValueError):self.make(str(i),rows)
            self.assertFalse((path/'manifest.json').exists())

    def test_finite_writer_and_no_overwrite(self):
        path=self.make()
        with self.assertRaises(FileExistsError):self.make()
        m=json.loads((path/'manifest.json').read_text())
        self.assertEqual(m['target_tokens'],9)
        self.assertFalse(m['training_admitted'])

if __name__=='__main__':unittest.main()

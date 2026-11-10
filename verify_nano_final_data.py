import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from cloud_training.nano_final_data import download_resume,full_fit_texts,EXCLUDED

class Response(io.BytesIO):
    def __init__(self,data,status,headers):super().__init__(data);self.status=status;self.headers=headers

class FinalDataTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
    def test_resume_range_preserves_prefix_and_counts_only_new(self):
        p=self.root/'file.parquet';p.with_suffix('.parquet.partial').write_bytes(b'ab')
        ledger={'transferred_bytes':2}
        def open_(request,timeout):
            self.assertEqual(request.get_header('Range'),'bytes=2-')
            return Response(b'cde',206,{'Content-Range':'bytes 2-4/5','Content-Length':'3'})
        result=download_resume('https://example.test/file',p,ledger,self.root/'ledger.json',opener=open_,guard=lambda _:None)
        self.assertEqual(p.read_bytes(),b'abcde');self.assertEqual(ledger['transferred_bytes'],5)
        self.assertEqual(result['bytes'],5)
    def test_slow_transfer_keeps_accounted_partial_for_resume(self):
        p=self.root/'file';ledger={'transferred_bytes':0}
        with patch('cloud_training.nano_final_data.time.monotonic',side_effect=[0,60]):
            with self.assertRaises(TimeoutError):
                download_resume('https://example.test/file',p,ledger,self.root/'ledger.json',opener=lambda *a,**k:Response(b'ab',200,{'Content-Length':'3'}),guard=lambda _:None,minimum_rate=100,rate_grace_seconds=45)
        self.assertEqual(ledger['transferred_bytes'],2)
        self.assertEqual(p.with_suffix('.partial').read_bytes(),b'ab')
        self.assertFalse(p.exists())
    def test_ignored_range_does_not_corrupt_partial(self):
        p=self.root/'file';p.with_suffix('.partial').write_bytes(b'ab')
        with self.assertRaises(RuntimeError):
            download_resume('https://example.test/file',p,{},self.root/'ledger.json',opener=lambda *a,**k:Response(b'abc',200,{}),guard=lambda _:None)
        self.assertEqual(p.with_suffix('.partial').read_bytes(),b'ab');self.assertFalse(p.exists())
    def test_partial_range_is_not_mistaken_for_complete_file(self):
        p=self.root/'file';p.with_suffix('.partial').write_bytes(b'ab')
        with self.assertRaises(RuntimeError):
            download_resume('https://example.test/file',p,{},self.root/'ledger.json',opener=lambda *a,**k:Response(b'cd',206,{'Content-Range':'bytes 2-3/9','Content-Length':'2'}),guard=lambda _:None)
        self.assertEqual(p.with_suffix('.partial').read_bytes(),b'ab');self.assertFalse(p.exists())
    def test_truncated_download_never_publishes(self):
        p=self.root/'file'
        with self.assertRaises(RuntimeError):
            download_resume('https://example.test/file',p,{},self.root/'ledger.json',opener=lambda *a,**k:Response(b'ab',200,{'Content-Length':'3'}),guard=lambda _:None)
        self.assertFalse(p.exists());self.assertEqual(p.with_suffix('.partial').read_bytes(),b'ab')
    def test_budget_stops_without_overrun(self):
        p=self.root/'file';ledger={'transferred_bytes':0}
        with patch('cloud_training.nano_final_data.MAX_DOWNLOAD',2):
            with self.assertRaises(RuntimeError):download_resume('https://example.test/file',p,ledger,self.root/'ledger.json',opener=lambda *a,**k:Response(b'abc',200,{}),guard=lambda _:None)
        self.assertEqual(ledger['transferred_bytes'],2);self.assertFalse(p.exists())
    def test_pinned_tokenizer_iterator_strict_greater_and_doc_cap(self):
        import pyarrow as pa
        import pyarrow.parquet as pq
        p=self.root/'input.parquet';pq.write_table(pa.table({'text':['abcde','fghij','k'*20000]}),p)
        stats={};self.assertEqual(list(full_fit_texts([p],stats,target_chars=5)),['abcde','fghij'])
        self.assertEqual(stats['characters'],10)
        stats={}
        self.assertEqual([len(x) for x in full_fit_texts([p],stats,target_chars=10000)],[5,5,10000])
        with self.assertRaises(RuntimeError):list(full_fit_texts([p],{},target_chars=20000))
    def test_split_excludes_benchmark_and_final_holdout(self):self.assertEqual(EXCLUDED,{1,6542})

if __name__=='__main__':unittest.main()

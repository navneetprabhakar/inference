import tempfile
from pathlib import Path
import unittest
import json
import subprocess
import sys
from unittest.mock import patch
from cloud_training.nano_corpus import DedupIndex,normalize,signature,pack_one,anchors
from cloud_training.nano_data import sha256_file

class CorpusTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.index=DedupIndex(Path(self.tmp.name)/'index.sqlite');self.addCleanup(self.index.close)
 def test_download_expansion_requires_review_before_any_io(self):
  root=Path(self.tmp.name)/'must-not-exist'
  result=subprocess.run([sys.executable,'-m','cloud_training.nano_corpus','--download-cap','6000000000','--root',str(root)],capture_output=True,text=True)
  self.assertNotEqual(result.returncode,0)
  self.assertIn('continuation review receipt required',result.stderr)
  self.assertFalse(root.exists())
 def test_normalized_exact_and_validation_isolation(self):
  self.assertTrue(self.index.admit('Hello  WORLD','val','validation')[0])
  self.assertEqual(self.index.admit('hello\nworld','train','train')[1],'exact_duplicate')
  self.assertEqual(normalize('Ａ B'),'a b')
 def test_near_duplicate_with_small_middle_change(self):
  words=['word'+str(i) for i in range(500)];first=' '.join(words)
  self.assertTrue(self.index.admit(first,'a','train')[0])
  words[200]='changed';self.assertEqual(self.index.admit(' '.join(words),'b','train')[1],'near_duplicate')
 def test_strict_development_rejects_fit_prefix_even_if_tail_differs(self):
  prefix='word '*2000
  self.index.admit(prefix,'fit','tokenizer_reference')
  self.index.check_fit_prefix=True
  self.assertEqual(self.index.admit(prefix+'unseen ending','val','validation')[1],'tokenizer_fit_prefix_duplicate')
 def test_strict_development_rejects_incomplete_candidate_screen(self):
  text='shared anchor text for a document with many candidates and other details'
  anchor=anchors(normalize(text))[0]
  for i in range(33):
   digest=f'{i:064x}'
   self.index.db.execute('INSERT INTO docs VALUES(?,?,?,?)',(digest,'fit','reference',b''))
   self.index.db.execute('INSERT INTO anchors VALUES(?,?)',(anchor,digest))
  self.index.reject_truncated=True
  self.assertEqual(self.index.admit(text,'val','validation')[1],'near_screen_incomplete')
 def test_corrected_dev_cannot_introduce_new_duplicate_representative(self):
  self.index.allowed_hashes=set()
  self.assertEqual(self.index.admit('otherwise unique text','val','validation')[1],'not_original_validation_kept')
 def test_different_document_kept(self):
  self.assertTrue(self.index.admit('apple orange pear kiwi','a','train')[0])
  self.assertTrue(self.index.admit('server database request latency','b','train')[0])
 def test_interrupted_source_rollback_preserves_earlier_sources(self):
  self.index.admit('keep earlier document','earlier','validation')
  self.index.admit('remove partial document','partial','train')
  self.index.rollback_source('partial')
  self.assertTrue(self.index.admit('remove partial document','partial','train')[0])
  self.assertFalse(self.index.admit('keep earlier document','next','train')[0])
 def test_empty_and_deterministic_bounded_signature(self):
  self.assertEqual(self.index.admit(' \n\t','x','train')[1],'empty')
  t=' '.join(map(str,range(5000)));self.assertEqual(signature(t),signature(t));self.assertLessEqual(len(signature(t)),64)

class PackResumeTests(unittest.TestCase):
 def test_mid_pack_crash_rebuilds_same_bytes_without_losing_committed_docs(self):
  import pyarrow as pa
  import pyarrow.parquet as pq
  class Tok:
   def __init__(self,fail=False):self.calls=0;self.fail=fail
   def get_bos_token_id(self):return 0
   def encode(self,texts,prepend,num_threads):
    self.calls+=1
    if self.fail and self.calls==18:raise RuntimeError('injected mid-source process failure')
    return [[prepend]+[ord(c) for c in t] for t in texts]
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);source=root/'shard_00002.parquet'
   texts=[' '.join(f'doc{i}word{j}' for j in range(100)) for i in range(1200)]
   pq.write_table(pa.table({'text':texts}),source,row_group_size=64)
   receipt={'sha256':sha256_file(source)}
   recovery=root/'recovery';recovery.mkdir();index=DedupIndex(recovery/'index.sqlite')
   with patch('cloud_training.nano_corpus.resource_guard',lambda _:None):
    with self.assertRaisesRegex(RuntimeError,'injected'):
     pack_one(source,'train',recovery,Tok(fail=True),index,receipt,'a'*64)
    # SQLite closes without commit, as if the process died between row groups.
    index.db.close()
    index=DedupIndex(recovery/'index.sqlite')
    self.assertGreater(index.db.execute('SELECT COUNT(*) FROM docs').fetchone()[0],0)
    incomplete=recovery/'packed/train/shard_00002'
    self.assertFalse((incomplete/'audit.json').exists())
    (incomplete/'rows.u16.partial').write_bytes(b'orphaned partial payload')
    resumed=pack_one(source,'train',recovery,Tok(),index,receipt,'a'*64)
    index.close()
    clean=root/'clean';clean.mkdir();fresh=DedupIndex(clean/'index.sqlite')
    expected=pack_one(source,'train',clean,Tok(),fresh,receipt,'a'*64);fresh.close()
   self.assertEqual(resumed['documents'],expected['documents'])
   self.assertEqual(resumed['targets'],expected['targets'])
   self.assertEqual(sha256_file(Path(resumed['directory'])/'rows.u16'),sha256_file(Path(expected['directory'])/'rows.u16'))

 def test_completed_shard_resume_binds_index_and_receipt(self):
  import pyarrow as pa
  import pyarrow.parquet as pq
  class Tok:
   def get_bos_token_id(self):return 0
   def encode(self,texts,prepend,num_threads):return [[prepend]+[ord(c) for c in t] for t in texts]
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);source=root/'shard_00002.parquet'
   pq.write_table(pa.table({'text':[' '.join('word'+str(i) for i in range(1500))]}),source)
   index=DedupIndex(root/'index.sqlite')
   try:
    with patch('cloud_training.nano_corpus.resource_guard',lambda _:None):
     first=pack_one(source,'train',root,Tok(),index,{'sha256':sha256_file(source)},'a'*64)
     second=pack_one(source,'train',root,Tok(),index,{'sha256':sha256_file(source)},'a'*64)
     self.assertEqual(first,second)
     with self.assertRaises(RuntimeError):pack_one(source,'train',root,Tok(),index,{'sha256':sha256_file(source)},'b'*64)
     index.rollback_source(source.name)
     with self.assertRaises(RuntimeError):pack_one(source,'train',root,Tok(),index,{'sha256':sha256_file(source)},'a'*64)
   finally:index.close()

if __name__=='__main__':unittest.main()

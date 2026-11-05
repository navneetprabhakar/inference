import hashlib,json,os,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from checkpoint_retention import prune
class RetentionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.names=[]
        for i in range(4):
            p=self.root/f'checkpoint-{i:012d}-{i}';p.mkdir();(p/'model.safetensors').write_bytes(b'model');(p/'state.json').write_text(json.dumps({'model_sha256':hashlib.sha256(b'model').hexdigest()}));os.utime(p,(100+i,100+i));self.names.append(p.name)
    def test_keep_latest_two_and_selected_with_manifest(self):
        prune(self.root,{self.names[0]});self.assertTrue((self.root/self.names[0]).exists());self.assertFalse((self.root/self.names[1]).exists());self.assertTrue((self.root/self.names[2]).exists());self.assertTrue((self.root/self.names[3]).exists())
        log=[json.loads(l) for l in (self.root/'retention-manifest.jsonl').read_text().splitlines()];self.assertEqual([r['status'] for r in log],['deletion_planned','deleted']);self.assertTrue(log[0]['files'][0]['sha256'])
    def test_hash_mismatch_prevents_deletion(self):
        (self.root/self.names[0]/'model.safetensors').write_bytes(b'changed')
        with self.assertRaisesRegex(RuntimeError,'hash mismatch'):prune(self.root,{self.names[1]})
        self.assertTrue((self.root/self.names[0]).exists())
    def test_unknown_directory_not_deleted(self):
        p=self.root/'checkpoint-unrecognized';p.mkdir();os.utime(p,(1,1))
        with self.assertRaisesRegex(RuntimeError,'unrecognized'):prune(self.root,set(self.names))
        self.assertTrue(p.exists())
if __name__=='__main__':unittest.main()

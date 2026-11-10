import base64
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from cloud_training.nano_data import write_rows
from cloud_training.nano_inventory_backup import scan,sha,acquire_lock


def fixture(root):
    directory=root/'packed/train/shard_00002'
    m=write_rows(directory,[[3]*2049],sequence_length=2048,vocab_size=32768,
        tokenizer_sha256='a'*64,split='train',source_manifest_sha256='b'*64,packing='fixture',max_rows=1)
    entry={'directory':str(directory),'manifest_sha256':sha(directory/'manifest.json'),
           'training_admitted':False,'rows':m['rows'],'targets':m['target_tokens']}
    (directory/'audit.json').write_text(json.dumps(entry))
    report=root/'progress.json';report.write_text(json.dumps({'status':'bounded_corpus_packed_review_pending',
        'training_admitted':False,'tokenizer_sha256':'a'*64,'train':[entry],'validation':[]}))
    return report,directory


class BackupTests(unittest.TestCase):
    def test_dryrun_no_cloud_and_incomplete_not_published(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);report,d=fixture(root)
            def forbidden(*a):raise AssertionError('Cloud called')
            result=scan(report,root,root/'receipt',time.monotonic()+10,dry_run=True,runner=forbidden)
            self.assertEqual(result['pending'],['train/shard_00002'])
            self.assertFalse((root/'receipt').exists())
            (d/'audit.json').unlink()
            result=scan(report,root,root/'receipt',time.monotonic()+10,dry_run=True,runner=forbidden)
            self.assertEqual(result['incomplete_entries'],1)
            self.assertFalse(result['terminal_all_uploaded'])

    def test_changed_manifest_or_payload_rejected(self):
        for name in ('manifest.json','rows.u16'):
            with tempfile.TemporaryDirectory() as t:
                root=Path(t);report,d=fixture(root);path=d/name
                raw=path.read_bytes();path.write_bytes(bytes([raw[0]^1])+raw[1:])
                with self.assertRaises(ValueError):scan(report,root,root/'receipt',time.monotonic()+10,dry_run=True)

    def fake_cloud(self,remote,calls):
        def run(args,deadline):
            calls.append(args)
            if args[0]=='cat':
                if args[1] not in remote:raise subprocess.CalledProcessError(1,args,stderr='404 NotFound')
                return remote[args[1]].decode()
            if args[:2]==['cp','--no-clobber']:
                remote.setdefault(args[3],Path(args[2]).read_bytes());return ''
            if args[:2]==['objects','describe']:
                raw=remote[args[2]]
                return json.dumps({'size':len(raw),'md5_hash':base64.b64encode(hashlib.md5(raw).digest()).decode()})
            raise AssertionError(args)
        return run

    def test_upload_manifest_last_receipt_and_changed_remote_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);report,d=fixture(root);remote={};calls=[];runner=self.fake_cloud(remote,calls)
            result=scan(report,root,root/'receipt',time.monotonic()+10,runner=runner)
            self.assertTrue(result['terminal_all_uploaded'])
            copies=[c for c in calls if c[0]=='cp']
            self.assertEqual([Path(c[2]).name for c in copies],['rows.u16','audit.json','manifest.json'])
            self.assertTrue((root/'receipt').exists())
            calls.clear();scan(report,root,root/'receipt',time.monotonic()+10,runner=runner)
            self.assertFalse(calls)
            # Fresh receipt cannot accept wrong preexisting remote metadata.
            manifest=next(k for k in remote if k.endswith('manifest.json'));remote[manifest]=b'wrong'
            with self.assertRaisesRegex(ValueError,'remote metadata mismatch'):
                scan(report,root,root/'new-receipt',time.monotonic()+10,runner=runner)

    def test_wrong_preexisting_payload_not_silently_accepted(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);report,d=fixture(root)
            from cloud_training.nano_inventory_backup import PREFIX
            remote={PREFIX+'/train/shard_00002/rows.u16':b'x'*(d/'rows.u16').stat().st_size}
            with self.assertRaisesRegex(ValueError,'Remote payload'):
                scan(report,root,root/'receipt',time.monotonic()+10,runner=self.fake_cloud(remote,[]))
            self.assertFalse((root/'receipt').exists())

    def test_lock_excludes_second_uploader(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'lock'
            with acquire_lock(p):
                with self.assertRaises(BlockingIOError):acquire_lock(p)
            with acquire_lock(p):pass


if __name__=='__main__':unittest.main()

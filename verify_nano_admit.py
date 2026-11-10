"""Tiny local fixtures only; never admits the real corpus."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from cloud_training.nano_data import write_rows,sha256_file
from cloud_training.nano_admit import materialize,REQUIRED_TARGETS
from cloud_training.nano_train import read_campaign


def fixture(root):
    root=Path(root);entries=[]
    for i,split in enumerate(('train','validation')):
        directory=root/'prep'/split/f'shard_{i:05d}'
        write_rows(directory,[[i+1]*2049],sequence_length=2048,vocab_size=32768,
            tokenizer_sha256='a'*64,split=split,source_manifest_sha256='b'*64,packing='fixture',max_rows=1)
        entries.append({'directory':str(directory.relative_to(root)),'manifest_sha256':sha256_file(directory/'manifest.json')})
    c={'schema':1,'training_admitted':False,'tokenizer_sha256':'a'*64,'sequence_length':2048,'vocab_size':32768,
       'train':entries[:1],'validation':entries[1:]}
    candidate=root/'candidate.json';candidate.write_text(json.dumps(c))
    r={'schema':1,'approved':True,'candidate_sha256':sha256_file(candidate),'tokenizer_sha256':'a'*64,
       'source_manifest_sha256':[e['manifest_sha256'] for e in entries],'reviewer':'unit-test',
       'evidence':['synthetic test fixture only']}
    review=root/'review.json';review.write_text(json.dumps(r))
    return candidate,review


class AdmitTests(unittest.TestCase):
    def run_fixture(self,c,r,out):
        return materialize(c,r,out,metadata_prefix='gs://test-bucket/admitted/v1')

    def test_immutable_copy_index_and_existing_destination_refused(self):
        with tempfile.TemporaryDirectory() as t,patch('cloud_training.nano_admit.REQUIRED_TARGETS',2048):
            c,r=fixture(t);before={str(p):sha256_file(p) for p in Path(t).rglob('*') if p.is_file()}
            out=Path(t)/'admitted';result=self.run_fixture(c,r,out)
            admitted=read_campaign(out/'campaign.json')
            self.assertTrue(admitted['training_admitted'])
            for p,sha in before.items():self.assertEqual(sha256_file(p),sha)
            index=json.loads((out/'data-index.json').read_text())
            self.assertEqual(index['campaign_path'],'campaign.json')
            self.assertEqual(index['campaign_sha256'],result['campaign_sha256'])
            for entry in index['files']:
                self.assertEqual(sha256_file(out/entry['path']),entry['sha256'])
                self.assertEqual((out/entry['path']).stat().st_size,entry['bytes'])
            rows=[e for e in index['files'] if e['path'].endswith('rows.u16')]
            self.assertTrue(all('/corpus-inventory/' in e['uri'] for e in rows))
            self.assertEqual((out/'packed/train/shard_00000/rows.u16').stat().st_ino,
                             (Path(t)/'prep/train/shard_00000/rows.u16').stat().st_ino)
            with self.assertRaises(FileExistsError):self.run_fixture(c,r,out)

    def test_production_floor_not_overridable(self):
        self.assertEqual(REQUIRED_TARGETS,10_000_269_312)
        with tempfile.TemporaryDirectory() as t:
            c,r=fixture(t)
            with self.assertRaisesRegex(ValueError,'Production requires'):self.run_fixture(c,r,Path(t)/'out')
            self.assertFalse((Path(t)/'out').exists())

    def test_changed_review_source_or_payload_rejected(self):
        for change in ('review','manifest','payload'):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as t,patch('cloud_training.nano_admit.REQUIRED_TARGETS',2048):
                c,r=fixture(t)
                if change=='review':
                    doc=json.loads(r.read_text());doc['candidate_sha256']='0'*64;r.write_text(json.dumps(doc))
                else:
                    p=Path(t)/'prep/train/shard_00000'/('manifest.json' if change=='manifest' else 'rows.u16')
                    p.write_bytes(p.read_bytes()+b' ')
                with self.assertRaises(ValueError):self.run_fixture(c,r,Path(t)/'out')

    def test_duplicate_payload_rejected_and_copy_fallback(self):
        with tempfile.TemporaryDirectory() as t,patch('cloud_training.nano_admit.REQUIRED_TARGETS',2048):
            c,r=fixture(t)
            with patch('cloud_training.nano_admit.os.link',side_effect=OSError('cross device')):
                self.run_fixture(c,r,Path(t)/'out')
            src=Path(t)/'prep/train/shard_00000';val=Path(t)/'prep/validation/shard_00001'
            (val/'rows.u16').write_bytes((src/'rows.u16').read_bytes())
            m=json.loads((val/'manifest.json').read_text());m['sha256']=sha256_file(val/'rows.u16');(val/'manifest.json').write_text(json.dumps(m))
            doc=json.loads(c.read_text());doc['validation'][0]['manifest_sha256']=sha256_file(val/'manifest.json');c.write_text(json.dumps(doc))
            review=json.loads(r.read_text());review['candidate_sha256']=sha256_file(c);review['source_manifest_sha256'][1]=doc['validation'][0]['manifest_sha256'];r.write_text(json.dumps(review))
            with self.assertRaisesRegex(ValueError,'Duplicate payload'):self.run_fixture(c,r,Path(t)/'duplicate')


if __name__=='__main__':unittest.main()

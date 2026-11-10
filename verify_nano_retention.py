"""Mock-only checkpoint retention tests: never contacts GCP or deletes real files."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cloud_training.nano_retention import record_upload, apply_retention, _manifest_bytes

CAMPAIGN = 'gs://test-bucket/ownbase-run/checkpoints'


def receipt(i):
    return {'status': 'gcs_bundle_uploaded', 'remote_prefix': CAMPAIGN + '/checkpoint-' + f'{i:032x}',
            'step': i, 'identity': {'run': 'test'},
            'publication_order': ['payload.pt', 'metadata.json', 'manifest.json', 'COMMITTED'],
            'manifest': {'version': 1, 'step': i, 'files': {
                'payload.pt': {'bytes': 100, 'sha256': '1'*64},
                'metadata.json': {'bytes': 50, 'sha256': '2'*64}}}}


class RetentionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'journal.json'
        self.receipts = [receipt(i) for i in range(1, 6)]
        for r in self.receipts:
            record_upload(self.path, r, campaign_prefix=CAMPAIGN,
                          pins=('milestone',) if r['step'] == 1 else ())
        self.calls = []

    def remote(self, args, deadline):
        self.calls.append(args)
        uri = args[2] if args[:2] == ['objects', 'describe'] else args[1]
        root, name = uri.rsplit('/', 1)
        r = next(v for v in self.receipts if v['remote_prefix'] == root)
        if args[:2] == ['objects', 'describe']:
            return json.dumps({'generation': '100', 'size': r['manifest']['files'].get(name, {}).get('bytes', 20)})
        if args[0] == 'cat':
            raw = _manifest_bytes(r['manifest'])
            if name == 'manifest.json': return raw.decode()
            return json.dumps({'version': 1, 'manifest_sha256': hashlib.sha256(raw).hexdigest()})
        if args[0] == 'rm':
            self.assertIn('--if-generation-match=100', args)
            self.assertNotIn('--recursive', args)
            self.assertNotIn('*', uri)
            return ''
        raise AssertionError(args)

    def test_dry_run_is_default_no_cloud(self):
        with patch('cloud_training.nano_retention._run', side_effect=AssertionError('cloud call')):
            result = apply_retention(self.path, campaign_prefix=CAMPAIGN)
        self.assertEqual(result['status'], 'dry_run')
        self.assertEqual(result['candidates'], [r['remote_prefix'] for r in self.receipts[1:3]])
        self.assertEqual(result['kept'], [self.receipts[i]['remote_prefix'] for i in (0, 3, 4)])

    def test_only_explicit_old_bundle_objects_deleted_marker_first(self):
        with patch('cloud_training.nano_retention._run', side_effect=self.remote):
            result = apply_retention(self.path, campaign_prefix=CAMPAIGN, execute=True)
        deletes = [args for args in self.calls if args[0] == 'rm']
        self.assertEqual(len(deletes), 8)
        for i in (0, 4): self.assertTrue(deletes[i][1].endswith('/COMMITTED'))
        self.assertEqual(result['deleted'], result['candidates'])
        self.assertTrue(all(not d[1].startswith(self.receipts[4]['remote_prefix']) for d in deletes))
        self.assertTrue(all(not d[1].startswith(self.receipts[0]['remote_prefix']) for d in deletes))
        with patch('cloud_training.nano_retention._run', side_effect=AssertionError('cloud call')):
            self.assertEqual(apply_retention(self.path, campaign_prefix=CAMPAIGN)['candidates'], [])

    def test_malformed_and_protected_prefix_rejected(self):
        for prefix in ('gs://test-bucket', 'gs://test-bucket/inputs/checkpoints',
                       'gs://test-bucket/run/../checkpoints', CAMPAIGN+'/*', 'http://bucket/run/checkpoints'):
            with self.assertRaises(ValueError): apply_retention(self.path, campaign_prefix=prefix)

    def test_foreign_and_nongenerated_receipt_rejected(self):
        for uri in ('gs://other-bucket/run/checkpoints/checkpoint-'+'1'*32,
                    CAMPAIGN+'/old-input', CAMPAIGN+'/checkpoint-'+'1'*32+'/../inputs'):
            r = receipt(9); r['remote_prefix'] = uri
            with self.assertRaises(ValueError): record_upload(self.path, r, campaign_prefix=CAMPAIGN)

    def test_incomplete_upload_receipt_rejected(self):
        r = receipt(9); r['status'] = 'uploading'
        with self.assertRaises(ValueError): record_upload(self.path, r, campaign_prefix=CAMPAIGN)
        r = receipt(9); r['publication_order'] = ['COMMITTED', 'payload.pt']
        with self.assertRaises(ValueError): record_upload(self.path, r, campaign_prefix=CAMPAIGN)

    def test_remote_missing_or_corrupt_commit_blocks_all_deletions(self):
        for bad_i in (1, 2, 5):  # pinned, candidate, newest recovery point
            self.calls.clear()
            def bad(args, deadline):
                result = self.remote(args, deadline)
                if args[0] == 'cat' and args[1] == self.receipts[bad_i-1]['remote_prefix']+'/COMMITTED':
                    return '{}'
                return result
            with patch('cloud_training.nano_retention._run', side_effect=bad):
                with self.assertRaises(ValueError): apply_retention(self.path, campaign_prefix=CAMPAIGN, execute=True)
            self.assertFalse(any(c[0] == 'rm' for c in self.calls))

    def test_missing_kept_payload_blocks_deletion(self):
        def bad(args, deadline):
            if args[:2] == ['objects', 'describe'] and args[2].startswith(self.receipts[-1]['remote_prefix']):
                raise FileNotFoundError('remote object absent')
            return self.remote(args, deadline)
        with patch('cloud_training.nano_retention._run', side_effect=bad):
            with self.assertRaises(FileNotFoundError): apply_retention(self.path, campaign_prefix=CAMPAIGN, execute=True)
        self.assertFalse(any(c[0] == 'rm' for c in self.calls))

    def test_partial_delete_fails_closed(self):
        def fail(args, deadline):
            if args[0] == 'rm' and args[1].endswith('/payload.pt'):
                raise RuntimeError('generation mismatch or interruption')
            return self.remote(args, deadline)
        with patch('cloud_training.nano_retention._run', side_effect=fail):
            with self.assertRaises(RuntimeError): apply_retention(self.path, campaign_prefix=CAMPAIGN, execute=True)
        journal = json.loads(self.path.read_text())
        candidate = journal['entries'][1]
        self.assertEqual(candidate['state'], 'deleting')
        self.assertEqual(candidate['deleted_objects'], ['COMMITTED'])
        with patch('cloud_training.nano_retention._run', side_effect=AssertionError('cloud call')):
            with self.assertRaisesRegex(ValueError, 'reconciliation'):
                apply_retention(self.path, campaign_prefix=CAMPAIGN, execute=True)

    def test_pin_best_is_additive_and_idempotent(self):
        for _ in range(2): record_upload(self.path, self.receipts[1], campaign_prefix=CAMPAIGN, pins=('best',))
        result = apply_retention(self.path, campaign_prefix=CAMPAIGN)
        self.assertIn(self.receipts[1]['remote_prefix'], result['kept'])
        self.assertEqual(len(json.loads(self.path.read_text())['entries']), 5)

    def test_late_old_receipt_cannot_displace_current(self):
        old = receipt(0)
        record_upload(self.path, old, campaign_prefix=CAMPAIGN)
        result = apply_retention(self.path, campaign_prefix=CAMPAIGN)
        self.assertIn(self.receipts[-1]['remote_prefix'], result['kept'])
        self.assertIn(self.receipts[-2]['remote_prefix'], result['kept'])
        self.assertIn(old['remote_prefix'], result['candidates'])

    def test_current_two_never_deleted(self):
        path = self.path.parent / 'two.json'
        for r in self.receipts[:2]: record_upload(path, r, campaign_prefix=CAMPAIGN)
        with patch('cloud_training.nano_retention._run', side_effect=AssertionError('cloud call')):
            self.assertEqual(apply_retention(path, campaign_prefix=CAMPAIGN, execute=True)['deleted'], [])

    def test_journal_campaign_mismatch_and_identity_receipt_change_rejected(self):
        with self.assertRaises(ValueError): apply_retention(self.path, campaign_prefix='gs://test-bucket/other/checkpoints')
        r = receipt(2); r['identity'] = {'run': 'changed'}
        with self.assertRaises(ValueError): record_upload(self.path, r, campaign_prefix=CAMPAIGN)


if __name__ == '__main__':
    unittest.main()

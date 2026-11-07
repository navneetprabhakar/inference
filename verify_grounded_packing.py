"""Proof-boundary regressions; synthetic files only, no private material."""
import json
from pathlib import Path
import tempfile
import unittest
from pack_grounded_sft import encoded, positions, sha, validate_proofs

def save(p, value):
    p.write_text(json.dumps(value))

def fixture(p):
    (p/'candidates.sqlite').write_bytes(b'synthetic identity only')
    save(p/'policy.json', {})
    save(p/'candidate-manifest.json', {'database': {'sha256': sha(p/'candidates.sqlite')},
        'policy_sha256':sha(p/'policy.json'), 'state':'candidate_only_not_admitted','failure':None})
    proof = dict(state='PASS_independent_grounded_candidates_not_admitted', failures=[],
                 verified_rows=4, database_sha256=sha(p/'candidates.sqlite'),
                 manifest_sha256=sha(p/'candidate-manifest.json'))
    save(p/'candidate-verification.json', proof)
    pins = {n: sha(p/n) for n in ('candidates.sqlite','candidate-manifest.json',
                                'candidate-verification.json')}
    for filename,key,ids in [('custody.json','pins',['a','b']),
                             ('public-development-custody.json','candidate_pins',['b','c'])]:
        save(p/filename, dict(state='screened_not_admitted', training_admitted=False,
              counts=dict(reviewed=4, excluded=2), excluded_doc_ids=ids, **{key:pins}))

class PackingProofTests(unittest.TestCase):
    def test_exclusion_union_not_intersection(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d); fixture(p)
            _, excluded, count = validate_proofs(p,'primary_tool')
            self.assertEqual(excluded, {'a','b','c'})
            self.assertEqual(count,4)

    def test_missing_public_receipt_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d); fixture(p); (p/'public-development-custody.json').unlink()
            with self.assertRaises(FileNotFoundError): validate_proofs(p,'primary_tool')

    def test_stale_database_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d); fixture(p); (p/'candidates.sqlite').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'independent candidate'): validate_proofs(p,'primary_tool')

    def test_stale_policy_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d); fixture(p); save(p/'policy.json', {'changed':True})
            with self.assertRaisesRegex(ValueError,'policy identity'): validate_proofs(p,'primary_tool')

    def test_stale_custody_and_partial_counts_rejected(self):
        for mutation in ('hash','count','excluded'):
            with tempfile.TemporaryDirectory() as d:
                p=Path(d); fixture(p); path=p/'public-development-custody.json'
                v=json.loads(path.read_text())
                if mutation=='hash': v['candidate_pins']['candidate-verification.json']='wrong'
                elif mutation=='count': v['counts']['reviewed']=3
                else: v['excluded_doc_ids']=['b','b']
                save(path,v)
                with self.assertRaises(ValueError): validate_proofs(p,'primary_tool')

    def test_author_selfcheck_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d); fixture(p); path=p/'candidate-verification.json'
            v=json.loads(path.read_text());v['state']='PASS_builder_self_check';save(path,v)
            with self.assertRaisesRegex(ValueError,'independent candidate'): validate_proofs(p,'primary_tool')

    def test_stream_mask_encoding_and_positions(self):
        self.assertEqual(encoded([0,50256,-100]),b'\x00\x00\x50\xc4\xff\xff')
        labels=[-100]*256;labels[0]=2;labels[255]=3
        self.assertEqual(positions(labels),{'0..255':1,'256..511':1,'512..767':0,'768..1023':0})
        with self.assertRaises(ValueError): encoded([65535])

if __name__=='__main__': unittest.main()

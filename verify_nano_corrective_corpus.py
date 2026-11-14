"""Whole-packet integrity, real broker parity and adversarial release-custody checks."""
import json,tempfile,shutil,hashlib,unittest,copy
from pathlib import Path
from cloud_training.nano_corpus_guard import verify_freeze,reject_split_leakage,claim_release
from cloud_training.nano_quality import validate_context_requirement
from cloud_training.nano_quality_gate import contract_errors,dataset_coverage
from tools import FixtureSession
P=Path('reports/corrective-corpus-v1');H='a'*64
class CorrectiveTests(unittest.TestCase):
    def test_frozen_full_packet_and_source_separation(self):
        self.assertEqual(verify_freeze(P)['release_model_exposures'],0)
        rows=[list(map(json.loads,(P/'candidate-4k'/name).read_text().splitlines())) for name in ['train.jsonl','validation.jsonl']]
        release=json.loads((P/'release-suite.json').read_text());self.assertEqual(len(release['sessions']),63)
        self.assertEqual(reject_split_leakage(*rows,release)['release_prompt_overlap'],0)
        self.assertEqual([len(r) for r in rows],[272,61])
    def test_every_candidate_tool_record_matches_actual_broker(self):
        total=0;errors=0
        for name in ['train.jsonl','validation.jsonl']:
            for row in map(json.loads,(P/'candidate-4k'/name).read_text().splitlines()):
                broker=FixtureSession();turn=-1
                for i,m in enumerate(row['messages']):
                    if m['role']=='user':
                        turn+=1;broker.start_turn(**(row.get('policies') or [{'permit_calls':False,'allowed_names':[]}]*100)[turn])
                    if m['role']=='assistant' and 'tool_call' in m:
                        actual=broker.propose(json.dumps(m['tool_call']),assistant_call_boundary=True);actual.pop('timestamp');self.assertEqual(actual,row['messages'][i+1]['record']);total+=1;errors+=not actual['ok']
        self.assertEqual(total,190);self.assertEqual(errors,3)
    def test_frozen_mutation_and_repeat_release_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'packet';shutil.copytree(P,root,ignore=shutil.ignore_patterns('__pycache__'))
            suite=hashlib.sha256((root/'release-suite.json').read_bytes()).hexdigest()
            claim_release(root,checkpoint_sha256=H,suite_sha256=suite,output=str(root/'result.json'))
            with self.assertRaises(ValueError):claim_release(root,checkpoint_sha256=H,suite_sha256=suite,output='second.json')
            (root/'release-use.json').unlink()
            with (root/'candidate-4k/train.jsonl').open('a') as f:f.write('\n')
            with self.assertRaises(ValueError):verify_freeze(root)
    def test_missing_group_and_exact_release_leak_rejected(self):
        a=[{'messages':[{'role':'user','content':'one'}],'provenance':{'source_group':'a'}}]
        b=[{'messages':[{'role':'user','content':'two'}],'provenance':{'source_group':'b'}}]
        r={'sessions':[{'source_group':'c','turns':[{'user':'three'}]}]}
        reject_split_leakage(a,b,r)
        b[0]['provenance']['source_group']='a'
        with self.assertRaises(ValueError):reject_split_leakage(a,b,r)
        b[0]['provenance']['source_group']='b';r['sessions'][0]['turns'][0]['user']='one'
        with self.assertRaises(ValueError):reject_split_leakage(a,b,r)
    def test_release_context_mismatch_fails_before_model_loading(self):
        s={'required_context_tokens':4096}
        with self.assertRaises(ValueError):validate_context_requirement(s,{'identity':{'config':{'sequence_len':2048}}})
        validate_context_requirement(s,{'identity':{'config':{'sequence_len':4096}}})
        with self.assertRaises(ValueError):validate_context_requirement({'required_context_tokens':True},{})
    def test_data_contract_passes_but_unbounded_pilot_cannot(self):
        import sys
        sys.path.insert(0,'runs/nanochat-source')
        from nanochat.tokenizer import RustBPETokenizer
        from cloud_training.nano_sft import load_manifest,JsonlConversations
        c=json.loads((P/'quality-contract.json').read_text());m=load_manifest(P/'candidate-4k/manifest.json',c['tokenizer_sha256'],4096);a=json.loads((P/'candidate-4k/admission.json').read_text());tok=RustBPETokenizer.from_directory('runs/ownbase-v2-data/tokenizer')
        cov={s:dataset_coverage(JsonlConversations(m[s]['_file'],tok,m[s]['sha256'],context=4096)) for s in ['train','validation']}
        kwargs=dict(manifest=m,admission=a,train=cov['train'],dev=cov['validation'],epochs=2,lr_multiplier=.125,eval_interval=10)
        self.assertEqual(contract_errors(c,**kwargs,max_updates=10),[])
        for n in [None,0,11,True]:self.assertTrue(any('bounded pilot' in x for x in contract_errors(c,**kwargs,max_updates=n)))

if __name__=='__main__':unittest.main()

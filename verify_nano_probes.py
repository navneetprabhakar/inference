import random
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import torch
from cloud_training.nano_checkpoint import capture_rng,_exact_fingerprint
from cloud_training.nano_probes import run_probes,configuration,load_tokenizer,FINAL_TOKENIZER_SHA256


class Tokenizer:
    def get_bos_token_id(self):return 0
    def encode(self,text,prepend):return [prepend,1,2]
    def decode(self,ids):return ''.join(str(i) for i in ids)


class Model(torch.nn.Module):
    def __init__(self):
        super().__init__();self.weight=torch.nn.Parameter(torch.zeros(1));self.child=torch.nn.Dropout()
        self.config=SimpleNamespace(sequence_len=2048);self.calls=0
    def forward(self,ids):
        self.calls+=1
        # Deliberate global RNG consumption proves diagnostics restore state.
        random.random();torch.rand(1)
        self.assert_inference = not torch.is_grad_enabled()
        logits=torch.zeros(1,ids.shape[1],4);logits[:,:,-1]=2
        return logits


class ProbeTests(unittest.TestCase):
    def test_fixed_budget_raw_greedy_preserves_rng_modes_parameters(self):
        model=Model();model.train();model.child.eval()
        rng=_exact_fingerprint(capture_rng());before=model.weight.detach().clone()
        result=run_probes(model,Tokenizer())
        self.assertEqual(model.calls,128);self.assertEqual(result['generated_tokens'],128)
        self.assertTrue(result['complete']);self.assertTrue(model.assert_inference)
        self.assertTrue(model.training);self.assertFalse(model.child.training)
        self.assertEqual(_exact_fingerprint(capture_rng()),rng)
        self.assertTrue(torch.equal(before,model.weight))
        for row in result['results']:
            self.assertEqual(row['generated_ids'],[3]*32)
            self.assertEqual(row['raw_completion'],'3'*32)  # No repetition repair.
        self.assertEqual(configuration(False)['max_total_new_tokens'],128)

    def test_deadline_stops_before_next_token_and_restores_state(self):
        model=Model();rng=_exact_fingerprint(capture_rng())
        result=run_probes(model,Tokenizer(),should_stop=lambda:model.calls>=5)
        self.assertEqual(result['generated_tokens'],5);self.assertFalse(result['complete'])
        self.assertEqual(model.calls,5);self.assertEqual(_exact_fingerprint(capture_rng()),rng)
        result=run_probes(model,Tokenizer(),should_stop=lambda:True)
        self.assertEqual(result['generated_tokens'],0)

    def test_error_restores_modes_and_rng(self):
        model=Model();model.config.sequence_len=3;rng=_exact_fingerprint(capture_rng())
        with self.assertRaisesRegex(ValueError,'no truncation'):run_probes(model,Tokenizer())
        self.assertTrue(model.training);self.assertEqual(_exact_fingerprint(capture_rng()),rng)

    def test_tokenizer_identity_fails_before_loading_untrusted_pickle(self):
        with self.assertRaises(ValueError):load_tokenizer('/missing','f'*64)
        with patch('cloud_training.nano_data.sha256_file',return_value='f'*64):
            with self.assertRaises(ValueError):load_tokenizer('/fake',FINAL_TOKENIZER_SHA256)


if __name__=='__main__':unittest.main()

"""Small deterministic general-SFT preparation tests, no downloads or model use."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from cloud_training.nano_chat_format import SPECIALS, encode_conversation
from cloud_training.nano_sft_data import normalize_general, encode_general, process_rows, combine_counted, tool_inventory, FILES, MAX_DOWNLOAD


class ByteTokenizer:
    def get_vocab_size(self):return 32768
    def encode_special(self,name):return 32000+SPECIALS.index(name)
    def get_bos_token_id(self):return self.encode_special('<|bos|>')
    def encode(self,text):return list(text.encode('utf8'))
    def decode(self,ids):return bytes(ids).decode('utf8')


def row(user='What is a cloud?',answer='A visible group of tiny water droplets.',source='unit'):
    return {'messages':[{'role':'user','content':user},{'role':'assistant','content':answer}],'source':source}


def source_rows(rows):return [('test.parquet',i,r) for i,r in enumerate(rows)]


class SFTDataTests(unittest.TestCase):
    def setUp(self):
        self.tok=ByteTokenizer();self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
    def prepare(self,train,dev,name='out'):
        return process_rows({'train':source_rows(train),'validation':source_rows(dev)},self.tok,self.root/name,
                            source_identity={'repository':'test','revision':'pinned'},min_free=0)

    def test_complete_text_preserved_and_assistant_only_count(self):
        original=row();original['messages'].insert(0,{'role':'system','content':'Be concise.'})
        before=deepcopy(original);item,_=encode_general(original,self.tok)
        self.assertEqual(original,before);self.assertEqual(item['messages'],original['messages'])
        rendered=encode_conversation(self.tok,item['messages'])
        self.assertEqual(item['assistant_target_count'],sum(rendered['mask'][1:]))
        for span in rendered['spans']:
            if span['kind'] in ('user_prompt','user_start','user_end','assistant_start','bos'):
                self.assertFalse(any(rendered['mask'][span['start']:span['end']]))

    def test_incomplete_and_bad_order_rejected_whole(self):
        for messages in ([{'role':'user','content':'Continue.'}],
                         [{'role':'assistant','content':'Premature.'},{'role':'user','content':'No.'}]):
            with self.assertRaises(ValueError):normalize_general({'messages':messages})

    def test_structured_and_markup_tool_calls_rejected(self):
        for altered in (
            {'messages':[{'role':'user','content':'Do something.'},{'role':'tool','content':'result'}]},
            {'messages':[{'role':'user','content':'Do something.'},{'role':'assistant','content':'ok','tool_calls':[]}]},
            row(answer='<|python_start|>print(2)<|python_end|>'),
            row(answer='{"tool_calls": [{"name":"web"}]}')):
            with self.assertRaises(ValueError):normalize_general(altered)

    def test_ordinary_code_answer_is_not_executed_or_rewritten(self):
        original=row('Show a Python expression.','Use `sum([1, 2])` in Python.')
        item,_=encode_general(original,self.tok)
        self.assertEqual(item['messages'][-1]['content'],original['messages'][-1]['content'])

    def test_unsupported_external_action_claims_rejected_without_answer_repair(self):
        for text in ("I will proceed with scheduling the posts.","I've sent the email.","I can book that hotel."):
            original=row(answer=text)
            with self.assertRaisesRegex(ValueError,'unsupported_external_action_claim'):normalize_general(original)
            self.assertEqual(original['messages'][-1]['content'],text)
        for text in ('I cannot schedule posts.','Here is a draft email you can send.'):
            self.assertEqual(normalize_general(row(answer=text))[0][-1]['content'],text)

    def test_context_overflow_rejects_no_truncation(self):
        original=row(answer='x'*2200)
        with self.assertRaisesRegex(ValueError,'context_overflow'):encode_general(original,self.tok)
        self.assertEqual(len(original['messages'][-1]['content']),2200)

    def test_exact_dedup_and_cross_split_prompt_isolation(self):
        dev=row('Shared prompt.','Held-out answer.')
        unique=row('Distinct training prompt.','Training answer.')
        manifest=self.prepare([dev,row('Shared prompt.','Different answer.'),unique,unique],[dev,dev])
        self.assertEqual(manifest['validation']['sessions'],1)
        self.assertEqual(manifest['train']['sessions'],1)
        self.assertEqual(manifest['stats']['validation']['rejected']['duplicate_exact_conversation'],1)
        self.assertEqual(manifest['stats']['train']['rejected']['duplicate_exact_conversation'],2)
        self.assertEqual(manifest['stats']['train']['rejected']['validation_prompt_overlap'],1)
        self.assertFalse(manifest['training_admitted'])

    def test_deterministic_shuffle_and_counts(self):
        train=[row(f'Train {i}?',f'Answer {i}.') for i in range(12)]
        dev=[row('Development?','Development answer.')]
        a=self.prepare(train,dev,'a');b=self.prepare(train,dev,'b')
        self.assertEqual(a['train']['sha256'],b['train']['sha256'])
        self.assertEqual(a['validation']['sha256'],b['validation']['sha256'])
        rows=[json.loads(line) for line in (self.root/'a/train.jsonl').read_text().splitlines()]
        self.assertEqual(sum(r['assistant_target_count'] for r in rows),a['train']['assistant_targets'])
        self.assertEqual(len({r['id'] for r in rows}),12)

    def test_empty_retained_split_cannot_publish_admitted_manifest(self):
        with self.assertRaises(ValueError):self.prepare([], [row()])
        self.assertFalse((self.root/'out/manifest.json').exists())

    def test_mix_is_counted_unique_and_not_admitted(self):
        self.prepare([row('Train one.','One.'),row('Train two.','Two.')],[row('Dev one.','Three.')])
        mixed=combine_counted(self.root/'out',self.tok,self.root/'mixed',tool_per_family=2,min_free=0)
        self.assertFalse(mixed['training_admitted'])
        seen=set()
        for split in ('train','validation'):
            rows=[json.loads(line) for line in (self.root/'mixed'/mixed[split]['file']).read_text().splitlines()]
            self.assertEqual(sum(r['assistant_target_count'] for r in rows),mixed[split]['assistant_targets'])
            self.assertEqual(len(rows),mixed[split]['sessions'])
            for item in rows:
                self.assertNotIn(item['id'],seen);seen.add(item['id'])
            self.assertEqual(mixed['stats'][split]['tool_sessions'],16)
            self.assertGreater(mixed['stats'][split]['tool_assistant_target_fraction'],0)

    def test_tool_inventory_unique_prefix_counted_without_replay(self):
        from unittest.mock import patch
        from cloud_training.nano_tool_lessons import build_lessons
        def small(split,**kwargs):return build_lessons(split,per_family=2,seed=kwargs.get('seed',103))
        with patch('cloud_training.nano_tool_lessons.build_lessons',side_effect=small):
            result=tool_inventory(self.tok,self.root/'tools',max_sessions=16,min_free=0)
        self.assertFalse(result['training_admitted'])
        self.assertEqual(result['train']['sessions'],16)
        self.assertEqual(result['milestones']['16']['prefix_sha256'],result['train']['sha256'])
        rows=[json.loads(line) for line in (self.root/'tools/train.jsonl').read_text().splitlines()]
        self.assertEqual(len({r['id'] for r in rows}),16)
        self.assertEqual(sum(r['assistant_target_count'] for r in rows),result['train']['assistant_targets'])

    def test_entity_is_not_a_modulo_shortcut_for_arithmetic_operation(self):
        from unittest.mock import patch
        from cloud_training.nano_tool_lessons import build_lessons
        def small(split,**kwargs):return build_lessons(split,per_family=16,seed=kwargs.get('seed',103))
        with patch('cloud_training.nano_tool_lessons.build_lessons',side_effect=small):
            result=tool_inventory(self.tok,self.root/'decorrelated',max_sessions=128,min_free=0)
        counts=result['entity_operation_counts']
        for op in ('add','subtract','multiply','divide'):
            entities={key.split('/')[0] for key in counts if key.endswith('/'+op)}
            self.assertGreater(len(entities),1)

    def test_source_download_cap_and_hash_shape(self):
        self.assertLessEqual(sum(size for _,size,_ in FILES),MAX_DOWNLOAD)
        self.assertEqual(len(FILES),5)
        for _,_,sha in FILES:self.assertRegex(sha,'^[0-9a-f]{64}$')


if __name__=='__main__':unittest.main()

"""CPU tests for explicit2K-to4K framing, packing, lineage and native model state."""
import copy,hashlib,json,tempfile,unittest
from pathlib import Path
import torch
from cloud_training.nano_context import transition_config,validate_context_edge
from cloud_training.nano_chat_format import encode_conversation,VERSION
from cloud_training.nano_sft import (batch_recipe,JsonlConversations,BestFitConversations,FiniteEpochDataset,
    collect_update,load_manifest,validate_parent_chain,PINNED_REVISION)
from cloud_training.nano_checkpoint import save_bundle
from verify_nano_sft import FakeTokenizer,FakeDataset,TinyLM

class ContextTests(unittest.TestCase):
    def test_extension_explicit_no_architecture_change_or_8k(self):
        old={'sequence_len':2048,'n_embd':1024,'window_pattern':'SSSL'}
        with self.assertRaises(ValueError):transition_config(old,4096)
        new,record=transition_config(old,4096,allow_extension=True)
        self.assertEqual(old['sequence_len'],2048)
        self.assertEqual(new,{**old,'sequence_len':4096})
        validate_context_edge({'config':old},{'config':new,'context_transition':record})
        for child in ({'config':new},{'config':{**new,'n_embd':2048},'context_transition':record}):
            with self.assertRaises(ValueError):validate_context_edge({'config':old},child)
        for target in (True,8192,1024):
            with self.assertRaises(ValueError):transition_config(new,target,allow_extension=True)

    def test_full_4k_conversation_preserved_and_2k_default_still_rejects(self):
        tok=FakeTokenizer();messages=[{'role':'user','content':'x'*2700},{'role':'assistant','content':'complete answer'}]
        with self.assertRaisesRegex(ValueError,'Context overflow'):encode_conversation(tok,messages)
        encoded=encode_conversation(tok,messages,context=4096)
        self.assertGreater(len(encoded['ids']),2048);self.assertLess(len(encoded['ids']),4096)
        with self.assertRaises(ValueError):encode_conversation(tok,messages,context=8192)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'data.jsonl';p.write_text(json.dumps({'messages':messages})+'\n');sha=hashlib.sha256(p.read_bytes()).hexdigest()
            data=JsonlConversations(p,tok,sha,context=4096)
            self.assertEqual(data.get(0),(encoded['ids'],encoded['mask']))
            repeated=FiniteEpochDataset(data,2);self.assertEqual(repeated.context,4096)
            pack=BestFitConversations(repeated);self.assertEqual(pack.capacity,4097)
            batches,targets=collect_update(pack,1,1)
            self.assertEqual(len(batches[0][0][0]),4096)
            self.assertEqual(targets,sum(encoded['mask'][1:]))
            state=pack.state_dict();other=BestFitConversations(repeated);other.load_state_dict(state)
            self.assertEqual(other.next_row(),pack.next_row())

    def test_4k_batch_and_cursor_boundaries(self):
        self.assertEqual(batch_recipe(8192,2,4096)['rows_per_update'],2)
        with self.assertRaises(ValueError):batch_recipe(8192,4,4096)
        data=FakeDataset([100,100]);a=BestFitConversations(data,capacity=2049);b=BestFitConversations(data,capacity=4097)
        with self.assertRaisesRegex(ValueError,'identity'):b.load_state_dict(a.state_dict())

    def test_4k_admission_binds_context(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);sha=lambda x:hashlib.sha256(x.read_bytes()).hexdigest()
            (p/'train').write_text('train');(p/'dev').write_text('dev')
            review={'training_admitted':True,'tokenizer_sha256':'a'*64,'format_version':VERSION,'jsonl_sha256':[sha(p/'train'),sha(p/'dev')],'context_tokens':4096}
            (p/'review').write_text(json.dumps(review))
            manifest={'schema':1,'training_admitted':True,'format_version':VERSION,'tokenizer_sha256':'a'*64,'context_tokens':4096,'admission':{'receipt':'review','sha256':sha(p/'review')},'train':{'file':'train','sha256':sha(p/'train')},'validation':{'file':'dev','sha256':sha(p/'dev')}}
            (p/'manifest').write_text(json.dumps(manifest));load_manifest(p/'manifest','a'*64,4096)
            with self.assertRaises(ValueError):load_manifest(p/'manifest','a'*64)
            del review['context_tokens'];(p/'review').write_text(json.dumps(review));manifest['admission']['sha256']=sha(p/'review');(p/'manifest').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError,'receipt must bind context'):load_manifest(p/'manifest','a'*64,4096)

    def test_actual_checkpoint_lineage_accepts_only_recorded_transition(self):
        cfg={'sequence_len':2048,'vocab_size':32768,'n_layer':12,'n_embd':768,'n_head':6,'n_kv_head':6,'window_pattern':'SSSL'}
        baseid={'phase':'base','initialization':'own_random','revision':PINNED_REVISION,'tokenizer_sha256':'a'*64,'config':cfg}
        with tempfile.TemporaryDirectory() as d:
            model=TinyLM();opt=torch.optim.AdamW(model.parameters())
            def save(name,identity):
                p=Path(d)/name;save_bundle(p,model=model,optimizer=opt,metadata={'step':1,'identity':identity},data_state={'exact':True,'next_batch':1});return p,hashlib.sha256((p/'manifest.json').read_bytes()).hexdigest()
            parent,sha=save('base',baseid);new,record=transition_config(cfg,4096,allow_extension=True)
            ident={'phase':'sft','config':new,'revision':PINNED_REVISION,'tokenizer_sha256':'a'*64,'format_version':VERSION,'source_manifest_sha256':'b'*64,'parent_bundle_manifest_sha256':sha,'parent_identity':baseid,'base_bundle_manifest_sha256':sha,'base_identity':baseid,'context_transition':record}
            child,csha=save('extended',ident);validate_parent_chain(child,csha,'a'*64,stage='targeted',ancestors=[parent])
            broken=dict(ident);del broken['context_transition'];p,psha=save('bad',broken)
            with self.assertRaisesRegex(ValueError,'transition'):validate_parent_chain(p,psha,'a'*64,stage='targeted',ancestors=[parent])

    def test_native_model_weights_shapes_and_4k_forward_backward(self):
        from nanochat.gpt import GPT,GPTConfig
        torch.set_num_threads(2)
        a=GPT(GPTConfig(sequence_len=2048,vocab_size=128,n_layer=2,n_embd=64,n_head=2,n_kv_head=2));a.init_weights()
        b=GPT(GPTConfig(sequence_len=4096,vocab_size=128,n_layer=2,n_embd=64,n_head=2,n_kv_head=2));b.init_weights()
        before={k:v.detach().clone() for k,v in a.state_dict().items()};b.load_state_dict(before,strict=True)
        self.assertEqual(set(a.state_dict()),set(b.state_dict()))
        for key,value in before.items():self.assertTrue(torch.equal(value,b.state_dict()[key]))
        self.assertEqual(b.window_sizes,[(1024,0),(4096,0)])
        x=torch.randint(0,128,(1,4096));loss=b(x,x);self.assertTrue(torch.isfinite(loss));loss.backward()
        self.assertTrue(any(p.grad is not None for p in b.parameters()))
        for key,value in before.items():self.assertTrue(torch.equal(value,a.state_dict()[key]))

if __name__=='__main__':unittest.main()

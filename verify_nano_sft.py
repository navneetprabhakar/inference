"""CPU-only SFT objective, finite packing, admission and exact restart tests."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import torch
import torch.nn.functional as F
from cloud_training.nano_sft import (BestFitConversations,JsonlConversations,backward_weighted,
    collect_update,count_packed_rows,load_manifest,reset_sft_lrs,sft_schedule,evaluate_fixed,NATIVE_IGNORE,ensure_separate_output,replace_best_pin,batch_recipe,validate_parent_chain,PINNED_REVISION)
from cloud_training.nano_checkpoint import save_bundle,load_bundle
from cloud_training.nano_benchmark import digest_state
from cloud_training.nano_chat_format import SPECIALS,VERSION


class TinyLM(torch.nn.Module):
    def __init__(self):
        super().__init__();self.embedding=torch.nn.Embedding(8,4,dtype=torch.float64)
        self.output=torch.nn.Linear(4,8,dtype=torch.float64)
    def forward(self,x,y,loss_reduction='sum'):
        return F.cross_entropy(self.output(self.embedding(x)).reshape(-1,8),y.reshape(-1),ignore_index=-1,reduction=loss_reduction)


class FakeTokenizer:
    def get_bos_token_id(self):return 32759
    def get_vocab_size(self):return 32768
    def encode_special(self,value):return 32759+SPECIALS.index(value)
    def encode(self,text):return [1+(ord(c)%200) for c in text]


class FakeDataset:
    def __init__(self,lengths):
        self.lengths=lengths;self.sha='a'*64
        self.tokenizer=type('Tokenizer',(),{'get_bos_token_id':lambda self:0})()
    def __len__(self):return len(self.lengths)
    def get(self,index):
        n=self.lengths[index]
        return [0]+[index%6+1]*(n-1),[0]+[1]*(n-1)


class SFTTests(unittest.TestCase):
    def setUp(self):torch.manual_seed(101)

    def test_uneven_mask_accumulation_equals_global_target_objective(self):
        initial=TinyLM();full=copy.deepcopy(initial);split=copy.deepcopy(initial)
        xs=[[1,2,3,4],[2,3,4,5],[3,4,5,6]]
        ys=[[2,-1,-1,-1],[3,4,5,6],[4,5,-1,-1]]
        whole=[(xs,ys)];uneven=[(xs[:1],ys[:1]),(xs[1:],ys[1:])]
        expected=backward_weighted(full,whole,7,device='cpu')
        actual=backward_weighted(split,uneven,7,device='cpu')
        self.assertAlmostEqual(actual,expected,places=12)
        for a,b in zip(full.parameters(),split.parameters()):
            torch.testing.assert_close(a.grad,b.grad,rtol=1e-12,atol=1e-12)
        # A mean of microbatch means is observably a different gradient here.
        wrong=copy.deepcopy(initial)
        for x,y in uneven:
            (wrong(torch.tensor(x),torch.tensor(y),loss_reduction='mean')/2).backward()
        self.assertTrue(any(not torch.allclose(a.grad,b.grad) for a,b in zip(full.parameters(),wrong.parameters())))

    def test_zero_target_microbatch_and_denominator_validation(self):
        m=TinyLM();batches=[([[1,2]],[[-1,-1]]),([[2,3]],[[3,4]])]
        self.assertTrue(torch.isfinite(torch.tensor(backward_weighted(m,batches,2,device='cpu'))))
        with self.assertRaises(ValueError):backward_weighted(m,batches,3,device='cpu')
        with self.assertRaises(ValueError):backward_weighted(m,[],0,device='cpu')
        with self.assertRaises(InterruptedError):backward_weighted(m,batches,2,device='cpu',stop_check=lambda:True)

    def test_complete_bestfit_packing_no_wrap_and_exact_buffer_restore(self):
        d=FakeDataset([10,7,6,4,3]);p=BestFitConversations(d,capacity=13,buffer_size=3)
        first=p.next_indices();self.assertEqual(first,[0])
        state=p.state_dict();next_indices=p.next_indices()
        restored=BestFitConversations(d,capacity=13,buffer_size=3);restored.load_state_dict(state)
        self.assertEqual(restored.next_indices(),next_indices)
        seen=first+next_indices
        while True:
            try:seen.extend(p.next_indices())
            except StopIteration:break
        self.assertEqual(sorted(seen),list(range(len(d))))
        self.assertEqual(len(seen),len(set(seen)))
        with self.assertRaises(StopIteration):p.next_indices()
        with self.assertRaises(ValueError):BestFitConversations(FakeDataset([14]),capacity=13)
        state['buffer']=[0,0]
        with self.assertRaises(ValueError):restored.load_state_dict(state)

    def test_padding_and_final_short_update_have_no_targets(self):
        d=FakeDataset([3]);p=BestFitConversations(d,capacity=5)
        batches,count=collect_update(p,microbatch=2,rows_per_update=2)
        self.assertEqual(count,2)
        self.assertEqual(batches[0][1][0],[1,1,-1,-1])
        self.assertEqual(batches[0][1][1],[-1]*4)
        self.assertEqual(collect_update(p,2,2),([],0))

    def test_exact_next_update_after_checkpoint_with_pending_pack_buffer(self):
        d=FakeDataset([4,3,5,2,4,3,5,4]);p=BestFitConversations(d,capacity=6,buffer_size=3)
        model=TinyLM();optimizer=torch.optim.AdamW(model.parameters(),lr=.01)
        def update():
            batches,count=collect_update(p,1,2)
            loss=backward_weighted(model,batches,count,device='cpu')
            optimizer.step();optimizer.zero_grad(set_to_none=True)
            return loss
        update()
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'snapshot'
            save_bundle(path,model=model,optimizer=optimizer,metadata={'step':1,'identity':{'phase':'tiny_sft_test'}},
                        data_state={'exact':True,'next_batch':1,'packing':p.state_dict()})
            expected_loss=update();expected=digest_state(model,optimizer);expected_cursor=p.state_dict()
            restored=load_bundle(path,model=model,optimizer=optimizer,expected_identity={'phase':'tiny_sft_test'})
            p.load_state_dict(restored['data_state']['packing'])
            self.assertEqual(update(),expected_loss)
            self.assertEqual(digest_state(model,optimizer),expected)
            self.assertEqual(p.state_dict(),expected_cursor)

    def test_fixed_development_preserves_state_and_masks(self):
        model=TinyLM();model.train();model.output.eval()
        states=[m.training for m in model.modules()]
        rng=torch.get_rng_state().clone()
        params=[p.detach().clone() for p in model.parameters()]
        ds=FakeDataset([3,5,3])
        result=evaluate_fixed(model,ds,rows=128,microbatch=2,device='cpu')
        self.assertEqual(result['assistant_targets'],8)
        self.assertEqual(result['rows'],1)
        self.assertEqual([m.training for m in model.modules()],states)
        self.assertTrue(torch.equal(torch.get_rng_state(),rng))
        for p,before in zip(model.parameters(),params):
            self.assertTrue(torch.equal(p,before));self.assertIsNone(p.grad)
        self.assertEqual(result,evaluate_fixed(model,ds,rows=128,microbatch=2,device='cpu'))

    def test_fresh_sft_lrs_not_final_base_lrs(self):
        model=TinyLM();optimizer=torch.optim.AdamW(model.parameters(),lr=.00001)
        optimizer.param_groups[0].update(kind='muon',initial_lr=.00001,weight_decay=.3)
        reset_sft_lrs(optimizer,[.02])
        group=optimizer.param_groups[0]
        self.assertEqual(group['lr'],.016);self.assertEqual(group['initial_lr'],.016);self.assertEqual(group['weight_decay'],0)
        self.assertEqual(sft_schedule(0,0),(1,.85))
        self.assertEqual(sft_schedule(.5,300),(1,.95))
        self.assertEqual(sft_schedule(1,300),(0,.95))

    def test_jsonl_exact_index_and_no_truncation(self):
        with tempfile.TemporaryDirectory() as t:
            file=Path(t)/'train.jsonl';row={'messages':[{'role':'user','content':'Hi'},{'role':'assistant','content':'Hello'}]}
            file.write_text(json.dumps(row)+'\n');sha=hashlib.sha256(file.read_bytes()).hexdigest()
            ds=JsonlConversations(file,FakeTokenizer(),sha)
            self.assertEqual(len(ds),1);self.assertGreater(ds.target_counts[0],0)
            row['messages'][-1]['content']='Other';file.write_text(json.dumps(row)+'\n')
            with self.assertRaises(ValueError):ds.get(0) # equal-length answer mutation
            row['messages'][-1]['content']='x'*3000;file.write_text(json.dumps(row)+'\n')
            with self.assertRaises(ValueError):JsonlConversations(file,FakeTokenizer(),hashlib.sha256(file.read_bytes()).hexdigest())

    def test_best_retention_requires_new_committed_copy(self):
        journal={'entries':[
            {'receipt':{'remote_prefix':'old'},'state':'committed','pins':['best','final']},
            {'receipt':{'remote_prefix':'new'},'state':'committed','pins':['best']}]}
        with self.assertRaises(ValueError):replace_best_pin(journal,'absent')
        updated=replace_best_pin(journal,'new')
        self.assertEqual(updated['entries'][0]['pins'],['final'])
        self.assertEqual(updated['entries'][1]['pins'],['best'])
        self.assertEqual(journal['entries'][0]['pins'],['best','final'])

    def test_output_guard_runs_before_any_base_mutation(self):
        with tempfile.TemporaryDirectory() as t:
            base=Path(t)/'base';base.mkdir();(base/'sentinel').write_text('immutable')
            for output in (base,base/'sft',base.parent):
                with self.assertRaises(ValueError):ensure_separate_output(base,output)
            self.assertEqual(list(base.iterdir()),[base/'sentinel'])
            self.assertEqual(ensure_separate_output(base,Path(t)/'sft')[1],(Path(t)/'sft').resolve())

    def test_effective_batch_and_scaled_fresh_lrs(self):
        self.assertEqual(batch_recipe(524288,4),{'batch_tokens':524288,'rows_per_update':256,'lr_batch_scale':1.0})
        recipe=batch_recipe(32768,4)
        self.assertEqual(recipe['rows_per_update'],16);self.assertEqual(recipe['lr_batch_scale'],.25)
        model=TinyLM();opt=torch.optim.AdamW(model.parameters(),lr=.00001)
        reset_sft_lrs(opt,[.02],recipe['lr_batch_scale'])
        self.assertEqual(opt.param_groups[0]['initial_lr'],.004)
        for batch,micro in [(0,4),(32769,4),(1048576,4),(32768,32),(32768,3),(True,1)]:
            with self.assertRaises(ValueError):batch_recipe(batch,micro)

    def test_small_batch_consumes_once_and_has_positive_last_update(self):
        ds=FakeDataset([2049]*35);packing=BestFitConversations(ds)
        updates=[];seen=0
        while packing.consumed<len(ds):
            before=packing.consumed
            batches,count=collect_update(packing,4,16)
            updates.append((packing.consumed-before,count,sft_schedule(before/len(ds),len(updates))[0]))
            seen+=count
        self.assertEqual([u[0] for u in updates],[16,16,3])
        self.assertEqual(seen,35*2048)
        self.assertTrue(all(u[2]>0 for u in updates))
        self.assertEqual(collect_update(packing,4,16),([],0))

    def test_verified_recursive_own_lineage_and_immutable_parents(self):
        cfg={'sequence_len':2048,'vocab_size':32768,'n_layer':12,'n_embd':768,'n_head':6,'n_kv_head':6,'window_pattern':'SSSL'}
        base_id={'phase':'base','initialization':'own_random','revision':PINNED_REVISION,'tokenizer_sha256':'a'*64,'config':cfg}
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);model=TinyLM();opt=torch.optim.AdamW(model.parameters())
            def save(name,identity):
                path=root/name
                save_bundle(path,model=model,optimizer=opt,metadata={'step':1,'identity':identity},data_state={'exact':True,'next_batch':1})
                return path,hashlib.sha256((path/'manifest.json').read_bytes()).hexdigest()
            base,bsha=save('base',base_id)
            self.assertEqual(validate_parent_chain(base,bsha,'a'*64,stage='general')[2],bsha)
            sid={'phase':'sft','stage':'general','revision':PINNED_REVISION,'tokenizer_sha256':'a'*64,'config':cfg,'format_version':VERSION,'source_manifest_sha256':'b'*64,'base_bundle_manifest_sha256':bsha,'base_identity':base_id,'parent_bundle_manifest_sha256':bsha,'parent_identity':base_id}
            general,gsha=save('general',sid)
            before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for d in (base,general) for p in d.iterdir()}
            self.assertEqual(validate_parent_chain(general,gsha,'a'*64,stage='targeted',ancestors=[base])[2],bsha)
            with self.assertRaisesRegex(ValueError,'Every ancestor'):validate_parent_chain(general,gsha,'a'*64,stage='targeted')
            with self.assertRaises(ValueError):validate_parent_chain(general,gsha,'a'*64,stage='general',ancestors=[base])
            tid={**sid,'stage':'targeted','source_manifest_sha256':'c'*64,'parent_bundle_manifest_sha256':gsha,'parent_identity':sid}
            targeted,tsha=save('targeted',tid)
            self.assertEqual(validate_parent_chain(targeted,tsha,'a'*64,stage='targeted',ancestors=[general,base])[2],bsha)
            wrong,wsha=save('wrong',{**base_id,'initialization':'pretrained'})
            with self.assertRaisesRegex(ValueError,'random'):validate_parent_chain(wrong,wsha,'a'*64,stage='general')
            broken,broken_sha=save('broken',{**sid,'parent_identity':{**base_id,'initialization':'pretrained'}})
            with self.assertRaisesRegex(ValueError,'identity mismatch'):validate_parent_chain(broken,broken_sha,'a'*64,stage='targeted',ancestors=[base])
            after={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for d in (base,general) for p in d.iterdir()}
            self.assertEqual(before,after)

    def test_manifest_never_admits_itself(self):
        with tempfile.TemporaryDirectory() as t:
            file=Path(t)/'manifest.json';file.write_text(json.dumps({'schema':1,'training_admitted':False,'format_version':VERSION}))
            with self.assertRaises(ValueError):load_manifest(file,'a'*64)


if __name__=='__main__':unittest.main()

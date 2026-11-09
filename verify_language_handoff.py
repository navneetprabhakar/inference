"""Small CPU metadata/optimizer fixtures; never edits a real checkpoint."""
import copy
import unittest
import torch
from own_base_language_data import MixedSchedule,ContinuedSchedule,digest
from own_base_language_parent import verify_payload,verify_source_handoff


class Tests(unittest.TestCase):
    def schedule(self):
        docs=[dict(id=str(i),tokens=8193,family=str(i),split='train',sha256='a'*64) for i in range(8)]
        return MixedSchedule(dict(schema=1,seed=19,length=512,sources=[dict(name='fresh',passes=1,documents=docs)],row_source_cycle=['fresh']*16))

    def test_continuation_matches_uninterrupted_rows(self):
        base=self.schedule();offset=3;wrapped=ContinuedSchedule(base,offset)
        a=base.state_at(offset);b=wrapped.initial()
        self.assertEqual(b['updates'],0)
        for step in range(3):
            expected,a=base.next_update(a);actual,b=wrapped.next_update(b)
            self.assertEqual(actual,expected)
            self.assertEqual(b['sources'],a['sources'])
            self.assertEqual(b['updates'],step+1)
            wrapped.validate_resume(b)
        self.assertEqual(b,wrapped.state_at(3))

    def test_offset_tamper_and_exhaustion_rejected(self):
        wrapped=ContinuedSchedule(self.schedule(),3)
        wrong=wrapped.initial();wrong['sources']['fresh']['offset']=0
        with self.assertRaises(ValueError):wrapped.next_update(wrong)
        with self.assertRaises(ValueError):wrapped.state_at(6)

    def test_cumulative_handoff_preserves_source_position(self):
        base=self.schedule()
        for offset in [0,2]:
            old=ContinuedSchedule(base,offset) if offset else base
            payload=dict(identity=dict(protocol=dict(source_start_updates=offset)),step=2,cursor=old.state_at(2))
            new=ContinuedSchedule(base,offset+2)
            verify_source_handoff(payload,new)
            expected,_=base.next_update(base.state_at(offset+2))
            actual,_=new.next_update(new.initial())
            self.assertEqual(actual,expected)
            wrong=copy.deepcopy(payload);wrong['cursor']['updates']+=1
            with self.assertRaises(ValueError):verify_source_handoff(wrong,new)
            with self.assertRaises(ValueError):verify_source_handoff(payload,ContinuedSchedule(base,offset+3))

    def fixture(self):
        identity=dict(initialization=dict(mode='own_pretraining',random_lineage_root='test-root'))
        campaign=dict(identity=identity)
        entry=dict(file='fixture.pt',sha256='a'*64,bytes=1)
        ledger=dict(spec=campaign,campaign_id='fixture',step=3,trained_tokens=24576,checkpoints=[entry])
        payload=dict(identity=identity,campaign_id='fixture',spec_sha256=digest(campaign),step=3,trained_tokens=24576,initial_optimizer_step=10,
                     optimizer=dict(state={0:dict(step=torch.tensor(13.),exp_avg=torch.ones(2),exp_avg_sq=torch.ones(2))}),
                     cpu_rng=torch.ones(10,dtype=torch.uint8),mps_rng=torch.ones(10,dtype=torch.uint8))
        return payload,campaign,ledger,entry

    def test_optimizer_rng_and_lineage_fail_closed(self):
        verify_payload(*self.fixture())
        for mutation in ['moment','step','rng','lineage','checkpoint','trained']:
            p,c,l,e=copy.deepcopy(self.fixture())
            if mutation=='moment':p['optimizer']['state'][0]['exp_avg_sq'][0]=-1
            elif mutation=='step':p['optimizer']['state'][0]['step']=torch.tensor(12.)
            elif mutation=='rng':p['mps_rng']=None
            elif mutation=='lineage':p['identity']['initialization']['mode']='pretrained'
            elif mutation=='checkpoint':l['checkpoints']=[]
            else:p['trained_tokens']=0
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):verify_payload(p,c,l,e)


if __name__=='__main__':unittest.main(verbosity=2)

"""Tiny pure-Python metadata tests; no tensors, corpus reads or GPU imports."""
import copy
import unittest
from own_base_language_data import MixedSchedule, validation_manifest, aggregate_validation


def plan(length=512, passes=2):
    return dict(schema=1,seed=7,length=length,sources=[dict(name=name,passes=passes,documents=[
        dict(id=name+str(i),tokens=4097,family=name+str(i),split='train',sha256=str(i)*64) for i in (1,2)]) for name in ('story','textbook')],
        row_source_cycle=['story','textbook']*(8192//length//2))


class Tests(unittest.TestCase):
    def test_layouts_targets_shift_and_source_quota(self):
        for length in (512,1024):
            s=MixedSchedule(plan(length));rows,state=s.next_update(s.initial())
            self.assertEqual(sum(r['targets'] for r in rows),8192)
            self.assertEqual(len(rows),8192//length)
            for name in s.sources:self.assertEqual(state['sources'][name]['targets'],4096)
            for row in rows:
                self.assertEqual(sum(x['count'] for x in row['input_spans']),length+1)
                self.assertEqual(sum(x['count'] for x in row['target_spans']),length)
                self.assertEqual(row['unique_targets'],length)
    def test_whole_document_order_seed_and_exact_exposure(self):
        s=MixedSchedule(plan());self.assertEqual(s.order('story',0),MixedSchedule(plan()).order('story',0))
        state=s.initial();seen=set();unique=repeat=0
        for _ in range(4):
            rows,state=s.next_update(state)
            for row in rows:
                for span in row['target_spans']:
                    for pos in range(span['offset'],span['offset']+span['count']):
                        key=(row['source'],span['document'],pos)
                        if key in seen:repeat+=1
                        else:unique+=1;seen.add(key)
        self.assertEqual(unique,sum(c['unique_targets'] for c in state['sources'].values()))
        self.assertEqual(repeat,sum(c['repeated_targets'] for c in state['sources'].values()))
        self.assertGreater(repeat,0)
        self.assertEqual(s.capacity('story')['unused_target_tail_per_pass'],1)
    def test_exhaustion_atomic_no_silent_wrap(self):
        s=MixedSchedule(plan(passes=1));state=s.initial()
        for _ in range(2):_,state=s.next_update(state)
        before=copy.deepcopy(state)
        with self.assertRaisesRegex(ValueError,'no wrap'):s.next_update(state)
        self.assertEqual(state,before)
    def test_partial_update_exhaustion_does_not_advance_any_source(self):
        p=plan(passes=1)
        for d in p['sources'][0]['documents']:d['tokens']=2049
        p['row_source_cycle']=['textbook','story']*8
        s=MixedSchedule(p);_,state=s.next_update(s.initial());before=copy.deepcopy(state)
        with self.assertRaisesRegex(ValueError,'no wrap'):s.next_update(state)
        self.assertEqual(state,before)
    def test_resume_exact_and_tamper_refusal(self):
        s=MixedSchedule(plan());state=s.initial()
        for _ in range(3):_,state=s.next_update(state)
        self.assertTrue(s.validate_resume(state))
        for key in ('targets','unique_targets','offset'):
            bad=copy.deepcopy(state);bad['sources']['story'][key]+=1
            with self.assertRaises(ValueError):s.validate_resume(bad)
        bad=copy.deepcopy(state);bad['plan_sha256']='changed'
        with self.assertRaises(ValueError):s.next_update(bad)
    def test_compact_exposure_matches_bruteforce_across_passes(self):
        for seed in range(5):
            p=plan(passes=3);p['seed']=seed
            for source in p['sources']:
                source['documents']=[dict(id=str(i),tokens=n,family=str(i),split='train',sha256='a'*64) for i,n in enumerate((23,509,1027,3077,4099))]
            s=MixedSchedule(p);state=s.initial();seen={n:set() for n in s.sources}
            for _ in range(6):
                rows,state=s.next_update(state)
                for row in rows:
                    for span in row['target_spans']:
                        seen[row['source']].update((span['document'],x) for x in range(span['offset'],span['offset']+span['count']))
                self.assertEqual(state,s.state_at(state['updates']))
                for name in s.sources:self.assertEqual(state['sources'][name]['unique_targets'],len(seen[name]))
            self.assertLess(len(str(state)),1000)
    def test_invalid_plan(self):
        for mutate in (lambda p:p['sources'][0].update(passes=0),lambda p:p.update(length=256),lambda p:p.update(row_source_cycle=['story']),lambda p:p['sources'][0]['documents'][0].update(split='validation')):
            p=plan();mutate(p)
            with self.assertRaises(ValueError):MixedSchedule(p)
    def fixture(self):
        docs=[dict(source='story',id=str(n),tokens=n+1,split='validation',sha256='a'*64) for n in (32,127,128,512)]
        windows=[dict(source='story',id=str(n),offset=0,targets=n) for n in (32,127,128,512)]
        return docs,windows
    def test_variable_length_and_distinct_averages(self):
        docs,windows=self.fixture();m=validation_manifest(docs,windows)
        result=aggregate_validation(m,[dict(source=w['source'],id=w['id'],targets=w['targets'],nll=w['targets']*(i+1)) for i,w in enumerate(windows)])
        self.assertEqual(m['evaluation_targets'],799)
        self.assertEqual(m['coverage_by_source']['story']['short_windows'],2)
        self.assertEqual(result['groups']['story/all']['document_mean_ce'],2.5)
        self.assertAlmostEqual(result['groups']['story/all']['token_mean_ce'],2718/799)
        self.assertEqual(result['groups']['story/short']['documents'],2)
        self.assertEqual(result['groups']['story/long']['documents'],2)
    def test_validation_boundary_identity_and_hash_refusal(self):
        docs,windows=self.fixture();bad=copy.deepcopy(windows);bad[0]['offset']=1
        with self.assertRaises(ValueError):validation_manifest(docs,bad)
        with self.assertRaises(ValueError):validation_manifest(docs,windows+[windows[0]])
        m=validation_manifest(docs,windows);rows=[dict(source=w['source'],id=w['id'],targets=w['targets'],nll=1.) for w in windows]
        with self.assertRaises(ValueError):aggregate_validation(m,list(reversed(rows)))
        m['windows'][0]['targets']+=1
        with self.assertRaises(ValueError):aggregate_validation(m,rows)

if __name__=='__main__':unittest.main(verbosity=2)

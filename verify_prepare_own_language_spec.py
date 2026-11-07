"""Pure CPU preparation checks; no model, corpus token or private-case reads."""
import tempfile
import unittest
from pathlib import Path
from prepare_own_language_spec import finite_passes,source_metadata,ROOT,UPDATES,GOAL
from own_base_language_data import MixedSchedule

class PreparationTests(unittest.TestCase):
    def test_exact_allocation(self):
        self.assertEqual(UPDATES*8192,GOAL)
        self.assertEqual(UPDATES*12*512,224999424)
        self.assertEqual(UPDATES*4*512,74999808)
        self.assertEqual(finite_passes(88790507,224999424),(3,88790016))
        self.assertEqual(finite_passes(31493507,74999808),(3,31493120))
    def test_four_pass_limit_and_tail(self):
        self.assertEqual(finite_passes(513,2048),(4,512))
        for tokens,required in [(513,2049),(512,1),(True,1)]:
            with self.assertRaises(ValueError):finite_passes(tokens,required)
    def test_missing_proof_refuses(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(FileNotFoundError):source_metadata(d,'narrative',8192)
            self.assertEqual(list(Path(d).iterdir()),[])
    def test_schedule_unique_repeats(self):
        sources=[]
        for name,total,rows in [('explanatory',88790507,12),('narrative',31493507,4)]:
            passes,_=finite_passes(total,UPDATES*rows*512)
            sources.append(dict(name=name,passes=passes,documents=[dict(id=name,tokens=total,family=name,split='train',sha256='0'*64)]))
        plan=MixedSchedule(dict(schema=1,seed=20261106,length=512,sources=sources,row_source_cycle=['explanatory']*12+['narrative']*4))
        state=plan.state_at(UPDATES)
        for name,rows in [('explanatory',12),('narrative',4)]:
            s=state['sources'][name]
            self.assertEqual(s['targets'],UPDATES*rows*512)
            self.assertEqual(s['unique_targets']+s['repeated_targets'],s['targets'])
            self.assertGreater(s['repeated_targets'],0)

if __name__=='__main__':unittest.main()

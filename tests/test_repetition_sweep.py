import sys,unittest,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from evaluate_repetition_v3 import admissible
class PenaltyGuardTest(unittest.TestCase):
 def baseline(self):
  m={k:{'strict_success_fraction':.8} for k in ['single','chain','result','grounded','error','none']}
  for k in ['single','chain']:m[k]['call_sequence_exact']=.9
  m['clarify']={'accepted_missing_slot_fraction':.8};m['chat']={'eos_fraction':.9}
  return m
 def test_tool_regression_cannot_win_on_repetition(self):
  b=self.baseline();m=copy.deepcopy(b);m['single']['strict_success_fraction']=.7
  self.assertFalse(all(admissible(m,b,{'empty_fraction':0},{'empty_fraction':0}).values()))
 def test_empty_or_unterminated_answers_rejected(self):
  b=self.baseline();m=copy.deepcopy(b);m['chat']['eos_fraction']=.7
  self.assertFalse(all(admissible(m,b,{'empty_fraction':0},{'empty_fraction':0}).values()))
  self.assertFalse(all(admissible(b,b,{'empty_fraction':.1},{'empty_fraction':0}).values()))
 def test_unchanged_baseline_is_admissible(self):
  b=self.baseline();self.assertTrue(all(admissible(b,b,{'empty_fraction':0},{'empty_fraction':0}).values()))
if __name__=='__main__':unittest.main()

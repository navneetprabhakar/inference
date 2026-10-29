"""Continuation using validated deterministic embedding backward; old runs immutable."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'resume-repair-v1'))
import validate as repair
s=repair.s
s.ROOT=ROOT;s.PRIVATE=ROOT/'private'
# Use original study caps. Ledger includes its four consumed preflight updates;
# the separately bounded repair has its own cumulative ten-update ledger.
if __name__=='__main__':repair.run.main()

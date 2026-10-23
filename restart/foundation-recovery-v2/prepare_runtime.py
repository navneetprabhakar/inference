"""One-time preparation of the approval-bound runtime. No model execution."""
from pathlib import Path
r=Path(__file__).resolve().parent;old=r.parent/'foundation-resolution-v1'
common=(old/'common.py').read_text().replace("read(ROOT/'clock.json')","read(ROOT/phase/'clock.json')")
common=common.replace("{'R0':2000000,'R1':72000000,'R2':82000000}","{'R0':4000000,'D0':0,'R1':42000000,'R2':42000000}").replace('total+n>156000000','total+n>88000000')
common=common.replace("freeze=read(ROOT/f'{phase}-freeze.json')","freeze=read(ROOT/phase/'freeze.json')")
(r/'common.py').write_text(common)
(r/'scorer.py').write_text((old/'scorer.py').read_text())
# Exact recursive checkpoint reload verifier is reused without importing the old trainer.
s=(old/'train.py').read_text();start=s.index('def exact(');end=s.index('\ndef snapshot(',start)
(r/'state_checks.py').write_text('import numpy as np\n'+s[start:end]+'\n')
s=(old/'supervise.py').read_text();s=s[:s.index('\ndef main():')]
s=s.replace("logpath=ROOT/f'{label}-{i}.log'","logpath=ROOT/phase/f'{label}-{i}.log'")
s=s.replace("resources(child.pid)","resources(os.getpid())")
(r/'supervise.py').write_text(s+'\n')
print('Prepared shared runtime without model execution')

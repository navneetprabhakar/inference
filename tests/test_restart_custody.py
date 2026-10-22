import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from slm.restart.custody import profile,runtime_roots,command

pytestmark=pytest.mark.skipif(sys.platform!='darwin',reason='macOS custody integration')

def test_real_process_cannot_read_holdout_symlink_or_network(tmp_path):
    project=Path(__file__).resolve().parents[1]
    allowed=tmp_path/'train';allowed.mkdir(); output=tmp_path/'out';output.mkdir()
    heldout=tmp_path/'sealed.txt';heldout.write_text('SEALED LABELS')
    (allowed/'train.txt').write_text('approved training text')
    (allowed/'link.txt').symlink_to(heldout)
    policy=tmp_path/'trainer.sb';policy.write_text(profile(read_roots=runtime_roots(project)+[allowed],write_root=output))
    script='''
import json,pathlib,socket
import numpy,torch,mlx.core as mx
probe=mx.array([1.,2.],dtype=mx.float32);mx.eval(probe+1);assert (probe+1).tolist()==[2.,3.]
allowed,heldout,output=map(pathlib.Path,__import__('sys').argv[1:])
assert (allowed/'train.txt').read_text()=='approved training text'
results={}
for name,p in [('direct',heldout),('symlink',allowed/'link.txt')]:
 try:p.read_text()
 except PermissionError:results[name]='denied'
 else:raise AssertionError(name+' exposed')
try:heldout.write_text('modified')
except PermissionError:results['outside_write']='denied'
else:raise AssertionError('outside write allowed')
s=socket.socket()
try:s.bind(('127.0.0.1',0))
except PermissionError:results['network']='denied'
else:raise AssertionError('network allowed')
finally:s.close()
(output/'receipt.json').write_text(json.dumps(results))
print(json.dumps(results))
'''
    env=dict(PATH='/usr/bin:/bin',PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(project/'src'),TMPDIR=str(output))
    result=subprocess.run(command(policy,[sys.executable,'-c',script,str(allowed),str(heldout),str(output)]),capture_output=True,text=True,env=env,cwd=output,timeout=45)
    assert result.returncode==0,result.stderr
    assert json.loads((output/'receipt.json').read_text())==dict(direct='denied',symlink='denied',outside_write='denied',network='denied')
    assert heldout.read_text()=='SEALED LABELS'

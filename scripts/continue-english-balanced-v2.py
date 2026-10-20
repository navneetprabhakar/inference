"""Execute the explicitly replanned balanced local control, without cloud calls."""
# Creator: Navneet Prabhakar
import importlib.util
import json
import os
from pathlib import Path
import shutil
from slm.data.stream_hash import sha

OUT=Path('data/english-balanced-local-v2')
CONFIG=Path('configs/english-balanced-local-v2.json')


def main():
    p=json.loads(CONFIG.read_text())
    spec=importlib.util.spec_from_file_location('_bounded_local_control','scripts/continue-english-local.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.OUT=OUT
    module.check_inputs(p)
    if OUT.exists():raise FileExistsError('Retain previous corrected-control attempt')
    root=Path('data/english-balanced-experiment-v2')
    if any((root/name).exists() for name in ['common','mlx','physical.sqlite']):
        raise FileExistsError('Do not duplicate actual corrected training')
    expected=[['common',['scripts/run-english-learning-v2.py','common'],4500],
              ['mlx',['scripts/run-english-learning-v2.py','mlx'],4500],
              ['package',['scripts/package-english-cloud-v2.py'],1800]]
    if p['steps']!=expected:raise ValueError('Reviewed balanced serial steps differ')
    OUT.mkdir();shutil.copyfile(__file__,OUT/'executed-controller.py');shutil.copyfile(CONFIG,OUT/'plan.json')
    module.save(OUT/'process.json',dict(parent=os.getpid(),deadline_unix=p['deadline_unix']))
    try:
        for name,args,seconds in expected:module.run_step(name,args,seconds,p)
        module.save(OUT/'supervisor-terminal.json',dict(complete=True,returncode=0,cloud_resources_created=0,
                                                       scope='Local balanced useful-learning gate/package only; CUDA/main/100conversations pending'))
    except BaseException as error:
        module.save(OUT/'supervisor-terminal.json',dict(complete=False,error_type=type(error).__name__,message=str(error)[:1000],no_automatic_retry=True))
        raise


if __name__=='__main__':main()

"""Collect all trajectory differences without converting a failed gate into a pass."""
import argparse
import json
from pathlib import Path
import numpy as np
from safetensors.numpy import load_file
from slm.common.training import Trainer
from slm.eval.portability import get_batches,capture,compare,environment,memory_snapshot,validate_bundle


def diagnose(bundle,checkpoint,output,backend='mlx',device='cpu',updates=2):
    bundle,output=Path(bundle),Path(output)
    if output.exists():raise FileExistsError(output)
    digest=validate_bundle(bundle)
    env=environment(backend,device)
    trainer=Trainer.resume(checkpoint,get_batches(bundle),backend,device)
    spec=json.loads((bundle/'fixture.json').read_text())
    policy=spec.get('comparison_policy','tiny_fp32_v1')
    start=trainer.step;end=start+updates
    if updates<1 or end>len(trainer.batches.items):raise ValueError('Diagnostic exceeds fixture stream')
    report={'diagnostic_only':True,'accepted_for_training_portability':False,'bundle_hash':digest,
            'environment':env,'comparison_policy':policy,'start_step':start,'end_step':end,'checks':{}}
    try:
        for step in (start,end):
            while trainer.step<step:trainer.update()
            actual=capture(trainer);expected=load_file(str(bundle/f'expected-{step}.safetensors'))
            if actual.keys()!=expected.keys():raise ValueError('Diagnostic tensor set differs')
            failures=[];groups={}
            for name,a in actual.items():
                e=expected[name]
                if a.shape!=e.shape or not np.isfinite(a).all() or not np.isfinite(e).all():
                    raise FloatingPointError('Invalid diagnostic tensor')
                difference=a.astype(np.float64)-e
                norm=float(np.linalg.norm(e.astype(np.float64).ravel()))
                g=groups.setdefault(name.split(':')[0],{'max_abs_error':0.,'max_relative_l2_error':0.})
                g['max_abs_error']=max(g['max_abs_error'],float(np.abs(difference).max()))
                if norm:g['max_relative_l2_error']=max(g['max_relative_l2_error'],float(np.linalg.norm(difference.ravel())/norm))
                try:compare({name:a},{name:e},policy,trainer.config)
                except AssertionError:failures.append(name)
            report['checks'][str(step)]={'policy_checks_passed':not failures,'failed_tensors':failures,'max_errors':groups}
            del actual,expected
        report.update(completed_update_step=trainer.step,processed_tokens=trainer.tokens,
                      supervised_tokens=trainer.supervised_tokens,all_probes_finite=True)
    except Exception as exc:
        report['error']=f'{type(exc).__name__}: {exc}'
        raise
    finally:
        report['memory']=memory_snapshot(backend,device)
        output.parent.mkdir(parents=True,exist_ok=True)
        with output.open('x') as stream:stream.write(json.dumps(report,indent=2)+'\n')
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle',required=True);p.add_argument('--checkpoint',required=True);p.add_argument('--output',required=True)
    p.add_argument('--backend',choices=['mlx','torch'],default='mlx');p.add_argument('--device',default='cpu');p.add_argument('--updates',type=int,default=2)
    a=p.parse_args();r=diagnose(a.bundle,a.checkpoint,a.output,a.backend,a.device,a.updates)
    print(json.dumps({k:v for k,v in r.items() if k!='checks'},indent=2))


if __name__=='__main__':main()

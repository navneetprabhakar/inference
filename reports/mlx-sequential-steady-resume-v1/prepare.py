"""Metadata-only steady/resume activation draft; no launch/model import."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import mlx_sequential_steady as s

def main():
 fit=s.fit.read(s.fit.RUN/'spec.json');s.fit.validate(fit);paths=[s.fit.RUN/n for n in ('spec.json','terminal.json','watchdog.json','ledger.json','result.json')]
 files={str(p):dict(bytes=p.stat().st_size,sha256=s.fit.digest(p))for p in paths};code=dict(fit['code_sha256'])
 new=['mlx_sequential_steady.py','mlx_sequential_native.py','verify_mlx_sequential_steady.py','reports/mlx-sequential-steady-resume-v1/PROTOCOL-DRAFT.md','reports/mlx-sequential-steady-resume-v1/prepare.py']
 code.update({n:s.fit.digest(ROOT/n)for n in new})
 for n,h in code.items():s.require(s.fit.digest(ROOT/n)==h,'changed verified dependency:'+n)
 spec=dict(schema=1,state='pending_root_review',run=str(s.RUN),limits=s.LIMITS,phases=s.PHASES,fit_run=str(s.fit.RUN),fit_spec=fit,python=fit['python'],stop_paths=fit['stop_paths']+[str(s.RUN/'STOP')],proof_files=files,code_sha256=code,execution_identity=dict(name='own124m-sequential-steady-native-v1',fit_spec_sha256=s.fit.read(s.fit.RUN/'launch.json')['spec_sha256'],source=fit['reference_spec']['source_spec']['parent'],strategy_core_sha256=code['mlx_sequential_train_core.py'],native_adapter_sha256=code['mlx_sequential_native.py']))
 out=Path(__file__).with_name('activation-draft.json');s.require(not out.exists(),'immutable draft exists');out.write_text(json.dumps(spec,indent=2)+'\n');print(dict(path=str(out),sha256=s.fit.digest(out)))
if __name__=='__main__':main()

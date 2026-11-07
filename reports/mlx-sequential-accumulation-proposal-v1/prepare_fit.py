"""Metadata-only exact two-update fit draft; never imports a model or launches."""
import json,hashlib,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import mlx_sequential_fit as f

def main():
 source=ROOT/'runs/own-base-mlx-full-benchmark-02';old=f.read(source/'spec.json');receipt=f.read(source/'artifacts/neutral-source.json');meta=receipt['metadata']['neutral'];python=str(ROOT/'.venv-mlx-own-base/bin/python')
 versions=json.loads(subprocess.check_output([python,'-c','import json,sys,importlib.metadata as m; print(json.dumps(dict(python=sys.version,mlx=m.version("mlx"),numpy=m.version("numpy"))))'],text=True))
 names=['spec.json','benchmark-ledger.json','artifacts/neutral-source.npz','artifacts/neutral-source.json','artifacts/ref-updates.npz','artifacts/ref-updates.json','phases/A00-source/result.json','phases/A00-source/watchdog.json','phases/Aupdates-cpu/result.json','phases/Aupdates-cpu/watchdog.json']
 paths=[source/n for n in names]+[Path(meta['source']['path'])]
 paths+=[Path(old['data'][k])for k in ('train_path','validation_path')]
 paths+=[Path(old['source_spec']['parent']['run'])/n for n in ('campaign.json','campaign-spec.json','protected.json')]
 files={str(p):dict(bytes=p.stat().st_size,sha256=f.digest(p))for p in paths}
 code=dict(old['code_sha256']);extra=['mlx_sequential_fit.py','verify_mlx_sequential_fit.py','mlx_sequential_train_core.py','verify_mlx_sequential_train_core.py','reports/mlx-sequential-accumulation-proposal-v1/TWO-UPDATE-FIT-PROTOCOL.md','reports/mlx-sequential-accumulation-proposal-v1/prepare_fit.py']
 code.update({n:f.digest(ROOT/n)for n in extra})
 for n,h in code.items():f.require(f.digest(ROOT/n)==h,'changed frozen dependency:'+n)
 spec=dict(schema=1,state='pending_root_review',run=str(f.RUN),source_run=str(source),python=python,versions=versions,limits=f.LIMITS,updates=2,cache_policy='fixed-clear-every-synchronized-boundary',stop_paths=old['stop_paths']+[str(f.RUN/'STOP')],reference_spec=old,input_files=files,code_sha256=code)
 out=Path(__file__).with_name('fit-activation-draft-r2.json');f.require(not out.exists(),'immutable draft exists');out.write_text(json.dumps(spec,indent=2)+'\n');print(dict(path=str(out),sha256=f.digest(out),input_files=len(files)))
if __name__=='__main__':main()

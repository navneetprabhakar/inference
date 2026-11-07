"""Metadata-only version2 draft; no model/GPU launch."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import mlx_full_benchmark_control_v2 as c

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 run=ROOT/'runs/own-base-mlx-full-benchmark-01';spec=json.loads((run/'spec.json').read_text());ledger=c.read_ledger(run);launch=json.loads((run/'launch.json').read_text());terminal=run/'terminal.json';paths=['launch.json','terminal.json','benchmark-ledger.json','spec.json','phases/A0gradients-cleanup/watchdog.json']
 spec['prior_attempt']=dict(run=str(run),files={n:dict(sha256=sha(run/n),bytes=(run/n).stat().st_size)for n in paths},reserved_targets=ledger['reserved_targets'],committed_targets=ledger['committed_targets'],period_seconds=ledger['period_seconds'],worker_active_seconds=ledger['active_seconds'],elapsed_wall_seconds=terminal.stat().st_mtime-launch['started_wall'],launch_wall=launch['started_wall'],terminal_mtime_ns=terminal.stat().st_mtime_ns)
 c.validate_prior_attempt(spec['prior_attempt']);spec['run']=str(ROOT/'runs/own-base-mlx-full-benchmark-02');spec['state']='pending_root_review';spec['worker']='mlx_full_benchmark_worker_v2.py'
 spec['stop_paths']+= [str(ROOT/'runs/own-base-mlx-full-benchmark-02/STOP')]
 files=['mlx_full_benchmark_control_v2.py','verify_mlx_full_benchmark_control_v2.py','mlx_full_benchmark_worker_v2.py','verify_mlx_full_benchmark_worker_v2.py','reports/mlx-own-base-full-benchmark-v2/PROTOCOL.md','reports/mlx-own-base-full-benchmark-v2/prepare_spec.py','reports/mlx-own-base-full-benchmark-v2/attempt-01-disposable-cleanup.json']
 spec['code_sha256'].update({n:sha(ROOT/n)for n in files})
 for n,h in spec['code_sha256'].items():c.require(sha(ROOT/n)==h,'changed frozen code:'+n)
 out=Path(__file__).with_name('activation-draft.json');c.require(not out.exists(),'immutable draft exists');out.write_text(json.dumps(spec,indent=2)+'\n');print(dict(path=str(out),sha256=sha(out),prior_conservative_seconds=spec['prior_attempt']['elapsed_wall_seconds'],retained_prior_bytes=c.output_bytes(run)))
if __name__=='__main__':main()

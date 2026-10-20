"""Explicit allowlisted private cloud input package; no credentials or cloud mutation."""
# Creator: Navneet Prabhakar
import json,tarfile
from pathlib import Path
from slm.data.stream_hash import sha
from slm.english_learning import compare_learning,save
ROOT=Path('data/english-balanced-experiment-v2');OUT=Path('data/english-training-cloud-package-v2');PREF=Path('data/english-training-cloud-preflight-v1')
def main():
 if OUT.exists():raise FileExistsError(OUT)
 p=json.loads((ROOT/'plan.json').read_text());common=json.loads((ROOT/'common-nll.json').read_text());mx=json.loads((ROOT/'mlx-nll.json').read_text())
 quality=compare_learning(common,mx,.02)
 if not quality['passed']:raise ValueError('Local resumed useful learning must pass before paid CUDA comparison')
 files=set()
 def add(path):
  path=Path(path)
  if not path.exists():raise FileNotFoundError(path)
  candidates=sorted(path.rglob('*')) if path.is_dir() else [path]
  for f in candidates:
   if f.is_symlink():raise ValueError('No archive symlinks')
   if f.is_file() and '__pycache__' not in f.parts:files.add(f)
 add('src')
 for name in ['run-english-learning-v2.py','run-english-learning.py','english-cloud-worker-v2.sh']:add(Path('scripts')/name)
 for f in p['inputs']:
  path=Path(f)
  if path.is_absolute():path=path.relative_to(Path.cwd())
  if str(path).startswith(('src/','scripts/','configs/')):add(path)
 for f in ['configs/current-model-100-conversations-v1.json','configs/main-learning-budget-authorization-v2.json','configs/teacher-extra-80-authorization-v1.json','configs/course-correction-v3.json']:add(f)
 add(p['tokenizer']);add(p['source_model']['model_path'] if not Path(p['source_model']['model_path']).is_absolute() else Path(p['source_model']['model_path']).relative_to(Path.cwd()))
 add('data/english-recovery-corpus-v1');add(p['preliminary']);add(p['prior_physical_ledger']['path']);add(ROOT/'curriculum');add(ROOT/'common')
 for f in ['plan.json','common-nll.json','mlx-nll.json']:add(Path('data/english-recovery-experiment-v1')/f)
 for f in p['inputs']:
  if str(f).startswith('reports/'):add(f)
 for f in ['plan.json','physical.sqlite','baseline-nll.json','common-nll.json','mlx-nll.json','mlx-import.json','common-inference.npz']:add(ROOT/f)
 if (ROOT/'physical.sqlite-journal').exists():raise ValueError('Closed serial physical ledger required')
 total=sum(f.stat().st_size for f in files)
 if total>12*1024**3:raise ValueError('Finite input-package byte limit')
 OUT.mkdir();manifest=dict(creator='Navneet Prabhakar',experiment_root=str(ROOT),plan_sha256=sha(ROOT/'plan.json'),files={str(f):sha(f) for f in sorted(files)},wheels=json.loads((PREF/'wheels.json').read_text()),total_project_bytes=total,mlx_useful_learning=quality,scope='Private allowlist only, no Git/auth/home configuration, teacher raw outputs, unrelated datasets or API credentials.')
 save(OUT/'manifest.json',manifest)
 with tarfile.open(OUT/'inputs.tar.gz','w:gz',compresslevel=1) as tar:
  for f in sorted(files):tar.add(f,arcname='project/'+str(f),recursive=False)
  for name,h in manifest['wheels'].items():
   f=PREF/'wheels'/name
   if sha(f)!=h:raise ValueError('Pinned offline dependency differs')
   tar.add(f,arcname='wheels/'+name,recursive=False)
  tar.add(OUT/'manifest.json',arcname='manifest.json',recursive=False)
 if (OUT/'inputs.tar.gz').stat().st_size>8*1024**3:raise ValueError('Archive byte limit')
 save(OUT/'receipt.json',dict(creator='Navneet Prabhakar',plan_sha256=manifest['plan_sha256'],archive_sha256=sha(OUT/'inputs.tar.gz'),archive_bytes=(OUT/'inputs.tar.gz').stat().st_size,project_files=len(files),wheel_files=len(manifest['wheels']),cloud_resources_created=0));print((OUT/'receipt.json').read_text())
if __name__=='__main__':main()

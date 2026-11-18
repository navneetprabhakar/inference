import hashlib,json,subprocess,tarfile
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[1];R=ROOT/'runs/ganesh-conversation-execution-v1';cfg=json.loads((P/'config-v2.json').read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def cp(src,dst):subprocess.run(['gcloud','storage','cp',src,str(dst),'--quiet'],check=True,capture_output=True,timeout=180)
cp(cfg['backup_prefix']+'/recovery/recovery-backups.json',P/'recovery-backups.json')
r=json.loads((P/'recovery-backups.json').read_text());assert r['status']=='required_backups_verified' and r['writers_joined'] and not r['pilot_started']
assert len(r['checkpoints'])==4 and all(x['receipt']['independent_sha256_readback'] for x in r['checkpoints'])
archive=R/'recovery-evidence.tar.gz';cp(r['evidence']['uri'],archive);assert sha(archive)==r['evidence']['sha256']
out=R/'recovery-evidence';assert not out.exists()
with tarfile.open(archive) as t:
 for m in t.getmembers():
  p=Path(m.name);assert m.isfile() and not p.is_absolute() and '..' not in p.parts
 t.extractall(out,filter='data')
# Compact primary evidence next to the current report.
for rel,name in [('qualification-v2/qualification.json','qualification-failure.json'),('qualification-v2/continuous/result.json','qualification-reference-result.json'),('qualification-v2/split_first/retention-journal.json','failed-upload-journal.json')]:
 (P/name).write_bytes((out/rel).read_bytes())
(P/'local-evidence-readback.json').write_text(json.dumps({'evidence_uri':r['evidence']['uri'],'evidence_sha256':sha(archive),'local_archive':str(archive),'local_full_readback_verified':True,'required_checkpoints':4,'pilot_started':False},indent=2)+'\n')
print('All4qualification checkpoints independently readback verified; evidence downloaded/hash verified locally.')

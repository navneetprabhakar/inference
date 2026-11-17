"""Only redundant archive download copies; originals and verified GCS receipts retained."""
import json,hashlib,datetime
from pathlib import Path
items=[('/opt/english','evidence.tar.gz','evidence-readback.tar.gz','closeout.json','evidence_sha256'),('/opt/english','optimizer-diagnosis-evidence.tar.gz','optimizer-diagnosis-readback.tar.gz','diagnosis-backup.json','sha256'),('/opt/english-eager','evidence.tar.gz','evidence-readback.tar.gz','closeout.json','evidence_sha256')]
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
records=[]
for folder,original,duplicate,receipt,key in items:
 root=Path(folder);a=root/original;b=root/duplicate;r=json.loads((root/receipt).read_text())
 assert a.is_file() and not a.is_symlink() and b.is_file() and not b.is_symlink()
 assert (r.get('evidence_readback') or r.get('full_readback_verified')) and sha(a)==sha(b)==r[key]
 records.append({'removed':str(b),'retained_original':str(a),'sha256':r[key],'bytes':b.stat().st_size,'verified_gcs_receipt':str(root/receipt)});b.unlink()
out=Path('/opt/english-eager/duplicate-readback-cleanup.json');out.write_text(json.dumps({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'removed_only_verified_duplicate_downloads':records},indent=2)+'\n');print(out.read_text())

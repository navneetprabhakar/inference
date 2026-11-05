"""Audited retention limited to complete checkpoints in one owned run directory."""
import hashlib,json,os,re,shutil
from pathlib import Path

def file_sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()

def prune(out, protected):
    out=Path(out).resolve()
    dirs=[p for p in out.glob('checkpoint-*') if p.is_dir() and not p.name.endswith('.partial')]
    dirs.sort(key=lambda p:p.stat().st_mtime,reverse=True)
    keep=set(protected)|{p.name for p in dirs[:2]}
    for p in dirs:
        if p.name in keep:continue
        if p.is_symlink() or p.parent.resolve()!=out or not re.fullmatch(r'checkpoint-\d{12}-\d+',p.name):
            raise RuntimeError('Refusing unrecognized checkpoint path')
        state=json.loads((p/'state.json').read_text())
        model=p/'model.safetensors'
        if state.get('model_sha256')!=file_sha(model):raise RuntimeError('Checkpoint hash mismatch; retained for investigation')
        files=[]
        for child in sorted(p.iterdir()):
            if child.is_symlink() or not child.is_file():raise RuntimeError('Unexpected checkpoint member; retained')
            files.append({'name':child.name,'bytes':child.stat().st_size,'sha256':file_sha(child)})
        record={'checkpoint':p.name,'reason':'superseded generated checkpoint outside latest-two and protected selection','files':files,'status':'deletion_planned'}
        with (out/'retention-manifest.jsonl').open('a') as log:
            log.write(json.dumps(record)+'\n');log.flush();os.fsync(log.fileno())
            shutil.rmtree(p)
            record['status']='deleted';log.write(json.dumps(record)+'\n');log.flush();os.fsync(log.fileno())
    return sorted(keep)

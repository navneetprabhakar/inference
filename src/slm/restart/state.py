"""Atomic, hash-verified fresh-run state bundles. No legacy checkpoint loading."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import numpy as np
from safetensors.numpy import save_file,load_file
from .supervisor import atomic_json


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def publish(root,name,arrays,state,*,identity,storage_cap=4*1024**3):
    root=Path(root).resolve();root.mkdir(parents=True,exist_ok=True)
    if not name or Path(name).name!=name or name.startswith('.') or not identity:raise ValueError('Invalid state identity/name')
    target=root/name
    if target.exists():raise FileExistsError(target)
    if not arrays or any(not isinstance(a,np.ndarray) or a.dtype!=np.float32 or not np.isfinite(a).all() for a in arrays.values()):raise ValueError('State requires finite FP32 arrays')
    required={'step','targets','data_cursor','rng','monitor','ledger_digest','tokenizer_hash','code_hash','config_hash'}
    if not required<=state.keys():raise ValueError('Incomplete state metadata')
    if any(type(state[k]) is not int or state[k]<0 for k in ('step','targets','data_cursor')):raise ValueError('Invalid state counters')
    used=sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
    # Include exact array bytes plus bounded overhead before writing; verify exact total later.
    if used+sum(a.nbytes for a in arrays.values())+1024*1024>storage_cap:raise ValueError('Checkpoint storage budget exhausted')
    stage=Path(tempfile.mkdtemp(prefix='.partial-',dir=root))
    try:
        save_file(arrays,str(stage/'arrays.safetensors'))
        with (stage/'arrays.safetensors').open('rb') as f:os.fsync(f.fileno())
        atomic_json(stage/'state.json',state)
        manifest={'format':'fresh-state-v1','identity':identity,'files':{p:digest(stage/p) for p in ('arrays.safetensors','state.json')}}
        atomic_json(stage/'manifest.json',manifest)
        if sum(p.stat().st_size for p in root.rglob('*') if p.is_file())>storage_cap:raise ValueError('Checkpoint storage budget exhausted')
        os.rename(stage,target)
        fd=os.open(root,os.O_RDONLY)
        try:os.fsync(fd)
        finally:os.close(fd)
    except BaseException:
        shutil.rmtree(stage,ignore_errors=True);raise
    return target


def read(path,*,identity,expected):
    path=Path(path)
    if path.name.startswith('.') or path.is_symlink():raise ValueError('Partial or aliased state forbidden')
    names={'manifest.json','state.json','arrays.safetensors'}
    if {p.name for p in path.iterdir()}!=names or any(p.is_symlink() or not p.is_file() for p in path.iterdir()):raise ValueError('Incomplete/unexpected state files')
    manifest=json.loads((path/'manifest.json').read_text())
    if manifest.get('format')!='fresh-state-v1' or manifest.get('identity')!=identity or set(manifest.get('files',{}))!=names-{'manifest.json'}:raise ValueError('Unauthorized state identity/format')
    if any(digest(path/p)!=h for p,h in manifest['files'].items()):raise ValueError('Corrupt state')
    state=json.loads((path/'state.json').read_text())
    if any(state.get(k)!=v for k,v in expected.items()):raise ValueError('Changed resume contract')
    arrays=load_file(str(path/'arrays.safetensors'))
    if any(a.dtype!=np.float32 or not np.isfinite(a).all() for a in arrays.values()):raise ValueError('Invalid state tensors')
    return arrays,state

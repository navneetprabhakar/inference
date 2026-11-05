"""Publish verified, immutable optimizer-boundary checkpoints; retain two plus pins."""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path

import torch


FILE_NAME = re.compile(r"step-\d+(?:-[0-9a-f]{64})?\.pt")
GIB = 1024**3


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def checksum(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


@contextmanager
def _lock(path, exclusive):
    with (path / ".checkpoint.lock").open("a+b") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        yield


def _atomic_json(path, value):
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False, mode="w") as stream:
        temp = Path(stream.name)
        try:
            json.dump(value, stream)
            stream.flush()
            os.fsync(stream.fileno())
            stream.close()
            os.replace(temp, path)
            sync_dir(path.parent)
        finally:
            temp.unlink(missing_ok=True)


def _filename(name):
    if not isinstance(name, str) or not FILE_NAME.fullmatch(name):
        raise ValueError("invalid checkpoint filename in manifest")
    return name


def _inventory(path):
    entries = json.loads((path / "latest.json").read_text())
    if not isinstance(entries, list) or not 1 <= len(entries) <= 2:
        raise ValueError("invalid checkpoint inventory")
    for entry in entries:
        _filename(entry["file"])
        if not re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]) or entry["bytes"] <= 0:
            raise ValueError("invalid checkpoint checksum or size")
    return entries


def _verified_file(path, entry):
    file = path / _filename(entry["file"])
    if file.is_symlink() or file.stat().st_size != entry["bytes"] or checksum(file) != entry["sha256"]:
        raise ValueError(f"checkpoint checksum or size mismatch: {file.name}")
    return file


def _protected(path):
    pointer = path / "protected.json"
    names = json.loads(pointer.read_text()) if pointer.exists() else []
    if not isinstance(names, list):
        raise ValueError("invalid protected checkpoint inventory")
    return {_filename(name) for name in names}


def protect(path):
    """Pin the current verified checkpoint before advancing its run's latest pointer."""
    with _lock(path, True):
        entry = _inventory(path)[0]
        _verified_file(path, entry)
        _atomic_json(path / "protected.json", sorted(_protected(path) | {entry["file"]}))
        return dict(entry)


def _tensor_bytes(obj):
    if isinstance(obj, torch.Tensor):
        return obj.numel() * obj.element_size()
    if isinstance(obj, dict):
        return sum(_tensor_bytes(v) for v in obj.values())
    if isinstance(obj, (list, tuple)):
        return sum(_tensor_bytes(v) for v in obj)
    return 0


def save(path, state):
    step = state["step"]
    if not isinstance(step, int) or step < 0 or "identity" not in state:
        raise ValueError("missing checkpoint identity or invalid optimizer step")
    with _lock(path, True):
        previous = _inventory(path) if (path / "latest.json").exists() else []
        protected = _protected(path)
        if previous:
            latest = _verified_file(path, previous[0])
            prior = torch.load(latest, map_location="cpu", weights_only=True, mmap=True)
            if prior["identity"] != state["identity"] or prior["step"] > step:
                raise ValueError("refusing to change run identity or rewind the current checkpoint")
            del prior
        estimate = _tensor_bytes(state) + 16 * 1024**2
        if shutil.disk_usage(path).free < estimate + max(20 * GIB, 2 * estimate):
            raise OSError("insufficient free space for atomic checkpoint and disk reserve")
        with tempfile.NamedTemporaryFile(dir=path, suffix=".tmp", delete=False) as stream:
            temp = Path(stream.name)
            try:
                torch.save(state, stream)
                stream.flush()
                os.fsync(stream.fileno())
                stream.close()
                sha = checksum(temp)
                check = torch.load(temp, map_location="cpu", weights_only=True, mmap=True)
                if check["step"] != step or check["identity"] != state["identity"] or check.keys() != state.keys():
                    raise ValueError("checkpoint verification failed")
                del check
                dest = path / f"step-{step:06d}-{sha}.pt"
                os.replace(temp, dest)
                sync_dir(path)
            finally:
                temp.unlink(missing_ok=True)
        entry = dict(file=dest.name, sha256=sha, bytes=dest.stat().st_size)
        keep = [entry] + [e for e in previous if e["file"] != dest.name][:1]
        _atomic_json(path / "latest.json", keep)
        for e in previous:
            if e in keep or e["file"] in protected:
                continue
            # Only remove files whose bytes still agree with the replaced pointer.
            redundant = _verified_file(path, e)
            with (path / "retention.jsonl").open("a") as log:
                log.write(json.dumps(dict(e, reason="replaced resumable checkpoint")) + "\n")
                log.flush()
                os.fsync(log.fileno())
            redundant.unlink()
            sync_dir(path)


def load(path, identity):
    with _lock(path, False):
        entry = _inventory(path)[0]
        file = _verified_file(path, entry)
        state = torch.load(file, map_location="cpu", weights_only=True, mmap=True)
        if state["identity"] != identity:
            raise ValueError("run identity mismatch")
        return state

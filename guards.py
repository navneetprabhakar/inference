"""Exclusive local run guard with preflight and periodic Apple telemetry."""
import ctypes
import fcntl
import json
import math
import os
import re
import shutil
import subprocess
import hashlib
import time


import torch


class ResourceStop(RuntimeError):
    pass


def thermal():
    ctypes.CDLL("/System/Library/Frameworks/Foundation.framework/Foundation")
    objc = ctypes.CDLL("/usr/lib/libobjc.A.dylib")
    objc.objc_getClass.argtypes = [ctypes.c_char_p]
    objc.objc_getClass.restype = ctypes.c_void_p
    objc.sel_registerName.argtypes = [ctypes.c_char_p]
    objc.sel_registerName.restype = ctypes.c_void_p
    address = ctypes.cast(objc.objc_msgSend, ctypes.c_void_p).value
    send = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(address)
    integer = ctypes.CFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p)(address)
    proc = send(objc.objc_getClass(b"NSProcessInfo"), objc.sel_registerName(b"processInfo"))
    return integer(proc, objc.sel_registerName(b"thermalState"))


def swap_mib():
    value = subprocess.check_output(["sysctl", "-n", "vm.swapusage"], text=True, timeout=5)
    match = re.search(r"used = ([\d.]+)([KMG])", value)
    return float(match[1]) * {"K":1/1024, "M":1, "G":1024}[match[2]]


class Guard:
    def __init__(self, path, seconds, *, resume=False):
        if seconds <= 0:
            raise ValueError("elapsed limit must be positive")
        path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = open(path.parent / "mps.lock", "a+")
        self.path = path
        owns_new_path = False
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if not resume:
                path.mkdir(exist_ok=False)
                owns_new_path = True
            self.start = time.monotonic()
            self.last_wall = time.time()
            self.last_mono = self.start
            self.limit = seconds
            meta_path = path / "guard.json"
            if resume:
                meta = json.loads(meta_path.read_text())
                if meta["elapsed_cap"] != seconds:
                    raise ResourceStop("resume would change the run deadline")
                self.wall_start = meta["started"]
                self.swap = meta["baseline_swap_mib"]
            else:
                self.wall_start = self.last_wall
                self.swap = swap_mib()
                sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, timeout=5).strip()
                diff = subprocess.check_output(["git", "diff", "--binary", "HEAD"], timeout=5)
                meta = dict(started=self.wall_start, elapsed_cap=seconds, baseline_swap_mib=self.swap,
                            git_sha=sha, tracked_diff_sha256=hashlib.sha256(diff).hexdigest(),
                            torch=str(torch.__version__), pid=os.getpid(), parent=os.getppid())
                meta_path.write_text(json.dumps(meta, indent=2))
            self.high_rss = self.high_swap = 0
            self.last = -math.inf
            self.check(force=True)
        except BaseException as error:
            self.lock.close()
            if owns_new_path:
                (path / "status.json").write_text(json.dumps(
                    dict(state="stopped", stage="preflight", reason=str(error), timestamp=time.time()),
                    indent=2,
                ))
            raise

    def close(self):
        self.lock.close()

    def check(self, force=False):
        now = time.monotonic()
        wall = time.time()
        if (self.path / "STOP").exists() or (self.path.parent / "STOP").exists():
            raise ResourceStop("explicit STOP")
        if max(now - self.start, wall - self.wall_start) >= self.limit:
            raise ResourceStop("elapsed cap")
        sleep_gap = wall - self.last_wall - (now - self.last_mono)
        self.last_wall, self.last_mono = wall, now
        if abs(sleep_gap) > 2:
            # The descriptor stays open through sleep. Reassert ownership and resample.
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            force = True
        if not force and now - self.last < 30:
            return
        self.last = now
        try:
            state = thermal()
            swap = swap_mib()
            rss = int(subprocess.check_output(["ps", "-o", "rss=", "-p", str(os.getpid())], timeout=5)) / 1024
            disk = shutil.disk_usage(self.path).free / 2**30
            if state not in range(4) or rss <= 0:
                raise ValueError("unreadable guard")
            sample = dict(elapsed=now-self.start, wall_elapsed=wall-self.wall_start, sleep_gap=sleep_gap,
                          thermal=state, rss_mib=rss, swap_mib=swap, swap_growth_mib=swap-self.swap,
                          disk_gib=disk, mps_allocated=torch.mps.current_allocated_memory(),
                          battery=subprocess.check_output(["pmset","-g","batt"],text=True, timeout=5).strip(),
                          pid=os.getpid(), parent=os.getppid(), timestamp=time.time())
            with (self.path / "resources.jsonl").open("a") as log:
                log.write(json.dumps(sample)+"\n")
        except Exception as error:
            raise ResourceStop(f"guard unavailable: {error}") from error
        self.high_rss = self.high_rss + 1 if rss > 18*1024 else 0
        self.high_swap = self.high_swap + 1 if swap-self.swap > 1024 else 0
        if state >= 2 or self.high_rss >= 2 or self.high_swap >= 2 or disk < 20:
            raise ResourceStop(f"resource threshold: {sample}")

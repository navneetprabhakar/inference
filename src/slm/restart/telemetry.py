"""Read actual macOS thermal, global swap, disk and owned process-group RSS."""
import ctypes
import math
import os
import re
import shutil
import subprocess
import sys
import time


def thermal_state():
    if sys.platform!='darwin':raise RuntimeError('macOS thermal telemetry required')
    ctypes.CDLL('/System/Library/Frameworks/Foundation.framework/Foundation')
    objc=ctypes.CDLL('/usr/lib/libobjc.A.dylib')
    objc.objc_getClass.argtypes=[ctypes.c_char_p];objc.objc_getClass.restype=ctypes.c_void_p
    objc.sel_registerName.argtypes=[ctypes.c_char_p];objc.sel_registerName.restype=ctypes.c_void_p
    ptr=ctypes.CFUNCTYPE(ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p)(('objc_msgSend',objc))
    integer=ctypes.CFUNCTYPE(ctypes.c_long,ctypes.c_void_p,ctypes.c_void_p)(('objc_msgSend',objc))
    info=ptr(objc.objc_getClass(b'NSProcessInfo'),objc.sel_registerName(b'processInfo'))
    if not info:raise RuntimeError('NSProcessInfo unavailable')
    value=integer(info,objc.sel_registerName(b'thermalState'))
    if value not in range(4):raise RuntimeError('Unknown thermal status')
    return ['nominal','fair','serious','critical'][value]


def swap_mib():
    text=subprocess.run(['/usr/sbin/sysctl','-n','vm.swapusage'],check=True,capture_output=True,text=True,timeout=5).stdout
    match=re.search(r'\bused\s*=\s*([0-9.]+)([KMG])\b',text)
    if not match:raise RuntimeError('Missing swap telemetry')
    value=float(match[1])*{'K':1/1024,'M':1,'G':1024}[match[2]]
    if not math.isfinite(value):raise RuntimeError('Invalid swap telemetry')
    return value


def group_rss_gib(pgid):
    if type(pgid) is not int or pgid<=1 or pgid==os.getpgrp():raise ValueError('Worker must have its own process group')
    text=subprocess.run(['/bin/ps','-axo','pgid=,rss='],check=True,capture_output=True,text=True,timeout=5).stdout
    rows=[line.split() for line in text.splitlines() if line.strip()]
    values=[int(rss) for group,rss in rows if int(group)==pgid]
    if not values:raise ProcessLookupError('Worker process group is absent')
    return sum(values)/(1024*1024)


def snapshot(pgid,disk_path,baseline_swap):
    return {'now':time.monotonic(),'rss_gib':group_rss_gib(pgid),
            'swap_growth_mib':swap_mib()-baseline_swap,
            'free_disk_gib':shutil.disk_usage(disk_path).free/(1024**3),'thermal':thermal_state()}

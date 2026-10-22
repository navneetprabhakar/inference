"""Independent 900s / 1GB process-tree RSS / 1GB output supervisor.

No automatic launch on import. Parent reviews code-pins before invoking CLI.
"""
import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from shared_clock import shared_clock
from inventory import CAPS,FREE_RESERVE,TERMINAL_RESERVE,INTAKE_ROOT,PROCESSED_CEILING,check_pins,output_size,terminal_write,check_processed_reservation
import shutil

def tree_rss_from_ps(snapshot,root_pid):
    parents={};rss={}
    for line in snapshot.splitlines():
        parts=line.split()
        if len(parts)!=3:continue
        try:pid,ppid,kib=map(int,parts)
        except ValueError:continue
        parents[pid]=ppid;rss[pid]=kib*1024
    if root_pid not in rss:raise ValueError('supervisor_process_missing_from_RSS_snapshot')
    owned={root_pid}
    while True:
        updated=owned|{pid for pid,ppid in parents.items() if ppid in owned}
        if updated==owned:break
        owned=updated
    return sum(rss.get(pid,0) for pid in owned),sorted(owned)

def decision(elapsed,rss,bytes_written,free_bytes):
    if elapsed>=CAPS['seconds']:return 'elapsed_time_cap'
    if rss>CAPS['rss_hard_bytes']:return 'process_tree_RSS_hard_cap'
    if bytes_written>CAPS['output_bytes']-TERMINAL_RESERVE:return 'aggregate_output_byte_cap'
    if free_bytes<FREE_RESERVE:return 'disk_weights_free_floor'
    return None

def kill_group(proc):
    if proc.poll() is None:
        try:os.killpg(proc.pid,signal.SIGTERM)
        except ProcessLookupError:pass
        try:proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try:os.killpg(proc.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            proc.wait(timeout=5)

def supervise(archive,output):
    start=shared_clock();pins=check_pins()
    output.mkdir(parents=True,exist_ok=False)
    terminal_write(output/'supervisor-result.json',{'status':'RUNNING_NOT_COMPLETE'},CAPS['output_bytes'],'supervisor')
    terminal_write(output/'worker-result.json',{'status':'NOT_STARTED_NOT_COMPLETE'},CAPS['output_bytes'])
    try:check_processed_reservation(output,CAPS['output_bytes'])
    except Exception as exc:
        terminal_write(output/'supervisor-result.json',{'status':'PARTIAL_INVENTORY_NO_ADMISSION','reason':str(exc)},CAPS['output_bytes'],'supervisor');return 1
    if shutil.disk_usage(output).free<FREE_RESERVE+CAPS['output_bytes']:
        r={'status':'PARTIAL_INVENTORY_NO_ADMISSION','reason':'supervisor_preflight_disk_reservation','new_admitted_documents':0,'new_admitted_tokens':0}
        terminal_write(output/'supervisor-result.json',r,CAPS['output_bytes'],'supervisor');return 1
    worker=Path(__file__).with_name('inventory.py')
    cmd=[sys.executable,str(worker),'--archive',str(archive.resolve()),'--output',str(output.resolve()),'--supervisor-pid',str(os.getpid()),'--start-monotonic',str(start)]
    peak_rss=0;peak_output=0;target_crossed=False;reason=None;last_pids=[];proc=None
    try:
        with (output/'worker.log').open('xb') as log:
            proc=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            while proc.poll() is None:
                elapsed=shared_clock()-start
                remaining=CAPS['seconds']-elapsed
                if remaining<=0:reason='elapsed_time_cap';kill_group(proc);break
                # Timeout bounds the observation itself; failed observation
                # stops closed rather than asserting the worker is healthy.
                ps=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,timeout=min(1,remaining),check=True)
                rss,last_pids=tree_rss_from_ps(ps.stdout,os.getpid())
                used=output_size(output);free=shutil.disk_usage(output).free
                peak_rss=max(peak_rss,rss);peak_output=max(peak_output,used)
                target_crossed=target_crossed or rss>CAPS['rss_target_bytes']
                reason=decision(shared_clock()-start,rss,used,free)
                if reason is None and output_size(INTAKE_ROOT)>PROCESSED_CEILING:reason='combined_intake64GB_processed_ceiling'
                if reason:kill_group(proc);break
                time.sleep(min(.5,max(0,CAPS['seconds']-(shared_clock()-start))))
            rc=proc.wait(timeout=5)
        result_path=output/'worker-result.json'
        worker_result=json.loads(result_path.read_text()) if result_path.exists() else None
        complete=rc==0 and reason is None and worker_result is not None and worker_result.get('status')=='COMPLETE_SOURCE_INVENTORY_NO_ADMISSION'
        if complete:
            inv=output/'inventory.sqlite3'
            h=hashlib.sha256()
            with inv.open('rb') as f:
                for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
            if h.hexdigest()!=worker_result.get('inventory_sha256'):complete=False;reason='postworker_inventory_hash_mismatch'
        final_decision=decision(shared_clock()-start,peak_rss,output_size(output),shutil.disk_usage(output).free)
        if final_decision:complete=False;reason=reason or final_decision
        result={'status':'COMPLETE_SOURCE_INVENTORY_NO_ADMISSION' if complete else 'PARTIAL_INVENTORY_NO_ADMISSION',
                'reason':reason or (None if complete else 'worker_terminal_or_missing_complete_evidence'),
                'worker_exit_code':rc,'elapsed_seconds':shared_clock()-start,'peak_observed_process_tree_RSS_bytes':peak_rss,
                'rss_target_bytes':CAPS['rss_target_bytes'],'rss_target_crossed':target_crossed,'rss_hard_bytes':CAPS['rss_hard_bytes'],
                'peak_observed_output_bytes':peak_output,'last_observed_process_tree_pids':last_pids,
                'limits':CAPS,'code_pins':pins,'worker_result_sha256':hashlib.sha256(result_path.read_bytes()).hexdigest() if result_path.exists() else None,
                'memory_observation_limit':'RSS observed every0.5seconds; transient peaks between observations are not proven absent.1GB is the explicit observed-RSS stop threshold, not a512MB cap.',
                'new_admitted_documents':0,'new_admitted_tokens':0}
        terminal_write(output/'supervisor-result.json',result,CAPS['output_bytes'],'supervisor');return 0 if complete else 1
    except BaseException as exc:
        if proc is not None:kill_group(proc)
        result={'status':'PARTIAL_INVENTORY_NO_ADMISSION','reason':'supervisor_exception:'+str(exc)[:1500],
                'elapsed_seconds':shared_clock()-start,'new_admitted_documents':0,'new_admitted_tokens':0}
        terminal_write(output/'supervisor-result.json',result,CAPS['output_bytes'],'supervisor');raise

def main():
    p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    raise SystemExit(supervise(a.archive,a.output))

if __name__=='__main__':main()

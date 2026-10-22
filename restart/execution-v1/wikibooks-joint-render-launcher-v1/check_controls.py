"""Real isolated process-group cleanup and pure budget/durability checks."""
import json,os,signal,subprocess,sys,tempfile,time
from pathlib import Path
from unittest.mock import patch
import launch as j

HERE=Path(__file__).resolve().parent
def main():
    checks=[];observations=[]
    assert j.decision(925,0,0,j.rc.FREE_RESERVE,0)=='global_wall_cap_cleanup_reserve';checks.append('global930s_contains5s_cleanup_reserve')
    assert j.decision(0,4_000_000_001,0,j.rc.FREE_RESERVE,0)=='global4GB_observed_owned_tree_RSS_cap';checks.append('owned_process_tree4GB_RSS_stop')
    assert j.decision(0,0,4_000_000_001,j.rc.FREE_RESERVE,0)=='joint4GB_output_cap';checks.append('four_output_combined_cap')
    assert j.decision(0,0,0,j.rc.FREE_RESERVE-1,0)=='joint_disk_weights_free_floor';checks.append('weights_and_free_floor')
    assert j.decision(0,0,0,j.rc.FREE_RESERVE,64_000_000_001)=='joint_combined_intake64GB_cap';checks.append('combined_processed64GB_ceiling')
    tracker=j.Owned(10,[20]);tracker.observe({10:{'pid':10,'ppid':1,'pgid':10,'rss':1,'birth':'root','command':'root'},20:{'pid':20,'ppid':10,'pgid':20,'rss':1,'birth':'old','command':'supervisor'}})
    after=tracker.observe({10:{'pid':10,'ppid':1,'pgid':10,'rss':1,'birth':'root','command':'root'},20:{'pid':20,'ppid':1,'pgid':20,'rss':1,'birth':'new','command':'unrelated'},40:{'pid':40,'ppid':20,'pgid':20,'rss':1,'birth':'newchild','command':'unrelated-child'}})
    assert set(after)=={10};checks.append('PID_reuse_birth_identity_prevents_unrelated_descendant_claim')
    with tempfile.TemporaryDirectory(dir=HERE) as td:
        p=Path(td);events=[];real_fsync=os.fsync;real_replace=os.replace
        def fsync(fd):events.append('fsync');return real_fsync(fd)
        def replace(a,b):events.append('replace');return real_replace(a,b)
        with patch('aggregate.os.fsync',side_effect=fsync),patch('aggregate.os.replace',side_effect=replace):j.aggregate.durable_write(p/'durable.json',{'state':'reserved'})
        assert events==['fsync','replace','fsync'] and json.loads((p/'durable.json').read_text())['state']=='reserved';checks.append('file_fsync_then_replace_then_directory_fsync_real_filesystem')
        # Unrelated sentinel is intentionally orphaned by its short helper so
        # it is outside this test launcher's owned descendant tree.
        sleeper='import time; time.sleep(30)'
        sentinel_helper='import subprocess,sys; p=subprocess.Popen([sys.executable,"-c",'+repr(sleeper)+'],start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); print(p.pid,flush=True)'
        sentinel=int(subprocess.run([sys.executable,'-c',sentinel_helper],capture_output=True,text=True,check=True,timeout=3).stdout)
        parent=None
        try:
            helper='import subprocess,sys; p=subprocess.Popen([sys.executable,"-c",'+repr(sleeper)+'],start_new_session=True); print(p.pid,flush=True); p.wait()'
            parent=subprocess.Popen([sys.executable,'-c',helper],stdout=subprocess.PIPE,text=True,start_new_session=True)
            leaf=int(parent.stdout.readline());tracker=j.Owned(os.getpid(),[parent.pid],root=p)
            owned=tracker.observe(j.snapshot());assert leaf in owned and parent.pid in owned and sentinel not in owned and owned[leaf]['pgid']==leaf
            checks.append('real_separate_session_worker_owned_unrelated_sentinel_excluded')
            result=j.stop_owned(tracker,[parent]);assert result['direct_children_reaped'] and parent.poll() is not None
            after=j.snapshot();assert leaf not in after and sentinel in after
            checks.append('real_worker_group_terminated_parent_reaps_child_launcher_reaps_parent')
            observations.append({'test':'separate_session_cleanup','parent_pid':parent.pid,'worker_pid':leaf,'sentinel_pid':sentinel,'cleanup':result})
            # Registration recovers an owned worker after its supervisor exits.
            marker=p/'fixture-render-worker.py';root=p/'orphan-root';(root/'shard-1').mkdir(parents=True)
            child_args=[sys.executable,'-c',sleeper,str(marker),'--supervisor-pid','PLACEHOLDER','--output',str((root/'shard-1').resolve())]
            orphan_helper='import subprocess,sys,os,json; a='+repr(child_args)+'; a[a.index("PLACEHOLDER")]=str(os.getpid()); c=subprocess.Popen(a,start_new_session=True); print(json.dumps({"supervisor_pid":os.getpid(),"worker_pid":c.pid}),flush=True)'
            orphan_parent=subprocess.Popen([sys.executable,'-c',orphan_helper],stdout=subprocess.PIPE,text=True,start_new_session=True)
            reg=json.loads(orphan_parent.stdout.readline());orphan_parent.wait(timeout=3);reg.update({'worker_script':str(marker.resolve()),'output':str((root/'shard-1').resolve())});j.aggregate.durable_write(root/'shard-1/process-ownership.json',reg)
            tracker2=j.Owned(os.getpid(),[orphan_parent.pid],root=root,worker_script=marker);owned=tracker2.observe(j.snapshot());assert reg['worker_pid'] in owned
            checks.append('durable_registration_recovers_reparented_separate_session_worker')
            result2=j.stop_owned(tracker2,[orphan_parent]);assert reg['worker_pid'] not in j.snapshot();checks.append('registered_orphan_group_terminated_without_unrelated_kill')
            observations.append({'test':'registered_orphan_cleanup','registration':reg,'cleanup':result2})
        finally:
            if parent is not None and parent.poll() is None:
                try:os.killpg(parent.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                parent.wait(timeout=3)
            try:os.killpg(sentinel,signal.SIGKILL)
            except ProcessLookupError:pass
    result={'status':'PASS_REAL_ISOLATED_CONTROL_TESTS_NO_RENDER_SHARD_LAUNCH','check_count':len(checks),'checks':checks,'process_observations':observations,'new_admitted_documents':0,'new_admitted_tokens':0}
    (HERE/'control-check-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()

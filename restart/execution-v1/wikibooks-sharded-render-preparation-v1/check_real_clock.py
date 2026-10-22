"""Real short child-process clock/handshake checks; no source inventory run."""
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

from shared_clock import shared_clock

HERE=Path(__file__).resolve().parent
CHILD='''import sys,os,json
sys.path.insert(0,sys.argv[1])
from shared_clock import shared_clock
import reader_core as inventory
start=float(sys.argv[2]);pid=int(sys.argv[3]);value=shared_clock()
try:
 inventory.validate_supervisor_start(pid,start)
 result={"accepted":True,"clock":value,"elapsed":value-start,"ppid":os.getppid()}
except ValueError as exc:
 result={"accepted":False,"clock":value,"elapsed":value-start,"reason":str(exc),"ppid":os.getppid()}
print(json.dumps(result))
'''

def probe(start,pid):
    p=subprocess.run([sys.executable,'-c',CHILD,str(HERE),str(start),str(pid)],capture_output=True,text=True,check=True,timeout=5)
    return json.loads(p.stdout)

def main():
    observations=[];checks=[]
    for n in range(3):
        before=shared_clock();child=probe(before,os.getpid());after=shared_clock()
        assert child['accepted'] and before<=child['clock']<=after
        observations.append({'parent_before':before,'child':child,'parent_after':after});checks.append('fresh_child_'+str(n+1)+'_inside_parent_CLOCK_MONOTONIC_interval_and_live_parent_binding')
    aged_start=shared_clock()-1
    aged=probe(aged_start,os.getpid());assert aged['accepted'] and 1<=aged['elapsed']<5
    checks.append('inherited_deadline_ages_during_process_startup')
    expired=probe(shared_clock()-901,os.getpid());assert not expired['accepted'];checks.append('expired900second_origin_rejected')
    future=probe(shared_clock()+10,os.getpid());assert not future['accepted'];checks.append('future_clock_origin_rejected')
    wrong_parent=probe(shared_clock(),os.getpid()+100000);assert not wrong_parent['accepted'];checks.append('wrong_direct_supervisor_PID_rejected')
    result={'status':'PASS_REAL_CLOCK_CHILDREN_ONLY_NO_INVENTORY_LAUNCH','checks':checks,'check_count':len(checks),'observations':observations,'aged':aged,'expired':expired,'future':future,'wrong_parent':wrong_parent,'clock_implementation':'time.clock_gettime(time.CLOCK_MONOTONIC)','interpreter':sys.executable,'python':platform.python_version(),'real_source_records_processed':0,'new_admitted_documents':0,'new_admitted_tokens':0}
    (HERE/'real-clock-check-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':main()

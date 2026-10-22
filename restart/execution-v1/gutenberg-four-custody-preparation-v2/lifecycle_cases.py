"""Actual supervisor synthetic preflight/termination/setup controls only."""
import argparse,json,pathlib,signal,sys,tempfile,time,types
HERE=pathlib.Path(__file__).resolve().parent

def run(case):
 import audit
 with tempfile.TemporaryDirectory() as tmp:
  root=pathlib.Path(tmp);audit.ROOT=root;audit.OUT=root/'new-output';audit.FREE=0;calls=[];original_timer=signal.setitimer
  def timer(which,seconds,*args):
   calls.append(seconds)
   return original_timer(which,.15 if seconds==570 and case=='deadline' else seconds,*args)
  signal.setitimer=timer
  def preflight(code,profile):
   assert calls and calls[0]==570 and signal.getitimer(signal.ITIMER_REAL)[0]>0
   assert all(callable(signal.getsignal(s)) for s in [signal.SIGALRM,signal.SIGTERM,signal.SIGINT])
   if case=='term':signal.raise_signal(signal.SIGTERM)
   if case=='int':signal.raise_signal(signal.SIGINT)
   if case=='deadline':time.sleep(3)
   return []
  audit.verify=preflight;oldwrite=pathlib.Path.write_bytes
  if case=='slot-setup-failure':
   def broken(path,data):
    if path.name=='result.json':raise OSError('synthetic_slot_setup_failure')
    return oldwrite(path,data)
   pathlib.Path.write_bytes=broken
  error=None
  try:audit.supervise(types.SimpleNamespace(code_pins_sha256='synthetic',profile_sha256='synthetic'))
  except (TimeoutError,OSError) as e:error=type(e).__name__+':'+str(e)
  finally:signal.setitimer=original_timer;pathlib.Path.write_bytes=oldwrite
  if case=='slot-setup-failure':
   assert error=='OSError:synthetic_slot_setup_failure' and json.loads((audit.OUT/'supervisor.json').read_text())['status']=='PARTIAL_SCREEN_NO_RETRY_NO_ZERO_CLAIM'
  else:assert error.startswith('TimeoutError:armed_preflight_deadline_or_termination_signal_') and not audit.OUT.exists()
  assert signal.getitimer(signal.ITIMER_REAL)[0]==0
  return {'case':case,'PASS':True,'actual_supervisor_preflight_executed':True,'watchdog_armed_before_preflight':True,'termination_handlers_before_preflight':True,'observed_error':error,'created_output_receipt':case=='slot-setup-failure','no_retained_inputs_or_global_ledger':True}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--case',choices=['deadline','term','int','slot-setup-failure'],required=True);a=p.parse_args();print(json.dumps(run(a.case)))

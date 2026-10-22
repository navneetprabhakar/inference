"""Main-thread entire-attempt deadline; independent of cooperative transport checks."""
import os,signal,threading,time
clk=lambda:time.clock_gettime(time.CLOCK_MONOTONIC)
class Guard:
 def __init__(self,global_active_deadline,*,active_seconds=55,external_seconds=60):
  if not 0<active_seconds<external_seconds:raise ValueError('finite_attempt_deadline')
  self.global_active=global_active_deadline;self.active_seconds=active_seconds;self.external_seconds=external_seconds
 def __enter__(self):
  if threading.current_thread() is not threading.main_thread():raise ValueError('attempt_alarm_main_thread_required')
  self.started=clk();self.active=min(self.started+self.active_seconds,self.global_active);self.hard=min(self.started+self.external_seconds,self.global_active+5)
  self.previous=signal.getsignal(signal.SIGALRM)
  signal.signal(signal.SIGALRM,self.expired);signal.setitimer(signal.ITIMER_REAL,max(.001,self.active-clk()));return self
 def expired(self,*args):
  # A stuck cleanup cannot silently turn a 60-second attempt into a profile-long operation.
  signal.signal(signal.SIGALRM,self.hard_exit);signal.setitimer(signal.ITIMER_REAL,max(.001,self.hard-clk()))
  raise TimeoutError('whole_attempt_active_deadline_including_validation_and_receipt')
 def hard_exit(self,*args):
  # Pending durable charges and ownership receipts remain for explicit parent reconciliation.
  os._exit(124)
 def __exit__(self,*args):
  signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,self.previous)
  signal.setitimer(signal.ITIMER_REAL,max(.001,self.global_active-clk()))

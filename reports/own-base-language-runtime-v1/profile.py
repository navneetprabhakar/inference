"""Synthetic metadata profile only; no real corpus/admission/model work."""
import json,time,resource,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from own_base_language_data import MixedSchedule
records=[]
for length in (512,1024):
 p=dict(schema=1,seed=7,length=length,sources=[dict(name='text',passes=3,documents=[dict(id=str(i),tokens=257,family=str(i),split='train',sha256='a'*64) for i in range(170000)])],row_source_cycle=['text']*(8192//length))
 a=time.perf_counter();s=MixedSchedule(p);init=time.perf_counter()-a;state=s.initial();a=time.perf_counter()
 for _ in range(20):_,state=s.next_update(state)
 first20=time.perf_counter()-a;a=time.perf_counter()
 for _ in range(1000):_,state=s.next_update(state)
 next1000=time.perf_counter()-a;a=time.perf_counter();later=s.state_at(12000);reconstruct=time.perf_counter()-a;a=time.perf_counter();s.validate_resume(later);resume=time.perf_counter()-a
 # Fresh instance proves reconstruction is independent of previous cache/state.
 fresh=MixedSchedule(p);a=time.perf_counter();fresh.validate_resume(later);cold=time.perf_counter()-a
 records.append(dict(length=length,documents=170000,passes=3,initialization_seconds=init,first20_updates_seconds=first20,next1000_updates_seconds=next1000,state_at12000_seconds=reconstruct,warm_resume12000_seconds=resume,cold_resume12000_seconds=cold,state_bytes=len(json.dumps(later)),new_targets=later['sources']['text']['unique_targets'],repeated_targets=later['sources']['text']['repeated_targets'],peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))
result=dict(state='synthetic_metadata_profile_not_corpus_admission',helper_sha256=hashlib.sha256((ROOT/'own_base_language_data.py').read_bytes()).hexdigest(),records=records)
Path(__file__).with_name('profile-after.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

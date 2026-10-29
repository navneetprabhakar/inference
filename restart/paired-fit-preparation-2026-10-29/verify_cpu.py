"""Input, matching, ledger, and pair-distance verification; no model calls."""
import json,collections,hashlib,sqlite3
from pathlib import Path
from inputs import FitInputs,read,sha,P,ROOT

def main():
 inp=FitInputs();details={};totals={}
 for arm in ['paired','shuffled']:
  positions=targets=narrative=0;dist=[];before_first=0
  for t in range(256):
   (x,y,m),replay=inp.batch(arm,t,.5);assert x.shape==y.shape==m.shape;assert replay.shape==(8,257);assert (m.sum(axis=1)>0).all();positions+=x.size;targets+=int(m.sum());narrative+=replay[:,:-1].size
   (_,_,_),other=inp.batch('shuffled' if arm=='paired' else 'paired',t,.5);assert (other==replay).all()
  for start in range(0,256,64):
   loc={}
   for t,b in enumerate(inp.schedule[arm][start:start+64]):
    r=inp.rows[b[0]];loc.setdefault(r['pair'],{})[r['side']]=t
   for pair,sides in loc.items():dist.append(abs(sides['before']-sides['after']));before_first+=sides['before']<sides['after']
  totals[arm]=dict(padded_positions=positions,assistant_targets=targets,narrative_targets=narrative)
  details[arm]=dict(pair_instances=len(dist),distance_histogram=dict(sorted(collections.Counter(dist).items())),before_first=before_first,after_first=len(dist)-before_first)
 assert totals['paired']==totals['shuffled']
 for bad in [-1,256]:
  try:inp.batch('paired',bad,.5)
  except ValueError:pass
  else:raise AssertionError('INVALID_CURSOR_ACCEPTED')
 carry=read(P/'carry-forward.json');actual=dict(positions=0,updates=0,assistant=0,narrative=0);seconds=0
 for path,h in carry['sources'].items():
  assert sha(ROOT/path)==h;db=sqlite3.connect(f'file:{ROOT/path}?mode=ro',uri=True)
  vals=db.execute('SELECT SUM(positions),SUM(updates),SUM(assistant),SUM(narrative) FROM events').fetchone();sec,active=db.execute('SELECT seconds,active_start FROM timing').fetchone();assert active is None;db.close();seconds+=sec
  for k,v in zip(actual,vals):actual[k]+=v
 assert actual==carry['charges'];assert abs(seconds-carry['seconds'])<1e-6
 source=ROOT/'restart/foundation-resolution-v1/B/checkpoint.pt';assert sha(source)=='bf45241501cee600bd618677dc1a3ae666e6f50d9c628e29e7326ee9c87d338d'
 result=dict(status='PASS',actual_batches_checked=512,totals_per_arm=totals,ordering=details,read_only_ledger_carry_verified=actual,model_executed=False,optimizer_updates=0)
 (P/'cpu-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()

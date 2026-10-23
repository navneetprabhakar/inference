"""Once-only fresh 50+50 native-token-weighted semantic audit selection."""
import sys,json,sqlite3,hashlib,time,collections
import numpy as np
from common import *
def main():
 check('D0');assert not (ROOT/'D0/fresh-sample.json').exists(),'NO_REDRAW'
 db=sqlite3.connect('file:'+str(ROOT/'payloads/broad-candidate.sqlite')+'?mode=ro',uri=True)
 rows=[dict(h=h,family=f,domain=d,native_content_tokens=n) for h,f,d,n in db.execute('select h,family_component,domain,tokens from clean order by h')]
 frame=hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 save(ROOT/'D0/cohort-freeze.json',dict(frame_sha256=frame,documents=len(rows),native_content_tokens=sum(r['native_content_tokens'] for r in rows),candidate_db_sha256=sha(ROOT/'payloads/broad-candidate.sqlite'),inventory_sha256=sha(ROOT/'D0/inventory.json'),dedup_sha256=sha(ROOT/'D0/dedup.json'),sample_source_sha256=sha(__file__),epoch=time.time(),filter_repair_or_sample_redraw_after_this_point=False,not_admitted=True))
 uniform=sorted(rows,key=lambda r:hashlib.sha256(('20261024\nUNIFORM\n'+r['h']).encode()).digest())[:50]
 cumulative=np.cumsum([r['native_content_tokens'] for r in rows],dtype=np.int64);rng=np.random.default_rng(20261024);positions=rng.integers(0,int(cumulative[-1]),size=50);weighted=[rows[int(np.searchsorted(cumulative,p,side='right'))] for p in positions]
 draws=[dict(**r,mode=mode,draw=i+1) for mode,items in [('uniform',uniform),('token_weighted',weighted)] for i,r in enumerate(items)]
 assert len(draws)==100 and len({r['h'] for r in uniform})==50
 save(ROOT/'D0/fresh-sample.json',dict(status='FROZEN_FRESH_SAMPLE_NOT_REVIEWED',frame_sha256=frame,seed=20261024,draws=draws,uniform_without_replacement=50,native_content_token_weighted_with_replacement=50,weighted_positions=[int(p) for p in positions],unique_documents=len({r['h'] for r in draws}),no_redraw=True,epoch=time.time()))
 save(ROOT/'D0/semantic-review.json',dict(status='IN_PROGRESS_NOT_ADMISSION',reviews=[],sample_sha256=sha(ROOT/'D0/fresh-sample.json'),not_human_certification=True,epoch=time.time()))
 print(json.dumps(dict(frozen_draws=100,unique_documents=len({r['h'] for r in draws}),cohort_documents=len(rows),cohort_native_tokens=int(cumulative[-1]))))
if __name__=='__main__':main()

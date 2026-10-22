"""Not run yet. Parent-reviewed metadata-only selection; no gzip/source text access."""
import sqlite3,json,hashlib,time,signal,argparse
from pathlib import Path
import select_core
D=Path(__file__).resolve().parent;R=D.parent
h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def ident(p):
 s=p.stat(follow_symlinks=False);return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
def main():
 a=argparse.ArgumentParser();a.add_argument('--profile-sha256',required=True);a.add_argument('--code-pins-sha256',required=True);a.add_argument('--execute-metadata-only',action='store_true');a=a.parse_args()
 assert h(D/'profile.json')==a.profile_sha256 and h(D/'code-pins.json')==a.code_pins_sha256
 for p,v in json.loads((D/'code-pins.json').read_text())['SHA256'].items():assert h(Path(p))==v
 if not a.execute_metadata_only:print('STATIC_PREPARATION_VALID_NO_DRAW');return
 clock=lambda:time.clock_gettime(time.CLOCK_MONOTONIC);start=clock()
 def stop(*x):raise TimeoutError('metadata_selection60sec')
 signal.signal(signal.SIGALRM,stop);signal.setitimer(signal.ITIMER_REAL,60)
 profile=json.loads((D/'profile.json').read_text());DB=Path(profile['candidate_frame']['path']);before=ident(DB);assert before==profile['candidate_frame']['stat']
 c=sqlite3.connect(DB.as_uri()+'?mode=ro&immutable=1',uri=True);c.execute('PRAGMA query_only=ON');c.execute('PRAGMA cache_size=-4096');c.execute('PRAGMA mmap_size=0');c.set_progress_handler(lambda: (_ for _ in ()).throw(TimeoutError()) if clock()-start>55 else 0,10000)
 pop=[];counts={k:0 for k in select_core.SETS}
 for row in c.execute('SELECT t.text_SHA256,t.UTF8_bytes,t.M1_content_tokens,t.language_pass,t.explicit_known_hold,t.generic_mask,t.queue_mask,t.first_source,t.first_ordinal,t.prior_reviewed_or_held,r.receipt_JSON_SHA256,r.receipt_zlib,r.receipt_zlib_SHA256,t.receipt_JSON_bytes FROM texts t JOIN receipts r USING(text_SHA256) WHERE language_pass=1 AND explicit_known_hold=0 AND generic_mask=0 AND queue_mask=1'):
  hx,nb,tok,lang,known,mask,queue,sid,ordinal,seen,rawsha,packed,packedsha,n=row
  obj=select_core.decode(packed,packedsha,rawsha,n);k=select_core.stratum(dict(language_pass=lang,explicit_known_hold=known,generic_mask=mask,queue_mask=queue),obj)
  if k:counts[k]+=1;pop.append(dict(text_SHA256=bytes(hx).hex(),text_UTF8_bytes=nb,M1_content_tokens=tok,stratum=k,source_id=sid,ordinal=ordinal,already_seen=seen,policy_receipt_SHA256=bytes(rawsha).hex()))
 chosen=select_core.select(pop)
 for r in chosen:
  sid=r['source_id'];ordinal=r['ordinal'];f=profile['sources'][sid-1]['frame'];p=Path(f['path']);assert ident(p)==f['stat'];db=sqlite3.connect(p.as_uri()+'?mode=ro&immutable=1',uri=True)
  x=db.execute('SELECT line_offset,line_bytes,ends_LF,line_SHA256,text_SHA256,text_UTF8_bytes FROM records WHERE ordinal=?',(ordinal,)).fetchone();db.close();assert ident(p)==f['stat'] and x and bytes(x[4]).hex()==r['text_SHA256'] and x[5]==r['text_UTF8_bytes'];r.update(line_offset=x[0],line_bytes=x[1],ends_LF=x[2],line_SHA256=bytes(x[3]).hex())
 assert ident(DB)==before;c.close();assert counts=={'A_MATH_ONLY':520,'B_FIGURE_ONLY':3505}
 # Selection freezes before any source access; oversized/cost failures retain all outcomes, no reroll.
 textbytes=sum(r['text_UTF8_bytes'] for r in chosen);linebytes=sum(r['line_bytes'] for r in chosen)
 out={'status':'FROZEN_DEVELOPMENT_ONLY_NOT_ACCEPTANCE','seed':select_core.SEED,'population_counts':counts,'draws':[{'mode':r['stratum'],'draw':i%10+1,**r} for i,r in enumerate(chosen)],'selected_capture_occurrences':chosen,'capture_distinct_textSHA':20,'source_body_reads':0,'elapsed':clock()-start,'measured_capture_cost':{'whole_text_bytes':textbytes,'whole_raw_JSON_line_bytes':linebytes,'whole_text_M1_tokens_provisional':sum(r['M1_content_tokens'] for r in chosen),'all_output_preflight_upper_bytes':textbytes+linebytes+8000000,'full_two_gzip_read_bytes':sum(s['raw']['bytes'] for s in profile['sources']),'wholetext_max_bytes':max(r['text_UTF8_bytes'] for r in chosen)},'capture_dispatch_status':'BLOCKED_UNTIL_PARENT_COST_REVIEW_AND_BOUND_CAPTURE_PINS','no_policy_change_no_admission':True}
 target=D/'selection.json'
 with target.open('x') as f:f.write(json.dumps(out,indent=2)+'\n')
 signal.setitimer(signal.ITIMER_REAL,0);print(json.dumps(out['measured_capture_cost']))
if __name__=='__main__':main()

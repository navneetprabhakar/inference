"""Metadata-only deterministic development draws; no source body access."""
import hashlib,bisect
SEED='English-SLM-restart-PressBooks-two-shard-development-v1'
def priority(textsha):return hashlib.sha256((SEED+'\nuniform\n'+textsha).encode()).digest()
def byte_draw(draw,total):
 if total<=0:raise ValueError('positive_byte_population_required')
 bound=(1<<256)-((1<<256)%total)
 for attempt in range(64):
  value=int.from_bytes(hashlib.sha256((SEED+'\nUTF8-byte-with-replacement\n'+str(draw)+'\n'+str(attempt)).encode()).digest(),'big')
  if value<bound:return value%total
 raise ValueError('deterministic_rejection_sampler64cap_no_replacement')
def draws(cohort):
 if len(cohort)<20:raise ValueError('atleast20distincttexthashes')
 rows=sorted(cohort,key=lambda r:r['text_SHA256'])
 if len({r['text_SHA256'] for r in rows})!=len(rows):raise ValueError('duplicate_texthash_population')
 if any(type(r['text_UTF8_bytes']) is not int or r['text_UTF8_bytes']<0 for r in rows):raise ValueError('invalid_UTF8byte_weight')
 uniform=sorted(rows,key=lambda r:(priority(r['text_SHA256']),r['text_SHA256']))[:20]
 cumulative=[];total=0
 for r in rows:total+=r['text_UTF8_bytes'];cumulative.append(total)
 out=[{'mode':'uniform_distinct_textSHA_without_replacement','draw':i+1,'text_SHA256':r['text_SHA256'],'priority_SHA256':priority(r['text_SHA256']).hex()} for i,r in enumerate(uniform)]
 for i in range(1,11):
  n=byte_draw(i,total);r=rows[bisect.bisect_right(cumulative,n)];out.append({'mode':'UTF8_byte_weighted_with_replacement_NOT_tokens','draw':i,'text_SHA256':r['text_SHA256'],'byte_position_zero_based':n})
 return {'seed':SEED,'draws':out,'population_distinct_textSHA':len(rows),'population_UTF8_bytes':total,'capture_distinct_textSHA':len({r['text_SHA256'] for r in out}),'probability_acceptance_sample':False}

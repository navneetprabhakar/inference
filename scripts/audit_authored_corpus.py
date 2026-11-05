"""Post-generation integrity/leakage audit. No inference, training or semantic judge."""
import collections,hashlib,json,re,statistics
from pathlib import Path
import numpy as np
from tokenizers import Tokenizer
from sft_common import ROOT,encode_episode,render
from prepare_continuation import Near,fingerprint

def norm(x):return ' '.join(x.casefold().split())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 src=ROOT/'data/author-only-v2/conversations-2500.jsonl';out=ROOT/'reports/author-review-v1';out.mkdir(exist_ok=True)
 rows=[json.loads(x) for x in src.read_text().splitlines()];manifest=json.loads(src.with_name('manifest.json').read_text());assert len(rows)==2500 and sha(src)==manifest['corpus_sha256']
 tok=Tokenizer.from_file(str(ROOT/'data/sft-v3/tokenizer.json'));protected={};near=Near();protection={};full=[];first=[];lengths=[];targets=[];flags=[];eos=0
 for v in ['sft-v1','sft-v2','sft-v3']:
  for split in ['dev','test']:
   p=ROOT/'data'/v/(split+'.jsonl')
   if not p.exists():continue
   protection[str(p.relative_to(ROOT))]=sha(p)
   for line in p.read_text().splitlines():
    r=json.loads(line)
    for m in r.get('episode',r.get('messages',[])):
     if m['role']=='user' and len(m['content'].split())>=8:
      s=norm(m['content']);protected.setdefault(s,[]).append(str(p.relative_to(ROOT)));near.add(fingerprint(s))
 for r in rows:
  ms=r['messages'];assert len(ms)%2==0 and all(m['role']==('user' if i%2==0 else 'assistant') for i,m in enumerate(ms))
  e=encode_episode(tok,ms);assert e is not None;rids,mask,n=e;assert rids[n-1]==1 and mask[n-2]==1;eos+=1;lengths.append(n);targets.append(int(mask.sum()))
  full.append(norm(render(ms)));first.append(norm(ms[0]['content']))
  rf=[]
  for i,m in enumerate(ms):
   s=norm(m['content'])
   if m['role']=='user' and len(s.split())>=8:
    if s in protected:rf.append({'kind':'heldout_exact_user_turn','turn':i,'source_sets':protected[s]})
    elif near.contains(fingerprint(s)):rf.append({'kind':'heldout_approximate_user_turn','turn':i})
   if m['role']=='assistant':
    words=re.findall(r'\w+',s);grams=[tuple(words[k:k+6]) for k in range(len(words)-5)]
    if len(grams)>len(set(grams)):rf.append({'kind':'repeated_six_word_phrase_review_required','turn':i})
    if re.search(r"\b(i(?:'ve| have) (?:booked|sent|reserved|checked|confirmed)|see you there|let me (?:check|contact|book)|(?:usually|always) home|on page \d+|shelf \d+[a-z]?)\b",s):rf.append({'kind':'possible_unavailable_action_or_observation','turn':i})
  if rf:flags.append({'id':r['id'],'flags':rf})
 dupfirst={s:n for s,n in collections.Counter(first).items() if n>1};dupfull={s:n for s,n in collections.Counter(full).items() if n>1}
 # Candidate near duplicates, using 5-word shingles and exact Jaccard >= .8.
 inverted=collections.defaultdict(set);sets=[];pairs=[]
 for i,r in enumerate(rows):
  w=re.findall(r'\w+',first[i]);ss={tuple(w[j:j+5]) for j in range(len(w)-4)};sets.append(ss)
  if len(ss)<5:continue
  candidates=set()
  for sh in ss:candidates.update(inverted[sh])
  for j in candidates:
   sim=len(ss&sets[j])/len(ss|sets[j])
   if sim>=.8:pairs.append({'a':rows[j]['id'],'b':r['id'],'first_user_fiveword_jaccard':sim})
  for sh in ss:inverted[sh].add(i)
 normalized_categories={'small_talk':'everyday','everyday_planning':'everyday','preferences':'everyday','context_followup':'followup','corrections':'followup','explanations':'explanation','learning':'explanation','simple_reasoning':'explanation','honesty':'clarification','required_repetition':'instruction'}
 result={'corpus_sha256':sha(src),'conversations':len(rows),'provenance':dict(collections.Counter(r['provenance']['method'] for r in rows)),'categories':dict(collections.Counter(normalized_categories.get(r.get('category'),r.get('scenario',{}).get('category',r.get('category'))) for r in rows)),'message_counts':dict(collections.Counter(len(r['messages']) for r in rows)),'student_tokens':{'total':sum(lengths),'min':min(lengths),'median':statistics.median(lengths),'max':max(lengths),'supervised_targets':sum(targets)},'unique_ids':len({r['id'] for r in rows}),'full_normalized_duplicate_groups':len(dupfull),'duplicate_first_user_groups':len(dupfirst),'first_user_near_duplicate_pairs':len(pairs),'supervised_final_eos':eos,'protected_sets':protection,'flagged_conversations':len(flags),'flags_by_type':dict(collections.Counter(f['kind'] for r in flags for f in r['flags'])),'limitations':['All flags require review; repetition may be explicitly requested.','Shared generic questions are not automatically disqualifying leakage.','Exact and near checks do not establish semantic independence.','No factual accuracy score is produced by this script.'],'training_started':False,'paid_api_calls':0}
 for name,obj in [('integrity-and-overlap.json',result),('review-flags.json',flags),('near-duplicate-pairs.json',pairs)]: (out/name).write_text(json.dumps(obj,indent=2)+'\n')
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()

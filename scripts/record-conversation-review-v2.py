"""Direct second review, retaining source-stratum failure instead of waiving it."""
# Creator: Navneet Prabhakar
import collections,json
from pathlib import Path
from slm.data.schema import digest
from slm.data.stream_hash import sha
ROOT=Path('data/conversation-review-v2')
BAD={4:'Invents a provided map when none is supplied; template compliance alone misses unsupported context.',10:'Changes brainstorming possible activities into sharing ideas already, overstating supplied action.',12:'Never answers Paris; a city placeholder is substituted for the requested factual answer.',13:'Initial rewrite removes requested emotional force; subsequent repair does not undo earlier weak targets.',17:'Get money is narrowed to borrowing and avoid at all costs weakened; source meaning changes.',21:'Endorses an erroneous parallelism explanation and changes article recommendations inconsistently across the dialogue.',29:'Adds an unsupported tens-of-thousands downtime cost assertion to attract attention.',37:'Adds access from anywhere to supplied electronic-device access; the location claim is not grounded.',41:'Grammar explanation says remove we were although revised sentence retains were; adverb-placement explanation is misleading.',45:'First rewrite preserves an awkward although I considered construction and changes tense; only later user correction fixes it.',49:'Changes limited engagement into fleeting impact, conflating degree with temporal duration.',53:'Drops the important pajamas detail at first and requires repeated user correction; additional productivity claims are unsupplied.',57:'Rewrites nearly the whole passage before the user requests targeted editing; retain whole-dialogue target defect.',59:'Infers Mrs. Johnson as the mother from an ambiguous case label, introducing an unsupported personal identity.',61:'Claims the rewritten sentence has fewer words although both have16 whitespace-delimited words.'}
def main():
 if (ROOT/'direct-judgments.jsonl').exists():raise FileExistsError('Immutable direct review')
 sample=[json.loads(x) for x in (ROOT/'sample.jsonl').open()];out=[]
 for s in sample:
  i=s['index'];r=s['record'];reason=BAD.get(i,'Complete dialogue read: relevant low-risk instruction, grounded summary, formal transformation or writing exchange; no material observed defect. Source assertions are supplied context, not independently certified facts. Consideration only.')
  out.append(dict(index=i,row_index=r['row_index'],split_group=r['split_group'],source=r['source'],record_sha256=digest(r),sample_sha256=sha(ROOT/'sample.jsonl'),full_text_read=True,human_attestation=False,review_mode='delegated_expert',judgment='exclude' if i in BAD else 'consider',reason=reason,training_approved=False))
 with (ROOT/'direct-judgments.jsonl').open('x') as f:
  for r in out:f.write(json.dumps(r,sort_keys=True)+'\n')
 strata={}
 for source in sorted({r['source'] for r in out}):
  subset=[r for r in out if r['source']==source];bad=sum(r['judgment']!='consider' for r in subset);strata[source]=dict(read=len(subset),nonapprovals=bad,fraction=bad/len(subset),passed=bad/len(subset)<=.25)
 report=dict(creator='Navneet Prabhakar',complete=True,fully_read=64,counts=dict(collections.Counter(r['judgment'] for r in out)),nonapproval_fraction=len(BAD)/64,maximum_nonapproval_fraction=.25,passed=len(BAD)/64<=.25,strata=strata,training_approved=False,source_rule='Only passing constituent strata may be considered for bounded private research; observed excluded components always withheld. Failing magpie stratum is not admitted by aggregate pass.',human_attestation=False,sample_sha256=sha(ROOT/'sample.jsonl'),journal_sha256=sha(ROOT/'direct-judgments.jsonl'),scope='Second purposive source-stratified review after an explicit narrower rule; not a population failure estimate or individual approval for unread rows.')
 (ROOT/'report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()

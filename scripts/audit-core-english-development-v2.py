"""Preserve v1 and clarify fallible self-check criteria before any suite capture."""
# Creator: Navneet Prabhakar
import json,struct,time
from pathlib import Path
from slm.data.schema import digest
from slm.data.stream_hash import sha
from slm.data.conversation_grouping import Query
ROOT=Path('data/core-english-development-v1')
AMENDMENTS={24:'Accurately state whether the actual previous request specifies a quantity; the original user supplied no quantity. Do not deny a quantity that the student itself invented.',33:'Accurately report whether the actual previous statement asserts completion. The requested negative statement should deny completion, but an earlier error must not force a false self-check.',37:'Accurately report whether the actual previous invitation makes attendance compulsory. An invitation should be optional, but do not misdescribe an earlier erroneous command.',44:'Accurately state whether the actual previous message gives a reason. The user requested no reason; acknowledge one if the student previously invented it.',57:'Accurately state whether the actual previous caption names a city. The user supplied no city; do not deny a city that the student itself invented.'}
def main():
 out=ROOT/'protocol-v2.json'
 if out.exists():raise FileExistsError(out)
 original=json.loads((ROOT/'protocol.json').read_text());p=json.loads((ROOT/'protocol.json').read_text())
 for c in p['conversations']:
  if c['id'] in AMENDMENTS:c['turns'][2]['success_criterion']=AMENDMENTS[c['id']]
 # Case37 is the17th editing scenario: invitation, rather than an unrelated amendment.
 for a,b in zip(original['conversations'],p['conversations']):
  if a['id']!=b['id'] or [t['user'] for t in a['turns']]!=[t['user'] for t in b['turns']]:raise ValueError('Never replace cases/user requests during criterion review')
 bindings={str(ROOT/'protocol.json'):sha(ROOT/'protocol.json'),str(ROOT/'manifest.json'):sha(ROOT/'manifest.json'),str(Path(__file__)):sha(__file__)};start=time.monotonic();checks={}
 paths=[('prose','data/global-prefix-grouping-v2/index','data/prefix-near-benchmark-v1/ordering-counts.bin'),('smol','data/conversation-groups-v1/index','data/prefix-near-benchmark-v1/ordering-counts.bin'),('qa','data/grounded-qa-groups-v2/index','data/grounded-qa-groups-v2/ordering-counts.bin')]
 for name,index,ordering in paths:
  order={}
  with Path(ordering).open('rb') as f:
   while b:=f.read(36):order[b[:32]]=struct.unpack('<I',b[32:])[0]
  q=Query(index,order,2000000);first=[];whole=[];generic=[]
  for c in p['conversations']:
   if time.monotonic()-start>1800:raise TimeoutError('Finite development scenario audit')
   if q.matches(c['turns'][0]['user']):first.append(c['id'])
   if q.matches('\n'.join(t['user'] for t in c['turns'])):whole.append(c['id'])
   for t in (1,2):
    if q.matches(c['turns'][t]['user']):generic.append([c['id'],t+1])
  checks[name]=dict(first_scenario_request_near_hits=first,whole_request_sequence_near_hits=whole,generic_followup_near_hits=generic,verified_candidate_comparisons=q.pairs,maximum_comparisons=2000000,ordering_sha256=sha(ordering));q.close()
 p['criterion_review']='Five self-check criteria clarified before capture; all100case requests/order retained. Judge current requests using actual student history, even when an earlier student reply failed. Correct behavior on a later turn is not automatically denied because an earlier turn failed.'
 p['kind']='authored-core-english-development-v2';out.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n')
 report=dict(creator='Navneet Prabhakar',complete=True,training_approved=False,human_attestation=False,all100_scenarios_and300_requests_preserved=True,amended_third_turn_criteria=AMENDMENTS,original_protocol_sha256=sha(ROOT/'protocol.json'),revised_protocol_sha256=sha(out),grouping_checks=checks,source_bindings=bindings,scope='Pre-capture criterion clarification, not repair of student answers or score-based case selection. First/full request exact17-of20near checks are literal scenario checks only; generic English followups and skills may recur. No claim that all broad English task types are unseen, and no semantic/paraphrase-family certification. New authored development cases, not a random population sample or untouched final test.')
 (ROOT/'audit-v2.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()

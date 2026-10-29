"""Report predeclared fit gates and paired differences from completed outputs only."""
import json,collections
from pathlib import Path
P=Path(__file__).resolve().parent;PRE=P.parent/'paired-fit-preparation-2026-10-29'
def read(p):return json.loads(p.read_text())
def lines(p):return [json.loads(x) for x in p.read_text().splitlines()]
def norm(x):return ' '.join(x.casefold().strip().split())
def main():
 records=read(PRE/'private/fit-records.json');dev=read(PRE/'private/development.json');meta={r['id']:r for r in records};dm={r['id']:r for r in dev};all_results={};pair_outcomes={}
 for arm in ['source','paired','shuffled']:
  folder=P/'private'/arm/'evaluation';fit=lines(folder/'fit.jsonl');development=lines(folder/'development.jsonl');summary=read(folder/'summary.json');by=collections.defaultdict(dict)
  assert len(fit)==1408 and len(development)==176
  for r in fit:assert r['turn'] not in by[r['id']];by[r['id']][r['turn']]=r
  assert len(by)==1024
  pairs=collections.defaultdict(dict)
  for id,r in meta.items():pairs[(r['view'],r['pair'])][r['side']]=id
  cells={};outcomes={};changed=collections.defaultdict(lambda:dict(both_correct=0,unchanged_answer=0,total=0));state=collections.defaultdict(lambda:dict(correct=0,total=0))
  for (view,pair),members in pairs.items():
   a,b=by[members['before']],by[members['after']];family=meta[members['before']]['scenario']['family'];key=f'{family}|v{view}';cell=cells.setdefault(key,dict(both_correct=0,total=0));correct=all(r['complete'] for r in list(a.values())+list(b.values()));cell['both_correct']+=correct;cell['total']+=1;outcomes[(view,pair)]=correct
   for t in ([1] if family=='clarification' else [0,1,2] if family=='state' else [0]):
    assert norm(a[t]['expected'])!=norm(b[t]['expected']);c=changed[key];c['both_correct']+=a[t]['complete'] and b[t]['complete'];c['unchanged_answer']+=norm(a[t]['response'])==norm(b[t]['response']);c['total']+=1
  for r in fit:
   if r['family']=='state':c=state[str(r['turn'])];c['correct']+=r['complete'];c['total']+=1
  strata={}
  for r in development:
   m=dm[r['id']];keys=[r['family'],r['family']+'|'+m['scope'],r['family']+'|'+m['style']]
   if r['family']=='name':keys+=['name|'+('new_components' if int(r['id'].split('-')[1])>=32 else 'familiar_name')]
   if r['family'] in ['distractor','state'] and m['scenario']['color']!=m['scenario']['other_color']:keys += [r['family']+'|unequal_initial_distractor']
   for k in keys:c=strata.setdefault(k,dict(correct=0,total=0));c['correct']+=r['complete'];c['total']+=1
  all_results[arm]=dict(fit_pairs=cells,fit_gate=all(c['both_correct']>=29 and c['total']==32 for c in cells.values()),changed_answer=dict(changed),state_turns=dict(state),development=strata,fit_correct_turns=sum(r['complete'] for r in fit),development_correct_turns=sum(r['complete'] for r in development),teacher_loss=summary['teacher_loss'],native_nll=summary['native_nll']['nll'],termination_failures=sum(not r['terminal'] for r in fit+development));pair_outcomes[arm]=outcomes
 source=all_results['source']['native_nll']
 for a,r in all_results.items():r['native_nll_ratio']=r['native_nll']/source;r['research_nll_guard']=r['native_nll_ratio']<=1.65
 a,b=pair_outcomes['paired'],pair_outcomes['shuffled'];comparison=dict(paired_gains=sum(a[k] and not b[k] for k in a),paired_losses=sum(b[k] and not a[k] for k in a),pair_presentations=len(a),underlying_semantic_pairs=256)
 result=dict(status='COMPLETED_REASSESSED',arms=all_results,comparison=comparison,promotion=False,limitation='One seed, small synthetic fit;view repeats are not independent;ordering includes orientation;development is not paired transfer or acceptance.')
 (P/'assessment.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({'comparison':comparison,'arms':{k:{x:v[x] for x in ['fit_gate','fit_correct_turns','development_correct_turns','native_nll','native_nll_ratio','research_nll_guard']} for k,v in all_results.items()}},indent=2))
if __name__=='__main__':main()

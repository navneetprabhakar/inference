import sys,json,collections,math
from pathlib import Path
P=Path(__file__).resolve().parent;PRE=P.parent/'tiny-copy-preparation-2026-10-29';sys.path.insert(0,str(PRE));from metrics import summarize,select_lr

def read(p):return json.loads(p.read_text())
def lines(p):return [json.loads(x) for x in p.read_text().splitlines()]
def token_stats(rows):
 out={}
 for kind in ['answer','eos']:
  ts=[t for r in rows for t in r['tokens'] if t['eos']==(kind=='eos')];out[kind]=dict(correct=sum(t['expected']==t['predicted'] for t in ts),total=len(ts),mean_nll=sum(t['nll'] for t in ts)/len(ts))
 out['first_error_positions']=dict(collections.Counter(str(r['first_error']) for r in rows));return out

def failure_stats(records,outputs):
 by={r['id']:r for r in records};bad=[];copied_distractor=0;components=[0,0];terminal=0
 for o in outputs:
  r=by[o['id']];pred=o['response'].strip();copied_distractor+=r['scope']=='distractor' and pred==r['distractor_value'];terminal+=o['terminal'];sep=' ' if r['family']=='name' else ':';actual=pred.split(sep);expected=r['value'].split(sep)
  for i in [0,1]:components[i]+=len(actual)==2 and actual[i]==expected[i]
  if not o['complete']:bad.append(dict(id=r['id'],expected=r['value'],response=o['response'],eos=o['eos']))
 return dict(total=len(outputs),terminal=terminal,component1_correct=components[0],component2_correct=components[1],distractor_copies=copied_distractor,wrong_examples=bad[:8])

def main():
 result=read(P/'result.json');fit=read(PRE/'private/fit.json');dev=read(PRE/'private/transfer.json');source=read(P/'private/source/summary.json');selection=read(P/'selection.json');assert select_lr(selection['endpoint_training_losses'],selection['source_training_losses'])==result['selected_lr'];arms={}
 for arm in result['arms']:
  folder=P/'private'/arm['arm'];rs=[r for r in fit if r['family']==arm['family']];measurements={}
  for step in [64,128]:
   outputs=lines(folder/'evaluation'/f'{step}-fit.jsonl');cells=summarize(rs,outputs);ts=read(folder/'evaluation'/f'{step}-teacher.json');measurements[str(step)]=dict(cells=cells,fit_pass=all(c['passes'] for c in cells.values()),correct=sum(c['correct'] for c in cells.values()),teacher_tokens=token_stats(ts),failures=failure_stats(rs,outputs),loss=read(folder/'evaluation'/f'{step}-summary.json')['loss'])
  record=dict(family=arm['family'],lr=arm['lr'],fit=measurements,native_nll=arm['native_nll'],native_ratio=arm['native_nll']/source['native']['nll'],research_retention_guard=arm['native_nll']/source['native']['nll']<=1.65,selected=arm['lr']==result['selected_lr'])
  if record['selected']:
   ds=[r for r in dev if r['family']==arm['family']];outputs=lines(folder/'transfer.jsonl');cells=summarize(ds,outputs);record['transfer']=dict(cells=cells,pass_gate=all(c['passes'] for c in cells.values()),correct=sum(c['correct'] for c in cells.values()),failures=failure_stats(ds,outputs))
  else:assert not (folder/'transfer.jsonl').exists()
  arms[arm['arm']]=record
 selected=[r for r in arms.values() if r['selected']];out=dict(status='COMPLETED_REASSESSED',selected_lr=result['selected_lr'],selected_fit_pass=all(r['fit']['128']['fit_pass'] for r in selected),selected_transfer_pass=all(r['transfer']['pass_gate'] for r in selected),selected_research_retention_pass=all(r['research_retention_guard'] for r in selected),source_native_nll=source['native']['nll'],arms=arms,promotion=False)
 (P/'assessment.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='arms'},indent=2))
 for a,r in arms.items():print(a,'fit',r['fit']['64']['correct'],r['fit']['128']['correct'],'loss',r['fit']['128']['loss'],'NLLratio',r['native_ratio'],'transfer',r.get('transfer',{}).get('correct'))
if __name__=='__main__':main()

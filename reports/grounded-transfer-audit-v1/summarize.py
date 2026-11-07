"""CPU-only descriptive analysis of completed transfer-audit artifacts; never polls."""
import argparse,hashlib,json,math,statistics
from pathlib import Path

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def require(value,message):
 if not value:raise ValueError(message)

def summarize(selection,events,terminal):
 require(terminal.get('state')=='completed_transfer_audit_not_acceptance','completed foreground terminal required')
 cases={(c['role'],c['split'],c['doc_id'],c['turn']):c for c in selection['cases']}
 completed=[e for e in events if e['event']=='case_completed'];seen=set();groups={};behavior={};rows=[]
 for e in completed:
  ident=e['identity'];key=tuple(ident[x]for x in ('role','split','doc_id','turn'));require(key in cases and key not in seen,'unknown/duplicate completed case');seen.add(key);case=cases[key]
  require(all(ident[k]==case[k]for k in ('family','donor_doc_id','donor_turn')),'case provenance mismatch')
  require(e['swap_equal']==case['swap_equal'],'swap equality differs')
  require(set(e['ce'])=={'correct','swapped'},'paired variants required')
  require(set(e['ce']['correct'])==set(e['ce']['swapped'])==set(case['correct']['groups']),'CE category mismatch')
  pair=dict(identity=ident,swap_equal=e['swap_equal'],categories={})
  for category in e['ce']['correct']:
   values=e['ce'];n=values['correct'][category]['targets'];require(n==values['swapped'][category]['targets']==len(case['correct']['groups'][category]) and n>0,'paired target count differs')
   losses={variant:values[variant][category]['loss_sum']for variant in ('correct','swapped')};require(all(isinstance(x,(int,float)) and math.isfinite(x) and x>=0 for x in losses.values()),'invalid CE loss')
   group=groups.setdefault((key[0],key[1],category),dict(rows=0,targets=0,correct_loss_sum=0.,swapped_loss_sum=0.,paired_row_deltas=[],equal_swaps=0))
   group['rows']+=1;group['targets']+=n;group['correct_loss_sum']+=losses['correct'];group['swapped_loss_sum']+=losses['swapped'];delta=(losses['swapped']-losses['correct'])/n;group['paired_row_deltas'].append(delta);group['equal_swaps']+=int(e['swap_equal'])
   pair['categories'][category]=dict(targets=n,correct_ce=losses['correct']/n,swapped_ce=losses['swapped']/n,delta_swapped_minus_correct=delta)
  expected=case['expected_first_frame'];known='call'if 'call'in expected else'text';b=behavior.setdefault((key[0],key[1],known),dict(rows=0,protocol_valid=0,exact_teacher_frame_match=0,generated_call=0,generated_text=0,invalid=0))
  valid=e['parsed']is not None and e['protocol_failure']is None;match=valid and e['parsed']==expected
  require(e['exact_teacher_frame_match']==match,'stored exact-match inconsistent')
  b['rows']+=1;b['protocol_valid']+=valid;b['exact_teacher_frame_match']+=match
  if valid:require(set(e['parsed'])in ({'call'},{'text'}),'invalid parsed schema');b['generated_call'if'call'in e['parsed']else'generated_text']+=1
  else:b['invalid']+=1
  pair.update(expected_first_frame=expected,parsed=e['parsed'],raw=e['raw'],protocol_failure=e['protocol_failure'],exact_teacher_frame_match=match);rows.append(pair)
 require(seen==set(cases),'incomplete planned denominator')
 wt=terminal.get('worker_terminal',{});require(wt.get('completed_rows')==len(cases) and wt.get('planned_histories')==48,'terminal denominator mismatch')
 summary=[]
 for (role,split,category),g in sorted(groups.items()):
  ds=g.pop('paired_row_deltas');n=g['targets'];summary.append(dict(role=role,split=split,category=category,**g,correct_tokenweighted_ce=g['correct_loss_sum']/n,swapped_tokenweighted_ce=g['swapped_loss_sum']/n,tokenweighted_delta=(g['swapped_loss_sum']-g['correct_loss_sum'])/n,paired_row_delta_mean=statistics.mean(ds),paired_row_delta_median=statistics.median(ds),paired_row_delta_min=min(ds),paired_row_delta_max=max(ds),rows_positive_delta=sum(x>0 for x in ds)))
 return dict(state='complete_descriptive_analysis_not_acceptance',planned_rows=len(cases),completed_rows=len(seen),conditioning=summary,first_frame=[dict(role=k[0],split=k[1],teacher_frame=k[2],**v)for k,v in sorted(behavior.items())],paired_rows=rows,interpretation='Positive swapped-minus-correct CE means correct current-user text predicts fixed targets better. Local out-of-distribution swap only; teacher observations and earlier teacher turns remain. Readback and conditioned-call categories cannot establish autonomous tool selection. Exact teacher match is diagnostic, not semantic or acceptance certification.')

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path);p.add_argument('output',type=Path);a=p.parse_args();require(not a.output.exists(),'immutable fresh output required')
 spec=read(a.run/'spec.json');selectionpath=Path(spec['selection']['path']);require(digest(selectionpath)==spec['selection']['sha256'],'selection changed');selection=read(selectionpath)
 events=[json.loads(line)for line in (a.run/'events.jsonl').read_text().splitlines()];terminal=read(a.run/'terminal.json');result=summarize(selection,events,terminal)
 result['artifact_sha256']={str(p):digest(p)for p in (selectionpath,a.run/'spec.json',a.run/'events.jsonl',a.run/'terminal.json',Path(__file__))}
 a.output.write_text(json.dumps(result,indent=2)+'\n');print({k:result[k]for k in ('state','planned_rows','completed_rows')})
if __name__=='__main__':main()

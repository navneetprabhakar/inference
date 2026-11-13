"""Read-only review aggregation; does not infer acceptance from teacher verdicts."""
import datetime,json
from pathlib import Path
report=Path('reports/l4-qualification-v1/long-context-campaign-v3');root=Path('runs/long-context-campaign-v3')
roots=[p.parent for p in sorted(root.glob('*/root-review.json'))]
rows=[];unique=set();sources=[]
for d in roots:
 review=json.loads((d/'root-review.json').read_text());metrics={r['id']:r for r in json.loads((d/'verification.json').read_text())['rows']}
 sources.append([str(d.relative_to('runs')),'train'])
 for row in review['reviews']:
  unique.add(row['id']);rows.append({**row,**{k:v for k,v in metrics[row['id']].items() if k not in ['sha256','id']},'root':str(d)})
selected=[r for r in rows if r['selected_for_supplement']]
state={'updated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'full_dialogues_reviewed':len(rows),'unique_scenarios_reviewed':len(unique),'content_pass':sum(r['content_pass'] for r in rows),'selected_pending_admission':len(selected),'new_assistant_targets':sum(r.get('assistant_targets',0) for r in selected),'new_assistant_targets_after_3072':sum(r.get('assistant_targets_after_3072',0) for r in selected),'selected_with_at_least_128_late_targets':sum(r.get('assistant_targets_after_3072',0)>=128 for r in selected),'selected_tool_calls':sum(r['replayed_calls'] for r in selected),'admitted_by_this_script':0,'actual_trained_targets':0}
(root/'review-progress.json').write_text(json.dumps(state,indent=2)+'\n');(report/'reviewed-sources.json').write_text(json.dumps(sources,indent=2)+'\n');print(json.dumps(state,indent=2))

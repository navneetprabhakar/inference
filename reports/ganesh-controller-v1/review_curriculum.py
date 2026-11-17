"""Second-pass data audit. Independent implementation, same author/reviewer."""
import json,hashlib,collections,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from cloud_training.nano_tool_lessons import validate_lesson
P=ROOT/'reports/ganesh-english-curriculum-v2'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
expected={
'parcel_shelf':'E','book_club_lead':'Arun.','ticket_name':'Dev Menon','display_order':'Pottery.','collection_day':'Saturday','plant_choice':'Fern and orchid.',
 'tea_preference':'You prefer your tea without sugar.','repair_colour':'The legs.','museum_bag':'At the museum desk.','borrow_return':'Priya.','nickname_boundary':'Finch.','task_constraint':'You asked for an activity that is not noisy.',
 'spare_key':'In the desk drawer.','stage_part':'Mira.','printing_finish':'Matte.','train_window':'Yellow.','folder_contents':'The grey folder.','visitor_limit':'No. You specified an adults-only gathering.','speaker_details':'Vik.'}
review=json.loads((P/'review.json').read_text());records={r['id']:r for r in review['records']}
results=[];seen=set();calls=0
for split,file in [('train','train.jsonl'),('development','development.jsonl')]:
 for line in (P/file).read_text().splitlines():
  row=json.loads(line);group=row['provenance']['source_group'];ident=row['id'];seen.add(group)
  references=[m['content'] for m in row['messages'] if m['role']=='assistant' and 'content' in m]
  rec=records[ident]
  assert rec['row_sha256']==hashlib.sha256(json.dumps(row,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
  assert [t['reference'] for t in rec['turns']]==references
  assert len(rec['turns'])==len(row['policies']) and all(t['pass'] is True and t['reason'] for t in rec['turns'])
  if group in expected:assert references[-1]==expected[group],group
  if group=='catalogue_label':assert len(references[1].split())==3
  if group=='weather_wording':assert len(references[1].split())==2
  if row['family']=='tools':calls+=validate_lesson(row)['actual_calls']
  results.append({'id':ident,'split':split,'all_turn_references_rechecked':True,'critical_state_oracle':group in expected,'pass':True})
assert set(expected)<=seen
stats=review['stats'];identity=stats['train']['families']['model_identity']['assistant_targets']/stats['train']['assistant_targets']
assert identity<=.05
for split in ('train','development'):
 mass=stats[split]['target_mass_by_mode'];total=sum(mass.values())
 assert mass['enabled_no_call']/total>=.2 and mass['disabled_no_call']/total>=.2 and mass['enabled_call']/total>=.05
for n,h in json.loads((P/'freeze.json').read_text())['files'].items():assert sha(P/n)==h
result={'status':'pass_pilot_data_only','reviewer':'Same Codex agent, second semantic pass and separate validator; not independent release review','rows':len(results),'user_turns':sum(sum(s['turn_modes'].values()) for s in stats.values()),'critical_state_checks':len(expected),'tool_calls_replayed':calls,'identity_target_fraction':identity,'records':results,'limitations':['31train sessions/1052unique target positions is a small seed pilot, not broad English curriculum sufficiency.','Development has related structural skills and is exposed, not sealed release.','No near2K context or general conversation release claim.'],'v1_rejected':'Identity share exceeded proposed5%ceiling; redundant fourth identity lesson omitted in v2.'}
(ROOT/'reports/ganesh-controller-v1/curriculum-adverse-review.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ('status','rows','user_turns','critical_state_checks','tool_calls_replayed','identity_target_fraction')}))

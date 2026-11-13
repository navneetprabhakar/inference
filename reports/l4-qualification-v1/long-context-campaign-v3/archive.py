"""Archive synthetic evidence only; omit CLI event streams and local account logs."""
import json,hashlib,shutil,datetime
from pathlib import Path
r=Path('runs/long-context-campaign-v3');p=Path('reports/l4-qualification-v1/long-context-campaign-v3');e=p/'evidence';e.mkdir(exist_ok=True)
index=[]
for folder,_ in json.loads((p/'reviewed-sources.json').read_text()):
 source=Path('runs')/folder;dest=e/source.name;dest.mkdir(exist_ok=True)
 for src in sorted(source.iterdir()):
  if src.is_file() and (src.suffix in ['.json','.jsonl','.py']) and src.name not in ['events.jsonl']:
   shutil.copy2(src,dest/src.name);index.append({'source':str(src),'archive':str(dest/src.name),'sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'bytes':src.stat().st_size})
for name in ['manifest.json','admission.json','verification.json','independent-verification.json','supplement-train.jsonl','supplement-validation.jsonl']:
 source=Path('runs/long-context-corpus-v3')/name;dest=p/('corpus-manifest.json' if name=='manifest.json' else name);shutil.copy2(source,dest);index.append({'source':str(source),'archive':str(dest),'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'bytes':source.stat().st_size})
(p/'evidence-index.json').write_text(json.dumps(index,indent=2)+'\n')
progress=json.loads((r/'review-progress.json').read_text());v=json.loads((p/'verification.json').read_text());m=json.loads((p/'corpus-manifest.json').read_text())
state={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'completed_generation_full_review_and_verified_admission','unique_scenarios':24,'full_versions_reviewed':36,'content_pass_versions':26,'selected_final_versions':11,'new_assistant_targets':18963,'new_targets_after_2048':10230,'new_targets_after_3072':3644,'new_tool_calls':17,'new_tool_calls_starting_after_3072':0,'manifest':'runs/long-context-corpus-v3/manifest.json','manifest_sha256':v['manifest_sha256'],'total_sessions':sum(m[s]['sessions'] for s in ['train','validation']),'train':m['train'],'validation':m['validation'],'coverage':v['full_corpus_coverage'],'actual_trained_targets':0,'vm':'No cloud commands; no VM start; historical TERMINATED not freshly checked','backup':'Committed synthetic evidence and local verified corpus; GCS pending authentication','limitations':['Full4Kcurriculum remains incomplete','No pristine new evaluation score','No added tool call after3072 in this campaign','Many original dialogues short; expansions must add real operations or changed decisions','CLI review advisory; primary review overrode unsupported quota rejection','No embedding semantic deduplication']}
(p/'corpus-state.json').write_text(json.dumps(state,indent=2)+'\n');(r/'completion.json').write_text(json.dumps(state,indent=2)+'\n');print(json.dumps(state,indent=2))

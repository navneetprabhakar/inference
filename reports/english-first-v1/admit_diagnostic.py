"""Admit only the reviewed English fit diagnostic; never production/release."""
import json,hashlib,sys
from pathlib import Path
P=Path(__file__).parent;ROOT=P.resolve().parents[1];sys.path.insert(0,str(ROOT))
if (P/'packet-freeze.json').exists():raise SystemExit('Frozen diagnostic packet: create a new version')
from cloud_training.nano_chat_format import VERSION
from cloud_training.nano_qualification_schedule import restart_branches
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
write=lambda n,x:(P/n).write_text(json.dumps(x,indent=2)+'\n')
review=json.loads((P/'data-review.json').read_text());assert len(review['records'])==36 and all(r['pass'] for r in review['records'])
assert review['source_sha256']==sha(ROOT/'reports/corrective-corpus-v1/train.jsonl')
tok='ad777bb448ea8fcf115835548596f9303f3ee5e85a014b0bb315567091080cc5'
parent=sha(ROOT/'reports/corrective-corpus-v1/candidate-4k/manifest.json')
files=[P/'fit-train.jsonl',P/'development-reference.jsonl']
admission={'schema':1,'diagnostic_only':True,'training_admitted':True,'scope':'English tiny-fit learnability diagnostic only; NOT a conversation release candidate. Preserve production gates.','format_version':VERSION,'context_tokens':2048,'tokenizer_sha256':tok,'parent_manifest_sha256':parent,'jsonl_sha256':[sha(p) for p in files],'review_sha256':sha(P/'data-review.json')}
write('diagnostic-admission.json',admission)
manifest={'schema':1,'diagnostic_only':True,'training_admitted':True,'format_version':VERSION,'context_tokens':2048,'tokenizer_sha256':tok,'parent_manifest_sha256':parent,'admission':{'receipt':'diagnostic-admission.json','sha256':sha(P/'diagnostic-admission.json')}}
for split,p in zip(('train','validation'),files):manifest[split]={'file':p.name,'sha256':sha(p)}
write('diagnostic-manifest.json',manifest)
contract={'schema':1,'objective':'english_fit_diagnostic','diagnostic_only':True,'dataset_manifest_sha256':sha(P/'diagnostic-manifest.json'),'tokenizer_sha256':tok,'context_tokens':2048,'required_parent_manifest_sha256':parent,'review_sha256':sha(P/'data-review.json'),'development_suite_sha256':sha(P/'development-suite.json'),'unresolved_required_data':[],'recipe_limits':{'max_epochs':64,'max_pilot_updates':64,'max_eval_interval':5,'max_lr_multiplier':.25},'regression':{'relative_tolerance':.05,'patience':2},'fit_go_gate':{'complete_training_sessions_minimum':23,'training_sessions':24,'no_invalid_or_forbidden_tool_actions':True},'notes':['Explicit isolated diagnostic permits up to64finite epochs/updates; production default remains8epochs and existing corrective pilot remains10updates.','656unique training targets; replay counts never represented as new data.','Development regression guards remain active. A stop before fit is inconclusive about maximum learnability, not grounds for automatic extension.','No promotion even if tiny fit passes. Independent transfer and protected tool tests remain required.']}
write('diagnostic-contract.json',contract)
write('qualification-schedule.json',{'branches':restart_branches(),'scope':'actual GPU/GCS execution still required','do_not_relax_exact_comparison':True})

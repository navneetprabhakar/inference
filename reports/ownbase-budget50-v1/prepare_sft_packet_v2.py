"""Package already reviewed2K inputs, frozen assessment and separate current code."""
import copy,hashlib,json,os,subprocess,tarfile
from pathlib import Path
P=Path('reports/ownbase-budget50-v1');R=Path('runs/ownbase-budget50-v1/sft-packet-v2');R.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
protected=[];sources=[]
for label,p in [('original',Path('cloud_training/evaluation/conversation-tools-dev.json')),('v2',Path('reports/l4-qualification-v1/instruction-repair-v2/heldout-suite.json')),('v3',Path('reports/l4-qualification-v1/instruction-repair-v3/heldout-suite.json'))]:
 m=json.loads(p.read_text());assert m['purpose']=='development_only_never_train';sources.append({'path':str(p),'sha256':sha(p)})
 for original in m['sessions']:
  selected=original['id'] in ['calculate-grounding','convert-grounding'] if label=='original' else original['id'].rsplit('-',1)[0] in ['calculate','convert','tool_correction']
  if selected:
   s=copy.deepcopy(original);s['id']=label+'-'+s['id'];protected.append(s)
assert sum(len(s['turns']) for s in protected)==18
(P/'protected-tools.json').write_text(json.dumps({'purpose':'development_only_never_train','sessions':protected,'source_hashes':sources,'scope':'Exactly18 previously passing protected turns, session order retained; historical exposed regression.'},indent=2)+'\n')
archive=R/'code.tar.gz'
with tarfile.open(archive,'w:gz') as tar:
 for name in subprocess.check_output(['git','ls-files','cloud_training','tools'],text=True).splitlines():
  if name.endswith('.py'):tar.add(name,arcname=name,recursive=False)
 tar.add(P/'assess_model.py',arcname='assessment.py',recursive=False)
prefix='gs://forge-ownbase-a100-20261110/ownbase-v2/budget50-v1';cfg={'schema':1,'run_id':'forge-ownbase-budget50-v1','code_uri':prefix+'/sft-packet-v2/code.tar.gz','code_sha256':sha(archive),'files':[],'finite_recipes':[{'name':'new-base-2k-8epochs','stage':'general','epochs':8,'batch_tokens':8192,'lr_multiplier':1.0},{'name':'retained605-2k-4epochs','stage':'targeted','epochs':4,'batch_tokens':8192,'lr_multiplier':0.125}],'retained_lineage':json.loads((P/'retained-lineage.json').read_text()),'experiment_revision':'v2: replace redundantnew-base4epocharm withretained605fork; stillmax2predefinedpilots, same50USDcap/deadlines, nocontaminationoftrainingtargetsfromassessment','training_scope':'2K diagnostic;349 fully reviewed whole sessions,43183 assistant targets per pass; not broad SFT.4Kgate remains unmet.','promotion':'No automatic promotion;60synthetic sessions+18protectedturns plusfullreview required. Preserve605 fallback.'}
for name in ['manifest.json','admission.json','train.jsonl','validation.jsonl','verification.json']:
 p=Path('runs/ownbase-budget50-v1/sft-2k')/name;cfg['files'].append({'path':'data/'+name,'uri':prefix+'/data/sft-2k/'+name,'sha256':sha(p)})
for source,dest in [('assessment.json','assessment.json'),('protected-tools.json','protected.json')]:
 (R/dest).write_bytes((P/source).read_bytes());cfg['files'].append({'path':dest,'uri':prefix+'/sft-packet-v2/'+dest,'sha256':sha(R/dest)})
(R/'config.json').write_text(json.dumps(cfg,indent=2)+'\n');script=(P/'run_sft.py').read_text().replace('CONFIG_SHA256 = None',"CONFIG_SHA256 = '"+sha(R/'config.json')+"'");(R/'next-stage.py').write_text(script)
receipt={'config_sha256':sha(R/'config.json'),'script_uri':prefix+'/sft-packet-v2/next-stage.py','script_sha256':sha(R/'next-stage.py'),'code_sha256':sha(archive),'run_id':cfg['run_id'],'files':{p.name:sha(p) for p in R.iterdir() if p.is_file()}}
(P/'sft-packet-v2.json').write_text(json.dumps(receipt,indent=2)+'\n')
subprocess.run(['gcloud','storage','rsync','--recursive',str(R),prefix+'/sft-packet-v2','--quiet'],check=True,timeout=180)
back=R/'readback';back.mkdir()
subprocess.run(['gcloud','storage','rsync','--recursive',prefix+'/sft-packet-v2',str(back),'--quiet'],check=True,timeout=180)
for name,digest in receipt['files'].items():assert sha(back/name)==digest
receipt['all_packet_files_independent_sha_readback']=True;(P/'sft-packet-v2.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))

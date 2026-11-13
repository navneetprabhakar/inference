"""Bind the retained605parent and all six ancestors by original GCS manifests."""
import hashlib,json,subprocess
from pathlib import Path
P=Path('reports/ownbase-budget50-v1');R=Path('runs/ownbase-budget50-v1/retained-lineage');R.mkdir(exist_ok=False)
identity=json.loads(Path('runs/literal-state-repair-v1/results/sft/step-00000605/metadata.json').read_text())['identity'];expected='05ab60c277c0bcfb4288215b8909aa693a451ab1e059fa5aacd7946f2a1854a8';items=[]
names=['literal-state-repair-v1','conversation-repair-v1','instruction-repair-v3','instruction-repair-v2','instruction-repair-v1','broad-conversation-pilot-v1','base6b']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for name in names:
 uri='gs://forge-ownbase-a100-20261110/ownbase-v2/campaign-b2f327b0119c/checkpoints/checkpoint-34d63089948340e0abf756818b9df73b' if name=='base6b' else json.loads((Path('reports/l4-qualification-v1')/name/'assessment.json').read_text())['checkpoint']
 d=R/name;d.mkdir()
 for file in ['manifest.json','metadata.json','COMMITTED']:subprocess.run(['gcloud','storage','cp',uri+'/'+file,str(d/file),'--quiet'],check=True,timeout=90)
 assert sha(d/'manifest.json')==expected
 manifest=json.loads((d/'manifest.json').read_text());meta=json.loads((d/'metadata.json').read_text());assert meta['identity']==identity;assert sha(d/'metadata.json')==manifest['files']['metadata.json']['sha256']
 # A metadata/receipt check is not payload verification; remote stage must validate every bundle.
 items.append({'name':name,'uri':uri,'manifest_sha256':expected,'manifest':manifest,'step':meta['step'],'payload_verified_here':False})
 if name!='base6b':expected=identity.get('parent_bundle_manifest_sha256',identity.get('base_bundle_manifest_sha256'));identity=identity.get('parent_identity',identity.get('base_identity'))
assert identity['phase']=='base' and identity['initialization']=='own_random' and len(items)==7
report={'schema':1,'run_id':'forge-ownbase-budget50-v1','items':items,'scope':'Exact metadata chain bound locally; full VM payload readback and validate_parent_chain required before any targetedpilot. Originalsources unchanged.'}
(P/'retained-lineage.json').write_text(json.dumps(report,indent=2)+'\n');print('Bound7 immutable manifest identities; payload verification pending onVM.')

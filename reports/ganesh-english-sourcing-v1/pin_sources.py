"""Fetch small public metadata/cards only; never download source shards."""
import hashlib,json,urllib.request
from pathlib import Path
R=Path(__file__).resolve().parent;D=R/'source-cards';D.mkdir(exist_ok=True)
items=[('fineweb_edu','HuggingFaceFW/fineweb-edu','foundation_candidate'),('smol_smoltalk','HuggingFaceTB/smol-smoltalk','conversation_candidate'),('oasst2','OpenAssistant/oasst2','conversation_candidate'),('finemath','HuggingFaceTB/finemath','catalog_only_maths_deferred'),('openmathinstruct2','nvidia/OpenMathInstruct-2','catalog_only_maths_deferred')]
registry=[]
def fetch(url):
 with urllib.request.urlopen(url,timeout=40) as r:
  b=r.read(2*1024*1024+1)
 if len(b)>2*1024*1024:raise ValueError('Metadata size bound exceeded')
 return b
for key,dataset,purpose in items:
 meta=json.loads(fetch('https://huggingface.co/api/datasets/'+dataset));rev=meta['sha'];url=f'https://huggingface.co/datasets/{dataset}/raw/{rev}/README.md';card=fetch(url)
 p=D/(key+'.md');p.write_bytes(card)
 registry.append({'key':key,'dataset':dataset,'revision_observed_now':rev,'purpose':purpose,'card_url':url,'card_sha256':hashlib.sha256(card).hexdigest(),'license_tags':[t for t in meta.get('tags',[]) if t.startswith('license:')],'training_admitted':False,'payload_downloaded_this_task':False,'license_scope':'Dataset declaration only; retain upstream source/generator conditions before admission'})
(R/'source-registry.json').write_text(json.dumps(registry,indent=2)+'\n');print(json.dumps(registry,indent=2))

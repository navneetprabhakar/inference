"""Bounded metadata/license preparation for the proposed narrative source."""
# Creator: Navneet Prabhakar
from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import sys
import urllib.request
from slm.data.intake_ledger import IntakeLedger
from slm.data.schema import Source
from slm.data.tokenized import sha

ROOT=Path('data/tinystories-source-preparation-v1')
PLAN=Path('configs/tinystories-source-preparation-v1.json')


def save(p,v):p.write_text(json.dumps(v,indent=2,sort_keys=True)+'\n')


def worker():
    plan=json.loads(PLAN.read_text());ledger=IntakeLedger(ROOT/'charges',plan['ledger_contract'])
    try:
        def get(name,url):
            cap=262144;ledger.reserve(name,requests=1,body_bytes=cap+1,output_bytes=cap)
            request=urllib.request.Request(url,headers={'Accept-Encoding':'identity'})
            with urllib.request.urlopen(request,timeout=45) as response:
                if response.status!=200 or response.headers.get('Content-Encoding','identity')!='identity':raise ValueError('Identity metadata response required')
                if response.headers.get('Link'):raise ValueError('Unexpected metadata pagination')
                raw=response.read(cap+1)
            if len(raw)>cap:raise ValueError('Metadata body cap exceeded')
            (ROOT/name).write_bytes(raw);ledger.finish(name,raw=raw);return raw
        info=json.loads(get('dataset-info.json','https://huggingface.co/api/datasets/roneneldan/TinyStories'))
        revision=info['sha']
        card=get('card.txt',f'https://huggingface.co/datasets/roneneldan/TinyStories/raw/{revision}/README.md')
        if [s.strip() for s in card.decode().splitlines() if s.startswith('license:')]!=['license: cdla-sharing-1.0']:
            raise ValueError('Pinned card license differs')
        inventory=json.loads(get('inventory.json',f'https://huggingface.co/api/datasets/roneneldan/TinyStories/tree/{revision}?recursive=false&expand=false'))
        license_url='https://raw.githubusercontent.com/spdx/license-list-data/v3.27.0/text/CDLA-Sharing-1.0.txt'
        license_text=get('license.txt',license_url)
        get('official-license.html','https://cdla.dev/sharing-1-0/')
        source=Source('roneneldan/TinyStories',revision,'https://huggingface.co/datasets/roneneldan/TinyStories',
            'cdla-sharing-1.0',sha(ROOT/'license.txt'),sha(ROOT/'card.txt'),
            ('Published synthetic GPT-3.5 and GPT-4 short stories as declared by pinned source card',),'sample_only')
        record=asdict(source);record['evidence_files']=dict(card='card.txt',license='license.txt',license_url=license_url)
        save(ROOT/'source.json',record);snapshot=ledger.snapshot();save(ROOT/'ledger-snapshot.json',snapshot)
        for p,h in plan['input_bindings'].items():
            if sha(p)!=h:raise ValueError('Preparation implementation changed')
        result=dict(creator='Navneet Prabhakar',kind='actual-tinystories-source-preparation-v1',complete=True,
            plan_sha256=sha(PLAN),revision=revision,source_sha256=sha(ROOT/'source.json'),
            card_sha256=sha(ROOT/'card.txt'),license_sha256=sha(ROOT/'license.txt'),official_license_sha256=sha(ROOT/'official-license.html'),
            inventory_sha256=sha(ROOT/'inventory.json'),files=[r for r in inventory if r['type']=='file'],
            reserved=snapshot['reserved'],successful_body_bytes=sum(r['actual_body_bytes'] or 0 for r in snapshot['attempts']),
            data_rows_fetched=0,training_approved=False,teacher_calls=0,model_updates=0,cloud_spend=0,
            scope='Pinned source metadata/card/license only; dataset remains sample_only. No narrative-row acquisition, source population review, training admission or legal certification of downstream distribution.')
        save(ROOT/'report.json',result);save(Path('reports/tinystories-source-preparation.json'),result)
        print(json.dumps({k:v for k,v in result.items() if k!='files'},indent=2),flush=True)
    except BaseException as error:
        save(ROOT/'failure.json',dict(complete=False,error_type=type(error).__name__,message='Bounded source preparation stopped; charges retained, no automatic retry.',ledger=ledger.snapshot()))
        raise SystemExit('Narrative source preparation stopped; inspect retained evidence') from None
    finally:ledger.close()


def main():
    if '--worker' in sys.argv:worker();return
    if ROOT.exists():raise FileExistsError('Source preparation already attempted')
    ROOT.mkdir();save(ROOT/'plan.json',json.loads(PLAN.read_text()))
    subprocess.run([sys.executable,__file__,'--worker'],timeout=300,check=True)


if __name__=='__main__':main()

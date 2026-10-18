"""Offline human review UI and decision-only patches; publication stays separate."""
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from slm.data.build import verify
from slm.data.review import records,check_packet,oasst_mapping,REVIEWER,CATEGORIES,PRIORITY
from slm.data.schema import digest

SOURCE_FIELDS={'approved','terms_reviewed','allowed_categories','evidence_note'}
DECISION_FIELDS={'approved','english_verified','privacy_verified','quality_verified','content_category','upstream_partition','partition_evidence','note'}


def read_json(path):
    def unique(pairs):
        result={}
        for k,v in pairs:
            if k in result:raise ValueError('Duplicate JSON field')
            result[k]=v
        return result
    with Path(path).open('rb') as f:data=f.read(16*1024*1024+1)
    if len(data)>16*1024*1024:raise ValueError('Review input exceeds byte bound')
    return json.loads(data,object_pairs_hook=unique)


def choice(value):
    if value is not None and type(value) is not bool:raise ValueError('Boolean or pending decision required')


def note(value):
    if not isinstance(value,str) or len(value.encode())>8192:raise ValueError('Bounded review note required')


def decisions(sources,examples):
    for entry in sources.values():
        if set(entry)!=SOURCE_FIELDS:raise ValueError('Source decision fields differ')
        choice(entry['approved']);choice(entry['terms_reviewed']);note(entry['evidence_note'])
        cats=entry['allowed_categories']
        if not isinstance(cats,list) or any(not isinstance(v,str) for v in cats) or len(set(cats))!=len(cats) or not set(cats)<=CATEGORIES:
            raise ValueError('Source categories differ')
    for entry in examples.values():
        if set(entry)!=DECISION_FIELDS:raise ValueError('Example decision fields differ')
        for key in ('approved','english_verified','privacy_verified','quality_verified'):choice(entry[key])
        if entry['content_category'] is not None and entry['content_category'] not in CATEGORIES:raise ValueError('Unknown content category')
        if entry['upstream_partition'] is not None and entry['upstream_partition'] not in PRIORITY:raise ValueError('Unknown upstream partition')
        note(entry['partition_evidence']);note(entry['note'])


def bind(dataset,packet):
    dataset=Path(dataset);verify(dataset)
    if (set(packet)!={'version','dataset_manifest_sha256','reviewer','human_attestation','source_reviews','examples'}
        or type(packet['version']) is not int or packet['version']!=1
        or packet['reviewer'] not in (None,REVIEWER) or type(packet['human_attestation']) is not bool):raise ValueError('Review packet contract differs')
    if hashlib.sha256((dataset/'manifest.json').read_bytes()).hexdigest()!=packet['dataset_manifest_sha256']:raise ValueError('Dataset binding differs')
    sources=read_json(dataset/'sources.json');items=records(dataset)
    if set(sources)!=set(packet['source_reviews']) or not 1<=len(sources)<=16:raise ValueError('Source inventory differs')
    if not isinstance(packet['examples'],dict) or not 1<=len(packet['examples'])<=200:raise ValueError('Console supports 1–200 reviewed examples')
    for name,entry in packet['source_reviews'].items():
        if set(entry)!={'source_record','source_sha256',*SOURCE_FIELDS} or entry['source_record']!=sources[name] or entry['source_sha256']!=digest(sources[name]):raise ValueError('Source provenance differs')
    for key,entry in packet['examples'].items():
        if set(entry)!={'record','record_sha256','decision'} or key not in items or entry['record']!=items[key] or entry['record_sha256']!=digest(items[key]):raise ValueError('Record identity/content differs')
        if items[key]['source']=='OpenAssistant/oasst2' and 'upstream_mapping' in items[key]['validation_results']:
            if entry['decision']['upstream_partition']!=oasst_mapping(items[key])['split']:raise ValueError('Machine-mapped partition cannot change')
    decisions({k:{f:v[f] for f in SOURCE_FIELDS} for k,v in packet['source_reviews'].items()},{k:v['decision'] for k,v in packet['examples'].items()})
    return sources,items


def evidence(packet,root):
    result={}
    if root is None:return result
    files=sorted(Path(root).glob('*/source/source.json'))
    if len(files)>64:raise ValueError('Evidence folder inventory exceeds bound')
    for meta_file in files:
        meta=read_json(meta_file);name=meta.get('source_id')
        if name not in packet['source_reviews']:continue
        source=packet['source_reviews'][name]['source_record']
        if any(meta.get(k)!=v for k,v in source.items()):raise ValueError('Evidence source descriptor differs')
        if name in result:raise ValueError('Duplicate source evidence')
        texts={}
        for key,filename,want in [('card','card.txt',source['card_sha256']),('license','license.txt',source['license_text_sha256'])]:
            with (meta_file.parent/filename).open('rb') as f:data=f.read(2*1024*1024+1)
            if len(data)>2*1024*1024 or hashlib.sha256(data).hexdigest()!=want:raise ValueError('Pinned source evidence checksum differs')
            texts[key]=data.decode('utf-8')
        result[name]=texts
    if set(result)!=set(packet['source_reviews']):raise ValueError('Pinned source evidence missing')
    return result


def render(dataset,packet_file,output,evidence_root=None):
    output=Path(output)
    if output.exists():raise FileExistsError(output)
    packet=read_json(packet_file);bind(dataset,packet);texts=evidence(packet,evidence_root)
    payload={'packet':packet,'packet_sha256':digest(packet),'reviewer':REVIEWER,'evidence':texts}
    template=Path(__file__).with_suffix('.html').read_text()
    data=base64.b64encode(json.dumps(payload,ensure_ascii=False,allow_nan=False).encode()).decode()
    html=template.replace('__PAYLOAD__',data)
    script=html.split('<script>')[1].split('</script>')[0];style=html.split('<style>')[1].split('</style>')[0]
    hashes=[base64.b64encode(hashlib.sha256(v.encode()).digest()).decode() for v in (script,style)]
    csp=f"default-src 'none'; script-src 'sha256-{hashes[0]}'; style-src 'sha256-{hashes[1]}'; connect-src 'none'; base-uri 'none'; form-action 'none'"
    html=html.replace('__CSP__',csp);output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x') as f:f.write(html)
    return {'creator':REVIEWER,'examples':len(packet['examples']),'sources':len(packet['source_reviews']),'pinned_evidence_sources':len(texts),
        'review_packet_sha256':digest(packet),'html_sha256':hashlib.sha256(html.encode()).hexdigest(),'human_attestation_changed':False,'output':str(output)}


def apply_patch(dataset,packet_file,patch_file,output):
    output=Path(output)
    if output.exists():raise FileExistsError(output)
    packet=read_json(packet_file);sources,items=bind(dataset,packet);patch=read_json(patch_file)
    if set(patch)!={'version','review_packet_sha256','reviewer','human_attestation','sources','examples'} or type(patch['version']) is not int or patch['version']!=1:
        raise ValueError('Decision patch contract differs')
    if patch['review_packet_sha256']!=digest(packet):raise ValueError('Stale/different review packet')
    if patch['reviewer']!=REVIEWER or type(patch['human_attestation']) is not bool:raise ValueError('Explicit review identity/attestation required')
    if set(patch['sources'])!=set(packet['source_reviews']) or set(patch['examples'])!=set(packet['examples']):raise ValueError('Decision inventory differs')
    decisions(patch['sources'],patch['examples']);candidate=deepcopy(packet)
    for name,entry in patch['sources'].items():candidate['source_reviews'][name].update(entry)
    for key,entry in patch['examples'].items():
        record=packet['examples'][key]['record']
        if record['source']=='OpenAssistant/oasst2' and 'upstream_mapping' in record['validation_results']:
            if entry['upstream_partition']!=oasst_mapping(record)['split']:raise ValueError('Machine-mapped partition cannot change')
        candidate['examples'][key]['decision']=entry
    candidate.update(reviewer=REVIEWER,human_attestation=patch['human_attestation'])
    if candidate['human_attestation']:check_packet(candidate,sources,items)
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x') as f:f.write(json.dumps(candidate,sort_keys=True,ensure_ascii=False,indent=2)+'\n')
    return {'output':str(output),'human_attestation':candidate['human_attestation'],'approved_decisions':sum(v['decision']['approved'] is True for v in candidate['examples'].values()),
        'training_release_created':False,'review_packet_sha256':digest(candidate)}


def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('render');a.add_argument('--evidence-root')
    a=sub.add_parser('apply');a.add_argument('--patch',required=True)
    for a in sub.choices.values():
        a.add_argument('--dataset',required=True);a.add_argument('--packet',required=True);a.add_argument('--output',required=True)
    a=p.parse_args();result=render(a.dataset,a.packet,a.output,a.evidence_root) if a.command=='render' else apply_patch(a.dataset,a.packet,a.patch,a.output)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()

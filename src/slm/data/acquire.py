"""Explicit bounded public-source audit acquisition. No credentials or bulk downloads."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import urllib.parse
import urllib.request
import urllib.error
import zlib
import time
from slm.data.schema import Source


def open_response(request):
    for attempt in range(3):
        try:
            return urllib.request.urlopen(request,timeout=45)
        except urllib.error.HTTPError as exc:
            if exc.code not in (429,500,502,503,504) or attempt == 2: raise
        except (urllib.error.URLError,TimeoutError):
            if attempt == 2: raise
        time.sleep(attempt+1)


def fetch(url, limit=4*1024*1024):
    request=urllib.request.Request(url,headers={'User-Agent':'portable-slm-source-audit/1'})
    with open_response(request) as response:
        content=response.read(limit+1)
        if len(content)>limit: raise ValueError('Source audit response exceeds byte limit')
        return content, dict(response.headers.items())


def register(dataset, expected_license, output, revision=None, upstream_origins=None):
    if not upstream_origins:
        raise ValueError('Explicit upstream origins from the source card are required')
    root=Path(output)
    if root.exists(): raise FileExistsError(root)
    metadata,_=fetch('https://huggingface.co/api/datasets/'+dataset)
    info=json.loads(metadata)
    revision=revision or info['sha']
    # A pinned revision can be historical; read its card, never a mutable main card.
    card,_=fetch(f'https://huggingface.co/datasets/{dataset}/raw/{revision}/README.md')
    license_lines=[line.strip() for line in card.decode().splitlines() if line.startswith('license:')]
    if license_lines != ['license: '+expected_license]:
        raise ValueError('Published card license differs; manual review required')
    spdx={'apache-2.0':'Apache-2.0','mit':'MIT','cc-by-sa-3.0':'CC-BY-SA-3.0','odc-by':'ODC-By-1.0'}
    license_url=f'https://raw.githubusercontent.com/spdx/license-list-data/v3.27.0/text/{spdx[expected_license]}.txt'
    license_text,_=fetch(license_url)
    source=Source(dataset,revision,f'https://huggingface.co/datasets/{dataset}',expected_license,
                  hashlib.sha256(license_text).hexdigest(),hashlib.sha256(card).hexdigest(),
                  tuple(upstream_origins),'sample_only')
    root.mkdir(parents=True)
    (root/'card.txt').write_bytes(card); (root/'license.txt').write_bytes(license_text)
    raw=asdict(source);raw['evidence_files']={'card':'card.txt','license':'license.txt'}
    raw['evidence_files']['license_url']=license_url
    (root/'source.json').write_text(json.dumps(raw,indent=2)+'\n')
    return source


def sample(source, config, split, output, count=200):
    """First N rows are schema/yield probes, not representative quality estimates."""
    if count<1 or count>500: raise ValueError('Audit sample must contain 1–500 rows')
    root=Path(output)
    if root.exists(): raise FileExistsError(root)
    rows, pages, total_bytes=[],[],0
    for offset in range(0,count,100):
        params=urllib.parse.urlencode({'dataset':source.source_id,'config':config,'split':split,
                                       'offset':offset,'length':min(100,count-offset)})
        raw,headers=fetch('https://datasets-server.huggingface.co/rows?'+params)
        total_bytes+=len(raw)
        if total_bytes>24*1024*1024: raise ValueError('Total audit download limit exceeded')
        revision=next((v for k,v in headers.items() if k.lower()=='x-revision'),None)
        if revision != source.revision: raise ValueError('Viewer revision differs from pinned source')
        body=json.loads(raw)
        if body.get('partial'): raise ValueError('Partial viewer response')
        for entry in body['rows']:
            if entry.get('truncated_cells'): raise ValueError('Truncated viewer cell')
            rows.append(entry['row'])
        pages.append({'offset':offset,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),
                      'revision':revision,'returned_rows':len(body['rows'])})
    root.mkdir(parents=True)
    payload=''.join(json.dumps(row,sort_keys=True,ensure_ascii=False)+'\n' for row in rows)
    (root/'rows.jsonl').write_text(payload)
    report={'source':source.source_id,'revision':source.revision,'config':config,'split':split,
            'selection':'first_n; not representative, no quality clearance', 'rows':len(rows),
            'raw_response_bytes':total_bytes,'pages':pages,
            'rows_sha256':hashlib.sha256(payload.encode()).hexdigest()}
    (root/'acquisition.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def sample_ready_trees(source, output, count=200):
    """Read only a bounded gzip prefix, accepting complete nested JSON lines."""
    if source.source_id != 'OpenAssistant/oasst2' or not 1 <= count <= 500:
        raise ValueError('Ready-tree sampling supports OASST2, 1–500 trees')
    root=Path(output)
    if root.exists(): raise FileExistsError(root)
    filename='2023-11-05_oasst2_ready.trees.jsonl.gz'
    url=f'https://huggingface.co/datasets/{source.source_id}/resolve/{source.revision}/{filename}'
    request=urllib.request.Request(url,headers={'Range':'bytes=0-4194303',
                                               'User-Agent':'portable-slm-source-audit/1'})
    decoder=zlib.decompressobj(16+zlib.MAX_WBITS)
    rows,buffer,total_raw,total_text=[],b'',0,0
    checksum=hashlib.sha256()
    with open_response(request) as response:
        while len(rows)<count and total_raw<4*1024*1024:
            block=response.read(min(65536,4*1024*1024-total_raw))
            if not block: break
            total_raw+=len(block);checksum.update(block)
            text=decoder.decompress(block,16*1024*1024-total_text+1)
            total_text+=len(text)
            if total_text>16*1024*1024: raise ValueError('Decompressed tree audit limit exceeded')
            buffer+=text
            while b'\n' in buffer and len(rows)<count:
                line,buffer=buffer.split(b'\n',1)
                row=json.loads(line)
                if row.get('tree_state') != 'ready_for_export' or 'prompt' not in row:
                    raise ValueError('Unexpected ready-tree schema')
                rows.append(row)
    if len(rows)!=count:
        raise ValueError('Insufficient complete trees within download cap; no partial snapshot written')
    payload=''.join(json.dumps(row,sort_keys=True,ensure_ascii=False)+'\n' for row in rows)
    report={'source':source.source_id,'revision':source.revision,'url':url,'rows':len(rows),
            'selection':'first_n_complete_ready_trees; not representative',
            'raw_response_bytes':total_raw,'compressed_prefix_sha256':checksum.hexdigest(),
            'rows_sha256':hashlib.sha256(payload.encode()).hexdigest()}
    root.mkdir(parents=True)
    (root/'rows.jsonl').write_text(payload)
    (root/'acquisition.json').write_text(json.dumps(report,indent=2)+'\n')
    return report



UPSTREAM_SPLITS={'train':'train','validation':'validation','test':'test',
    'train_sft':'train','test_sft':'test','train_gen':'train','test_gen':'test'}


def verified_cached_spec(item,folder):
    """Bind cached bytes to the pinned source AND actual upstream config/split."""
    from slm.data.build import read_source
    from slm.data.schema import digest
    folder=Path(folder);expected=item['source'];source=read_source(folder/'source/source.json')
    acquisition=json.loads((folder/'sample/acquisition.json').read_text());path=folder/'sample/rows.jsonl'
    if path.stat().st_size>32*1024*1024:raise ValueError('Cached sample exceeds bounded audit scope')
    raw=path.read_bytes()
    if (digest(asdict(source))!=digest(expected) or acquisition.get('source')!=source.source_id
        or acquisition.get('revision')!=source.revision or acquisition.get('rows')!=item['sample_count']
        or acquisition.get('rows_sha256')!=hashlib.sha256(raw).hexdigest()
        or len(raw.splitlines())!=item['sample_count']):
        raise ValueError('Cached acquisition identity or content differs')
    if item['adapter']=='oasst':
        expected_url=f'https://huggingface.co/datasets/{source.source_id}/resolve/{source.revision}/2023-11-05_oasst2_ready.trees.jsonl.gz'
        if acquisition.get('url')!=expected_url:raise ValueError('Cached ready-tree export URL differs')
        split=None
    else:
        if (acquisition.get('config')!=item['config'] or acquisition.get('split')!=item['upstream_split']
            or item['upstream_split'] not in UPSTREAM_SPLITS):
            raise ValueError('Cached upstream config/split differs')
        split=UPSTREAM_SPLITS[item['upstream_split']]
    return {'source_record':str(folder/'source/source.json'),'path':str(path),
        'adapter':item['adapter'],'official_split':split}

def main():
    from slm.data.build import read_source
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='command',required=True)
    r=sub.add_parser('register');r.add_argument('--dataset',required=True)
    r.add_argument('--license',required=True);r.add_argument('--revision');r.add_argument('--output',required=True)
    r.add_argument('--upstream',action='append',required=True)
    s=sub.add_parser('sample');s.add_argument('--source-record',required=True)
    s.add_argument('--config',required=True);s.add_argument('--split',required=True)
    s.add_argument('--count',type=int,default=200);s.add_argument('--output',required=True)
    t=sub.add_parser('sample-trees');t.add_argument('--source-record',required=True)
    t.add_argument('--count',type=int,default=200);t.add_argument('--output',required=True)
    a=p.parse_args()
    if a.command=='register':
        result=asdict(register(a.dataset,a.license,a.output,a.revision,a.upstream))
    elif a.command=='sample': result=sample(read_source(a.source_record),a.config,a.split,a.output,a.count)
    else: result=sample_ready_trees(read_source(a.source_record),a.output,a.count)
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()

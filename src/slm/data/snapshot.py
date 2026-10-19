"""Explicit small complete JSONL source acquisition; always sample-only."""
# Creator: Navneet Prabhakar
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import time
import urllib.parse
import urllib.request
from slm.data.acquire import fetch,open_response
from slm.data.build import read_source
from slm.data.staging import metadata,canonical
from slm.data.tokenized import sha,stamp

MAX_BYTES=24*1024*1024


def acquire(source_record,filename,output,*,max_bytes=MAX_BYTES):
    source_record,output=Path(source_record),Path(output)
    if output.exists():raise FileExistsError(output)
    if type(max_bytes) is not int or not 1<=max_bytes<=MAX_BYTES:raise ValueError('Complete-source audit byte ceiling is 24 MiB')
    if not isinstance(filename,str) or not re.fullmatch(r'[A-Za-z0-9_.-]+\.jsonl',filename):raise ValueError('One root JSONL file required')
    raw_source=metadata(source_record);source=read_source(source_record)
    if source.review_status=='excluded' or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',source.source_id):raise ValueError('Explicit non-excluded pinned dataset required')
    evidence={name:source_record.parent/raw_source['evidence_files'][name] for name in ('card','license')}
    guards={p.resolve():stamp(p) for p in [source_record,*evidence.values(),Path(__file__)]}
    url=f'https://huggingface.co/api/datasets/{source.source_id}/tree/{source.revision}?recursive=false&expand=false'
    tree_raw,_=fetch(url,limit=1024*1024);tree=json.loads(tree_raw)
    matches=[x for x in tree if x.get('type')=='file' and x.get('path')==filename]
    if len(matches)!=1:raise ValueError('Pinned source file metadata missing or ambiguous')
    info=matches[0];expected=info.get('lfs',{}).get('oid')
    if not isinstance(expected,str) or not re.fullmatch('[a-f0-9]{64}',expected):raise ValueError('Published LFS SHA256 required; no mutable-file fallback')
    size=info.get('size')
    if type(size) is not int or not 0<size<=max_bytes or info['lfs'].get('size')!=size:raise ValueError('Pinned file exceeds byte limit or metadata differs')
    output.parent.mkdir(parents=True,exist_ok=True);temp=Path(tempfile.mkdtemp(prefix='.source-snapshot-',dir=output.parent))
    content_url=f'https://huggingface.co/datasets/{source.source_id}/resolve/{source.revision}/{urllib.parse.quote(filename)}'
    try:
        h=hashlib.sha256();total=0;start=time.monotonic()
        request=urllib.request.Request(content_url,headers={'User-Agent':'portable-slm-source-audit/1','Accept-Encoding':'identity'})
        with open_response(request) as response,(temp/'rows.jsonl').open('wb') as out:
            for chunk in iter(lambda:response.read(65536),b''):
                total+=len(chunk)
                if total>max_bytes or total>size:raise ValueError('Source download exceeds pinned byte ceiling')
                if time.monotonic()-start>60:raise ValueError('Source download wall limit exceeded')
                h.update(chunk);out.write(chunk)
        if total!=size or h.hexdigest()!=expected:raise ValueError('Downloaded source differs from published size/SHA256')
        for name,path in evidence.items():shutil.copyfile(path,temp/(name+'.txt'))
        copied={**raw_source,'evidence_files':{**raw_source['evidence_files'],'card':'card.txt','license':'license.txt'}}
        (temp/'source.json').write_text(canonical(copied)+'\n');read_source(temp/'source.json')
        for path,before in guards.items():
            if stamp(path)!=before:raise ValueError('Source evidence or acquisition implementation changed')
        (temp/'file-metadata.json').write_text(canonical(dict(metadata_url=url,source_revision=source.revision,file=info,metadata_response_sha256=hashlib.sha256(tree_raw).hexdigest()))+'\n')
        report=dict(release='sample_only',scope='Complete pinned root JSONL file for bounded audit, not training approval.',
                    source_id=source.source_id,source_revision=source.revision,url=content_url,published_sha256=expected,
                    bytes=total,max_bytes=max_bytes,download_seconds=time.monotonic()-start,training_eligible=False,source_rights_approved=False,
                    source_descriptor_sha256=sha(source_record),implementation_sha256=sha(__file__))
        (temp/'acquisition.json').write_text(canonical(report)+'\n');os.rename(temp,output);return report
    except BaseException:shutil.rmtree(temp,ignore_errors=True);raise


def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-record',required=True);p.add_argument('--filename',required=True);p.add_argument('--output',required=True);p.add_argument('--max-bytes',required=True,type=int)
    a=p.parse_args();print(json.dumps(acquire(a.source_record,a.filename,a.output,max_bytes=a.max_bytes),sort_keys=True))


if __name__=='__main__':main()

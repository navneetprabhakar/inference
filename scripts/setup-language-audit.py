#!/usr/bin/env python3
"""Explicit small official fastText acquisition/build for offline sample auditing."""
# Creator: Navneet Prabhakar
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import urllib.request

REV='5b5943c118b0ec5fb9cd8d20587de2b2d3966dfe'


def fetch(url,path,limit):
    with urllib.request.urlopen(url,timeout=30) as response,path.open('wb') as f:
        total=0
        while chunk:=response.read(65536):
            total+=len(chunk)
            if total>limit:raise ValueError('Explicit detector download byte limit exceeded')
            f.write(chunk)
    return dict(url=url,bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);a=p.parse_args()
    root=Path(a.output).resolve();root.mkdir(parents=True,exist_ok=False)
    files={}
    files['source.tar.gz']=fetch(f'https://codeload.github.com/facebookresearch/fastText/tar.gz/{REV}',root/'source.tar.gz',10*1024*1024)
    files['lid.176.ftz']=fetch('https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.ftz',root/'lid.176.ftz',2*1024*1024)
    files['model-card.md']=fetch(f'https://raw.githubusercontent.com/facebookresearch/fastText/{REV}/docs/language-identification.md',root/'model-card.md',512*1024)
    files['model-license.html']=fetch('https://raw.githubusercontent.com/creativecommons/cc-legal-tools-data/a0dac18d1a773b4cdb7d8dd5d9bf4efab7901030/legacy/legalcode/by-sa_3.0.html',root/'model-license.html',1024*1024)
    with tarfile.open(root/'source.tar.gz') as archive:
        members=archive.getmembers()
        if len(members)>2000 or sum(m.size for m in members)>20*1024*1024:raise ValueError('Bounded source archive required')
        for member in members:
            if not (member.isfile() or member.isdir()) or '..' in Path(member.name).parts or Path(member.name).is_absolute():raise ValueError('Unsafe source archive member')
        archive.extractall(root/'source',filter='data')
    source=root/'source'/('fastText-'+REV)
    compiler=shutil.which('clang++') or shutil.which('g++')
    if compiler is None:raise ValueError('Local C++ compiler required')
    command=[compiler,'-O3','-std=c++11','-pthread',*[str(p) for p in sorted((source/'src').glob('*.cc'))],'-o',str(root/'fasttext')]
    with (root/'build.stdout').open('wb') as out,(root/'build.stderr').open('wb') as err:
        subprocess.run(command,stdout=out,stderr=err,timeout=60,check=True)
    descriptor=dict(version=1,kind='offline-fasttext-lid-v1',source_revision=REV,
                    binary=str(root/'fasttext'),binary_sha256=hashlib.sha256((root/'fasttext').read_bytes()).hexdigest(),
                    model=str(root/'lid.176.ftz'),model_sha256=files['lid.176.ftz']['sha256'],model_license='CC-BY-SA-3.0',code_license='MIT',
                    evidence=files,source_license_sha256=hashlib.sha256((source/'LICENSE').read_bytes()).hexdigest(),
                    compiler=subprocess.check_output([compiler,'--version'],text=True).splitlines()[0],
                    scope='Offline data-audit dependency only; no pretrained student initialization or source/corpus approval.')
    (root/'detector.json').write_text(json.dumps(descriptor,indent=2)+'\n')
    print(json.dumps({k:descriptor[k] for k in ('kind','source_revision','binary_sha256','model_sha256')}))


if __name__=='__main__':main()

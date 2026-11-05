"""Discard biography/health cues and template holes from the provisional v1 extraction."""
from collections import Counter
import argparse
import hashlib
import json
from pathlib import Path
import os
import re
import sys

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tokenizer import load

PERSONAL = re.compile(
    r'\b(?:born|died|married|marriage|diagnos\w*|hiv|aids|addict\w*|ethnic\w*|racism|sexual\w*|'
    r'gay|lesbian|bisexual|transgender|queer|lgbt\w*|religio\w*|arrest\w*|convict\w*|accused|'
    r'charged with|disab\w*|injured|illness|autism|disorder|syndrome|disease|patient\w*|'
    r'suicid\w*|abuse\w*|mental health|criminal|poverty|persecution|politician|political activist)\b',re.I)
BIOGRAPHY = re.compile(
    r'\([^()\n]{0,100}\b(?:1[0-9]{3}|20[0-2][0-9])\b[^()\n]{0,100}\)|'
    r'\b(?:she|he|her|his)\b', re.I)
GAP = re.compile(r'\b(?:a|an|about|roughly|approximately|nearly|is|was|of|on|around|over|under|by|measured|at|from|to|located) {2,}\w|\b(?:about|roughly|approximately)\s+(?:off|away|from|wide|long)\b|\s{2,}[-–—]\s|\b(?:is a|was a)\s+(?:east|west|north|south)[–-]', re.I)


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()


def refine(source,output, tighten=False):
    manifest=json.loads((source/'manifest.json').read_text())
    if sha(source/'documents.jsonl')!=manifest['documents_sha256']:
        raise ValueError('input attribution index mismatch')
    if output.exists():
        raise FileExistsError(output)
    partial=output.with_name(output.name+'.partial')
    partial.mkdir(parents=True,exist_ok=False)
    tokenizer=load()
    rows=[json.loads(line) for line in (source/'documents.jsonl').read_text().splitlines()]
    rejected=Counter()
    stats={}
    with (partial/'documents.jsonl').open('w') as docs:
        for key, shard in manifest['shards'].items():
            path=source/(key+'.u16')
            if sha(path)!=shard['sha256']:
                raise ValueError('input payload mismatch')
            data=np.memmap(path,mode='r',dtype='<u2')
            output_path=partial/path.name
            offset=count=0
            with output_path.open('wb') as f:
                for r in rows:
                    if key!=r['source']+'-'+r['split']:continue
                    ids=data[r['offset']:r['offset']+r['tokens']]
                    if r['source']=='wiki':
                        s=tokenizer.decode(ids[:-1].tolist())
                        if PERSONAL.search(s) or BIOGRAPHY.search(s):
                            rejected['biographic_or_sensitive_salience']+=1
                            continue
                        if GAP.search(s) or (tighten and re.search(r'\b(?:is|was|are|were|length|of|to|at|by)\s+[.,;]|[;,:]\s*\)', s, re.I)):
                            rejected['possible_template_hole']+=1
                            continue
                    f.write(ids.tobytes())
                    docs.write(json.dumps(dict(r,offset=offset),ensure_ascii=False)+'\n')
                    count+=1
                    offset+=len(ids)
            stats[key]=dict(tokens=offset,docs=count,sha256=sha(output_path))
    manifest.update(shards=stats,documents_sha256=sha(partial/'documents.jsonl'),
                    parent_manifest_sha256=sha(source/'manifest.json'),
                    refinement_script_sha256=sha(Path(__file__)),refinement_exclusions=rejected)
    (partial/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    os.rename(partial,output)
    print(json.dumps(stats,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('source',type=Path)
    parser.add_argument('output',type=Path)
    parser.add_argument('--tighten',action='store_true')
    args=parser.parse_args()
    refine(args.source,args.output,args.tighten)

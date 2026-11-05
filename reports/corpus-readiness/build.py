"""Build a disjoint, finite English text trial from existing local archives."""
import argparse
from array import array
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import random
import re
import sys
import unicodedata
from urllib.parse import unquote, urlsplit
import zlib

import numpy as np
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tokenizer import document_ids, load

M2 = ROOT.parent / 'inference-archive-20261029/restart/execution-v1/m2-intake'
RAW = M2 / 'raw/79ee06627f4ba2fec056fcd23c077a29238bbcbacc3187e8d1a0b47e663e9c7a.parquet'
STORY = ROOT.parent / 'inference-archive-20261029/restart/mac15m-feasibility-v1/upstream/data/TinyStories_all_data'
WIKI_REV = 'b04c8d1ceb2f5cd4588862100d08de323dccfbaa'
STORY_REV = 'f54c09fd23315a6f9c86f9dc80f725de7d8f9c64'
SALT = 'astra-local-text-v2'
WORD = re.compile(r"\w+",re.UNICODE)
RIGHTS = re.compile(r'incorporat(?:es|ed|ing) text|copyright|all rights reserved|used with permission|copied from|under licen[sc]e|creative commons|public domain text|reproduced (?:from|by)|translated from|adapted from|reprinted|attribut(?:ed|ion) to', re.I)
CONTACT = re.compile(r'[\w.+-]+@[\w.-]+\.\w+|\b\d{3}[-. ]\d{3}[-. ]\d{4}\b|\b\d{3}-\d{2}-\d{4}\b|\b(?:API[_ -]?KEY|PASSWORD)\s*[:=]',re.I)
RESIDUE = re.compile(r'https?://|<[^>]+>|\{\{|\}\}|\[\[|\]\]|\(\s*[,;)]|\|\||\bcitation needed\b|\bmay (?:also )?refer to|\bdisambiguation\b|\bformula_[0-9]|\[\s*\d+\s*\]|[<>|=\\]|\ufffd',re.I)


def sha(s):
    return hashlib.sha256(s).hexdigest()


def file_hash(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()


def norm(s):
    return ' '.join(unicodedata.normalize('NFKC',s).casefold().split())


def signature(s):
    words = WORD.findall(norm(s))
    return {zlib.crc32(' '.join(words[i:i+5]).encode()) for i in range(len(words)-4)}


def chunks8(s):
    words = WORD.findall(norm(s))
    return {' '.join(words[i:i+8]) for i in range(len(words)-7)}


def family(title):
    title = norm(unquote(title)).replace('_',' ')
    title = re.sub(r'\s*\([^()]*\)\s*$', '', title)
    return re.sub(r'\b\d{2,4}\b|\bseason \d+\b','#',title).strip()


def jsonrows(path):
    with path.open() as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def wiki_intro(row):
    text = row['text']
    paras = [p.strip() for p in text.split('\n\n')]
    out = []
    for para in paras:
        if not para or len(out)==3 or '\n' in para or para[-1] not in '.!?':
            break
        if RESIDUE.search(para) or CONTACT.search(para) or not para[0].isascii() or not para[0].isupper():
            break
        if len(para.split()) < 24 or len(para.split()) > 200 or len(para)>1500:
            break
        if len(out)>0 and len((' '.join(out)+' '+para).split())>245:
            break
        out.append(para)
    intro='\n\n'.join(out)
    if len(intro.split())<60 or len(intro.split())>245 or len(re.findall(r'[.!?](?:\s|$)',intro))<2:
        return ''
    if re.search(r'^\d|^List of |^Index of |^Outline of ', row['title']) or ':' in row['title']:
        return ''
    if re.search(r'^\s*(?:[-*•]|References|Notes|External links)|\b(?:born|died)\s*,',intro) or re.search(r'(?<!\w)[“”"]',intro):
        return ''
    english = re.findall(r'\b(?:the|a|of|for|in|to|is|was|that|and)\b',intro,re.I)
    if len(english)<5 or len({w.casefold() for w in intro.split()})/len(intro.split()) < .38:
        return ''
    return intro


def build(output):
    if output.exists():
        raise FileExistsError(output)
    partial=output.with_name(output.name+'.partial')
    partial.mkdir(parents=True,exist_ok=False)
    manifest=json.loads((ROOT/'data/feasibility-v1/manifest.json').read_text())
    for p in (RAW,STORY/'data00.json',STORY/'data01.json'):
        expected = RAW.stem if p==RAW else manifest['raw_sha256'][p.name]
        if file_hash(p)!=expected:
            raise ValueError(f'archive hash mismatch: {p.name}')
    tokenizer=load()
    pilot=ROOT/'data/feasibility-v1'
    protected_groups=set()
    exact=set()
    # Only compact bottom-k signatures are kept in memory. Reject candidate on >=4 common minima.
    inverted=defaultdict(list)
    authored_8=set()
    for filename, fields in [('runs/astra-confirmation-v1/cases.jsonl',('user_turns','criteria')),
                             ('reports/dialogue-readiness/conversation-dev-v1.jsonl',('turns','rubric'))]:
        for row in jsonrows(ROOT/filename):
            for field in fields:
                for s in row[field]: authored_8.update(chunks8(s))
    pilot_maps={p.stem:np.memmap(p,mode='r',dtype='<u2') for p in pilot.glob('*.u16')}
    def remember(s,label):
        sig=sorted(signature(s))[:16]
        for k in sig: inverted[k].append(label)
        exact.add(sha(norm(s).encode()))
    for r in jsonrows(pilot/'documents.jsonl'):
        if r['source']=='wiki': protected_groups.add(family(r['group'].split('/wiki/',1)[-1]))
        stream=pilot_maps[r['source']+'-'+r['split']]
        s=tokenizer.decode(stream[r['offset']:r['offset']+r['tokens']-1].tolist())
        remember(s,'pilot:'+r['document_id'])
    historical_ids=set()
    for f in [M2/'wikipedia-discovery-sample.jsonl', M2/'wikipedia-prose-v1/uniform-sample.jsonl', M2/'wikipedia-prose-v1/token-weighted-sample.jsonl']:
        for r in jsonrows(f):
            historical_ids.add(str(r.get('source_id',r.get('id',''))))
    protected_story={sha(norm(s['story']).encode()) for s in json.loads((STORY/'data00.json').read_bytes())}
    selected=[]
    rejections=Counter()
    near_examples=[]
    def accept(source, group, document, text, **extra):
        normalized_hash=sha(norm(text).encode())
        if normalized_hash in exact or (source=='stories' and normalized_hash in protected_story):
            rejections['exact_or_official_story_holdout']+=1
            return
        if chunks8(text)&authored_8:
            rejections['eight_word_authored_set_overlap']+=1
            return
        sig=sorted(signature(text))[:16]
        hits=Counter(label for k in sig for label in inverted[k])
        if hits and hits.most_common(1)[0][1]>=4:
            rejections['near_signature']+=1
            if len(near_examples)<8:near_examples.append([document,*hits.most_common(1)[0]])
            return
        split='validation' if int(sha((SALT+source+group).encode())[:12],16)%20==0 else 'train'
        ids=document_ids(tokenizer,text)
        if max(ids)!=50256 or ids[-1]!=50256 or 50256 in ids[:-1]:
            raise ValueError('invalid token boundary')
        for k in sig: inverted[k].append(document)
        exact.add(normalized_hash)
        selected.append((dict(source=source,group=group,document_id=document,split=split,
                              normalized_sha256=normalized_hash,tokens=len(ids),**extra),array('H',ids)))
    for b in pq.ParquetFile(RAW).iter_batches(batch_size=200,use_threads=False):
        for row in b.to_pylist():
            if row['id'] in historical_ids or family(row['title']) in protected_groups:
                rejections['archived_or_pilot_family']+=1;continue
            if RIGHTS.search(row['text']) or CONTACT.search(row['text']):
                rejections['article_notice_or_contact']+=1;continue
            text=wiki_intro(row)
            if not text:
                rejections['wiki_quality_shape']+=1;continue
            accept('wiki',family(row['title']),'wiki:'+row['id'],text,
                   canonical_url=row['url'],title=row['title'],raw_sha256=sha(row['text'].encode()),
                   raw_bytes=len(row['text'].encode()),license='Wikipedia article attribution via URL, CC BY-SA; historical card 3.0/GFDL; transition evidence 4.0',
                   transform='Extracted contiguous lead prose paragraphs; other sections omitted.')
    stories=json.loads((STORY/'data01.json').read_bytes())
    for i,row in enumerate(stories[2500:22500],2500):
        text=row['story']
        if CONTACT.search(text) or RESIDUE.search(text) or not 60<=len(text.split())<=400:
            rejections['story_quality_shape']+=1;continue
        normalized_hash=sha(norm(text).encode())
        accept('stories',normalized_hash,'data01.json:'+str(i),text,raw_sha256=sha(text.encode()),
               raw_bytes=len(text.encode()),license='TinyStories CDLA-Sharing 1.0',transform='Story field, verbatim.')
    random.Random(11813).shuffle(selected)
    stats={}
    with (partial/'documents.jsonl').open('w') as docs:
        for source in ('wiki','stories'):
            for split in ('train','validation'):
                key=source+'-'+split
                payload=partial/(key+'.u16')
                offset=0; count=0
                with payload.open('wb') as tokens:
                    for r,ids in selected:
                        if r['source']!=source or r['split']!=split:continue
                        if sys.byteorder!='little':ids.byteswap()
                        tokens.write(ids.tobytes())
                        docs.write(json.dumps(dict(r,offset=offset),ensure_ascii=False)+'\n')
                        offset+=len(ids);count+=1
                stats[key]=dict(tokens=offset,docs=count,sha256=file_hash(payload))
    summary=dict(shards=stats,documents_sha256=file_hash(partial/'documents.jsonl'),split_salt=SALT,
                 transform_script_sha256=file_hash(Path(__file__)),rejections=rejections,near_examples=near_examples,
                 distinct_pilot_protected_documents=len(list(jsonrows(pilot/'documents.jsonl'))),
                 raw_sha256={p.name:file_hash(p) for p in (RAW,STORY/'data01.json',STORY/'data00.json')},
                 revision={'wiki':WIKI_REV,'stories':STORY_REV},
                 sealed_sha256=file_hash(ROOT/'runs/astra-confirmation-v1/cases.jsonl'),
                 dev_sha256=file_hash(ROOT/'reports/dialogue-readiness/conversation-dev-v1.jsonl'))
    (partial/'manifest.json').write_text(json.dumps(summary,indent=2)+'\n')
    os.rename(partial,output)
    print(json.dumps(stats,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('output',type=Path)
    build(parser.parse_args().output)

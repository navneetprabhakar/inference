"""Bounded CPU-only candidate intake. No packing, training or protected-case reads."""
import os
for _key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS'):
    os.environ[_key] = '1'
os.environ['TOKENIZERS_PARALLELISM'] = 'false'
from collections import Counter, defaultdict
import hashlib
import heapq
import importlib.util
import json
from pathlib import Path
import re
import resource
import shutil
import sqlite3
import sys
import tarfile
import time
from urllib.request import urlopen
import zlib

import numpy as np
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tokenizer import document_ids, load

_spec = importlib.util.spec_from_file_location('mixture_foundation_helpers', ROOT/'reports/base-foundation-100m/build.py')
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)  # Pure definitions only; never invokes its build/pack.
DATA = ROOT/'data/language-mixture-v1'
STORIES = ROOT.parent/'inference-archive-20261029/restart/mac15m-feasibility-v1/upstream/data/TinyStories_all_data'
ARCHIVE_SHA = '26cf7605aca15bc4ea6fa637256400d9d01317b28ed296172b2d1dd160cd7699'
STORY_REV = 'f54c09fd23315a6f9c86f9dc80f725de7d8f9c64'
CHAT_REV = 'f73fe857d519ff6ac5af2ea67c4d3834da7b8bcc'
SALT = 'forge-language-mixture-v1-20261106'
MIB = 1024**2
TRAIN = {'stories':30_000_000, 'dialogue':20_000_000, 'web':50_000_000}
VALID = {'stories':600_000, 'dialogue':400_000, 'web':1_000_000}
CONTACT = re.compile(r'[\w.+-]+@[\w.-]+\.\w+|\b\d{3}[-. ]\d{3}[-. ]\d{4}\b|\b\d{3}-\d{2}-\d{4}\b|-----BEGIN .*PRIVATE KEY|\b(?:password|api[_ -]?key)\s*[:=]', re.I)
CHAT_BAD = re.compile(r'https?://|```|<\|\w+\|>|\b(?:role.?play|pretend you|you are a \d|you.re a \d|my address|my phone number|credit card|social security|diagnos\w*|prescription|medical advice|legal advice|stock price|current weather)\b', re.I)
EXTERNAL = re.compile(r"\b(?:I|we)(?: have|'ve)? (?:booked|reserved|ordered|sent|emailed|called|purchased|cancelled|canceled|checked your|looked up|searched online|visited|was born|grew up|work as)\b", re.I)


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def write(path, value):
    tmp = path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n')
    tmp.replace(path)


def allocated():
    return sum(p.stat().st_blocks*512 for p in DATA.rglob('*') if p.is_file())


class Limits:
    def __init__(self):
        self.started = time.monotonic()

    def check(self):
        if (ROOT/'runs/STOP').exists() or (DATA/'STOP').exists():
            raise RuntimeError('explicit STOP')
        if time.monotonic()-self.started >= 1800:
            raise RuntimeError('30-minute CPU preparation cap')
        if allocated() > 975*MIB:
            raise RuntimeError('975MiB total additional storage cap')
        db = DATA/'candidates.sqlite'
        if db.exists() and db.stat().st_size > 500*MIB:
            raise RuntimeError('500MiB candidate database cap')
        if shutil.disk_usage(DATA).free < 20*1024**3:
            raise RuntimeError('20GiB free disk floor')
        # macOS reports ru_maxrss in bytes, Linux in KiB.
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if sys.platform != 'darwin': peak *= 1024
        if peak > 3*1024**3:
            raise RuntimeError('3GiB CPU preparation peak RSS cap')


class Dedupe:
    def __init__(self):
        self.exact, self.inv, self.n = set(), defaultdict(list), 0

    def signature(self, text):
        words = base.WORD.findall(base.normalized(text))
        return heapq.nsmallest(12, {zlib.crc32(' '.join(words[i:i+5]).encode()) for i in range(len(words)-4)})

    def add(self, text, force=False):
        key = sha(base.normalized(text))
        if key in self.exact: return False
        sig = self.signature(text)
        if not force:
            hits = Counter(i for k in sig for i in self.inv[k])
            if hits and hits.most_common(1)[0][1] >= 6: return False
        self.exact.add(key)
        for k in sig: self.inv[k].append(self.n)
        self.n += 1
        return True


def story_group(row):
    instruction = row.get('instruction')
    if not isinstance(instruction, dict) or 'words' not in instruction or 'features' not in instruction:
        raise ValueError('story lacks family metadata')
    return sha(base.normalized(json.dumps({k:instruction[k] for k in ('words','features')},sort_keys=True)))


def official_holdout(limits):
    url = f'https://huggingface.co/datasets/roneneldan/TinyStories/resolve/{STORY_REV}/TinyStories-valid.txt'
    dest = DATA/'TinyStories-valid.txt'
    started = time.monotonic()
    with urlopen(url, timeout=45) as response, dest.open('xb') as out:
        count = 0
        while chunk := response.read(256*1024):
            count += len(chunk)
            if count > 25*MIB or time.monotonic()-started > 45:
                raise RuntimeError('bounded official validation download limit')
            out.write(chunk)
            limits.check()
    return dict(url=url, revision=STORY_REV, bytes=count, sha256=base.checksum(dest), license='CDLA-Sharing-1.0')


def prior_indexes(domains, dedup, tok, limits):
    hashes, urls, receipts = base.previous_documents(domains)
    held_domains = {'wikipedia.org','openstax.org'}
    paths = [ROOT/'data'/name/'documents.jsonl' for name in
             ('feasibility-v1','extended-trial-v1','extended-trial-v2','extended-trial-v3',
              'balanced-continuation-v1','base-foundation-100m')]
    story_ids = set()
    for path in paths:
        if not path.exists(): continue
        receipts[str(path.relative_to(ROOT))] = base.checksum(path)
        maps = {}
        with path.open() as stream:
            for index,line in enumerate(stream):
                if index%1000==0: limits.check()
                row=json.loads(line)
                if row.get('normalized_sha256'): hashes.add(row['normalized_sha256'])
                url=row.get('canonical_url',row.get('group',''))
                if isinstance(url,str) and url.startswith('http'):
                    domain,canonical=domains.canonical(url)
                    if canonical: urls.add(canonical)
                    if row.get('split')=='validation' and domain: held_domains.add(domain)
                source=row.get('source')
                if source=='stories': story_ids.add(row['document_id'])
                if source=='stories' or row.get('split')=='validation':
                    shard_source='fineweb' if source=='fineweb' else source
                    binary=path.parent/f'{shard_source}-{row["split"]}.u16'
                    if not binary.exists():
                        raise ValueError('missing prior source stream for near exclusion: '+str(binary))
                    if binary not in maps: maps[binary]=np.memmap(binary,mode='r',dtype='<u2')
                    text=tok.decode(maps[binary][row['offset']:row['offset']+row['tokens']-1].tolist())
                    dedup.add(text,force=True)
        maps.clear()
    return hashes,urls,held_domains,receipts,story_ids


def build():
    if DATA.exists(): raise FileExistsError('immutable candidate output already exists')
    DATA.mkdir(parents=True)
    limits=Limits()
    if shutil.disk_usage(DATA).free < 20*1024**3+975*MIB:
        raise RuntimeError('preparation disk reserve does not fit')
    tok=load(); dedup=Dedupe(); domains=base.Domains()
    counts=Counter(); rejected=Counter(); source_files=[]; held_story_groups=set()
    connection=None
    try:
        holdout=official_holdout(limits)
        holdout_stories=[s.strip() for s in (DATA/'TinyStories-valid.txt').read_text().split('<|endoftext|>') if s.strip()]
        if len(holdout_stories)<1000: raise ValueError('official story validation download has unexpected format')
        for index,text in enumerate(holdout_stories):
            if index%1000==0:limits.check()
            dedup.add(text,force=True)
        official_hashes={sha(base.normalized(s)) for s in holdout_stories}
        del holdout_stories
        old_hashes,old_urls,held_domains,old_receipts,old_story_ids=prior_indexes(domains,dedup,tok,limits)
        archive=STORIES.with_suffix('.tar.gz')
        if base.checksum(archive)!=ARCHIVE_SHA:raise ValueError('TinyStories source archive checksum changed')
        limits.check()
        # Archive member comparison validates each additional raw file before use.
        archive_stream=tarfile.open(archive,mode='r:gz')
        members={Path(m.name).name:m for m in archive_stream.getmembers() if m.isfile()}
        verified_story={}
        def story_rows(name):
            path=STORIES/name
            actual=base.checksum(path)
            with archive_stream.extractfile(members[name]) as stream:
                expected=hashlib.file_digest(stream,'sha256').hexdigest()
            if actual!=expected:raise ValueError('story raw member differs from verified archive')
            verified_story[name]=actual
            source_files.append(dict(source='stories',path=str(path),sha256=actual,bytes=path.stat().st_size,archive_sha256=ARCHIVE_SHA,revision=STORY_REV))
            limits.check()
            return json.loads(path.read_bytes())
        rows=story_rows('data00.json')
        for index,row in enumerate(rows):
            if index%1000==0:limits.check()
            dedup.add(row['story'],force=True)
            held_story_groups.add(story_group(row))
        del rows
        connection=sqlite3.connect(DATA/'candidates.sqlite')
        connection.execute('pragma journal_mode=DELETE')
        connection.execute('pragma temp_store=MEMORY')
        connection.execute('pragma max_page_count=128000')
        connection.execute('create table documents (doc_id text primary key, source text, source_file integer, source_row integer, family text, split text, tokens integer, normalized_sha256 text unique, raw_sha256 text, canonical_url text, text text)')
        def ready(source):
            return all(counts[f'{source}_{split}_tokens']>=int(targets[source]*1.05) for split,targets in [('train',TRAIN),('validation',VALID)])
        def emit(source,doc_id,text,group,file_index,row_index,url=''):
            split='validation' if int(sha(SALT+source+group)[:12],16)%50==0 else 'train'
            target=(TRAIN if split=='train' else VALID)[source]
            if counts[f'{source}_{split}_tokens']>=int(target*1.05):return
            norm_hash=sha(base.normalized(text))
            if norm_hash in old_hashes or (url and url in old_urls):
                rejected[source+'_prior_document_or_url']+=1;return
            if not dedup.add(text):rejected[source+'_exact_or_near_duplicate']+=1;return
            ids=document_ids(tok,text)
            if ids[-1]!=50256 or 50256 in ids[:-1] or min(ids)<0 or max(ids)>50256:
                raise ValueError('invalid GPT2 document boundary')
            n=len(ids)
            connection.execute('insert into documents values (?,?,?,?,?,?,?,?,?,?,?)',
                               (doc_id,source,file_index,row_index,group,split,n,norm_hash,sha(text),url,text))
            counts[f'{source}_{split}_tokens']+=n
            counts[f'{source}_{split}_docs']+=1
            if split=='validation' and n>=33:counts[f'{source}_validation_eligible_docs']+=1
            if sum(v for k,v in counts.items() if k.endswith('_docs'))%500==0:
                connection.commit();limits.check()
                write(DATA/'status.json',dict(state='preparing_candidates',counts=dict(counts),rejections=dict(rejected),seconds=time.monotonic()-limits.started,allocated_bytes=allocated()))
        # Preserve complete short conversations; retain only the publisher's short conversational constituent.
        snapshot=ROOT.parent/'inference-snapshot-20261105-c5b911b/data'
        for folder,name in [('sft-v1','smol-smoltalk.parquet'),('sft-v3','smol-smoltalk-1.parquet')]:
            raw=snapshot/folder/'raw'/name
            receipt=json.loads((raw.parent/'receipt.json').read_text())
            if receipt['revision']!=CHAT_REV or base.checksum(raw)!=receipt['sha256'] or raw.stat().st_size!=receipt['bytes']:
                raise ValueError('chat source receipt mismatch')
            file_index=len(source_files);source_files.append(dict(source='dialogue',path=str(raw),**receipt))
            index=0
            for batch in pq.ParquetFile(raw).iter_batches(batch_size=128,use_threads=False):
                limits.check()
                for row in batch.to_pylist():
                    row_index=index;index+=1
                    if ready('dialogue'):break
                    messages=row['messages']
                    if row['source']!='smol-magpie-ultra-short' or not 2<=len(messages)<=8 or len(messages)%2:
                        rejected['dialogue_source_or_turn_count']+=1;continue
                    if any(m.get('role')!=('user' if i%2==0 else 'assistant') or not isinstance(m.get('content'),str) or not m['content'].strip() for i,m in enumerate(messages)):
                        rejected['dialogue_roles']+=1;continue
                    text='\n'.join(m['role'].capitalize()+': '+m['content'].strip() for m in messages)
                    if CONTACT.search(text) or CHAT_BAD.search(text) or base.CONTROL.search(text) or any(EXTERNAL.search(m['content']) for m in messages if m['role']=='assistant'):
                        rejected['dialogue_contact_external_or_scope']+=1;continue
                    ids=tok.encode(text).ids
                    if not 48<=len(ids)<=511 or any(len(tok.encode(m['content']).ids)>128 for m in messages if m['role']=='assistant'):
                        rejected['dialogue_length']+=1;continue
                    # Opening-task family abstracts numbers and quoted strings, not just exact message bytes.
                    opening=base.normalized(messages[0]['content'])
                    opening=re.sub(r'\b\d+(?:\.\d+)?\b','<number>',opening)
                    opening=re.sub(r'"[^"\n]*"', '<quoted>',opening)
                    group=sha(opening)
                    emit('dialogue',f'{folder}:{row_index}',text,group,file_index,row_index)
                if ready('dialogue'):break
        for number in range(1,5):
            if ready('stories'):break
            name=f'data{number:02d}.json';rows=story_rows(name);file_index=len(source_files)-1
            for row in rows:
                if sha(base.normalized(row['story'])) in old_hashes or sha(base.normalized(row['story'])) in official_hashes:
                    held_story_groups.add(story_group(row))
            for index,row in enumerate(rows):
                if index%500==0:limits.check()
                if ready('stories'):break
                text=row['story'];group=story_group(row)
                if group in held_story_groups or f'{name}:{index}' in old_story_ids:
                    rejected['stories_held_family']+=1;continue
                if not 50<=len(text.split())<=400 or CONTACT.search(text) or base.CONTROL.search(text) or text[-1:] not in '.!?"':
                    rejected['stories_quality']+=1;continue
                emit('stories',f'{name}:{index}',text,group,file_index,index)
            del rows
        archive_stream.close()
        # Later raw members can reveal a held family matching earlier candidates.
        connection.execute('create index document_family on documents(source,family)')
        connection.executemany("delete from documents where source='stories' and family=?", ((g,) for g in held_story_groups))
        for split in ('train','validation'):
            n,t=connection.execute("select count(*),coalesce(sum(tokens),0) from documents where source='stories' and split=?",(split,)).fetchone()
            counts[f'stories_{split}_docs']=n;counts[f'stories_{split}_tokens']=t
        counts['stories_validation_eligible_docs']=connection.execute("select count(*) from documents where source='stories' and split='validation' and tokens>=33").fetchone()[0]
        if base.checksum(base.RAW)!=base.RAW_SHA:raise ValueError('web raw source checksum mismatch')
        file_index=len(source_files);source_files.append(dict(source='web',path=str(base.RAW),sha256=base.RAW_SHA,revision=base.REVISION,bytes=base.RAW.stat().st_size))
        index=0
        for batch in pq.ParquetFile(base.RAW).iter_batches(batch_size=128,use_threads=False):
            limits.check()
            for row in batch.to_pylist():
                row_index=index;index+=1
                if ready('web'):break
                reason=base.quality(row)
                if reason:rejected['web_'+reason]+=1;continue
                domain,url=domains.canonical(row['url'])
                if not domain or domain in held_domains:
                    rejected['web_prior_validation_domain']+=1;continue
                emit('web',str(row['id']),row['text'],domain,file_index,row_index,url)
            if ready('web'):break
        connection.commit();connection.close();connection=None
        limits.check()
        shortfalls={f'{source}_{split}':max(0,targets[source]-counts[f'{source}_{split}_tokens']) for source in TRAIN for split,targets in [('train',TRAIN),('validation',VALID)]}
        manifest=dict(state='prepared_not_admitted',pending='Root custody (including historical chat dev/test and current private cases) then independent quality review. NO PACKING.',
                      candidate_database_sha256=base.checksum(DATA/'candidates.sqlite'),counts=dict(counts),shortfalls=shortfalls,rejections=dict(rejected),
                      train_targets=TRAIN,validation_targets=VALID,candidate_headroom_fraction=.05,source_files=source_files,
                      official_story_validation=holdout,official_story_validation_docs=len(official_hashes),original_data00_holdout='Entire raw file excluded separately; not relabeled as official validation',
                      prior_indexes=old_receipts,held_web_domains=sorted(held_domains),held_story_families=len(held_story_groups),
                      source_licenses={'stories':'CDLA-Sharing-1.0','dialogue':'Apache-2.0 publisher card; only smol-magpie-ultra-short constituent retained','web':'ODC-By1.0 collection and CommonCrawl source terms'},
                      split_salt=SALT,split='2% hash by source-family/domain; complete documents remain together; approximate cross-split near duplicates withheld',
                      tokenization='Exact existing GPT2 tokenizer; EOT50256 appended; no token files yet',
                      evaluation_plan='Source-stratified heldout >=128documents/source; variable32..512target windows within complete documents, report document-mean and target-weighted CE separately; retain original web256window diagnostics. Not forced to512long stories.',
                      limitation='Approximate lexical/family grouping does not establish semantic independence or conversational quality. Short SFT transcripts here are next-token text, not assistant-supervised targets. No tool execution examples.',
                      builder_sha256=base.checksum(Path(__file__)),protocol_sha256=base.checksum(Path(__file__).with_name('PROTOCOL.md')),
                      seconds=time.monotonic()-limits.started,allocated_bytes=allocated())
        write(DATA/'candidate-manifest.json',manifest)
        write(DATA/'status.json',dict(state='awaiting_root_custody',counts=dict(counts),shortfalls=shortfalls,allocated_bytes=allocated()))
        print(json.dumps(dict(state=manifest['state'],counts=dict(counts),shortfalls=shortfalls,allocated_bytes=allocated())))
    except BaseException as error:
        if connection is not None:connection.rollback();connection.close()
        write(DATA/'status.json',dict(state='stopped_not_admitted',error=f'{type(error).__name__}: {error}',counts=dict(counts),rejections=dict(rejected),seconds=time.monotonic()-limits.started,allocated_bytes=allocated()))
        raise


if __name__=='__main__':
    build()

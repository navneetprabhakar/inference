"""Build a finite, shuffled GPT-2 FineWeb-Edu corpus from verified local raw text."""
import argparse
from collections import Counter, defaultdict
import hashlib
import heapq
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import time
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import urlopen
import zlib

import numpy as np
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tokenizer import EOT, document_ids, load

REPORT = ROOT / 'reports/base-foundation-100m'
DATA = ROOT / 'data/base-foundation-100m'
RAW = ROOT.parent / 'inference-snapshot-20261105-c5b911b/data/continuation-v1/raw/fineweb-new.parquet'
RAW_SHA = '3fcf2dc69cd52503986276d3d2d26a8c356d0f2ea28a0de4fdbda8cf87755693'
REVISION = '87f09149ef4734204d70ed1d046ddc9ca3f2b8f9'
CARD = f'https://huggingface.co/datasets/HuggingFaceFW/fineweb-edu/raw/{REVISION}/README.md'
PSL = 'https://publicsuffix.org/list/public_suffix_list.dat'
SALT = 'forge-base-fineweb-20261106-v1'
WORD = re.compile(r"\w+", re.UNICODE)
CONTACT = re.compile(r'[\w.+-]+@[\w.-]+\.\w+|\b\d{3}-\d{2}-\d{4}\b|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\b(?:API[_ -]?KEY|PASSWORD)\s*[:=]\s*\S+', re.I)
CONTROL = re.compile('[\x00-\x08\x0b\x0c\x0e-\x1f\ufffd]')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def checksum(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write_json(path, value):
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    os.replace(temp, path)


def normalized(text):
    return ' '.join(unicodedata.normalize('NFKC', text).casefold().split())


def provenance():
    REPORT.mkdir(exist_ok=True)
    for name, url in (('source-card.md', CARD), ('public_suffix_list.dat', PSL)):
        dest = REPORT / name
        if not dest.exists():
            with urlopen(url, timeout=45) as response:
                content = response.read(2_000_000)
            dest.write_bytes(content)
    if checksum(RAW) != RAW_SHA:
        raise ValueError('FineWeb source hash mismatch')
    return dict(dataset='HuggingFaceFW/fineweb-edu', revision=REVISION,
                upstream_path='sample/10BT/001_00000.parquet', raw_path=str(RAW),
                raw_sha256=RAW_SHA, raw_bytes=RAW.stat().st_size,
                source_card_url=CARD, source_card_sha256=checksum(REPORT/'source-card.md'),
                psl_url=PSL, psl_sha256=checksum(REPORT/'public_suffix_list.dat'),
                license='ODC-By 1.0 for dataset; CommonCrawl terms apply to source collection',
                use='Local noncommercial model research; source URLs and raw text hashes retained. No claim of universal per-page rights clearance.')


class Domains:
    def __init__(self):
        rules = (REPORT/'public_suffix_list.dat').read_text().splitlines()
        self.exact, self.wild, self.exception = set(), set(), set()
        for raw in rules:
            rule = raw.strip()
            if not rule or rule.startswith('//'):
                continue
            target = self.exception if rule.startswith('!') else self.wild if rule.startswith('*.') else self.exact
            rule = rule.removeprefix('!').removeprefix('*.')
            target.add(rule.encode('idna').decode('ascii'))

    def canonical(self, url):
        try:
            parsed = urlsplit(url)
            host = (parsed.hostname or '').strip('.').lower().encode('idna').decode('ascii')
            if parsed.scheme not in ('http', 'https') or not host or ':' in host or host.replace('.', '').isdigit():
                return None, None
            labels = host.split('.')
            suffix_length = 1
            for i in range(len(labels)):
                tail = '.'.join(labels[i:])
                if tail in self.exception:
                    suffix_length = len(labels)-i-1
                    break
                if tail in self.exact:
                    suffix_length = max(suffix_length, len(labels)-i)
                if i and tail in self.wild:
                    suffix_length = max(suffix_length, len(labels)-i+1)
            domain = '.'.join(labels[-min(len(labels),suffix_length+1):])
            query = urlencode(sorted((k,v) for k,v in parse_qsl(parsed.query,keep_blank_values=True)
                                     if not k.lower().startswith('utm_') and k.lower() not in ('fbclid','gclid')))
            canonical = urlunsplit(('https',host.removeprefix('www.'),parsed.path.rstrip('/') or '/',query,''))
            return domain, canonical
        except (ValueError, UnicodeError):
            return None, None


def previous_documents(domains):
    hashes, urls = set(), set()
    paths = [ROOT/'data'/name/'documents.jsonl' for name in ('feasibility-v1','extended-trial-v1','extended-trial-v2','extended-trial-v3','balanced-continuation-v1')]
    receipts = {}
    for path in paths:
        if not path.exists():
            continue
        receipts[str(path.relative_to(ROOT))] = checksum(path)
        with path.open() as stream:
            for line in stream:
                row = json.loads(line)
                if row.get('normalized_sha256'):
                    hashes.add(row['normalized_sha256'])
                url = row.get('canonical_url',row.get('group',''))
                if isinstance(url,str) and url.startswith('http'):
                    _, canonical = domains.canonical(url)
                    if canonical:
                        urls.add(canonical)
    return hashes, urls, receipts


def quality(row):
    if row['language'] != 'en' or row['language_score'] < .9 or row['int_score'] < 3:
        return 'publisher_language_or_education_score'
    text = row['text']
    if not 400 <= len(text) <= 80_000 or not 100 <= row['token_count'] <= 12_000:
        return 'document_length'
    if CONTROL.search(text):
        return 'encoding_controls'
    if CONTACT.search(text):
        return 'obvious_contact_or_secret_pattern'
    words = WORD.findall(text)
    if len(words) < 60 or sum(ch.isalpha() for ch in text)/len(text) < .55:
        return 'nonprose_density'
    if max(Counter(w.casefold() for w in words).values()) / len(words) > .16:
        return 'word_repetition'
    lines = [line.strip() for line in text.splitlines() if len(line.strip()) > 20]
    if lines and (len(lines)-len(set(lines)))/len(lines) > .3:
        return 'line_repetition'
    return None


def prepare():
    if DATA.exists():
        raise FileExistsError(DATA)
    source = provenance()
    DATA.mkdir(parents=True)
    domains = Domains()
    old_hashes, old_urls, old_receipts = previous_documents(domains)
    connection = sqlite3.connect(DATA/'candidates.sqlite')
    connection.execute('create table documents (priority text primary key, row_index integer, doc_id text, domain text, canonical_url text, split text, normalized_sha256 text, raw_sha256 text, publisher_tokens integer, text text)')
    rejected = Counter()
    counts = Counter()
    scan = 0
    started = time.monotonic()
    for batch in pq.ParquetFile(RAW).iter_batches(batch_size=256, use_threads=False):
        for row in batch.to_pylist():
            index = scan
            scan += 1
            priority = digest((SALT+'order'+str(row['id'])).encode())
            if int(priority[:8],16) >= 0x55555555:
                rejected['outside_fixed_one_third_hash_sample'] += 1
                continue
            reason = quality(row)
            if reason:
                rejected[reason] += 1
                continue
            domain,url = domains.canonical(row['url'])
            if not domain:
                rejected['invalid_source_url'] += 1
                continue
            norm_hash = digest(normalized(row['text']).encode())
            if norm_hash in old_hashes or url in old_urls:
                rejected['previous_local_document_or_url'] += 1
                continue
            split = 'validation' if int(digest((SALT+'split'+domain).encode())[:8],16)%50==0 else 'train'
            try:
                connection.execute('insert into documents values (?,?,?,?,?,?,?,?,?,?)',
                    (priority,index,str(row['id']),domain,url,split,norm_hash,digest(row['text'].encode()),int(row['token_count']),row['text']))
            except sqlite3.IntegrityError:
                rejected['duplicate_source_id'] += 1
                continue
            counts[split+'_docs'] += 1
            counts[split+'_publisher_tokens'] += row['token_count']
        connection.commit()
        if scan % 4096 == 0:
            write_json(DATA/'prepare-status.json',dict(scanned=scan,counts=dict(counts),seconds=time.monotonic()-started))
    connection.execute('create index document_hash on documents(normalized_sha256)')
    connection.commit()
    connection.close()
    report = dict(source=source,salt=SALT,counts=dict(counts),rejections=dict(rejected),scanned=scan,
                  candidate_database_sha256=checksum(DATA/'candidates.sqlite'),previous_document_indexes=old_receipts,
                  filters='English probability >=0.9; education integer score>=3; practical document length, prose density, obvious contact/secret and repetitive-corruption checks. No topic exclusion.',
                  pending='Exact/near dedup, independent protected-set custody, GPT-2 counting and final packing remain.')
    write_json(DATA/'candidate-manifest.json',report)
    write_json(REPORT/'candidate-manifest.json',report)
    print(json.dumps(dict(counts=counts,seconds=time.monotonic()-started,database=str(DATA/'candidates.sqlite'))))


def pack(exclusions, train_target, validation_target):
    meta = json.loads((DATA/'candidate-manifest.json').read_text())
    if checksum(DATA/'candidates.sqlite') != meta['candidate_database_sha256']:
        raise ValueError('Candidate database changed')
    receipt = json.loads(exclusions.read_text())
    if receipt['candidate_database_sha256'] != meta['candidate_database_sha256'] or receipt.get('state') != 'cleared':
        raise ValueError('Matching independent custody receipt required')
    denied = set(receipt['excluded_doc_ids'])
    if (DATA/'manifest.json').exists():
        raise FileExistsError('Final corpus already exists')
    connection=sqlite3.connect(f'file:{DATA / "candidates.sqlite"}?mode=ro',uri=True)
    counts=Counter();rejected=Counter();exact=set();urls=set();inverted=defaultdict(list);domain_tokens=Counter()
    tok=load(); documents=[];windows=[];samples=[];start=time.monotonic()
    streams={split:(DATA/f'fineweb-{split}.u16').open('xb') for split in ('train','validation')}
    targets={'train':train_target,'validation':validation_target}
    try:
        for priority,row_index,doc_id,domain,url,split,norm_hash,raw_hash,publisher_tokens,text in connection.execute('select * from documents order by priority'):
            if counts[split+'_tokens']>=targets[split]:
                continue
            if doc_id in denied:
                rejected['protected_custody']+=1
                continue
            if norm_hash in exact or url in urls:
                rejected['exact_text_or_canonical_url_duplicate']+=1
                continue
            words=WORD.findall(normalized(text))
            fingerprint=heapq.nsmallest(12,{zlib.crc32(' '.join(words[i:i+5]).encode()) for i in range(len(words)-4)})
            matches=Counter(other for code in fingerprint for other in inverted[code])
            if matches and matches.most_common(1)[0][1]>=6:
                rejected['near_duplicate_bottom12_fivegrams']+=1
                continue
            ids=document_ids(tok,text)
            if EOT in ids[:-1] or ids[-1]!=EOT or min(ids)<0 or max(ids)>EOT:
                raise ValueError('Unexpected GPT-2 token boundary')
            if domain_tokens[split,domain]+len(ids)>targets[split]*.1:
                rejected['domain_token_cap_10_percent']+=1
                continue
            offset=counts[split+'_tokens']
            np.asarray(ids,dtype='<u2').tofile(streams[split])
            record=dict(source='fineweb',split=split,document_id=doc_id,source_row=row_index,group=domain,
                        canonical_url=url,normalized_sha256=norm_hash,raw_sha256=raw_hash,offset=offset,
                        tokens=len(ids),publisher_tokens=publisher_tokens,order_sha256=priority,
                        raw_source_sha256=RAW_SHA)
            documents.append(record)
            exact.add(norm_hash);urls.add(url)
            for code in fingerprint:inverted[code].append(doc_id)
            domain_tokens[split,domain]+=len(ids)
            counts[split+'_tokens']+=len(ids);counts[split+'_docs']+=1
            if split=='validation' and len(ids)>=1025 and len(windows)<256:
                local=int(digest((SALT+'window'+doc_id).encode())[:12],16)%(len(ids)-1025+1)
                windows.append(dict(start=offset+local,max_length=1025,document_id=doc_id,document_sha256=raw_hash,
                                    group=domain,document_offset=offset,document_tokens=len(ids)))
            if len(samples)<32 and int(priority[8:12],16)%31==0:
                samples.append(dict(record=record,text=text))
            if len(documents)%5000==0:
                write_json(DATA/'pack-status.json',dict(counts=dict(counts),rejections=dict(rejected),seconds=time.monotonic()-start))
            if all(counts[s+'_tokens']>=targets[s] for s in targets):break
    finally:
        for stream in streams.values():stream.flush();os.fsync(stream.fileno());stream.close()
        connection.close()
    if counts['train_tokens']<train_target or counts['validation_tokens']<validation_target or len(windows)<128:
        raise ValueError(f'Insufficient finite corpus: {dict(counts)}, {len(windows)} validation windows')
    with (DATA/'documents.jsonl').open('x') as out:
        for row in documents:out.write(json.dumps(row,ensure_ascii=False)+'\n')
    write_json(DATA/'validation-blocks.json',windows)
    write_json(DATA/'quality-sample.json',samples)
    manifest=dict(shards={f'fineweb-{s}':dict(tokens=counts[s+'_tokens'],docs=counts[s+'_docs'],sha256=checksum(DATA/f'fineweb-{s}.u16')) for s in targets},
                  source=meta['source'],documents_sha256=checksum(DATA/'documents.jsonl'),validation_blocks_sha256=checksum(DATA/'validation-blocks.json'),
                  custody_receipt_sha256=checksum(exclusions),candidate_database_sha256=meta['candidate_database_sha256'],
                  tokenizer='verified GPT-2 50257 IDs; EOT50256',split_salt=SALT,split='registrable domain via pinned Public Suffix List; 2% hash bucket validation',
                  order='Whole documents ordered by fixed SHA256 priority before packing; neither training nor validation repeats a document',
                  rejections=dict(rejected),document_boundary='Append EOT50256 to each complete source text; training may cross documents through EOT',
                  dedup='Exact normalized text and canonical URL; conservative rejection on six shared bottom12 CRC32 fivegram fingerprints. This is an approximate duplicate screen.',
                  domain_cap='At most10% of requested tokens per registrable domain per split',seconds=time.monotonic()-start)
    write_json(DATA/'manifest.json',manifest);write_json(REPORT/'manifest.json',manifest)
    print(json.dumps(dict(counts=counts,validation_windows=len(windows),seconds=time.monotonic()-start)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('phase',choices=('prepare','pack'))
    p.add_argument('--exclusions',type=Path)
    p.add_argument('--train-tokens',type=int,default=120_000_000)
    p.add_argument('--validation-tokens',type=int,default=2_000_000)
    a=p.parse_args()
    if a.phase=='prepare':prepare()
    elif a.exclusions is None:p.error('--exclusions is required for pack')
    else:pack(a.exclusions,a.train_tokens,a.validation_tokens)

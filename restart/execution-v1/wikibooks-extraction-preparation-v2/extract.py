"""Bounded offline Enterprise HTML inspection/extraction; never admits data.

Reads existing NDJSON or tar.gz, never extracts tar paths to disk. Requires an
explicit input SHA256. Historical schema differences fail closed for review.
"""
import argparse
import hashlib
import io
import json
import re
import gzip
import shutil
import sqlite3
import tarfile
import unicodedata
from pathlib import Path
from urllib.parse import unquote, urlparse

from bs4 import BeautifulSoup

SCHEMA_DOCS = ['https://enterprise.wikimedia.com/docs/data-dictionary/',
               'https://enterprise.wikimedia.com/docs/snapshot/']

def digest(b):
    return hashlib.sha256(b).hexdigest()

def file_sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''):
            h.update(b)
    return h.hexdigest()

def canon(s):
    return unicodedata.normalize('NFC', re.sub(r'\s+', ' ', s)).strip()

def validate(r):
    """Strict profile of documented keys, not a guess at historical aliases."""
    if not isinstance(r, dict):
        raise ValueError('record_not_object')
    for key in ['identifier', 'name', 'url', 'version', 'article_body', 'license']:
        if key not in r:
            raise ValueError('missing_'+key)
    for key in ['identifier']:
        if type(r[key]) is not int or r[key] < 1:
            raise ValueError('invalid_'+key)
    if not isinstance(r['version'], dict) or type(r['version'].get('identifier')) is not int:
        raise ValueError('missing_or_invalid_revision_id')
    if r['version']['identifier'] < 1:
        raise ValueError('invalid_revision_id')
    if not isinstance(r['name'], str) or not r['name'].strip():
        raise ValueError('missing_title')
    if not isinstance(r['article_body'],dict) or not isinstance(r['article_body'].get('html'),str):
        raise ValueError('missing_html')
    if not isinstance(r['url'],str):
        raise ValueError('invalid_url')
    u=urlparse(r['url'])
    if u.scheme not in ['http','https'] or u.hostname!='en.wikibooks.org' or not u.path.startswith('/wiki/'):
        raise ValueError('unexpected_project_url')
    if not isinstance(r['license'],list) or not r['license'] or not all(isinstance(x,dict) and isinstance(x.get('url'),str) for x in r['license']):
        raise ValueError('missing_structured_license_provenance')
    if 'namespace' in r and r['namespace'].get('identifier')!=0:
        raise ValueError('non_main_namespace')
    if r.get('is_part_of',{}).get('identifier','enwikibooks')!='enwikibooks':
        raise ValueError('wrong_project')
    # A namespace marker is not inferred solely from title punctuation.
    title=canon(r['name'].replace('_',' '))
    urltitle=canon(unquote(u.path[len('/wiki/'):]).replace('_',' '))
    if title != urltitle:
        raise ValueError('title_url_mismatch')
    return title

def extract_record(r):
    title=validate(r)
    root=title.split('/',1)[0]
    soup=BeautifulSoup(r['article_body']['html'],'lxml')
    content=soup.body or soup
    holds=[]
    if re.search(r'(?:^|/)(?:print(?:able)?[ _-]?version|all[ _-]?chapters|complete[ _-]?book|collection)(?:/|$)',title,re.I):
        holds.append('print_or_aggregate_page')
    if ':' in root:
        holds.append('colon_root_needs_namespace_review')
    if soup.select('table'):
        holds.append('table_structure_requires_review')
    if soup.select('math, .mwe-math-element, img.mwe-math-fallback-image-inline, img.tex'):
        holds.append('math_requires_lossless_representation')
    if soup.select('.error, .mw-ext-cite-error, .mw-parser-output .error, [typeof*="mw:Error"]'):
        holds.append('render_or_template_error')
    if re.search(r'\{\{[^{}]{1,300}\}\}|\[\[[^\[\]]{1,300}\]\]',content.get_text(' ',strip=True)):
        holds.append('unexpanded_markup')
    if soup.select('a.new[href*="Template"], a.new[href*="Module"], a.new[href*="/wiki/"]'):
        holds.append('missing_link_or_template_dependency')
    if content.select('iframe, object, embed, video, audio, canvas, svg'):
        holds.append('nontext_dependency')
    if content.select('img') and re.search(r'\b(?:shown (?:above|below)|(?:diagram|figure|image|graph|picture) (?:above|below)|following (?:diagram|figure|graph)|see (?:the )?(?:diagram|figure|graph))\b',content.get_text(' ',strip=True),re.I):
        holds.append('visual_dependency')
    # Navigation, edit affordances and hidden content are removed, but rendered
    # transclusion content is preserved: not every template is boilerplate.
    removed=[]
    for node in list(content.select('script, style, noscript, nav, .navbox, .vertical-navbox, .mw-editsection, .toc, #toc, .noprint, [hidden], [aria-hidden="true"]')):
        removed.append({'tag':node.name,'class':node.get('class',[]),'text_sha256':digest(node.get_text().encode())})
        node.decompose()
    # Mark formulas visibly while keeping the whole document held. They must
    # never silently disappear and make equations look like valid prose.
    for node in list(content.select('math, .mwe-math-element, img.mwe-math-fallback-image-inline, img.tex')):
        if node.parent is None:
            continue
        annotation=node.find('annotation',attrs={'encoding':'application/x-tex'}) if node.name!='img' else None
        formula=annotation.get_text() if annotation else node.get('alttext',node.get('alt',''))
        node.replace_with('[FORMULA REQUIRES REVIEW'+(': '+formula if formula else '')+']')
    blocks=[]
    tags={'h1','h2','h3','h4','h5','h6','p','li','pre','blockquote','dt','dd','table'}
    for node in content.find_all(list(tags)):
        # Highest structural block wins, avoiding p+li and table-cell repeats.
        if any(p.name in tags for p in node.parents if p is not content):
            continue
        text=node.get_text('\n' if node.name in ['pre','table'] else ' ',strip=True)
        text=canon(text) if node.name not in ['pre','table'] else text.strip()
        if text:
            blocks.append({'kind':node.name,'text':text,'sha256':digest(text.encode())})
    if not blocks:
        holds.append('no_structural_content_blocks')
    if not any(x['kind'] in ['p','li','pre','blockquote'] for x in blocks):
        holds.append('no_expository_content')
    text='\n\n'.join(x['text'] for x in blocks)
    if len(text)<200:
        holds.append('short_page_or_contents_only')
    metadata={k:v for k,v in r.items() if k!='article_body'}
    return {'page_id':r['identifier'],'revision_id':r['version']['identifier'],
            'title':title,'url':r['url'],'book_root_title':root,
            'family_id':'enwikibooks:book:'+digest(root.encode()),
            'family_rule':'NFC title before first slash; conservative grouping, aliases still need cross-book resolution',
            'license_provenance':r['license'],'source_metadata':metadata,
            'original_html':r['article_body']['html'],
            'html_sha256':digest(r['article_body']['html'].encode()),
            'wikitext_sha256':digest(r['article_body']['wikitext'].encode()) if isinstance(r['article_body'].get('wikitext'),str) else None,
            'blocks':blocks,'text':text,'text_sha256':digest(text.encode()),
            'removed_elements':removed,'holds':sorted(set(holds)),
            'training_admitted':False,'status':'EXTRACTED_FOR_REVIEW_ONLY'}

def stream_lines(path,max_line_bytes,max_decompressed_bytes,prefix_discovery=False):
    total=0
    def lines(f,member):
        nonlocal total
        n=0
        while True:
            b=f.readline(max_line_bytes+1)
            if not b:break
            n+=1;total+=len(b)
            if len(b)>max_line_bytes:raise ValueError('record_line_limit_exceeded')
            if total>max_decompressed_bytes:raise ValueError('decompressed_read_limit_exceeded')
            if b.strip():yield member,n,b
    if path.name.endswith('.tar.gz') or path.name.endswith('.tgz'):
        class CappedDecoded:
            """Counts gzip-decoded tar headers, padding and skipped contents too."""
            def __init__(self,f):self.f=f;self.n=0
            def read(self,n=-1):
                # tar streaming requests bounded blocks; never issue read-all.
                if n<0:n=max_decompressed_bytes+1
                b=self.f.read(min(n,max_decompressed_bytes-self.n+1));self.n+=len(b)
                if self.n>max_decompressed_bytes:raise ValueError('decoded_tar_container_limit_exceeded')
                return b
        with gzip.open(path,'rb') as decoded, tarfile.open(fileobj=CappedDecoded(decoded),mode='r|') as tar:
            for member in tar:
                if not member.isfile():
                    if member.isdir():continue
                    raise ValueError('unsafe_tar_nonregular_member')
                if not member.name.endswith(('.ndjson','.json')):
                    raise ValueError('unexpected_tar_member_'+member.name)
                if member.size>max_decompressed_bytes and not prefix_discovery:
                    raise ValueError('tar_member_declared_size_exceeds_budget')
                f=tar.extractfile(member)
                yield from lines(f,member.name)
    elif path.suffix in ['.ndjson','.jsonl','.json']:
        with path.open('rb') as f:yield from lines(f,path.name)
    else:raise ValueError('unsupported_container')

class OutputBudget:
    def __init__(self,path,cap,free_floor):
        self.path=path;self.cap=cap;self.free_floor=free_floor
    def size(self):return sum(f.stat().st_size for f in self.path.rglob('*') if f.is_file())
    def check(self,additional=0):
        # Keep a small separate allowance for a terminal diagnostic receipt.
        if self.size()+additional>self.cap-16384:raise ValueError('aggregate_output_byte_limit_exceeded')
        if shutil.disk_usage(self.path).free<self.free_floor+additional:raise ValueError('disk_reservation_floor_reached')
    def write(self,f,payload):
        n=len(payload.encode('utf-8')) if isinstance(payload,str) else len(payload)
        self.check(n);f.write(payload);f.flush();self.check()

def run(args):
    if file_sha(args.input)!=args.sha256:raise ValueError('input_hash_mismatch')
    args.output.mkdir(parents=True,exist_ok=False)
    try:
        return _run(args)
    except Exception as exc:
        # A failed run remains visibly terminal with its partial evidence. This
        # diagnostic is <=16KiB reserved outside normal output allocations.
        failure={'status':'TERMINAL_EXTRACTION_FAILURE_NO_ADMISSION','exception_type':type(exc).__name__,
                 'reason':str(exc)[:2000],'input_sha256':args.sha256,
                 'limits':{k:v for k,v in vars(args).items() if k.startswith('max_')},
                 'partial_files_bytes':sum(f.stat().st_size for f in args.output.rglob('*') if f.is_file()),
                 'new_admitted_documents':0,'new_admitted_tokens':0}
        (args.output/'failure.json').write_text(json.dumps(failure,indent=2)+'\n')
        raise

def _run(args):
    # Conservative reservation: ordinary 20GiB free floor plus the full 16GB
    # planned weights allowance, in addition to this bounded output allocation.
    reserve=20*1024**3+16_000_000_000
    budget=OutputBudget(args.output,args.max_output_bytes,reserve)
    if shutil.disk_usage(args.output).free<reserve+args.max_output_bytes:
        raise ValueError('insufficient_disk_for_output_plus_weights_and_free_floor')
    budget.check()
    db=sqlite3.connect(args.output/'spool.sqlite3')
    db.execute('pragma max_page_count='+str(args.max_output_bytes//4096))
    db.execute('create table pages (page_id integer primary key, title text, depth integer, data text)')
    count=0
    with (args.output/'source-records.jsonl').open('xb') as raw:
        records=stream_lines(args.input,args.max_line_bytes,args.max_decompressed_bytes,args.prefix_discovery)
        for member,line,b in records:
            r=json.loads(b)
            c=extract_record(r) # Failure retains prior evidence, never skips silently.
            c['source_location']={'input_sha256':args.sha256,'member':member,'line':line,'record_sha256':digest(b)}
            c['source_record_metadata']= {k:v for k,v in r.get('article_body',{}).items() if k not in ['html','wikitext']}
            payload=json.dumps(c)
            # Reserve conservatively for SQLite records, btree/journal overhead,
            # source preservation and later extracted evidence before mutation.
            budget.check(8*len(payload.encode())+len(b)+65536)
            budget.write(raw,b if b.endswith(b'\n') else b+b'\n')
            try:db.execute('insert into pages values (?,?,?,?)',(c['page_id'],c['title'],c['title'].count('/'),payload))
            except sqlite3.IntegrityError as exc:raise ValueError('duplicate_page_id_requires_revision_selection') from exc
            db.commit();budget.check()
            count+=1
            if count==args.max_pages:
                # Close while still inside the current large member: no tar
                # iteration/skip over its unread remainder in prefix mode.
                records.close()
                break
    db.commit()
    # Deeper chapters own substantive repeated blocks ahead of root summaries.
    # Whole overlapping pages are held; no sentence-splicing to manufacture a
    # passing document. This applies only to this bounded extraction, not unseen pages.
    db.execute('create table owners (family text, block text, page integer, primary key(family,block))')
    counters={'pages':count,'without_detected_extraction_holds':0,'held':0,'admitted':0}
    with (args.output/'extracted.jsonl').open('x') as out:
        for (s,) in db.execute('select data from pages order by depth desc,title collate binary,page_id'):
            c=json.loads(s)
            budget.check(8*len(s.encode())+65536)
            c['overlap_blocks']=[]
            # Aggregate/structurally held pages cannot reserve blocks and crowd
            # out clean chapter pages, but all extracted evidence is retained.
            if not c['holds']:
                for block in c['blocks']:
                    if len(block['text'])<80:continue
                    owner=db.execute('select page from owners where family=? and block=?',(c['family_id'],block['sha256'])).fetchone()
                    if owner:c['overlap_blocks'].append({'block_sha256':block['sha256'],'owner_page_id':owner[0]})
                if c['overlap_blocks']:c['holds'].append('substantive_block_duplicates_canonical_chapter')
                else:
                    for block in c['blocks']:
                        if len(block['text'])>=80:db.execute('insert or ignore into owners values (?,?,?)',(c['family_id'],block['sha256'],c['page_id']))
            counters['held' if c['holds'] else 'without_detected_extraction_holds']+=1
            budget.write(out,json.dumps(c,sort_keys=True)+'\n')
            db.commit();budget.check()
    db.commit();db.close()
    receipt={'status':'BOUNDED_PREFIX_EXTRACTION_REVIEW_ONLY','schema_docs':SCHEMA_DOCS,
             'explicit_prefix_discovery':args.prefix_discovery,
             'full_archive_processed':False,
             'prefix_limit_reached':count==args.max_pages,
             'input_sha256':args.sha256,'script_sha256':file_sha(Path(__file__)),
             'disk_reservation_bytes':reserve,
             'limits':{k:v for k,v in vars(args).items() if k.startswith('max_')},
             'selection':'archive/line prefix; not a representative sample or full-corpus inventory',
             'counts':counters,'source_records_sha256':file_sha(args.output/'source-records.jsonl'),
             'extracted_sha256':file_sha(args.output/'extracted.jsonl'),
             'limitations':['no admission, factual or rights clearance','schema must be confirmed against downloaded historical artifact','root-title grouping does not resolve aliases or translated versions','all page text preserved; no main/subpage concatenation','overlap protection covers this bounded run only','math/table pages held for a future lossless representation, not silently flattened into usable prose']}
    with (args.output/'receipt.json').open('x') as f:budget.write(f,json.dumps(receipt,indent=2)+'\n')
    return receipt

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--sha256',required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--max-pages',type=int,default=100)
    p.add_argument('--max-line-bytes',type=int,default=4*1024*1024)
    p.add_argument('--max-decompressed-bytes',type=int,default=128*1024*1024)
    p.add_argument('--max-output-bytes',type=int,default=256*1024*1024)
    p.add_argument('--prefix-discovery',action='store_true',help='Permit declared tar member size above actual decoded read budget; stop inside member at page cap. Not a complete corpus pass.')
    args=p.parse_args()
    if not 1<=args.max_pages<=100 or not 1<=args.max_line_bytes<=4*1024*1024 or not 1<=args.max_decompressed_bytes<=128*1024*1024 or not 128*1024<=args.max_output_bytes<=256*1024*1024:
        p.error('v2 prefix discovery caps: 100 pages, 4MiB/line, 128MiB decoded input, 128KiB-256MiB total output')
    print(json.dumps(run(args),indent=2))

if __name__=='__main__':main()

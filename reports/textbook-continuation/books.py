"""Verify title-level rights and extract only self-contained documentary prose."""
from collections import Counter
from pathlib import Path
from hashlib import sha1
import json,re
from xml.etree import ElementTree as ET
from local import DEST,ROOT,HERE,h,norm,Dedupe,split,EXTRA,CONTACT
from tokenizer import load

BASE=ROOT/'data/openstax-text'
MD='{http://cnx.rice.edu/mdml}'
DISC='(?:credit|adapted from|reprinted|reproduced|excerpted|third.party|courtesy of|used with permission|translated from|all rights reserved|copyright|fair use)'
MARKER=re.compile(DISC,re.I)
REFERENCE=re.compile(r'\b(?:see|shown|listed|as|use|using|illustrated|refer(?:ring)? to|in) (?:in |the |this |these )?(?:figure|table|link|equation|graph)|\b(?:this (?:chapter|section|book)|OpenStax|we will (?:discuss|learn)|learning objectives?|copyright|creative commons|copyright holder|click|https?://|www\.|source:|according to|said that|writes that|permission|adapted from|described below|as follows|shown above|picture above|Figure \d|Table \d)\b',re.I)
BOOK_RISK=re.compile(r"\b(?:suicid\w*|therapy|neurodegeneration|psychiatr\w*|prescription|patients?|slav(?:e|ery|es)|enslav\w*|racial|ethnicity|politic\w*|republicans?|democrats?|election|partisan|abortion|candidates? for office|trump|stalin\w*|muslim|religio\w*|persecution|genocide|torture|medical advice|classified as having|dose of|pharmac\w*|red blood cells|malaria)\b",re.I)
BADTITLE=re.compile(r'\b(?:references?|glossary|appendix|preface|review questions|sources|bibliography|answer key|introduction to this book|primary sources|further reading|credits|learning objectives|clinical|disorders?|diseases?|suicide|sexual|racis\w*|slavery|warfare|massacre|racism|brain injuries|controvers\w*|therapy)\b',re.I)
DISALLOWED_CLASS=re.compile(r'objective|exercise|ap-connection|sidebar|reading-discard|example|feature|attribution|appendix|summary|review|problem|assessment|note|takeaway|link-to-learning|footnote|quote|citation|case-study|project',re.I)
INLINE={'para','emphasis','term','foreign','span'}
def localtag(el):return el.tag.split('}')[-1]
def contextmap(root):
    mods={}
    def walk(node,group):
        tag=localtag(node)
        if tag=='subcollection':
            title=node.find(MD+'title')
            group=[*group,(title.text or '').strip()] if title is not None else group
        if tag=='module' and group:
            mods[node.get('document')]=group
        else:
            for child in node:walk(child,group)
    walk(root,[])
    return mods

def readbook(repo,slug,tok):
    info=json.loads((repo/'admitted-files.json').read_text())
    collection=next((x for x in info['metadata'] if x['path'].endswith('/'+slug+'.collection.xml')),None)
    if collection is None:return [],{}
    body=(repo/collection['path']).read_bytes()
    def checked(b,obj):
        if obj['sha']!=sha1(b'blob '+str(len(b)).encode()+b'\x00'+b).hexdigest():raise ValueError(obj['path'])
    checked(body,collection)
    coll=ET.fromstring(body)
    meta=next(x for x in coll if localtag(x)=='metadata')
    license=meta.find(MD+'license').get('url').replace('http:','https:').rstrip('/')+'/'
    if license not in {'https://creativecommons.org/licenses/by/4.0/','https://creativecommons.org/licenses/by-nc-sa/4.0/'}:return [],{}
    license_file=(repo/'LICENSE').read_text() if (repo/'LICENSE').exists() else ''
    is_nc='by-nc-sa' in license
    if ('NonCommercial' in license_file.splitlines()[0])!=is_nc:raise ValueError('license conflict '+slug)
    readme=info['readme']
    decl=next((s for s in readme.splitlines() if 'available under' in s),'')
    if ('NonCommercial' in decl)!=is_nc or not decl:raise ValueError('README license conflict '+slug)
    title=meta.find(MD+'title').text
    if meta.findtext(MD+'language') not in ['en','English']:return [],{}
    mods=contextmap(coll)
    out=[];excluded=Counter()
    for x in info['modules']:
        mid=Path(x['path']).parent.name
        if mid not in mods:continue
        group=slug+'/'+mods[mid][-1]
        if BADTITLE.search(group):continue
        raw=(repo/x['path']).read_bytes();checked(raw,x)
        root=ET.fromstring(raw)
        name=root.findtext('{*}title') or ''
        if not name or BADTITLE.search(name):continue
        # Explicit licensed or attributed outside text excludes the entire module.
        # Ignore credits inside images/figures only; their text never reaches the output.
        parents={kid:parent for parent in root.iter() for kid in parent}
        def chain(e):
            out=[]
            while e in parents:out.append(parents[e]);e=parents[e]
            return out
        bodyrights=False
        for node in root.iter():
            if MARKER.search(node.text or '') and not {localtag(p) for p in [node,*chain(node)]}&{'figure','media','image','caption','metadata','footnote','table','note'}:
                bodyrights=True;break
        if bodyrights:excluded['module_notice']+=1;continue
        provenance=f"https://github.com/openstax/{repo.name}/blob/{info['revision']}/{x['path']}"
        for j,node in enumerate(root.findall('.//{*}para')):
            lineage=chain(node)
            if any(localtag(el) not in {'section','content','document'} or DISALLOWED_CLASS.search(el.get('class','')) for el in lineage):continue
            if any(localtag(el) not in INLINE or DISALLOWED_CLASS.search(el.get('class','')) for el in node.iter()):continue
            t=' '.join(''.join(node.itertext()).split())
            if not 40<=len(t.split())<=220 or t[-1:] not in '.!?' or not t[:1].isupper() or len(re.findall(r'[.!?](?:\s|$)',t))<2:continue
            if any(r.search(t) for r in (CONTACT,REFERENCE,EXTRA,MARKER,BOOK_RISK)) or re.search(r'["“”«»]|\b(?:example|figure|table|chapter|exercise|section|equation)\s+[A-Z]?\d|\ufffd|\\|\$[^\d]|^\(?[A-Z]?\d[.) ]',t,re.I):continue
            if len(re.findall(r'\b(?:the|to|for|and|on|is|was|of|in)\b',t,re.I))<5:continue
            n=len(tok.encode(t).ids)+1
            out.append(dict(source='textbook',group=group,book=slug,book_title=title,chapter=mods[mid][-1],
              section=name,source_url=provenance,module=mid,paragraph=node.get('id') or str(j),
              document_id=slug+'/'+mid+'/'+str(j),split=split('textbook',group),text=t,tokens=n,normalized_sha256=h(norm(t)),
              raw_blob_sha1=x['sha'],revision=info['revision'],license=license,attribution='OpenStax, Rice University and credited contributors',
              book_url='https://openstax.org/details/books/'+slug))
    inf=dict(title=title,slug=slug,repo=repo.name,revision=info['revision'],license=license,
             canonical_book='https://openstax.org/details/books/'+slug,publisher_declaration=decl,collection_blob=collection['sha'],
             modules_fetched=len(info['modules']),selected_paragraphs=len(out),exclusions=excluded)
    return out,inf

def main():
    tok=load();allrows=[];decisions=[]
    for report in sorted(BASE.glob('*/admitted-files.json')):
        repo=report.parent
        slugs=[p.name.split('.collection')[0] for p in sorted((repo/'collections').glob('*.collection.xml'))]
        preferred={'osbooks-biology-bundle':'biology-2e','osbooks-principles-economics-bundle':'principles-economics-3e',
                   'osbooks-college-physics-bundle':'college-physics-2e'}
        if repo.name in preferred:slugs=[preferred[repo.name]]
        for slug in slugs:
            try:rows,meta=readbook(repo,slug,tok)
            except (ValueError,ET.ParseError) as e:
                decisions.append(dict(slug=slug,status='withheld',reason=str(e)));continue
            allrows.extend(rows)
            if meta:decisions.append(meta)
    (HERE/'titles.json').write_text(json.dumps(decisions,indent=2)+'\n')
    DEST.mkdir(exist_ok=True)
    with (DEST/'textbooks.jsonl').open('w') as f:
        for r in allrows:f.write(json.dumps(r,ensure_ascii=False)+'\n')
    print('textbook paragraphs',len(allrows),'positions',sum(r['tokens'] for r in allrows),'books',[(x['slug'],x.get('selected_paragraphs',x.get('reason'))) for x in decisions])
if __name__=='__main__':main()

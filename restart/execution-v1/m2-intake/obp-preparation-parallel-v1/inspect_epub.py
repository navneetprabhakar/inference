"""Bounded offline EPUB inspection. No path extraction, networking or admission."""
import hashlib,json,posixpath,re,stat,unicodedata,zipfile
from pathlib import Path,PurePosixPath
import xml.etree.ElementTree as ET

MAX_FILES=4000
MAX_EXPANDED=30000000
MAX_MEMBER=4000000
LICENSE=re.compile(r'https?://(?:www\.)?creativecommons\.org/(?:licenses/[a-z-]+/[0-9.]+|publicdomain/zero/[0-9.]+)(?:/)?',re.I)

def safe_name(name):
    if not isinstance(name,str) or not name or '\\' in name or '\x00' in name:
        raise ValueError('Unsafe archive name')
    p=PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or ':' in name or name.startswith('//'):
        raise ValueError('Archive path traversal or URL refused')
    return name

def safe_xml(raw):
    if b'\x00' in raw:raise ValueError('NUL or UTF16/32 XML refused before declaration screening')
    if re.search(br'<!\s*ENTITY',raw,re.I):raise ValueError('XML entity declaration refused')
    # Plain HTML5 doctype is harmless; all other DTD declarations are refused.
    stripped=re.sub(br'<!DOCTYPE\s+html\s*>',b'',raw,flags=re.I)
    if re.search(br'<!\s*DOCTYPE',stripped,re.I):raise ValueError('External or internal DTD refused')
    return ET.fromstring(stripped)

def joined(base,href):
    if not isinstance(href,str) or not href or '#' in href or '?' in href or '%' in href:
        raise ValueError('Ambiguous package href')
    safe_name(href)
    result=posixpath.normpath(posixpath.join(posixpath.dirname(base),href))
    return safe_name(result)

def norm(v):return ' '.join(unicodedata.normalize('NFKC',v).casefold().split())

class OutputBudget:
    """Conservative aggregate ceiling over every file in a caller-owned root."""
    def __init__(self,root,cap):
        if Path(root).is_symlink():raise ValueError('Budget root symlink refused')
        self.root=Path(root).resolve();self.cap=cap
        if type(cap) is not int or cap<=0:raise ValueError('Positive output cap required')
    def used(self):
        import os
        total=0
        if self.root.is_symlink():raise ValueError('Budget root symlink refused')
        if self.root.exists():
            for base,dirs,files in os.walk(self.root):
                for name in dirs+files:
                    if (Path(base)/name).is_symlink():raise ValueError('Output symlink refused')
                total+=sum((Path(base)/name).stat().st_size for name in files)
        return total
    def ensure(self,additional):
        if type(additional) is not int or additional<0 or self.used()+additional>self.cap:
            raise ValueError('Aggregate output byte ceiling before write')
    def write(self,path,data):
        path=Path(path)
        if not path.resolve().is_relative_to(self.root):raise ValueError('Output outside budget root')
        if path.exists():raise FileExistsError('Output already exists')
        self.ensure(len(data))
        with path.open('xb') as handle:
            handle.write(data)

def inspect(path,out,expected,*,budget_root=None,budget_cap=None):
    path=Path(path);out=Path(out)
    budget=OutputBudget(budget_root or out.parent,budget_cap if budget_cap is not None else MAX_EXPANDED+2000000)
    if out.exists():raise FileExistsError('Inspection output exists')
    with zipfile.ZipFile(path) as z:
        infos=z.infolist()
        if len(infos)>MAX_FILES:raise ValueError('Archive file limit')
        names=[safe_name(x.filename) for x in infos]
        if len(names)!=len(set(names)):raise ValueError('Duplicate archive names')
        if sum(x.file_size for x in infos)>MAX_EXPANDED:raise ValueError('Expanded archive limit')
        for x in infos:
            if x.flag_bits&1 or stat.S_ISLNK(x.external_attr>>16):raise ValueError('Encrypted or symlink member')
            if x.file_size>MAX_MEMBER:raise ValueError('Member size limit')
            if x.file_size>max(1,x.compress_size)*500:raise ValueError('Suspicious expansion ratio')
        if 'mimetype' not in names or z.read('mimetype')!=b'application/epub+zip':raise ValueError('EPUB mimetype required')
        if 'META-INF/container.xml' not in names:raise ValueError('Missing EPUB container')
        member_data={};member_inventory=[]
        expanded=0
        for info in infos:
            if info.is_dir():continue
            data=z.read(info)
            expanded+=len(data)
            if len(data)!=info.file_size or expanded>MAX_EXPANDED:raise ValueError('Actual expanded bytes limit')
            member_inventory.append({'member':info.filename,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
            if info.filename.lower().endswith(('.xml','.opf','.xhtml','.html','.htm','.ncx')):
                member_data[info.filename]=data
        container=safe_xml(member_data['META-INF/container.xml'])
        roots=[x.attrib.get('full-path') for x in container.iter() if x.tag.rsplit('}',1)[-1]=='rootfile' and x.attrib.get('media-type')=='application/oebps-package+xml']
        if len(roots)!=1:raise ValueError('Unique OPF package required')
        opf_name=safe_name(roots[0]);opf=safe_xml(member_data[opf_name])
        manifest={};spine=[];authors=[];identifiers=[];rights=[]
        for node in opf.iter():
            tag=node.tag.rsplit('}',1)[-1]
            if tag=='item':
                key=node.attrib.get('id')
                if not key or key in manifest:raise ValueError('Ambiguous manifest ID')
                manifest[key]={'member':joined(opf_name,node.attrib.get('href')),'media_type':node.attrib.get('media-type'),'properties':node.attrib.get('properties','')}
            elif tag=='itemref':spine.append({'idref':node.attrib.get('idref'),'linear':node.attrib.get('linear','yes')})
            elif tag=='creator':authors.append(''.join(node.itertext()).strip())
            elif tag=='identifier':identifiers.append(''.join(node.itertext()).strip())
            elif tag=='rights':rights.append(''.join(node.itertext()).strip())
        if not spine:raise ValueError('Missing package spine')
        ordered=[]
        for ordinal,item in enumerate(spine):
            if item['idref'] not in manifest:raise ValueError('Spine references missing manifest item')
            m=manifest[item['idref']]
            if m['member'] not in member_data:raise ValueError('Spine file missing or unsupported')
            if m['media_type'] not in {'application/xhtml+xml','text/html'}:raise ValueError('Non-HTML spine content needs separate renderer')
            tree=safe_xml(member_data[m['member']])
            headings=[' '.join(''.join(n.itertext()).split()) for n in tree.iter() if n.tag.rsplit('}',1)[-1] in {'h1','h2','h3'}]
            ordered.append({'ordinal':ordinal,**item,**m,'headings':headings})
        licenses=[]
        for name,data in member_data.items():
            for match in LICENSE.finditer(data.decode('utf-8',errors='replace')):
                url=match.group(0)
                licenses.append({'member':name,'url':url,'character_offset':match.start()})
        exact_license=lambda v: v.lower().replace('http://','https://').replace('www.','').rstrip('/')
        allowed={'https://creativecommons.org/licenses/by/4.0','https://creativecommons.org/publicdomain/zero/1.0'}
        flags=[]
        if not any(exact_license(x['url'])==exact_license(expected['license']) for x in licenses):flags.append('expected_work_license_not_found_in_package_text')
        if any(exact_license(x['url']) not in allowed for x in licenses):flags.append('other_license_urls_require_member_and_exception_review')
        if not all(any(norm(author)==norm(observed) for observed in authors) for author in expected['authors']):flags.append('creator_name_mismatch_or_missing_needs_review')
        isbn_digits=re.sub(r'[^0-9X]','',expected['epub_isbn'].upper())
        if not any(isbn_digits in re.sub(r'[^0-9X]','',identifier.upper()) or expected['doi'].casefold() in identifier.casefold() for identifier in identifiers):flags.append('package_isbn_or_doi_not_bound')
        originals=out/'original-members'
        saved=[]
        for name,data in sorted(member_data.items()):
            # Hash-based filenames avoid all archive-controlled filesystem paths.
            target=originals/(hashlib.sha256(name.encode()).hexdigest()+'.bin')
            saved.append({'member':name,'path':str(target),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
        receipt={'status':'DISCOVERY_ARCHIVE_INSPECTED_MANUAL_REVIEW_REQUIRED','source_epub':str(path),'epub_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'expected_work':expected,'package_opf':opf_name,'creators':authors,'identifiers':identifiers,'rights_strings':rights,'license_url_occurrences':licenses,'review_flags':flags,'spine_order':ordered,'manifest':manifest,'all_member_inventory':member_inventory,'preserved_original_xml_html':saved,'total_expanded_bytes_checked':expanded,'package_member_crc_checked':True,'unresolved':['Work/author/chapter license reconciliation by full content review','logical chapter reconstruction beyond spine technical boundaries','factual and semantic quality','family/dedup/leakage/splits'],'admitted_documents':0,'admitted_tokens':0,'external_requests':0,'policy_limitations':['Non-HTML5 DTD declarations rejected, including legitimate EPUB2 DTDs; failed inspection is diagnostic and never silently relaxed.','License URL detection identifies evidence and conflicts, not rights clearance.','Archive XHTML filenames and headings do not alone establish independent complete documents.']}
        receipt['aggregate_output_budget']={'root':str(budget.root),'cap_bytes':budget.cap,'all_existing_root_files_counted':True,'used_before_write':budget.used()}
        receipt_bytes=(json.dumps(receipt,indent=2,ensure_ascii=False)+'\n').encode()
        required=sum(len(data) for data in member_data.values())+len(receipt_bytes)
        budget.ensure(required)
        out.mkdir(parents=True);originals.mkdir()
        for member in saved:budget.write(member['path'],member_data[member['member']])
        budget.write(out/'inspection.json',receipt_bytes)
        return receipt

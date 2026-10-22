"""Offline DOM text rendering prototype. Inline tags never synthesize spaces."""
import hashlib,re
from bs4 import BeautifulSoup,Comment,NavigableString,Tag
BLOCK_TAGS={'address','article','aside','blockquote','dd','details','dialog','div','dl','dt','fieldset','figcaption','figure','footer','form','h1','h2','h3','h4','h5','h6','header','hgroup','hr','li','main','nav','ol','p','pre','section','summary','table','ul'}
STRUCTURAL_TAGS={'h1','h2','h3','h4','h5','h6','p','li','pre','blockquote','dt','dd','table'}
IGNORED={'script','style','noscript','template'}
def sha(s):return hashlib.sha256(s.encode()).hexdigest()
def render_block_text(node):
    """Preserve source text adjacency; HTML-flow whitespace folds only where present.

    This does not compute CSS. Math/tables become explicit held placeholders,
    never certified prose. Original HTML must be retained separately.
    """
    if isinstance(node,Tag) and node.name=='pre':return node.get_text()
    events=[]
    def walk(n,root=False):
        if isinstance(n,Comment):return
        if isinstance(n,NavigableString):events.append(('text',re.sub(r'[\t\n\r\f\v ]+',' ',str(n))));return
        if not isinstance(n,Tag):return
        if n.name in IGNORED:return
        if n.name=='br':events.append(('linebreak',1));return
        if n.name=='math' or 'mwe-math-element' in n.get('class',[]):events.append(('text','[MATH REQUIRES REVIEW]'));return
        if n.name=='table':events.extend([('break',2),('text','[TABLE REQUIRES REVIEW]'),('break',2)]);return
        if n.name=='pre':events.extend([('break',2),('verbatim',n.get_text()),('break',2)]);return
        boundary=n.name in BLOCK_TAGS and not root
        if boundary:events.append(('break',1 if n.name=='li' else 2))
        for c in n.children:walk(c)
        if boundary:events.append(('break',1 if n.name=='li' else 2))
    walk(node,True)
    out=''
    for kind,value in events:
        if kind=='linebreak':
            out=out.rstrip(' ')+'\n'
        elif kind=='break':
            out=out.rstrip(' ')
            trailing=len(out)-len(out.rstrip('\n'))
            if out and trailing<value:out+='\n'*(value-trailing)
        elif kind=='verbatim':out+=value
        else:
            if out.endswith((' ','\n')) and value.startswith(' '):value=value[1:]
            out+=value
    return out.strip(' \n')
def render_blocks(content):
    """Match existing highest-structural-block policy, retaining independent blocks."""
    blocks=[];holds=[]
    if content.select('math,.mwe-math-element'):holds.append('math_requires_lossless_representation')
    if content.select('table'):holds.append('table_structure_requires_review')
    if content.select('sup,sub'):holds.append('inline_script_format_requires_review')
    for n in content.find_all(list(STRUCTURAL_TAGS)):
        if any(p.name in STRUCTURAL_TAGS for p in n.parents if p is not content):continue
        text=render_block_text(n)
        if text:blocks.append({'kind':n.name,'text':text,'sha256':sha(text)})
    text='\n\n'.join(x['text'] for x in blocks)
    return {'blocks':blocks,'text':text,'text_sha256':sha(text),'holds':holds,'training_admitted':False}
def render_html(html):
    soup=BeautifulSoup(html,'lxml');r=render_blocks(soup.body or soup)
    return dict(r,original_html=html,html_sha256=sha(html))

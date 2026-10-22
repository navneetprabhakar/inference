"""Offline bounded JATS review renderer. Never fetches assets or admits text."""
import argparse,hashlib,html,json,re,sys
from pathlib import Path
from lxml import etree
HERE=Path(__file__).resolve().parent;EXEC=HERE.parent;ROOT=EXEC/'m2-intake'
sys.path.insert(0,str(ROOT/'obp-preparation-parallel-v1'))
from inspect_epub import OutputBudget
SOURCE=ROOT/'pmc-native-discovery-pilot-v1';DEST=ROOT/'pmc-structured-previews-v1'
CAP=100000000;MAX_XML=8*1024**2;MAX_NODES=100000
INLINE={'bold':'strong','italic':'em','sup':'sup','sub':'sub','monospace':'code','underline':'u','break':'br','named-content':'span','styled-content':'span','label':'span'}
BLOCK={'article':'article','front':'header','back':'section','body':'main','sec':'section','p':'p','list-item':'li','fig':'figure','caption':'figcaption','table-wrap':'section','table':'table','thead':'thead','tbody':'tbody','tfoot':'tfoot','tr':'tr','td':'td','th':'th','colgroup':'colgroup','col':'col','ref-list':'section','ref':'div','fn-group':'section','fn':'aside','disp-quote':'blockquote','preformat':'pre','code':'pre','boxed-text':'aside','def-list':'dl','def-item':'div','term':'dt','def':'dd','verse-group':'section','verse-line':'p'}
MATH={'math','mrow','mi','mn','mo','mtext','mspace','mfrac','msup','msub','msubsup','msqrt','mroot','mfenced','mtable','mtr','mtd','munder','mover','munderover','semantics','annotation','annotation-xml','menclose','mpadded','mphantom','mmultiscripts','mprescripts','none','mstyle'}
TRANSPARENT={'journal-meta','article-meta','title-group','journal-title-group','contrib-group','contrib','name','surname','given-names','collab','aff','permissions','license','license-p','copyright-statement','copyright-year','copyright-holder','pub-date','year','month','day','volume','issue','fpage','lpage','elocation-id','article-id','journal-id','issn','issn-l','publisher','publisher-name','publisher-loc','history','date','abstract','kwd-group','kwd','funding-group','award-group','funding-source','award-id','funding-statement','ack','notes','note','statement','related-article','related-object','mixed-citation','element-citation','person-group','article-title','journal-title','source','publisher-name','edition','uri','isbn','object-id','supplementary-material','media','email','uri','string-name','etal','size','table-wrap-foot','alt-text','long-desc'}

def sha(data):return hashlib.sha256(data).hexdigest()
def esc(value):return html.escape(value or '',quote=True)
def local(node):return etree.QName(node).localname if isinstance(node.tag,str) else ''

def parse(raw):
    if len(raw)>MAX_XML or b'\x00' in raw or re.search(br'<!\s*(?:DOCTYPE|ENTITY)',raw,re.I):raise ValueError('XML bound/DTD/entity/UTF16 refused')
    root=etree.fromstring(raw,etree.XMLParser(resolve_entities=False,no_network=True,load_dtd=False,huge_tree=False))
    if local(root)!='article':raise ValueError('Full article root required')
    if sum(1 for _ in root.iter())>MAX_NODES:raise ValueError('Node count bound')
    return root

def ast(node):
    if not isinstance(node.tag,str):return {'kind':'non_element','serialized_xml':etree.tostring(node,encoding='unicode',with_tail=False),'tail':node.tail}
    return {'kind':'element','qualified_tag':node.tag,'attributes':dict(node.attrib),'text':node.text,'tail':node.tail,'children':[ast(child) for child in node]}

def ast_text(tree,with_tail=False):
    value='' if tree['kind']!='element' else (tree['text'] or '')+''.join(ast_text(child,True) for child in tree['children'])
    return value+(tree.get('tail') or '' if with_tail else '')

def build(raw,source_identity):
    root=parse(raw);tree=ast(root);source_text=''.join(root.itertext())
    if ast_text(tree)!=source_text:raise ValueError('AST text/tail conservation failed')
    elements=[n for n in root.iter() if isinstance(n.tag,str)]
    paths={n:root.getroottree().getpath(n) for n in elements};ordinals={n:i for i,n in enumerate(elements)}
    ids={};holds=[];events=[];counts={};unsupported=set();node_refs=[]
    for n in elements:
        tag=local(n);counts[tag]=counts.get(tag,0)+1
        ident=n.get('id')
        if ident:ids.setdefault(ident,[]).append(n)
    for ident,nodes in ids.items():
        if len(nodes)>1:holds.append({'reason':'duplicate_source_id','source_id':ident,'paths':[paths[n] for n in nodes]})
    def event(n,role,**extra):
        row={'path':paths[n],'tag':local(n),'source_id':n.get('id'),'role':role,'serialized_node_sha256':sha(etree.tostring(n,encoding='utf-8',with_tail=False)),**extra};events.append(row)
    def children(n,depth):return esc(n.text)+''.join(render(c,depth)+esc(c.tail) for c in n)
    def math_native(n):
        tag=local(n)
        if tag not in MATH:raise ValueError('Unsupported MathML node')
        attrs=''
        for key,value in n.attrib.items():
            if key in {'display','mathvariant','mathsize','mathcolor','columnalign','rowalign','columnspan','rowspan','fence','separator','stretchy','symmetric','form','accent','accentunder','linethickness','notation','open','close','separators','width','height','depth','lspace','rspace','voffset','encoding'}:attrs+=' '+key+'="'+esc(value)+'"'
        if tag=='math':attrs+=' xmlns="http://www.w3.org/1998/Math/MathML"'
        return '<'+tag+attrs+'>'+esc(n.text)+''.join(math_native(c)+esc(c.tail) for c in n if isinstance(c.tag,str))+'</'+tag+'>'
    def render(n,depth):
        if not isinstance(n.tag,str):return ''
        tag=local(n);ident=' id="jats-n'+str(ordinals[n])+'"'
        if tag=='xref':
            targets=(n.get('rid') or '').split();display=children(n,depth);refs=[]
            if not targets:holds.append({'reason':'xref_missing_rid','path':paths[n]})
            for target in targets:
                nodes=ids.get(target,[])
                valid=len(nodes)==1;node_refs.append({'path':paths[n],'rid':target,'resolved':valid,'target_path':paths[nodes[0]] if valid else None})
                if valid:refs.append('<a href="#jats-n'+str(ordinals[nodes[0]])+'">'+esc(target)+'</a>')
                else:holds.append({'reason':'xref_missing_or_ambiguous_target','path':paths[n],'rid':target});refs.append(esc(target)+' [UNRESOLVED]')
            event(n,'cross_reference',targets=targets)
            return '<span'+ident+' class="xref">'+display+' <small>[targets: '+', '.join(refs)+']</small></span>'
        if tag in {'graphic','inline-graphic','media'}:
            href=n.get('{http://www.w3.org/1999/xlink}href') or n.get('href') or ''
            holds.append({'reason':'visual_or_media_asset_not_available_in_JATS_only_capture','path':paths[n],'asset_reference':href})
            event(n,'explicit_unavailable_asset',href=href)
            return '<span'+ident+' class="missing-asset">[ASSET NOT FETCHED: '+esc(href)+']'+children(n,depth)+'</span>'
        if tag in {'disp-formula','inline-formula'}:
            event(n,'formula_container');return '<span'+ident+' class="formula">'+children(n,depth)+'</span>'
        if tag=='math':
            event(n,'mathml_with_escaped_original_source')
            try:rendered=math_native(n)
            except ValueError:
                rendered='[UNSUPPORTED MATHML: inspect original below]';holds.append({'reason':'unsupported_MathML_rendering','path':paths[n]})
            original=esc(etree.tostring(n,encoding='unicode',with_tail=False))
            return '<span'+ident+'>'+rendered+' <span class="math-source">[Original MathML: <code>'+original+'</code>]</span></span>'
        if tag=='tex-math':
            event(n,'literal_TeX_preserved');holds.append({'reason':'TeX_preserved_literal_not_typeset','path':paths[n]})
            return '<code'+ident+' class="tex">'+children(n,depth)+'</code>'
        if tag=='ext-link':
            href=n.get('{http://www.w3.org/1999/xlink}href') or n.get('href') or ''
            event(n,'external_reference_visible_never_fetched',href=href)
            return '<span'+ident+'>'+children(n,depth)+' <small>[external: '+esc(href)+']</small></span>'
        if tag in {'title','article-title','journal-title'}:
            heading='h1' if tag=='article-title' and n.getparent() is not None and local(n.getparent())=='title-group' else ('span' if tag=='article-title' else 'h'+str(min(6,max(2,depth+1))))
            event(n,'heading');return '<'+heading+ident+'>'+children(n,depth)+'</'+heading+'>'
        if tag=='list':
            typ=n.get('list-type','bullet');container='ol' if typ in {'order','ordered','alpha-lower','alpha-upper','roman-lower','roman-upper'} else 'ul'
            if typ not in {'bullet','simple','order','ordered','alpha-lower','alpha-upper','roman-lower','roman-upper'}:holds.append({'reason':'unknown_list_type','path':paths[n],'list_type':typ})
            attrs=' type="'+{'alpha-lower':'a','alpha-upper':'A','roman-lower':'i','roman-upper':'I'}[typ]+'"' if typ in {'alpha-lower','alpha-upper','roman-lower','roman-upper'} else ''
            if typ=='simple' or any(local(x)=='label' for item in n for x in item):attrs+=' style="list-style-type:none"'
            event(n,'list',list_type=typ);return '<'+container+ident+attrs+'>'+children(n,depth)+'</'+container+'>'
        mapped=INLINE.get(tag) or BLOCK.get(tag)
        if mapped:
            attrs=''
            if tag in {'td','th','col','colgroup'}:
                for key in ['rowspan','colspan','span']:
                    value=n.get(key)
                    if value:
                        if not re.fullmatch(r'[1-9][0-9]{0,2}',value):holds.append({'reason':'invalid_table_span_attribute','path':paths[n],'attribute':key,'value':value})
                        else:attrs+=' '+key+'="'+value+'"'
            event(n,'mapped_structure',html_tag=mapped)
            if mapped in {'br','col'}:return '<'+mapped+ident+attrs+'>'+children(n,depth)
            return '<'+mapped+ident+attrs+'>'+children(n,depth+(1 if tag=='sec' else 0))+'</'+mapped+'>'
        if tag not in TRANSPARENT:unsupported.add(tag)
        event(n,'transparent_text_and_children_preserved')
        return '<span'+ident+' data-jats-tag="'+esc(tag)+'">'+children(n,depth)+'</span>'
    rendered=render(root,0)
    if unsupported:holds.append({'reason':'unmapped_source_tags_review_required','tags':sorted(unsupported)})
    warning='REVIEW PREVIEW ONLY. Original JATS/OAI bytes remain authoritative. No assets were fetched. Marked missing assets, formulas, tables and references need full review. No document or token is admitted.'
    page='<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'"><title>JATS review preview</title><style>body{max-width:1000px;margin:2rem auto;font:17px/1.5 Georgia,serif;padding:1rem}table,td,th{border:1px solid #999;border-collapse:collapse;padding:.4rem}figure,aside,section{margin-block:1rem}pre{white-space:pre-wrap;overflow-wrap:anywhere}.missing-asset{display:block;border:2px solid #b40;padding:.5rem}.xref small{font-size:.7em;color:#444}.warning{background:#fff3cf;padding:1rem}header{border-bottom:1px solid #aaa}details{font:13px monospace}</style></head><body><p class="warning">'+warning+'</p>'+rendered+'</body></html>'
    receipt={'status':'STRUCTURED_REVIEW_PREVIEW_NOT_CANDIDATE','source':source_identity,'source_article_xml_sha256':sha(raw),'AST_text_sha256':sha(source_text.encode()),'text_tail_conservation_verified':True,'node_counts':counts,'all_element_nodes':len(elements),'structure_events':events,'cross_references':node_refs,'holds':holds,'unmapped_tags':sorted(unsupported),'native_MathML_source_always_visible':True,'source_diagnostic_not_training_text':True,'network_requests':0,'admitted_documents':0,'admitted_tokens':0,'html_sha256':sha(page.encode()),'limitations':['AST preserves all element tags/attributes/text/tails; serialized source bytes remain authoritative.','HTML is a review view, not byte-for-byte source reproduction or an approved text extraction.','Graphics/media absent from captured XML remain explicit dependency holds.','Unmapped structures and unresolved/multiple-ID references remain holds; no inference or repairs applied.']}
    return tree,page.encode(),receipt

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--render-existing',action='store_true');args=parser.parse_args()
    if not args.render_existing:print(json.dumps({'status':'OFFLINE_RENDERER_READY','source':str(SOURCE),'output':str(DEST),'network':False,'admission':False}));return
    ready=json.loads((HERE/'ready.json').read_text())
    for path,digest in ready['input_sha256'].items():
        if sha(Path(path).read_bytes())!=digest:raise ValueError('Pinned source/renderer changed')
    rows=json.loads((SOURCE/'page-000.records.json').read_text())['rows'];budget=OutputBudget(DEST,CAP);DEST.mkdir(exist_ok=False)
    results=[]
    for row in rows:
        pmcid=row['pmcid'];path=SOURCE/f'PMC{pmcid}.article.xml';raw=path.read_bytes()
        if sha(raw)!=row['serialized_article_sha256']:raise ValueError('Source article SHA mismatch')
        tree,page,receipt=build(raw,{'pmcid':pmcid,'source_response_sha256':row['source_original_decoded_response_sha256'],'title':row['title'],'inherited_metadata_holds':row['holds'],'fulltext_rights_and_external_status_pending':True})
        content=(json.dumps({'source_article_sha256':sha(raw),'tree':tree},ensure_ascii=False)+'\n').encode();rec=(json.dumps(receipt,indent=2,ensure_ascii=False)+'\n').encode()
        budget.ensure(len(content)+len(page)+len(rec)+1000000)
        for suffix,value in [('ast.json',content),('html',page),('receipt.json',rec)]:budget.write(DEST/f'PMC{pmcid}.{suffix}',value)
        results.append({'pmcid':pmcid,'title':row['title'],'renderer_holds':len(receipt['holds']),'cross_references':len(receipt['cross_references']),'source_xml_sha256':sha(raw),'html_sha256':sha(page),'ast_sha256':sha(content),'text_tail_conservation_verified':True})
    report={'status':'EXISTING_DISCOVERY_ARTICLES_RENDERED_FOR_REVIEW_ONLY','articles':results,'count':len(results),'sourcewide_or_representative_claim':False,'all_source_text_and_original_files_unchanged':True,'network_requests':0,'new_admitted_documents':0,'new_admitted_tokens':0,'renderer_sha256':sha(Path(__file__).read_bytes())}
    budget.write(DEST/'result.json',(json.dumps(report,indent=2,ensure_ascii=False)+'\n').encode());print(json.dumps({'articles_rendered':len(results),'output':str(DEST),'new_admitted_tokens':0}))
if __name__=='__main__':main()

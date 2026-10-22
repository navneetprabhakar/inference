"""No network or corpus admission; faithful-structure and injection guard cases."""
import json
from pathlib import Path
from lxml import etree,html
import render as r
HERE=Path(__file__).parent;checks={}
raw=b'''<article xmlns:mml="http://www.w3.org/1998/Math/MathML" xmlns:xlink="http://www.w3.org/1999/xlink"><front><article-meta><title-group><article-title>Fixture only</article-title></title-group><permissions><license xlink:href="https://creativecommons.org/licenses/by/4.0/"><license-p>CC BY</license-p></license></permissions></article-meta></front><body><sec id="s1"><title>First section</title><p>Before <italic>emphasis</italic> after<xref rid="fig1 fn1">1</xref> tail.</p><list list-type="alpha-lower"><list-item><p>Alpha</p></list-item><list-item><p>Beta</p></list-item></list><fig id="fig1"><label>Figure 1</label><caption><p>Captured caption.</p></caption><graphic xlink:href="unavailable.png"/></fig><disp-formula><mml:math><mml:mfrac><mml:mi>x</mml:mi><mml:mn>2</mml:mn></mml:mfrac></mml:math></disp-formula><table-wrap><label>Table 1</label><table><tbody><tr><th>Label</th><td colspan="2">Value</td></tr></tbody></table></table-wrap></sec><sec><title>Second section</title><p>After all previous content.</p></sec></body><back><fn-group><fn id="fn1"><p>Footnote retained.</p></fn></fn-group><ref-list><ref id="ref1"><mixed-citation><article-title>Citation title</article-title> Reference.</mixed-citation></ref></ref-list></back></article>'''
tree,page,receipt=r.build(raw,{'fixture':True});doc=html.fromstring(page)
checks['AST_exact_text_tail_conservation']=r.ast_text(tree)==''.join(etree.fromstring(raw).itertext()) and receipt['text_tail_conservation_verified']
checks['section_order']=page.find(b'First section')<page.find(b'Second section')
checks['inline_and_tail_text_present']=b'emphasis' in page and b' after' in page and b' tail.' in page
checks['alphabetic_ordered_list_preserved']=len(doc.xpath('//ol[@type="a"]/li'))==2
checks['caption_preserved']=b'Captured caption.' in page
checks['missing_graphic_visible_and_held']=b'ASSET NOT FETCHED: unavailable.png' in page and any(x['reason']=='visual_or_media_asset_not_available_in_JATS_only_capture' for x in receipt['holds'])
checks['no_external_image_fetch']=not doc.xpath('//img|//iframe|//script|//link')
checks['math_fraction_preserved']=b'<mfrac>' in page and b'<mi>x</mi><mn>2</mn>' in page and b'Original MathML' in page
checks['table_structure_span_preserved']=len(doc.xpath('//table/tbody/tr/td[@colspan="2"]'))==1
checks['footnote_and_fig_xrefs_resolved']=all(x['resolved'] for x in receipt['cross_references']) and len(receipt['cross_references'])==2
checks['backmatter_footnote_kept']=b'Footnote retained.' in page
checks['citation_title_not_h1']=len(doc.xpath('//h1'))==1
checks['CSP_external_access_blocked']=b"default-src &#x27;none&#x27;" in page or b"default-src 'none'" in page
checks['never_admits']=receipt['admitted_documents']==receipt['admitted_tokens']==receipt['network_requests']==0
bad=raw.replace(b'rid="fig1 fn1"',b'rid="missing"')
checks['missing_reference_hold']=any(x['reason']=='xref_missing_or_ambiguous_target' for x in r.build(bad,{})[2]['holds'])
bad=raw.replace(b'<sec><title>Second',b'<sec id="fig1"><title>Second')
checks['duplicate_ID_hold']=any(x['reason']=='duplicate_source_id' for x in r.build(bad,{})[2]['holds'])
bad=raw.replace(b'<p>After all previous content.</p>',b'<p><ext-link xlink:href="javascript:alert(1)">Visible text</ext-link><script>alert(1)</script></p>')
_,escaped,holds=r.build(bad,{})
checks['injected_tags_and_URL_not_executable']=not html.fromstring(escaped).xpath('//script|//a[starts-with(@href,"javascript:")]') and b'javascript:alert(1)' in escaped
checks['unknown_tag_surfaced']=any(x['reason']=='unmapped_source_tags_review_required' and 'script' in x['tags'] for x in holds['holds'])
bad=raw.replace(b'colspan="2"',b'colspan="bad"')
checks['malformed_span_hold']=any(x['reason']=='invalid_table_span_attribute' for x in r.build(bad,{})[2]['holds'])
bad=raw.replace(b'<disp-formula>',b'<disp-formula><tex-math>x^2</tex-math>')
checks['literal_TeX_visible_with_hold']=any(x['reason']=='TeX_preserved_literal_not_typeset' for x in r.build(bad,{})[2]['holds'])
for name,bad in [('entity',b'<!DOCTYPE article [<!ENTITY x SYSTEM "file:///etc/passwd">]>'+raw),('utf16',raw.decode().encode('utf-16'))]:
 try:r.build(bad,{})
 except ValueError:checks['refuse_'+name]=True
 else:checks['refuse_'+name]=False
assert all(checks.values()),checks
out={'status':'PASS_OFFLINE_STRUCTURE_AND_SAFETY_GUARDS','checks':checks,'case_count':len(checks),'actual_source_articles_rendered':0,'new_cohort_created':False,'new_admitted_tokens':0,'renderer_sha256':r.sha((HERE/'render.py').read_bytes())};(HERE/'offline-checks.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))

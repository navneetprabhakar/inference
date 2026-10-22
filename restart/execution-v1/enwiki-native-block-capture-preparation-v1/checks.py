"""Small synthetic format checks only. No native blocks read."""
import bz2,hashlib,json
from lxml import etree
import capture_core as c
PAGE=b'<page><title>A &amp; B</title><ns>0</ns><id>123</id><revision><id>456</id><model>wikitext</model><format>text/x-wiki</format><text xml:space="preserve">Hello &lt;world&gt; {{template}}</text><sha1>native</sha1></revision></page>'
ROW={'page_ID_observed':123,'title_observed':'A & B','row_ordinal':1}
def run():
 result=[]
 def yes(name,fn,reject=False):
  try:fn()
  except (ValueError,etree.XMLSyntaxError,__import__('xml.parsers.expat',fromlist=['ExpatError']).ExpatError) as e:
   if not reject:raise
   result.append({'check':name,'PASS':True,'rejected':str(e)[:200]});return
  if reject:raise AssertionError(name+' accepted')
  result.append({'check':name,'PASS':True})
 def roundtrip():
  raw=b'\n'+PAGE+b'\n'+PAGE+b'\n';decoded,receipt=c.decode(bz2.compress(raw),100000000);pages,spans=c.page_spans(decoded)
  assert len(pages)==2 and len(spans)==2 and receipt['all_member_CRC_EOF']
  for p,s in zip(pages,spans):
   assert decoded[s[0]:s[1]]==PAGE
   m,b=c.fields(p,s,decoded,ROW);assert m['native_page_id']=='123' and m['native_revision']['id']=='456' and b==b'Hello <world> {{template}}' and not m['holds'] and m['observed_page_namespace_URI'] is None
 yes('synthetic_page_spans_direct_vs_revision_identity_entity_text',roundtrip)
 yes('concatenated_BZ2_CRC_EOF',lambda:c.decode(bz2.compress(b'a')+bz2.compress(b'b'),2))
 yes('trailing_garbage',lambda:c.decode(bz2.compress(PAGE)+b'x',100000),True)
 yes('truncated_BZ2',lambda:c.decode(bz2.compress(PAGE)[:-1],100000),True)
 corrupt=bytearray(bz2.compress(PAGE));corrupt[-5]^=1
 yes('CRC_corruption',lambda:c.decode(bytes(corrupt),100000),True)
 yes('decoded_aggregate_cap',lambda:c.decode(bz2.compress(PAGE),5),True)
 yes('empty_BZ2',lambda:c.decode(b'',1000),True)
 yes('DTD_entity_denied',lambda:c.page_spans(b'<!DOCTYPE a [<!ENTITY x SYSTEM "https://example.org/">]>'+PAGE),True)
 yes('malformed_nonrecovering_XML',lambda:c.page_spans(PAGE[:-1]),True)
 yes('no_invented_global_header_close',lambda:c.page_spans(b'<mediawiki>'+PAGE),True)
 yes('global_close_not_repaired',lambda:c.page_spans(PAGE+b'</mediawiki>'),True)
 yes('nonUTF8_denied',lambda:c.page_spans(b'\xff'+PAGE),True)
 def namespace():
  raw=PAGE.replace(b'<page>',b'<page xmlns="urn:observed-fixture">');pages,spans=c.page_spans(raw);m,b=c.fields(pages[0],spans[0],raw,ROW);assert m['observed_page_namespace_URI']=='urn:observed-fixture' and not m['global_dump_namespace_inherited_or_header_known']
 yes('namespace_only_from_actual_page_declaration_synthetic',namespace)
 for name,raw,hold in [('redirect',PAGE.replace(b'<revision>',b'<redirect title="X"/><revision>'),'redirect'),('namespace1',PAGE.replace(b'<ns>0</ns>',b'<ns>1</ns>'),'non_namespace0_or_missing'),('code_model',PAGE.replace(b'wikitext',b'Scribunto'),'non_wikitext_or_unverified_model_format'),('missingtext',PAGE.replace(b'<text xml:space="preserve">Hello &lt;world&gt; {{template}}</text>',b''),'missing_source_text')]:
  def check(raw=raw,hold=hold):
   ps,sp=c.page_spans(raw);m,b=c.fields(ps[0],sp[0],raw,ROW);assert hold in m['holds']
  yes(name+'_held',check)
 return {'status':'PASS_SYNTHETIC_ONLY_NO_NATIVE_PARSE','count':len(result),'checks':result,'lxml_version':list(etree.LXML_VERSION)}
if __name__=='__main__':print(json.dumps(run(),indent=2))

"""Exact SAX character collection; XML decoding only, never wikitext rendering."""
import hashlib,importlib.util
from pathlib import Path
TEXT_PATHS={('mediawiki','page','revision','text'),('mediawiki','page','revision','slots','slot','text')}

def module(path):
    spec=importlib.util.spec_from_file_location('pinned_native_semantic_maintext',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def extract(header,raw,expected,semantic_path,check):
    if type(header) is not bytes or type(raw) is not bytes or len(header)>65536 or not 0<len(raw)<=1000000:raise ValueError('bounded_raw_header_page')
    digest=hashlib.sha256(raw).hexdigest()
    if len(raw)!=expected['raw_XML_bytes'] or digest!=expected['raw_XML_SHA256']:raise ValueError('captured_raw_XML_identity')
    semantic=module(semantic_path);pages=[];revisions=[];revision_ids=[];revision_holds=set()
    def on_revision(r):
        revision_ids.append(r['revision_ID']);revision_holds.update(r['holds'])
        if len(revisions)<1:revisions.append(r)
    class Collect(semantic.Metadata):
        def __init__(self):
            self.texts={};self.collected_bytes=0
            super().__init__(pages.append,on_revision,page_cap=1,decoded_cap=len(header)+len(raw),boundary_flush_cap=1)
        def start(self,name,attrs):
            super().start(name,attrs);node=self.stack[-1]
            if node['path'] in TEXT_PATHS and not node['opaque']:self.texts[node['start']]=bytearray()
        def data(self,text):
            super().data(text)
            if self.stack:
                node=self.stack[-1]
                if node['path'] in TEXT_PATHS and not node['opaque']:
                    b=text.encode('utf8');self.collected_bytes+=len(b)
                    if self.collected_bytes>1000000:raise ValueError('collected_text_memory_cap')
                    self.texts[node['start']].extend(b)
    parser=Collect()
    for body in [header,raw]:
        for i in range(0,len(body),65536):check();parser.feed(body[i:i+65536])
    final=parser.finish_prefix();check()
    if len(pages)!=1 or final['pages']!=1 or final['siteinfo_base_status']!='VERIFIED_HTTPS_ENWIKI_BASE' or final['root_holds']:raise ValueError('actual_header_native_root_context')
    page=pages[0];selection=expected['selection'];source=page['raw_XML']
    if source['start']!=len(header) or source['end']!=len(header)+len(raw) or source['SHA256']!=digest or page['page_ID']!=selection['page_id'] or page['namespace']!=selection['namespace'] or page['revision_count']!=selection['revision_count'] or ((page['redirect'] is not None)!=(bool(selection['flags']&1))):raise ValueError('captured_semantic_identity_or_raw_span')
    if page['model']!=expected['expected_model'] or page['format']!=expected['expected_format']:raise ValueError('captured_native_model_format_identity')
    if revision_ids and revision_ids[0]!=selection['first_revision_id']:raise ValueError('captured_first_revision_identity')
    holds=set(page['holds'])|revision_holds
    record={'selection':selection,'raw_XML_SHA256':digest,'raw_XML_bytes':len(raw),
       'source_title':page['title'],'native_page_ID':page['page_ID'],'native_namespace':page['namespace'],'native_redirect':page['redirect'],
       'native_revision_IDs':revision_ids,'native_revision_count':page['revision_count'],'native_model':page['model'],'native_format':page['format'],
       'parser_local_page_ordinal':page['page_ordinal'],'original_global_page_ordinal':selection['row_ordinal'],
       'actual_header_context_bytes':len(header),'actual_root_left_open':True,'invented_XML_bytes':0,
       'page_semantic_holds':page['holds'],'unknown_schema_count':page['unknown_count'],
       'unknown_descriptor_SHA256':page['unknown_descriptor_SHA256'],'text_changed_beyond_XML_standard_decoding':False}
    if len(revision_ids)!=1 or len(revisions)!=1:holds.add('UNSUPPORTED_MULTIPLE_OR_MISSING_REVISIONS_NO_SELECTION')
    content=None
    if len(revision_ids)==1 and len(revisions)==1:
        revision=revisions[0];record['native_revision']=revision
        if len(revision['contents'])!=1 or revision['contents'][0]['role'] not in {'legacy','main'}:holds.add('UNSUPPORTED_CONTENT_CARDINALITY_OR_ROLE')
        else:content=revision['contents'][0]
    text=None
    if content is not None:
        descriptor=content['text'];status=content['status'];record['native_content_status']=status;record['native_content_role']=content['role']
        if content['model']!='wikitext' or content['format']!='text/x-wiki':holds.add('UNSUPPORTED_NATIVE_MODEL_OR_FORMAT')
        if descriptor is None:holds.add('MISSING_NATIVE_TEXT')
        elif status['deleted'] or descriptor['child_count'] or descriptor['oversized']:holds.add('UNSUPPORTED_DELETED_CHILD_OR_OVERSIZED_TEXT')
        elif descriptor['span'][0] not in parser.texts:raise ValueError('exact_SAX_text_collection_span_missing')
        else:
            buf=parser.texts[descriptor['span'][0]];actual_SHA=hashlib.sha256(buf).hexdigest();actual_SHA1=hashlib.sha1(buf).hexdigest()
            if len(buf)!=descriptor['decoded_UTF8_bytes'] or actual_SHA!=descriptor['decoded_SHA256'] or actual_SHA1!=descriptor['decoded_SHA1']:raise ValueError('SAX_collector_vs_native_semantic_text_hash')
            if selection['main_text_bytes']!=-1 and len(buf)!=selection['main_text_bytes']:raise ValueError('captured_frame_main_text_byte_count')
            if status['byte_status']!='MATCH':holds.add('NATIVE_TEXT_BYTE_COUNT_NOT_VERIFIED')
            native_match=(status['attribute_SHA1_status']=='MATCH' or status['content_sibling_SHA1_status']=='MATCH' or revision['sibling_SHA1']['status']=='MATCH')
            if not native_match:holds.add('NATIVE_TEXT_SHA1_NOT_VERIFIED')
            if content['role']=='legacy' and revision['sibling_SHA1']['status']!='MATCH':holds.add('LEGACY_REVISION_SHA1_NOT_VERIFIED')
            record['actual_main_text_UTF8_bytes']=len(buf);record['actual_main_text_SHA256']=actual_SHA;record['actual_main_text_SHA1']=actual_SHA1
            record['text_element_raw_span_in_captured_page']=[x-len(header) for x in descriptor['span']]
            if not holds:text=bytes(buf)
    record['extraction_holds']=sorted(holds)
    if text is None:record['outcome']='HELD_UNSUPPORTED_OR_UNVERIFIED_NO_MAIN_TEXT_OUTPUT'
    elif page['redirect'] is not None:record['outcome']='EXACT_WIKITEXT_REDIRECT_DIAGNOSTIC_NOT_ENGLISH_PROSE'
    elif page['namespace']!=0:record['outcome']='EXACT_WIKITEXT_NONZERO_NAMESPACE_DIAGNOSTIC_NOT_ENGLISH_PROSE'
    else:record['outcome']='EXACT_NATIVE_MAIN_WIKITEXT_ONLY_PROSE_AND_QUALITY_UNREVIEWED'
    return record,text

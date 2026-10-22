"""Finite SQL coding; original raw page is authoritative provenance backing."""
import hashlib,json,time

FLAGS={name:1<<i for i,name in enumerate([
 'redirect','nonzero_namespace','semantic_hold','no_revision','multiple_revisions',
 'main_unavailable','deleted_text','unsupported_model_format','unknown_schema',
 'oversized_scalar','bytes_missing','bytes_match','bytes_bad','text_SHA_missing',
 'text_SHA_match','text_SHA_bad','revision_SHA_missing','revision_SHA_match',
 'revision_SHA_bad','revision_SHA_unverified','unsupported_slots','content_SHA_missing',
 'content_SHA_match','content_SHA_bad','content_SHA_unverified'])}

class Codec:
    def __init__(self,sink,exception,check):
        self.sink,self.exception,self.check=sink,exception,check
        self.group_base=0;self.first_revision=None;self.flags=0;self.expected_page=1
        self.models={};self.hold_counts={};self.status_counts={};self.page_flag_counts={};self.namespace_counts={};self.ns0_nonredirect=0;self.first_diagnostic=None;self.first_diagnostic_emitted=False
        self.timings={'revision_SQL_insert_seconds':0.0,'page_SQL_insert_seconds':0.0}
    def flag(self,name):self.flags|=FLAGS[name]
    def revision(self,r):
        self.check()
        if r['page_ordinal']!=self.expected_page:raise ValueError('codec_revision_page_order')
        before=time.clock_gettime(time.CLOCK_MONOTONIC)
        self.sink.revision(r['revision_ID'],r['page_ordinal'],r['revision_ordinal'])
        self.timings['revision_SQL_insert_seconds']+=time.clock_gettime(time.CLOCK_MONOTONIC)-before
        if self.first_revision is None:self.first_revision=r['revision_ID']
        for c in r['contents']:
            if c['role'] not in {'legacy','main'}:self.flag('unsupported_slots')
            if c['model']!='wikitext' or c['format']!='text/x-wiki':self.flag('unsupported_model_format')
            st=c['status']
            if st['deleted']:self.flag('deleted_text')
            for key,prefix in [('byte_status','bytes'),('attribute_SHA1_status','text_SHA'),('content_sibling_SHA1_status','content_SHA')]:
                value=st[key];self.status_counts[key+':'+value]=self.status_counts.get(key+':'+value,0)+1
                self.flag(prefix+'_missing' if value=='MISSING' else prefix+'_match' if value=='MATCH' else prefix+'_unverified' if value.startswith('UNVERIFIED') and prefix=='content_SHA' else prefix+'_bad')
        v=r['sibling_SHA1']['status'];self.status_counts['revision:'+v]=self.status_counts.get('revision:'+v,0)+1
        self.flag('revision_SHA_missing' if v=='MISSING' else 'revision_SHA_match' if v=='MATCH' else 'revision_SHA_unverified' if v.startswith('UNVERIFIED') else 'revision_SHA_bad')
        # Exact holds/unknown metadata/status combinations are exceptions, not
        # a duplicated source-text/page JSON corpus. Even normal hash states
        # remain represented by finite SQL flags and aggregate counters.
        uncommon=r['holds'] or r['revision_ordinal']>1 or any(c['role'] not in {'legacy','main'} for c in r['contents']) or len(r['contents'])!=1
        diagnostic={'kind':'revision','page_ordinal':r['page_ordinal'],
             'revision_ordinal':r['revision_ordinal'],'revision_ID':r['revision_ID'],
             'span':r['span'],'holds':r['holds'],'unknown_count':r['unknown_count'],
             'attributes':r['attributes'],'fields':r['fields'],
             'contributor':r['contributor'],'contributor_attributes':r['contributor_attributes'],
             'unknown_examples':r['unknown_examples'],'unknown_descriptor_SHA256':r['unknown_descriptor_SHA256'],
             'content_states':[{'role':c['role'],'model':c['model'],'format':c['format'],
                 'status':c['status'],'text_span':c['text']['span'] if c['text'] else None,
                 'text_decoded_SHA256':c['text']['decoded_SHA256'] if c['text'] else None} for c in r['contents']],
             'revision_sibling_SHA1':r['sibling_SHA1']}
        if r['revision_ordinal']==1:self.first_diagnostic=diagnostic
        if r['revision_ordinal']==2 and self.first_diagnostic is not None and not self.first_diagnostic_emitted:
            self.exception({**self.first_diagnostic,'multiple_revision_context':True})
        if uncommon:
            self.exception(diagnostic)
            if r['revision_ordinal']==1:self.first_diagnostic_emitted=True
    def page(self,p):
        self.check()
        if p['page_ordinal']!=self.expected_page:raise ValueError('codec_page_order')
        if p['redirect'] is not None:self.flag('redirect')
        if p['namespace']!=0:self.flag('nonzero_namespace')
        if p['holds']:self.flag('semantic_hold')
        if p['revision_count']==0:self.flag('no_revision')
        if p['revision_count']>1:self.flag('multiple_revisions')
        if p['main_text'] is None:self.flag('main_unavailable')
        for h in p['holds']:
            self.hold_counts[h]=self.hold_counts.get(h,0)+1
            if 'UNKNOWN' in h or 'SCHEMA' in h:self.flag('unknown_schema')
            if 'OVERSIZED' in h:self.flag('oversized_scalar')
        key=(p['model'],p['format'])
        if key==(None,None):code=0
        else:
            if key not in self.models:
                if len(self.models)>=128:raise ValueError('model_format_dictionary_cap')
                self.models[key]=len(self.models)+1
            code=self.models[key]
        raw=p['raw_XML'];before=time.clock_gettime(time.CLOCK_MONOTONIC)
        self.sink.page({'row_ordinal':p['page_ordinal'],'page_id':p['page_ID'],
            'first_revision_id':self.first_revision,'namespace':p['namespace'],'flags':self.flags,
            'model_code':code,'revision_count':p['revision_count'],
            'main_text_bytes':-1 if p['main_text'] is None else p['main_text']['decoded_UTF8_bytes'],
            'group_decoded_start':raw['start']-self.group_base,
            'raw_XML_bytes':raw['bytes'],'raw_SHA256':bytes.fromhex(raw['SHA256'])},p['title'])
        self.timings['page_SQL_insert_seconds']+=time.clock_gettime(time.CLOCK_MONOTONIC)-before
        if p['holds']:
            self.exception({'kind':'page','page_ordinal':p['page_ordinal'],'page_ID':p['page_ID'],
             'raw_XML_SHA256':raw['SHA256'],'span':[raw['start'],raw['end']],
             'holds':p['holds'],'unknown_count':p['unknown_count'],'unknown_examples':p['unknown_examples'],
             'unknown_descriptor_SHA256':p['unknown_descriptor_SHA256']})
        for counter,key,cap in [(self.page_flag_counts,self.flags,4096),(self.namespace_counts,p['namespace'],1024)]:
            if key not in counter and len(counter)>=cap:raise ValueError('bounded_summary_cardinality_cap')
            counter[key]=counter.get(key,0)+1
        if p['namespace']==0 and p['redirect'] is None:self.ns0_nonredirect+=1
        self.first_revision=None;self.first_diagnostic=None;self.first_diagnostic_emitted=False;self.flags=0;self.expected_page+=1
    def summary(self):
        return {'flag_bits':FLAGS,'models':[{'code':v,'model':k[0],'format':k[1]} for k,v in self.models.items()],
                'model_code0':'UNAVAILABLE_OR_AMBIGUOUS','main_text_bytes_minus1':'MISSING_OR_AMBIGUOUS_NOT_EMPTY',
                'hold_counts':self.hold_counts,'native_hash_status_counts':self.status_counts,
                'cumulative_SQL_callback_timings':self.timings,
                'normal_source_attribution':'Original raw page hash/span + revision occurrence points to untouched native bytes; no last-editor-as-full-history claim.'}

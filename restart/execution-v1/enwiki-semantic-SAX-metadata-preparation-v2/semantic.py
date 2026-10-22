"""Synthetic-stage native metadata callbacks. No reader, SQL, model or network.

Original byte spans/SHA come from the separately pinned PageSpans helper.
Callbacks are provisional until actual source/group/index reconciliation commits.
"""
import hashlib
import importlib.util
import json
import urllib.parse
from pathlib import Path

HELPER = Path(__file__).resolve().parent.parent / 'enwiki-incremental-XML-span-preparation-v3/spans.py'
HELPER_SHA256 = '6ff69d7d96c27c48099283e6357f1faf406173efae3a60da6e96ea57d3e2865b'
XML = 'http://www.w3.org/XML/1998/namespace}'
ALLOWED = {
 'mediawiki': {'siteinfo', 'page'},
 'siteinfo': {'sitename','dbname','base','generator','case','namespaces'},
 'namespaces': {'namespace'},
 'page': {'title','ns','id','redirect','restrictions','revision'},
 'revision': {'id','parentid','timestamp','contributor','minor','comment','origin','model','format','text','sha1','slots'},
 'contributor': {'username','id','ip'}, 'slots': {'slot'},
 'slot': {'origin','model','format','text','sha1'},
}
ATTRS = {'mediawiki': {'version',XML+'lang', '{http://www.w3.org/2001/XMLSchema-instance}schemaLocation'},
 'namespace': {'key','case','canonical'}, 'redirect': {'title'},
 'slot': {'role'}, 'text': {XML+'space','bytes','sha1','deleted'},
 'comment': {'deleted'}, 'contributor': {'deleted'}, 'sha1': {'deleted'},
 'revision': set()}
LIMITS = {'depth':64,'scalar_bytes':65536,'attribute_bytes':16384,
 'attributes':32,'children_per_element':4096,'revisions_per_page':10000,
 'slots_per_revision':16,'unknown_examples':16,'namespace_definitions':512}


def _load_helper():
    if hashlib.sha256(HELPER.read_bytes()).hexdigest() != HELPER_SHA256:
        raise ValueError('span_helper_pin_mismatch')
    spec=importlib.util.spec_from_file_location('pinned_page_spans',HELPER)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module.PageSpans


def integer(value, *, signed=False):
    if not isinstance(value,str) or not value or len(value)>20:
        raise ValueError('direct_identity_missing_invalid_or_overflow')
    digits=value[1:] if signed and value.startswith('-') else value
    if not digits or any(c not in '0123456789' for c in digits):
        raise ValueError('direct_identity_missing_invalid_or_overflow')
    n=int(value)
    if not (-(2**63) <= n <= 2**63-1) or (not signed and n<=0):
        raise ValueError('direct_identity_missing_invalid_or_overflow')
    return n


def native_hash(value):
    if value is None:return None
    if not value or len(value)>31 or any(c not in '0123456789abcdefghijklmnopqrstuvwxyz' for c in value):
        raise ValueError('invalid_native_base36')
    n=int(value,36)
    if n>=2**160:raise ValueError('invalid_native_base36')
    return n


class Metadata:
    def __init__(self, page, revision, *, limits=None, require_enwiki_base=True, **span_limits):
        self.limits=dict(LIMITS)
        if limits:self.limits.update(limits)
        for k,v in self.limits.items():
            if k not in LIMITS or type(v) is not int or v<=0:raise ValueError('finite_semantic_limits')
        if type(require_enwiki_base) is not bool:raise ValueError('require_enwiki_base_boolean')
        self.require_enwiki_base=require_enwiki_base;self.siteinfo_base_status='MISSING';self.root_namespace_declarations=[];self.root_expanded_name=None;self.root_opening_span=None
        self.emit_page,self.emit_revision=page,revision
        self.stack=[];self.current=None;self.rev=None;self.slot=None
        self.pending=None;self.siteinfo_seen=False;self.namespace_keys=set()
        self.header_unknown={'unknown_count':0,'unknown_examples':[],'unknown_digest':hashlib.sha256()};self.root_holds=set();self.siteinfo_fields={};self.namespace_metadata={};self.root_attributes=None;self.pending_namespace_declarations=[];self.pages=0;self.revisions=0
        self.max_scalar=0;self.max_stack=0;self.max_revision_contents=0
        self.span=_load_helper()(self._page_span,start=self.start,end=self.end,data=self.data,**span_limits)
        self.span.parser.StartNamespaceDeclHandler=self.namespace_declaration

    def namespace_declaration(self,prefix,uri):
        if len(self.pending_namespace_declarations)>=self.limits['attributes'] or len((prefix or '').encode())+len((uri or '').encode())>self.limits['attribute_bytes']:
            raise ValueError('namespace_declaration_limit')
        self.pending_namespace_declarations.append({'prefix':prefix,'URI':uri})

    def hold(self, code):
        target=self.rev if self.rev is not None else self.current
        (target['holds'] if target is not None else self.root_holds).add(code)

    def start(self,name,attrs):
        local=name.rsplit('}',1)[-1];path=tuple(n['name'] for n in self.stack)+(local,)
        if len(path)>self.limits['depth']:raise ValueError('semantic_depth_limit')
        if len(attrs)>self.limits['attributes'] or len(json.dumps(attrs,ensure_ascii=False).encode())>self.limits['attribute_bytes']:
            raise ValueError('semantic_attribute_limit')
        if self.stack:
            parent=self.stack[-1];parent['children']+=1
            cap=(self.span.page_cap+1 if parent['path']==('mediawiki',) else self.limits['revisions_per_page']+16 if parent['path']==('mediawiki','page') else self.limits['children_per_element'])
            if parent['children']>cap:raise ValueError('element_child_count_limit')
            parent['counts'][local]=parent['counts'].get(local,0)+1
            if len(parent['counts'])>64:raise ValueError('distinct_child_names_limit')
        if path==('mediawiki',):
            self.root_attributes=dict(attrs);self.root_expanded_name=name
            self.root_namespace_declarations=[dict(x) for x in self.pending_namespace_declarations]
        if path==('mediawiki','page'):
            if not self.siteinfo_seen:raise ValueError('siteinfo_must_precede_page')
            self.current={'ordinal':self.pages+1,'fields':{},'holds':set(self.root_holds),
                'revision_count':0,'unknown_examples':[],'unknown_count':0,'unknown_digest':hashlib.sha256(),
                'redirect':None,'main_text':None,'model':None,'format':None}
        if path==('mediawiki','page','revision'):
            self.current['revision_count']+=1
            if self.current['revision_count']>self.limits['revisions_per_page']:raise ValueError('per_page_revision_limit')
            self.rev={'fields':{},'holds':set(),'contents':[],'contributor':{},
                'ordinal':self.current['revision_count'],'slots_present':False,
                'legacy':{},'unknown_examples':[],'unknown_count':0,'unknown_digest':hashlib.sha256()}
        if path==('mediawiki','page','revision','slots'):self.rev['slots_present']=True
        if path==('mediawiki','page','revision','slots','slot'):
            if len(self.rev['contents'])>=self.limits['slots_per_revision']:raise ValueError('slot_count_limit')
            self.slot={'role':attrs.get('role'),'attributes':dict(attrs),'start':self.span.parser.CurrentByteIndex,'fields':{}}
        unknown=bool(self.stack and local not in ALLOWED.get(self.stack[-1]['name'],set()))
        # A familiar name nested in an unknown branch never becomes semantic ID/text.
        opaque=unknown or bool(self.stack and self.stack[-1]['opaque'])
        if unknown:self.hold('UNKNOWN_CHILD_SCHEMA')
        expected=ATTRS.get(local,set())
        # Expat expanded attribute names use URI}local without a leading brace.
        expected={x.lstrip('{') for x in expected}
        if any(k not in expected for k in attrs):self.hold('UNKNOWN_ATTRIBUTE_SCHEMA')
        pos=self.span.parser.CurrentByteIndex;offset=pos-self.span.base;quote=None;opening_end=None
        for i in range(offset,len(self.span.raw)):
            b=self.span.raw[i]
            if quote is not None:
                if b==quote:quote=None
            elif b in (34,39):quote=b
            elif b==62:opening_end=self.span.base+i+1;break
        if opening_end is None:raise ValueError('semantic_opening_tag_unavailable')
        if path==('mediawiki',):self.root_opening_span=[pos,opening_end]
        empty=opening_end if self.span.raw[opening_end-self.span.base-2:opening_end-self.span.base]==b'/>' else None
        node={'namespace_declarations':self.pending_namespace_declarations,'empty_end':empty,'name':local,'path':path,'start':self.span.parser.CurrentByteIndex,
              'attrs':dict(attrs),'children':0,'counts':{},'opaque':opaque,
              'parts':[],'retained':0,'size':0,'hash':hashlib.sha256(),'sha1':hashlib.sha1(),'oversized':False}
        self.pending_namespace_declarations=[]
        self.stack.append(node);self.max_stack=max(self.max_stack,len(self.stack))

    def data(self,text):
        if not self.stack:return
        n=self.stack[-1];b=text.encode('utf8');n['size']+=len(b)
        if n['name'] in ALLOWED and text.strip():self.hold('NONWHITESPACE_CONTAINER_CHARACTER_DATA')
        n['hash'].update(b);n['sha1'].update(b)
        # Arbitrarily large ordinary text and unknown values hash incrementally.
        if n['name']!='text' and n['name'] not in ALLOWED:
            if not n['oversized'] and n['size']<=self.limits['scalar_bytes']:
                n['parts'].append(text);n['retained']+=len(b)
            else:
                n['oversized']=True;n['parts'].clear();n['retained']=0;self.hold('OVERSIZED_SCALAR_METADATA')
        self.max_scalar=max(self.max_scalar,n['retained'])

    def descriptor(self,n):
        end=n['empty_end']
        if end is None:
            pos=self.span.parser.CurrentByteIndex;i=pos-self.span.base
            if self.span.raw[i:i+2]!=b'</':raise ValueError('semantic_closing_tag_unavailable')
            j=self.span.raw.find(b'>',i)
            if j<0:raise ValueError('semantic_closing_tag_unavailable')
            end=self.span.base+j+1
        return {'span':[n['start'],end], 'attributes':n['attrs'],
                'namespace_declarations':n['namespace_declarations'],
                'decoded_UTF8_bytes':n['size'],'decoded_SHA256':n['hash'].hexdigest(),
                'decoded_SHA1':n['sha1'].hexdigest(),
                'value':None if n['name']=='text' or n['oversized'] else ''.join(n['parts']),
                'oversized':n['oversized'],'child_count':n['children']}

    def save(self, fields, name, desc):
        if name in fields:
            if name in {'id','ns','title'}:raise ValueError('duplicate_direct_identity_field')
            self.hold('DUPLICATE_DIRECT_FIELD');return
        fields[name]=desc

    def end(self,name):
        n=self.stack[-1];local=name.rsplit('}',1)[-1]
        if n['name']!=local:raise ValueError('semantic_end_mismatch')
        d=self.descriptor(n);path=n['path'];v=d['value']
        if local in {'revision','slots','slot','page'}:
            repeated=[k for k,vv in n['counts'].items() if vv>1 and k not in ({'revision'} if local=='page' else {'slot'} if local=='slots' else set())]
            if repeated:self.hold('DUPLICATE_CONTAINER_SCHEMA')
        if n['children'] and local not in ALLOWED:self.hold('SCALAR_HAS_CHILD_SCHEMA')
        if n['opaque']:
            target=self.rev if self.rev is not None else self.current
            if target is None:target=self.header_unknown
            if target is not None:
                target['unknown_count']+=1
                obj={'name':local,**d};target['unknown_digest'].update(json.dumps(obj,sort_keys=True).encode())
                if len(target['unknown_examples'])<self.limits['unknown_examples']:target['unknown_examples'].append(obj)
        elif path[:2]==('mediawiki','siteinfo'):
            if path==('mediawiki','siteinfo','namespaces','namespace'):
                key=integer(n['attrs'].get('key'),signed=True)
                if key in self.namespace_keys:self.root_holds.add('DUPLICATE_SITEINFO_NAMESPACE')
                self.namespace_keys.add(key);self.namespace_metadata[key]=d
                if len(self.namespace_keys)>self.limits['namespace_definitions']:raise ValueError('namespace_definition_limit')
            elif len(path)==3:self.save(self.siteinfo_fields,local,d)
        elif path[:2]==('mediawiki','page'):
            if len(path)==3 and local!='revision':
                self.save(self.current['fields'],local,d)
                if local=='redirect':self.current['redirect']=d
            elif len(path)==4 and path[2]=='revision' and local not in {'slots','contributor'}:
                self.save(self.rev['fields'],local,d)
                if local in {'model','format','text'}:self.save(self.rev['legacy'],local,d)
            elif len(path)==5 and path[2:4]==('revision','contributor'):
                self.save(self.rev['contributor'],local,d)
            elif len(path)==6 and path[2:5]==('revision','slots','slot'):
                self.save(self.slot['fields'],local,d)
        if path==('mediawiki','siteinfo'):
            if self.siteinfo_seen:raise ValueError('duplicate_siteinfo')
            self.siteinfo_seen=True
            base=self.siteinfo_fields.get('base')
            value=base.get('value') if base else None
            if not self.require_enwiki_base:self.siteinfo_base_status='NOT_REQUIRED_BY_FIXTURE_CONFIGURATION'
            else:
                try:
                    u=urllib.parse.urlsplit(value or '')
                    good=(base is not None and not base['child_count'] and bool(value)
                          and not any(ord(c)<=32 for c in value) and u.scheme=='https'
                          and u.netloc=='en.wikipedia.org' and not u.fragment)
                except ValueError:good=False
                self.siteinfo_base_status='VERIFIED_HTTPS_ENWIKI_BASE' if good else 'UNSUPPORTED_OR_MISSING'
                if not good:self.root_holds.add('SITEINFO_BASE_UNSUPPORTED_OR_MISSING')
        if path==('mediawiki','page','revision','contributor'):self.rev['contributor_attributes']=n['attrs']
        if path==('mediawiki','page','revision','slots','slot'):
            self.slot['span']=d['span'];self.rev['contents'].append(self.slot);self.slot=None
        if path==('mediawiki','page','revision'):self.close_revision(n,d)
        if path==('mediawiki','page'):
            c=self.current
            ident=self.required_int(c['fields'],'id');ns=self.required_int(c['fields'],'ns',signed=True)
            title=c['fields'].get('title')
            if title is None or title['value'] is None or title['child_count']:raise ValueError('direct_title_missing_or_unsupported')
            if ns not in self.namespace_keys:c['holds'].add('NAMESPACE_NOT_IN_SITEINFO')
            if not c['revision_count']:c['holds'].add('NO_REVISION')
            if c['revision_count']>1:c['holds'].add('MULTIPLE_REVISIONS_NO_CANONICAL_SELECTION')
            self.pending={'page_ordinal':c['ordinal'],'page_ID':ident,'title':title['value'],
                'namespace':ns,'redirect':c['redirect'],'revision_count':c['revision_count'],
                'main_text':c['main_text'] if c['revision_count']==1 else None,
                'model':c['model'] if c['revision_count']==1 else None,
                'format':c['format'] if c['revision_count']==1 else None,
                'holds':sorted(c['holds']),'unknown_count':c['unknown_count'],
                'unknown_examples':c['unknown_examples'],'unknown_descriptor_SHA256':c['unknown_digest'].hexdigest(),
                'no_admission_or_English_claim':True}
            self.current=None
        self.stack.pop()

    def required_int(self,fields,name,**kw):
        d=fields.get(name)
        if d is None or d['child_count']:raise ValueError('direct_identity_missing_invalid_or_overflow')
        return integer(d['value'],**kw)

    def text_check(self,fields):
        model=fields.get('model',{}).get('value');fmt=fields.get('format',{}).get('value')
        if model!='wikitext':self.hold('NON_WIKITEXT_OR_MISSING_MODEL')
        if fmt!='text/x-wiki':self.hold('NON_WIKI_OR_MISSING_FORMAT')
        t=fields.get('text')
        status={'present':t is not None,'deleted':False,'byte_status':'MISSING','attribute_SHA1_status':'MISSING','content_sibling_SHA1_status':'MISSING'}
        if t is None:self.hold('MISSING_TEXT');return {'model':model,'format':fmt,'text':None,'status':status}
        status['deleted']='deleted' in t['attributes']
        if status['deleted']:self.hold('DELETED_TEXT')
        if t['child_count']:self.hold('TEXT_HAS_CHILD_SCHEMA')
        b=t['attributes'].get('bytes')
        if b is not None:
            if not b or len(b)>20 or any(x not in '0123456789' for x in b):status['byte_status']='INVALID';self.hold('INVALID_NATIVE_TEXT_BYTES')
            else:
                status['byte_status']='MATCH' if int(b)==t['decoded_UTF8_bytes'] else 'MISMATCH'
                if status['byte_status']=='MISMATCH':self.hold('TEXT_BYTE_MISMATCH')
        h=t['attributes'].get('sha1')
        if h is not None:
            try:
                status['attribute_SHA1_status']='MATCH' if native_hash(h)==int(t['decoded_SHA1'],16) else 'MISMATCH'
            except ValueError:status['attribute_SHA1_status']='INVALID'
            if status['attribute_SHA1_status']!='MATCH':self.hold('TEXT_ATTRIBUTE_SHA1_MISMATCH_OR_INVALID')
        hnode=fields.get('sha1')
        if hnode is not None:
            if 'deleted' in hnode['attributes']:status['content_sibling_SHA1_status']='DELETED'
            else:
                try:
                    hh=native_hash(hnode['value'])
                    if hnode['child_count']:raise ValueError('child')
                    status['content_sibling_SHA1_status']='UNVERIFIED_UNSUPPORTED_CONTENT' if status['deleted'] or t['child_count'] or model!='wikitext' or fmt!='text/x-wiki' else 'MATCH' if hh==int(t['decoded_SHA1'],16) else 'MISMATCH'
                except ValueError:status['content_sibling_SHA1_status']='INVALID'
            if status['content_sibling_SHA1_status'] in {'INVALID','DELETED','MISMATCH'}:self.hold('CONTENT_SIBLING_SHA1_INVALID_DELETED_OR_MISMATCH')
        return {'model':model,'format':fmt,'text':t,'status':status}

    def close_revision(self,n,d):
        r=self.rev;rid=self.required_int(r['fields'],'id')
        contents=[]
        if r['slots_present']:
            if r['legacy']:self.hold('AMBIGUOUS_LEGACY_AND_SLOTS')
            for slot in r['contents']:contents.append({'role':slot['role'],'attributes':slot['attributes'],'span':slot['span'],**self.text_check(slot['fields'])})
            roles=[x['role'] for x in contents]
            if not roles:self.hold('EMPTY_SLOTS')
            if any(x!='main' for x in roles):self.hold('UNSUPPORTED_OR_MISSING_SLOT_ROLE')
            if len(set(roles))>1:self.hold('MIXED_SLOT_ROLES')
            if roles.count('main')>1:self.hold('MULTIPLE_MAIN_SLOTS')
        else:contents=[{'role':'legacy',**self.text_check(r['legacy'])}]
        self.max_revision_contents=max(self.max_revision_contents,len(contents))
        supported=len(contents)==1 and contents[0]['role'] in {'main','legacy'} and not (r['slots_present'] and r['legacy'])
        t=contents[0]['text'] if supported else None
        s=r['fields'].get('sha1');sibling={'status':'MISSING','matches':None,'raw':s}
        if s is not None:
            if 'deleted' in s['attributes']:sibling['status']='DELETED';self.hold('SIBLING_SHA1_DELETED_OR_INVALID')
            else:
                try:value=native_hash(s['value'])
                except ValueError:value=None
                if value is None or s['child_count']:sibling['status']='INVALID';self.hold('SIBLING_SHA1_DELETED_OR_INVALID')
                elif not supported or t is None or 'deleted' in t['attributes'] or t['child_count'] or contents[0]['model']!='wikitext' or contents[0]['format']!='text/x-wiki':sibling['status']='UNVERIFIED_UNSUPPORTED_CONTENT'
                else:
                    sibling['matches']=value==int(t['decoded_SHA1'],16)
                    sibling['status']='MATCH' if sibling['matches'] else 'MISMATCH'
                    if not sibling['matches']:self.hold('SIBLING_SHA1_MISMATCH')
        # Callback order intentionally does not accumulate revisions in a page.
        row={'revision_ID':rid,'page_ordinal':self.current['ordinal'],'revision_ordinal':r['ordinal'],
            'page_ID':self.required_int(self.current['fields'],'id'),
            'span':d['span'],'attributes':n['attrs'],'fields':r['fields'],'contributor':r['contributor'],'contributor_attributes':r.get('contributor_attributes'),
            'contents':contents,'sibling_SHA1':sibling,'holds':sorted(r['holds']),
            'unknown_count':r['unknown_count'],'unknown_examples':r['unknown_examples'],
            'unknown_descriptor_SHA256':r['unknown_digest'].hexdigest()}
        self.emit_revision(row);self.revisions+=1
        self.current['holds'].update(r['holds'])
        if r['ordinal']==1 and supported:
            self.current['main_text']=t;self.current['model']=contents[0]['model'];self.current['format']=contents[0]['format']
        self.rev=None

    def _page_span(self,raw):
        if self.pending is None or self.pending['page_ordinal']!=raw['ordinal']:raise ValueError('semantic_raw_page_handoff')
        self.pending['raw_XML']=raw;self.emit_page(self.pending);self.pending=None;self.pages+=1

    def feed(self,chunk):return self.span.feed(chunk)

    def finish_prefix(self):
        # The pinned helper first flushes Expat's deferred terminal token; its
        # callbacks must settle semantic state before this layer checks it.
        raw=self.span.finish_prefix()
        if (len(self.stack)!=1 or self.stack[0]['name']!='mediawiki' or self.pending
                or self.current or self.rev or not self.siteinfo_seen):
            raise ValueError('semantic_prefix_boundary_required')
        return {'scope':'PREFIX_ONLY_EXTERNAL_GROUP_INDEX_PROOF_REQUIRED',
                'root_attributes':self.root_attributes,'siteinfo_fields':self.siteinfo_fields,
                'namespace_metadata':self.namespace_metadata,'root_holds':sorted(self.root_holds),
                'header_unknown_count':self.header_unknown['unknown_count'],
                'header_unknown_examples':self.header_unknown['unknown_examples'],
                'header_unknown_descriptor_SHA256':self.header_unknown['unknown_digest'].hexdigest(),
                'pages':self.pages,'revision_occurrences':self.revisions,'raw':raw,
                'max_scalar_retained_bytes':self.max_scalar,'max_stack_depth':self.max_stack,
                'siteinfo_base_status':self.siteinfo_base_status,'root_namespace_declarations':self.root_namespace_declarations,
                'root_expanded_name':self.root_expanded_name,'root_opening_span':self.root_opening_span,
                'global_ID_uniqueness_claim':False,'source_admission':False}

    def finish(self):
        raw=self.span.finish()
        if self.stack or self.pending or self.current or self.rev:raise ValueError('semantic_terminal_state')
        return {'pages':self.pages,'revision_occurrences':self.revisions,'raw':raw,
            'max_scalar_retained_bytes':self.max_scalar,'max_stack_depth':self.max_stack,
            'siteinfo_base_status':self.siteinfo_base_status,'root_namespace_declarations':self.root_namespace_declarations,
            'root_expanded_name':self.root_expanded_name,'root_opening_span':self.root_opening_span,
            'siteinfo_fields':self.siteinfo_fields,'namespace_metadata':self.namespace_metadata,'root_attributes':self.root_attributes,
            'header_unknown_count':self.header_unknown['unknown_count'],'header_unknown_examples':self.header_unknown['unknown_examples'],
            'header_unknown_descriptor_SHA256':self.header_unknown['unknown_digest'].hexdigest(),
            'max_revision_contents':self.max_revision_contents,'root_holds':sorted(self.root_holds),
            'global_ID_uniqueness_claim':False,'source_admission':False}

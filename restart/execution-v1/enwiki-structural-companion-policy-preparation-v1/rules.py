"""Synthetic policy classifier only. No source rendering or text deletion."""
MAINTENANCE={'Use dmy dates','Use mdy dates','Use American English','Use Australian English','Use Indian English'}
SHORT={'Short description','short description'}
INFOBOX={'Infobox official post','Infobox settlement','Infobox Turkey place','Infobox radio station'}
NAV={'Human Rights in North Korea','Portal','New South Wales ministerial portfolios','Elazığ District','ElazığDistrict-geo-stub','WestGodavari-geo-stub','Fayetteville Radio','Urban Radio Stations in North Carolina','Beasley Broadcast Group'}
CITE={'cite web','Cite web','cite news','Cite news','cite magazine','Cite magazine','cite book','cite journal','cite AV media'}
INLINE={'dts','ayd','Sortname','sortname','hsp','Australian party style','Australian politics/name','transliteration','Langnf','As of','As of?','convert','coord','flag','section link','in lang','Quote box','ntsh','citation needed'}
REFDEP={'sfn','sfnRef','refn','efn','Reflist','reflist','Notelist','refbegin','refend','cite NSW Parliament','Cite NSW Parliament','Gazette NSW','NSW Parliamentary Record','Australian Dictionary of Biography'}
def template_rule(name,params,standalone):
 name=name.strip();keys=[k for k,v in params]
 base={'preserve_entire_raw_node_in_companion':True,'apply_to_source':False,'admitted':False}
 if name in MAINTENANCE:
  okay=standalone and len(keys)==len(set(keys)) and set(keys)<= {'date'}
  return {**base,'class':'maintenance_metadata','action':'PROPOSE_SOURCE_BOUND_METADATA_COMPANION' if okay else 'HOLD_INVALID_SCHEMA_OR_INLINE_METADATA','prose_may_proceed_after_review':okay}
 if name=='CS1 config':return {**base,'class':'citation_style_metadata','action':'PROPOSE_COMPANION_PENDING_REF_RESOLVER_STYLE_POLICY','prose_may_proceed_after_review':False}
 if name in SHORT or name in INFOBOX:return {**base,'class':'semantic_page_metadata','action':'PROPOSE_COMPLETE_PARAMETER_COMPANION_NO_VALUE_DELETION' if standalone else 'HOLD_INLINE_SEMANTIC_TEMPLATE','prose_may_proceed_after_review':False}
 if name.startswith('DEFAULTSORT:'):return {**base,'class':'sort_metadata','action':'PROPOSE_COMPLETE_SORT_COMPANION' if standalone and not params else 'HOLD_UNVERIFIED_SORT_SCHEMA','prose_may_proceed_after_review':False}
 if name in NAV:return {**base,'class':'navigation_or_taxonomy_with_semantic_labels','action':'PROPOSE_STANDALONE_COMPLETE_NAVIGATION_COMPANION' if standalone else 'HOLD_INLINE_NAV_DEPENDENCY','prose_may_proceed_after_review':False}
 if name in CITE:return {**base,'class':'literal_citation_parameters','action':'DEFER_BOUND_PAGE_LOCAL_REFERENCE_RESOLVER','prose_may_proceed_after_review':False}
 if name in REFDEP:return {**base,'class':'reference_or_bibliography_dependency','action':'HOLD_UNRESOLVED_REFERENCE_SEMANTICS','prose_may_proceed_after_review':False}
 if name in INLINE:return {**base,'class':'inline_or_semantic_template','action':'HOLD_UNRESOLVED_SEMANTIC_CONTENT_NO_SILENT_DROP','prose_may_proceed_after_review':False}
 return {**base,'class':'unknown_template','action':'HOLD_UNKNOWN_TEMPLATE','prose_may_proceed_after_review':False}

def span_rule(attrs):
 # Exact observed empty browser styling attrs do not remove their prose contents.
 allowed={'data-darkreader-inline-color','data-darkreader-inline-bgcolor'}
 okay=len(attrs)==len({k for k,v in attrs}) and all(k in allowed and v=='' for k,v in attrs)
 return {'action':'PROPOSE_TRANSPARENT_CONTENT_RECURSION_RAW_WRAPPER_COMPANION' if okay else 'HOLD_UNSUPPORTED_SPAN_ATTRIBUTES','preserve_every_content_byte_or_explicit_render_operation':True,'apply_to_source':False}

"""Preparation only: source-specific literal spans, no derivative materialization."""
import hashlib,json,pathlib,re
HERE=pathlib.Path(__file__).resolve().parent;BASE=HERE.parent;SOURCE=BASE/'m2-intake/enwiki-native-20row-capture-v1'
sha=lambda b:hashlib.sha256(b).hexdigest()
INPUTS={'WUKS':4481523,'Unikili':17544253}
def prepare(title,row):
 raw=(SOURCE/f'row-{row}.source-text.utf8').read_bytes();s=raw.decode();metadata=json.loads((SOURCE/f'row-{row}.json').read_text());body=s.index("'''"+title+"'''");end=s.index('==References==') if title=='WUKS' else s.index('== See also ==');ops=[];units=[];references=[];refnumbers={};refdefinitions={}
 def offset(i):return len(s[:i].encode())
 def op(a,b,replacement,kind,**extra):
  old=s[a:b].encode();new=replacement.encode();ops.append({'start_byte':offset(a),'end_exclusive_byte':offset(b),'original_hex':old.hex(),'original_SHA256':sha(old),'replacement_hex':new.hex(),'operation':kind,**extra})
 op(0,body,'','omit_complete_nonprose_prefix_metadata',hold='Native infobox/metadata remains preserved, not prose or inferred template values')
 op(end,len(s),'','omit_complete_endmatter_metadata',hold='References/navigation/category units retained in exact omission sidecar; not concatenated into prose')
 # Inspect only these exact retained sources. Regexes locate literal candidates;
 # the executor has no regex/template parser and consumes frozen spans only.
 refpattern=re.compile(r'<ref\b[^>]*?(?:/\s*>|>.*?</ref>)',re.S)
 refs=list(refpattern.finditer(s,body,end))
 if len(refs)!=len(re.findall(r'<ref\b',s[body:end])):raise ValueError('unrecognized_reference_boundary')
 for index,m in enumerate(refs):
  opening=m.group().split('>',1)[0];name=re.search(r'\bname\s*=\s*(?:"([^"]+)"|\x27([^\x27]+)\x27|([^\s/>]+))',opening);name=next((v for v in name.groups() if v is not None),None) if name else None;identity='name:'+name if name else 'anonymous:'+str(index+1)
  if identity not in refnumbers:refnumbers[identity]=len(refnumbers)+1
  if not re.search(r'/\s*>$',m.group()):
   if identity in refdefinitions and refdefinitions[identity]!=m.group():raise ValueError('conflicting_named_reference_definition')
   refdefinitions[identity]=m.group()
  references.append({'occurrence':index+1,'identity':identity,'marker':'['+str(refnumbers[identity])+']','start_byte':offset(m.start()),'end_exclusive_byte':offset(m.end()),'native_reference':m.group(),'native_reference_SHA256':sha(m.group().encode()),'content_rendered_or_template_expanded':False})
 for ref in references:
  ref['definition_resolved_locally']=ref['identity'] in refdefinitions
  ref['definition_native']=refdefinitions.get(ref['identity'])
  ref['dependency_hold']='Exact native citation metadata retained; citation-template rendering, source factual verification and component-rights review pending'
 position=body
 while position<end:
  stop=s.find('\n\n',position,end);stop=end if stop<0 else stop+2
  # These two exact standalone media lines are independent native units; the
  # first is followed by prose on the very next line. Do not hold that prose.
  media_lines=['[[Image:WUKS logo.png|left|thumb|"Kiss" logo]]\n','[[File:WUKS OldSchool107.7JAMZ logo.jpg|thumb|"Jamz" logo with the "Old School" branding]]\n'] if title=='WUKS' else []
  for line in media_lines:
   if s.startswith(line,position):stop=min(stop,position+len(line))
  native=s[position:stop];u={'ordinal':len(units)+1,'source_start_byte':offset(position),'source_end_exclusive_byte':offset(stop),'native_SHA256':sha(native.encode()),'native_text':native,'dependency_holds':[]}
  selectedrefs=[(m,ref) for m,ref in zip(refs,references) if position<=m.start()<stop]
  if any(m.end()>stop for m,r in selectedrefs):raise ValueError('crossunit_reference_requires_explicit_boundary_review')
  visible=list(native)
  for m,ref in selectedrefs:
   visible[m.start()-position:m.end()-position]=' '*(m.end()-m.start())
  visible=''.join(visible)
  manual_asof=None
  if title=='Unikili' and '{{As of|2011}}' in visible:
   if visible.count('{{As of|2011}}')!=1:raise ValueError('exact_once_manually_approved_As_of_literal')
   manual_asof=position+visible.index('{{As of|2011}}')
   visible=visible.replace('{{As of|2011}}',' '*len('{{As of|2011}}'))
  unsupported=[]
  if '{{' in visible or '}}' in visible:unsupported.append('unresolved_inline_template_complete_dependent_unit_held')
  if re.search(r'\[\[(?:File|Image):',visible):unsupported.append('complete_media_caption_unit_held')
  if '<' in visible or '>' in visible:unsupported.append('unsupported_inline_HTML_complete_unit_held')
  if unsupported:
   u['status']='HELD_COMPLETE_DEPENDENT_UNIT_NO_RENDER';u['dependency_holds']=unsupported;op(position,stop,'','omit_held_complete_dependent_unit',unit=u['ordinal'],holds=unsupported)
  else:
   u['status']='REVERSIBLE_DEVELOPMENT_PREVIEW_NOT_ACCEPTED'
   if manual_asof is not None:
    op(manual_asof,manual_asof+len('{{As of|2011}}'),'As of 2011','parent_manually_adjudicated_exact_literal_semantic_mapping',unit=u['ordinal'],approval='Parent explicitly authorized ONLY exact Unikili {{As of|2011}} to As of 2011; not templateexecution, certified same-snapshot expansion, grammatical or factual correction')
    u['dependency_holds'].append('Dated census factual provenance, rights and quality still pending; awkward source grammar retained')
   for m,ref in selectedrefs:
    op(m.start(),m.end(),ref['marker'],'reference_occurrence_to_local_provenance_marker',unit=u['ordinal'],reference_identity=ref['identity'],definition_resolved_locally=ref['definition_resolved_locally'])
    u['dependency_holds'].append(ref['dependency_hold'])
   links=list(re.finditer(r'\[\[([^\[\]\n]+)\]\]',visible))
   if len(links)!=visible.count('[[') or len(links)!=visible.count(']]'):raise ValueError('unrecognized_nested_link_requires_wholeunit_hold')
   covered=[]
   for m in links:
    inner=m.group(1)
    if inner.count('|')>1:raise ValueError('unsupported_multi_pipe_link')
    label=inner.rsplit('|',1)[-1]
    if not label or '{{' in label or '}}' in label:raise ValueError('unsupported_link_label')
    op(position+m.start(),position+m.end(),label,'exact_displayed_internal_link_label',unit=u['ordinal'],original_target=inner.split('|',1)[0],display_label_copied_verbatim=True)
    covered.append((m.start(),m.end()))
   for m in re.finditer(r"'{2,3}",visible):
    if not any(a<=m.start()<b for a,b in covered):op(position+m.start(),position+m.end(),'','literal_emphasis_delimiter_only',unit=u['ordinal'])
   for m in re.finditer(r'(?m)^==([^=\n]+)==$',visible):
    op(position+m.start(),position+m.start()+2,'','literal_heading_delimiter_only',unit=u['ordinal']);op(position+m.end()-2,position+m.end(),'','literal_heading_delimiter_only',unit=u['ordinal'])
   if '"' in visible:u['dependency_holds'].append('Attributed quoted wording retained; exact component rights and attribution review pending')
  if u['status']=='REVERSIBLE_DEVELOPMENT_PREVIEW_NOT_ACCEPTED' and u['dependency_holds']:u['status']='HELD_COMPLETE_UNIT_WITH_DIAGNOSTIC_PREVIEW'
  units.append(u);position=stop
 ops.sort(key=lambda o:o['start_byte'])
 for a,b in zip(ops,ops[1:]):
  if a['end_exclusive_byte']>b['start_byte']:raise ValueError('overlapping_literal_operations')
 for o in ops:
  if raw[o['start_byte']:o['end_exclusive_byte']].hex()!=o['original_hex']:raise ValueError('literal_operation_source_mismatch')
 return {'title':title,'index_row_ordinal':row,'page_ID':metadata['native_page_id'],'revision_ID':metadata['native_revision']['id'],'source_text_path':str((SOURCE/f'row-{row}.source-text.utf8').resolve()),'source_text_SHA256':sha(raw),'source_text_bytes':len(raw),'source_native_XML_SHA256':metadata['raw_page_XML_SHA256'],'operations':ops,'complete_native_units':units,'reference_occurrences':references,'native_citation_definitions':refdefinitions,'derivative_content_bytes_arithmetic_only':len(raw)+sum(len(bytes.fromhex(o['replacement_hex']))-(o['end_exclusive_byte']-o['start_byte']) for o in ops),'derivative_materialized':False,'acceptance_or_usable_count':False,'rights_or_facts_cleared':False}
if __name__=='__main__':
 recipes=[prepare(title,row) for title,row in INPUTS.items()]
 (HERE/'literal-recipes.json').write_text(json.dumps({'status':'FROZEN_SOURCE_SPECIFIC_PREPARATION_ONLY','source_scope':'Only exact WUKS and Unikili revisions; rules do not generalize','citation_marker_scope':'Generated numbered local provenance markers, not source wording; exact native reference metadata and unresolved citation/component review stay with full dependent units','recipes':recipes,'new_admitted_documents':0,'new_admitted_tokens':0},indent=2,ensure_ascii=False)+'\n')
 (HERE/'all20-original-decisions.json').write_bytes((SOURCE/'all20-native-decisions.json').read_bytes())
 print(json.dumps([{'title':r['title'],'operations':len(r['operations']),'units':len(r['complete_native_units']),'wholly_held_units':sum(u['status']=='HELD_COMPLETE_DEPENDENT_UNIT_NO_RENDER' for u in r['complete_native_units']),'reference_occurrences':len(r['reference_occurrences']),'derivative_bytes_arithmetic':r['derivative_content_bytes_arithmetic_only']} for r in recipes]))

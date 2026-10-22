"""Lossless PG envelope discovery; hints never authorize component removal or admission.
Canonical marker basis: pinned existing Gutenberg discovery/chapter utilities.
Explicit THE/THIS + EBOOK/ETEXT spellings are supported discovery grammar, not
an assertion that every PG historical convention or source edition is covered.
"""
import hashlib,re
sha=lambda b:hashlib.sha256(b).hexdigest()
MARKER=rb'(?mi)(?:\A|(?<=[\r\n]))\*\*\*[ \t]+(START|END) OF (THE|THIS) PROJECT GUTENBERG (EBOOK|ETEXT)([^\r\n]*?)\*\*\*[ \t]*(?:\r\n|\n|\r|$)'
# Only source-span diagnostics; captions, notes and editorial text remain intact.
HINTS={
 'illustration_caption':rb'\[Illustration:[^\]]*\]',
 'footnote_candidate':rb'\[(?:\d+|Footnote[^\]]*|[Tt]ranscriber[^\]]*)\]',
 'editorial_candidate':rb'(?i)transcriber.{0,100}|proofread.{0,100}|Project Gutenberg.{0,100}|Internet Archive.{0,100}|editor.s note.{0,100}',
 'chapter_heading_candidate':rb'(?mi)^[ \t]*(?:CHAPTER|BOOK|PART)[ \t]+[^\r\n]{1,120}$',
 'contents_heading_candidate':rb'(?mi)^[ \t]*(?:TABLE OF CONTENTS|CONTENTS|LIST OF ILLUSTRATIONS)[ \t]*\r?$',
}
FIELD=rb'(?mi)^(Title|Author|Authors|Editor|Editors|Illustrator|Illustrators|Translator|Translators|Contributor|Contributors|Release Date|Posting Date|Last Updated|Language|Character set encoding|Credits|Produced by):[^\r\n]*(?:(?:\r\n|\n|\r)[ \t]+[^\r\n]*)*'
def span(raw,a,b,role):return {'role':role,'start_byte':a,'end_byte':b,'bytes':b-a,'SHA256':sha(raw[a:b])}
def inspect(raw,eid,event_cap=4096):
 if not isinstance(raw,bytes) or not 0<len(raw)<=2400000:raise ValueError('raw_file_bound')
 text=raw.decode('utf8','strict');holds=[];markers=[]
 for m in re.finditer(MARKER,raw):
  if len(markers)>=64:raise ValueError('marker_event_cap')
  markers.append({**span(raw,m.start(),m.end(),'pg_marker'),'direction':m[1].decode().upper(),'article':m[2].decode().upper(),'format':m[3].decode().upper(),'label_exact':m[4].decode('utf8')})
 marker_like=sum(1 for _ in re.finditer(rb'(?mi)(?:\A|(?<=[\r\n]))\*\*\*[ \t]+(?:START|END)\b[^\r\n]*',raw))
 if marker_like!=len(markers):holds.append('unsupported_marker_like_lines_no_guess')
 starts=[x for x in markers if x['direction']=='START'];ends=[x for x in markers if x['direction']=='END']
 ids=sorted(set(int(x) for x in re.findall(rb'(?i)\b(?:e-?book)\s*#\s*([0-9]{1,12})',raw[:16384])))
 if ids!=[eid]:holds.append('header_ID_missing_conflicting_or_not_unique')
 partition=[];payload=None
 if len(starts)!=1 or len(ends)!=1:holds.append('missing_or_ambiguous_supported_marker_pair')
 elif starts[0]['end_byte']>=ends[0]['start_byte']:holds.append('unordered_or_empty_payload')
 else:
  s,e=starts[0],ends[0]
  if s['label_exact'].strip().casefold()!=e['label_exact'].strip().casefold():holds.append('start_end_marker_label_disagreement')
  if (s['article'],s['format'])!=(e['article'],e['format']):holds.append('start_end_marker_grammar_disagreement')
  cuts=[(0,s['start_byte'],'raw_header'),(s['start_byte'],s['end_byte'],'start_marker'),(s['end_byte'],e['start_byte'],'continuous_PG_payload_envelope'),(e['start_byte'],e['end_byte'],'end_marker'),(e['end_byte'],len(raw),'raw_footer')]
  partition=[span(raw,a,b,k) for a,b,k in cuts]
  if b''.join(raw[p['start_byte']:p['end_byte']] for p in partition)!=raw:raise ValueError('exact_partition_inverse')
  payload=partition[2]
 header_end=starts[0]['start_byte'] if len(starts)==1 else min(16384,len(raw))
 fields=[]
 for m in re.finditer(FIELD,raw[:header_end]):
  if len(fields)>=100:raise ValueError('header_field_cap')
  fields.append({**span(raw,m.start(),m.end(),'raw_header_field'),'key':m[1].decode(),'exact_text':m.group().decode('utf8')})
 annotations=[]
 if payload:
  a,b=payload['start_byte'],payload['end_byte'];body=raw[a:b]
  for kind,p in HINTS.items():
   for m in re.finditer(p,body):
    if len(annotations)>=event_cap:raise ValueError('annotation_event_cap_no_silent_truncation')
    annotations.append(span(raw,a+m.start(),a+m.end(),kind))
  if b'PROJECT GUTENBERG LICENSE' not in raw[ends[0]['end_byte']:].upper():holds.append('full_license_footer_heading_unobserved')
 return {'raw_bytes':len(raw),'raw_SHA256':sha(raw),'raw_characters':len(text),'raw_whitespace_words':len(text.split()),'strict_UTF8':True,'header_IDs_first16384bytes':ids,'markers':markers,'raw_header_fields':fields,'partition':partition,'payload':payload,'payload_characters':len(raw[payload['start_byte']:payload['end_byte']].decode('utf8')) if payload else None,'payload_whitespace_words':len(raw[payload['start_byte']:payload['end_byte']].decode('utf8').split()) if payload else None,'structural_hints':annotations,'boundary_holds':holds,'boundary_discovery_status':'HELD_DISCOVERY' if holds else 'UNIQUE_LOSSLESS_PG_ENVELOPE_DISCOVERED_NOT_MAIN_PROSE_APPROVED','payload_includes_all_print_frontmatter_endmatter_notes_unchanged':True,'chapter_boundaries_or_edition_rights_quality_cleared':False,'source_bytes_removed_or_rewritten':0}

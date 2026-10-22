"""Pure catalog classification; no network, model, ledger or book-body operations."""
import hashlib,json,re,unicodedata
from urllib.parse import urlsplit
POLICY_VERSION='gutenberg-native-catalog-discovery-v1'
CREATOR='{http://purl.org/dc/terms/}creator'
def sha(b):return hashlib.sha256(b).hexdigest()
def canonical(value):return json.dumps(value,ensure_ascii=True,separators=(',',':'),sort_keys=True).encode()
def normalized_title(title):return ' '.join(re.sub(r'[^\w\s]',' ',unicodedata.normalize('NFKC',title).casefold()).split())
def plain_utf8(f,eid):
 u=urlsplit(f.get('resolved_URL',''));bindings=f.get('isFormatOf_URLs',[]);bound=bool(bindings) and all(re.fullmatch(r'https?://(?:www\.)?gutenberg\.org/ebooks/'+str(eid),v) for v in bindings);m=[re.sub(r'\s+','',x.lower()) for x in f.get('MIME_values',[])]
 return (bound and not f.get('holds') and u.scheme in {'http','https'} and u.hostname in {'www.gutenberg.org','gutenberg.org'} and not u.query and not u.fragment and any(x=='text/plain;charset=utf-8' for x in m) and isinstance(f.get('extent_bytes'),int) and f['extent_bytes']>0)
def classify(row,source):
 eid=row['ebook_ID'];languages=row['languages'];types=row['types'];exclude=[];holds=[]
 if languages and 'en' not in languages:exclude.append('explicit_language_set_without_English')
 elif languages!=['en']:holds.append('missing_or_multilingual_language_set')
 if types and 'Text' not in types:exclude.append('explicit_non_Text_type')
 elif types!=['Text']:holds.append('missing_or_mixed_type')
 creators=[a for a in row['contributors_and_all_roles'] if a['role_qualified_name']==CREATOR]
 if not creators or any(a['stable_agent_ID'] is None or a['holds'] for a in creators):holds.append('stable_primary_creator_unresolved')
 formats=[f for f in row['formats'] if plain_utf8(f,eid)]
 if not formats:holds.append('no_source_bound_official_plain_UTF8_format')
 holds+=['native:'+v for v in row['holds']]
 if row['unresolved_contributor_fields']:holds.append('unresolved_contributor_reference')
 years=[]
 for a in creators:
  dates=a['deathdates']
  years.append(int(dates[0]) if len(dates)==1 and re.fullmatch(r'-?[0-9]{1,4}',dates[0]) else None)
 era='creator_deaths_all_exact_le1900_priority_only' if years and all(y is not None and y<=1900 for y in years) else ('creator_death_missing_or_uncertain' if not years or None in years else 'creator_death_after1900_review')
 labels=sorted({v for group in row['subjects']+row['bookshelves'] for v in group['values']})
 joined='\n'.join(labels).casefold();genres=[]
 for genre,pattern in [('narrative',r'\b(fiction|stories|novels|tales)\b'),('history',r'\bhistory\b'),('essays',r'\bessays\b'),('biography',r'\b(biography|autobiography|memoirs)\b'),('poetry',r'\b(poetry|poems|verse)\b'),('drama',r'\b(drama|plays)\b')]:
  if re.search(pattern,joined):genres.append(genre)
 if not genres:genres=['other_or_unclassified']
 title=row['titles'][0] if len(row['titles'])==1 else ''
 family_seed={'creator_IDs':sorted({a['stable_agent_ID'] for a in creators if a['stable_agent_ID'] is not None}),'normalized_title':normalized_title(title)}
 provisional='authority_title:'+sha(canonical(family_seed)) if family_seed['creator_IDs'] and family_seed['normalized_title'] else 'ebook:'+str(eid)
 # Explicit relation targets provide edges only, never invented work equivalence.
 related=set()
 for relation in row['native_relations_and_credits']:
  for v in list(relation.get('attributes',{}).values())+[relation.get('text','')]:
   for match in re.finditer(r'https?://(?:www\.)?gutenberg\.org/ebooks/([1-9][0-9]*)(?![0-9])',v):related.add(int(match.group(1)))
 status='EXCLUDED_FROM_ENGLISH_TEXT_DISCOVERY' if exclude else ('HELD_METADATA_REPAIR_OR_REVIEW' if holds else 'ELIGIBLE_FOR_BODY_REVIEW_METADATA_ONLY')
 return {'ebook_ID':eid,'source_binding':source,'discovery_status':status,'exclusion_reasons':sorted(set(exclude)),'metadata_hold_reasons':sorted(set(holds)),'languages':languages,'typed_language_fields':row['typed_language_fields'],'types':types,'titles':row['titles'],'subjects':row['subjects'],'bookshelves':row['bookshelves'],'observed_genre_strata':genres,'creator_era_stratum':era,'contributors_and_all_roles':row['contributors_and_all_roles'],'unresolved_contributor_fields':row['unresolved_contributor_fields'],'rights_fields':row['rights_fields'],'all_formats':row['formats'],'missingness':{'rights':not row['rights_fields'],'formats':not row['formats'],'subjects':not row['subjects'],'primary_creator_death':not years or None in years,'contributors_with_missing_birthdates':sum(not a['birthdates'] for a in row['contributors_and_all_roles']),'contributors_with_missing_deathdates':sum(not a['deathdates'] for a in row['contributors_and_all_roles']),'formats_with_missing_modified':sum(not f['modified_values'] for f in row['formats'])},'plain_UTF8_review_format_candidates':formats,'PG_issued_dates_not_print_dates':row['PG_issued_dates'],'native_relations_and_credits':row['native_relations_and_credits'],'original_print_dates_and_edition':row['original_print_dates_and_edition'],'provisional_family':provisional,'explicit_related_ebook_IDs':sorted(related),'original_English_composition':'UNVERIFIED_REQUIRES_BODY_AND_PRIMARY_BIBLIOGRAPHY','edition_and_jurisdiction_rights':'UNVERIFIED_PER_WORK_INCLUDING_MODERN_ADDITIONS','body_acquisition_authorized':False,'training_admitted':False,'priority_key':sha((POLICY_VERSION+'\n'+provisional).encode()),'genre_filter_exclusions':[]}
def summarize(rows):
 from collections import Counter
 return {'records':len(rows),'status_counts':dict(Counter(r['discovery_status'] for r in rows)),'exclusion_reason_counts_nonexclusive':dict(Counter(v for r in rows for v in r['exclusion_reasons'])),'hold_reason_counts_nonexclusive':dict(Counter(v for r in rows for v in r['metadata_hold_reasons'])),'genre_counts_nonexclusive':dict(Counter(v for r in rows for v in r['observed_genre_strata'])),'era_counts':dict(Counter(r['creator_era_stratum'] for r in rows)),'metadata_not_usable_documents_or_tokens':True,'training_eligible':0}

def families(items):
 """Conservative transitive connected components; these are split/dedup holds, not proven works."""
 parent={r['ebook_ID']:r['ebook_ID'] for r in items}
 def root(i):
  while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
  return i
 def union(a,b):
  a,b=root(a),root(b)
  if a!=b:parent[max(a,b)]=min(a,b)
 seeds={}
 for row in items:
  eid=row['ebook_ID'];seed=row['provisional_family']
  if seed in seeds:union(eid,seeds[seed])
  else:seeds[seed]=eid
  for related in row['explicit_related_ebook_IDs']:
   if related in parent:union(eid,related)
 for row in items:
  row['provisional_family_component']='gutenberg-component:'+str(root(row['ebook_ID']))
  row['priority_key']=sha((POLICY_VERSION+'\n'+row['provisional_family_component']).encode())
 return items

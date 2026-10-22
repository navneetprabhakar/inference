import copy,json
from pathlib import Path
import derive
p=Path(__file__).resolve().parent
native=json.loads(next((p/'prefix400-diagnostic-rows.jsonl').open()))
# Original retained row fixture, preserving all fields rather than reconstructing metadata.
import sqlite3
source=p.parent/'m2-intake/gutenberg-complete-native-catalog-v1/catalog.sqlite3'
c=sqlite3.connect('file:'+str(source)+'?mode=ro',uri=True)
try:row=json.loads(c.execute('select data from records where member=?',(native['source_binding']['ordinal'],)).fetchone()[0])
finally:c.close()
checks=[]
def test(name,ok):assert ok,name;checks.append(name)
def run(r):return derive.classify(r,{'test_fixture':True})
base=run(row);test('all_roles_rights_formats_verbatim_retained',base['contributors_and_all_roles']==row['contributors_and_all_roles'] and base['rights_fields']==row['rights_fields'] and base['all_formats']==row['formats'])
test('English_and_US_rights_never_admit',not base['training_admitted'] and base['original_English_composition'].startswith('UNVERIFIED') and base['edition_and_jurisdiction_rights'].startswith('UNVERIFIED'))
for name,fields,status in [('nonEnglish',{'languages':['fr']},'EXCLUDED'),('multilingual',{'languages':['en','fr']},'HELD'),('missinglanguage',{'languages':[]},'HELD'),('nonText',{'types':['Sound']},'EXCLUDED'),('missingcreator',{'contributors_and_all_roles':[]},'HELD'),('noformats',{'formats':[]},'HELD')]:
 r=copy.deepcopy(row);r.update(fields);test(name,run(r)['discovery_status'].startswith(status))
f={'resolved_URL':'https://www.gutenberg.org/ebooks/1.txt.utf-8','MIME_values':['text/plain; charset=utf-8'],'holds':[],'extent_bytes':100,'isFormatOf_URLs':['https://www.gutenberg.org/ebooks/2']}
test('wrong_format_source_identity_refused',not derive.plain_utf8(f,1))
f['isFormatOf_URLs']=['https://www.gutenberg.org/ebooks/1'];test('native_UTF8_source_binding_valid',derive.plain_utf8(f,1))
f['resolved_URL']='https://other.example/1.txt';test('offsite_body_candidate_not_authorized',not derive.plain_utf8(f,1))
a=copy.deepcopy(base);a.update(ebook_ID=1,provisional_family='a',explicit_related_ebook_IDs=[2]);b=copy.deepcopy(base);b.update(ebook_ID=2,provisional_family='b',explicit_related_ebook_IDs=[]);d=copy.deepcopy(base);d.update(ebook_ID=3,provisional_family='b',explicit_related_ebook_IDs=[])
out=derive.families([a,b,d]);test('transitive_explicit_and_authority_title_family_edges',len({r['provisional_family_component'] for r in out})==1)
(p/'checks.json').write_text(json.dumps({'status':'PASS','cases':checks,'count':len(checks),'no_network_or_full_parse':True},indent=2)+'\n');print(len(checks),'PASS')

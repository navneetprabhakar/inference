"""Exercise consequential exclusion boundaries using synthetic metadata, no source text."""
import copy
import hashlib
import json
from pathlib import Path
from prepare_frame import build, evaluate
root=Path(__file__).parent
base={'workId':'ef5e4013-a46c-4e61-924b-5c95f5f86f8b','workStatus':'ACTIVE','workType':'MONOGRAPH','withdrawnDate':None,'license':'http://creativecommons.org/licenses/by/4.0/','languages':[{'languageCode':'ENG','languageRelation':'ORIGINAL'}],'imprint':{'publisher':{'publisherName':'Open Book Publishers'}},'doi':'https://doi.org/10.11647/OBP.0054','titles':[{'canonical':True,'localeCode':'EN','fullTitle':'Synthetic boundary fixture, not source metadata'}],'publications':[{'publicationType':'EPUB','locations':[{'canonical':True,'fullTextUrl':'https://books.openbookpublishers.com/10.11647/obp.0054.epub'}]}],'relations':[]}
checks={}
checks['exact_ccby4_candidate']=evaluate(base)[0] is not None
for key, value in [('NC','https://creativecommons.org/licenses/by-nc/4.0/'),('ND','https://creativecommons.org/licenses/by-nd/4.0/'),('SA','https://creativecommons.org/licenses/by-sa/4.0/'),('lookalike','https://creativecommons.org.evil.invalid/licenses/by/4.0/'),('unknown',None)]:
    item=copy.deepcopy(base);item['license']=value
    checks['reject_license_'+key]=evaluate(item)[0] is None
item=copy.deepcopy(base);item['relations']=[{'relationType':'HAS_CHILD','relatedWork':{'license':'https://creativecommons.org/licenses/by-nc-nd/4.0/','workStatus':'ACTIVE'}}]
checks['reject_child_conflict_even_when_book_ccby']=evaluate(item)[0] is None
item=copy.deepcopy(base);item['languages']=[{'languageCode':'ENG'},{'languageCode':'LAT'}]
checks['reject_mixed_language']=evaluate(item)[0] is None
item=copy.deepcopy(base);item['workStatus']='WITHDRAWN'
checks['reject_withdrawn']=evaluate(item)[0] is None
item=copy.deepcopy(base);item['publications'][0]['locations'][0]['fullTextUrl']='https://store.example.invalid/pay.epub'
checks['reject_nonpublisher_download']=evaluate(item)[0] is None
item=copy.deepcopy(base);item['publications'][0]['locations'].append({'canonical':True,'fullTextUrl':'https://books.openbookpublishers.com/10.11647/different.epub'})
checks['reject_ambiguous_canonical_url']=evaluate(item)[0] is None
checks['exclude_seen_discovery_family']=build([base],[base['workId']])['eligible_records']==0
records=[]
for n in range(1,5):
    item=copy.deepcopy(base);item['workId']=f'00000000-0000-4000-8000-{n:012d}';item['doi']=f'https://doi.org/10.11647/OBP.TEST{n}';records.append(item)
a=build(records);b=build(list(reversed(records)))
checks['selection_independent_of_input_order']=a['selected']==b['selected']
checks['no_admission']=a['usable_tokens']==a['usable_documents']==0 and all(x['admitted'] is False for x in a['selected'])
try:
    build([base,base])
except ValueError:
    checks['duplicate_uuid_refused']=True
else:
    checks['duplicate_uuid_refused']=False
item=copy.deepcopy(base);item['workId']='00000000-0000-4000-8000-000000000009'
try:
    build([base,item])
except ValueError:
    checks['duplicate_doi_family_refused']=True
else:
    checks['duplicate_doi_family_refused']=False
assert all(checks.values()),checks
result={'status':'PASS_OFFLINE_SELECTION_BOUNDARIES','checks':checks,'checks_count':len(checks),'actual_publisher_frame_not_acquired':True,'source_epubs_not_downloaded':True,'script_sha256':hashlib.sha256((root/'prepare_frame.py').read_bytes()).hexdigest()}
(root/'selection-verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))

"""Exactly400 existing systematically selected prefix metadata records only."""
import json,sqlite3,sys
from pathlib import Path
import derive
HERE=Path(__file__).resolve().parent;EXEC=HERE.parent
sys.path.insert(0,str(EXEC/'gutenberg-catalog-compact-preparation-v2'));import compact
SOURCE=EXEC/'m2-intake/gutenberg-complete-native-catalog-v1/catalog.sqlite3'
EXPECTED='a2100b3dbb01f43688263789b798dc978e5daf22fe5bdb544693f3bf32319400'
assert compact.file_sha(SOURCE)==EXPECTED
connection=sqlite3.connect('file:'+str(SOURCE)+'?mode=ro',uri=True)
try:
 rows=[]
 for member,original,memberdata in connection.execute('select r.member,r.data,m.data from records r join members m on r.member=m.ordinal where r.member%90=0 order by r.member limit400'.replace('limit400','limit 400')):
  record=json.loads(original);native=json.loads(memberdata)
  rows.append(derive.classify(record,{'diagnostic_prefix_DB_SHA256':EXPECTED,'catalog_archive_SHA256':compact.ARCHIVE_SHA,'ordinal':member,'native_member':native,'original_JSON_SHA256':derive.sha(original.encode())}))
finally:connection.close()
assert len(rows)==400
rows=derive.families(rows)
with (HERE/'prefix400-diagnostic-rows.jsonl').open('x') as f:
 for row in rows:f.write(json.dumps(row,separators=(',',':'))+'\n')
summary={'scope':'400 retained-prefix metadata rows at member%90=0; not complete or representative; no quality/yield inference','source_DB_SHA256':EXPECTED,'summary':derive.summarize(rows),'no_network':True,'no_full_archive_parse':True,'training_admitted':0,'first20_historical_narrative_discovery_IDs_only':[r['ebook_ID'] for r in sorted(rows,key=lambda r:(r['priority_key'],r['ebook_ID'])) if r['discovery_status']=='ELIGIBLE_FOR_BODY_REVIEW_METADATA_ONLY' and r['creator_era_stratum']=='creator_deaths_all_exact_le1900_priority_only' and 'narrative' in r['observed_genre_strata']][:20]}
(HERE/'prefix400-diagnostic-summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))

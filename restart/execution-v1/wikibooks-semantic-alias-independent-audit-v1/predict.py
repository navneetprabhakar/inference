"""Independent expected semantic-role inventory from immutable hash metadata only."""
from pathlib import Path
import json,hashlib,collections
HERE=Path(__file__).resolve().parent;BASE=HERE.parent
H=lambda q:hashlib.sha256(q.read_bytes()).hexdigest()
def run():
 source=BASE/'wikibooks-three-renewed-custody-preparation-v1';rows=json.loads((source/'body-sources.json').read_text());pins=json.loads((source/'code-pins.json').read_text())['input_SHA256'];language=json.loads((BASE/'wikibooks-language-token-preparation-v1/profile.json').read_text());canonical=language['shards'];assert len(rows)==837 and len(canonical)==12
 canonical_by_hash={r['sha256']:r['path'] for r in canonical};assert len(canonical_by_hash)==12
 for r in canonical:assert pins[r['path']]==r['sha256']
 expected=[];groups=collections.defaultdict(list)
 for i,e in enumerate(rows):
  digest=pins[e['path']];role='CURRENT_WB_FINALIZED_RENDERED' if e['adapter']=='sqlite_json_data' and e.get('table')=='rendered' and digest in canonical_by_hash else None
  if role:groups[digest].append(e['path'])
  expected.append({'index':i,'path':e['path'],'adapter':e['adapter'],'table':e.get('table'),'input_SHA256':digest,'expected_semantic_role':role,'required_body_coverage':e['required_current_candidate_body_coverage']})
 qualified=[r for r in expected if r['expected_semantic_role']];assert len(qualified)==16 and len(groups)==12
 aliasowners=[]
 for digest,paths in groups.items():
  owner=paths[0];aliasowners.append({'digest':digest,'canonical_provenance_path':canonical_by_hash[digest],'first_frozen_owner':owner,'physical_paths':paths,'owner_is_recovered_alias':'-verification-v1/' in owner,'validated_owner_proof_required':True})
 report={'status':'INDEPENDENT_METADATA_EXPECTED_ROLES_NO_SOURCE_BODY_PARSE_OR_MATCH','input_pins':{str(source/'body-sources.json'):H(source/'body-sources.json'),str(source/'code-pins.json'):H(source/'code-pins.json'),str(BASE/'wikibooks-language-token-preparation-v1/profile.json'):H(BASE/'wikibooks-language-token-preparation-v1/profile.json')},'source_adapters':837,'canonical_hash_unique_stores':12,'qualifying_physical_rendered_adapters':16,'extra_exactbyte_physical_aliases':4,'canonical_finalized_expected_identities':89758,'recovered_original4_expected_identities':50457,'residual8_expected_identities':39301,'expected_roles':expected,'physical_alias_groups':aliasowners,'method':'Exact adapter+renderedtable+fullSQLiteSHA matched to pinnedlanguage canonical12. Pathspelling/lexicalorder alone neverassigns/clearsrole; allpayloadpage/revision/family/textSHA/finalroles mustvalidatebeforecompare andcompleteownerproofbeforealiasinheritance. Metadata prediction only, not assertionthosebodychecksran.','new_body_rows_parsed':0,'new_body_comparisons':0,'new_admitted_documents':0};(HERE/'expected-role-inventory.json').write_text(json.dumps(report,indent=2)+'\n');print('expectedroleSHA',H(HERE/'expected-role-inventory.json'));print('roles',len(qualified),'groups',len(groups))
if __name__=='__main__':run()

import copy,json,tempfile,sqlite3
from pathlib import Path
import canonical as c

HERE=Path(__file__).resolve().parent
def row(ordinal,revision=1,title='Book/Chapter'):
    return {'source_ordinal':ordinal,'revision_id':revision,'title':title,'url':'https://en.wikibooks.org/wiki/'+title,'html_sha256':'html','wikitext_sha256':'wiki','license_original_metadata':[{'identifier':'CC-BY-SA-4.0','url':'https://creativecommons.org/licenses/by-sa/4.0/'}],'identity_holds':[]}
def main():
    checks=[]
    assert c.resolve_group([row(1)])[0]==1;checks.append('single_eligible_selected')
    assert c.resolve_group([row(2,4),row(1,3)])[0]==2;checks.append('highest_revision_source_order_independent')
    assert c.resolve_group([row(2,4),row(1,4)])[0]==1;checks.append('equivalent_maximum_keeps_first_ordinal')
    for key,value in [('title','Other'),('url','https://en.wikibooks.org/wiki/Other'),('html_sha256','other'),('wikitext_sha256','other'),('license_original_metadata',[{'identifier':'CC-BY-SA-3.0','url':'https://creativecommons.org/licenses/by-sa/3.0/'}])]:
        a=row(1,4);b=row(2,4);b[key]=value;assert c.resolve_group([a,b])[0] is None
    checks.append('any_maximal_identity_component_conflict_holds_whole_group')
    a=row(1);a['identity_holds']=['title_URL_mismatch'];assert c.resolve_group([a])[0] is None;checks.append('identity_holds_excluded')
    a=row(2,4);a['license_original_metadata'][0]['identifier']='CC-BY-SA-3.0';assert c.resolve_group([row(1,3),a])[0] is None;checks.append('no_fallback_to_older_eligible_when_max_ineligible')
    a=row(1);a['license_original_metadata'].append(copy.deepcopy(a['license_original_metadata'][0]));assert not c.exact_four(a);checks.append('exact_single_captured4_license_only')
    old=row(1,3,'Old Book/Chapter');old['license_original_metadata'][0]['identifier']='CC-BY-SA-3.0';new=row(2,4,'New Book/Chapter');chosen,mapping=c.resolve_group([old,new]);assert chosen==2 and mapping[0]['canonical_source_ordinal']==2 and old['license_original_metadata'][0]['identifier']=='CC-BY-SA-3.0';checks.append('older_license_preserved_not_relabelled')
    assert c.resolve_group([row(1,3),row(2,4)])[0]==c.resolve_group([row(2,4),row(1,3)])[0];checks.append('group_input_order_deterministic')
    result={'status':'PASS_DETERMINISTIC_CANONICAL_RULES','checks':checks,'check_count':len(checks),'new_admitted_documents':0,'new_admitted_tokens':0};(HERE/'rule-check-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()

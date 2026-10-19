"""Whole-path eligibility and immutable source/partition candidate binding."""
# Creator: Navneet Prabhakar
from copy import deepcopy
import json
import pytest
from slm.data import dialogue_candidates as module
from slm.data.schema import Source,digest
from slm.data.tokenized import sha
from test_staging import setup


def node(key,role,parent=None,children=()):
    return dict(message_id=key,parent_id=parent,role=role,text='Hello '+key,lang='en',
                deleted=False,review_result=True,review_count=3,synthetic=False,model_name=None,rank=0,replies=list(children))


def fixture():
    a=node('a','assistant','u'); root=node('u','prompter',children=[a])
    tree=dict(message_tree_id='u',tree_state='ready_for_export',prompt=root)
    source=Source('OpenAssistant/oasst2','a'*40,'https://example.org','apache-2.0','b'*64,'c'*64,('https://example.org',))
    return tree,source


def projection(tree):
    rows=[];stack=[tree['prompt']]
    while stack:
        n=stack.pop();rows.append((n['message_id'],n['parent_id']));stack.extend(n['replies'])
    return dict(split='validation',messages=len(rows),node_identity_sha256=digest(sorted(rows)))


def test_exact_text_metadata_and_official_validation_are_retained():
    tree,source=fixture();tree['prompt']['text']='  Hi\nthere! '
    items,_,_,_=module.extract(tree,source,projection(tree),'d'*64)
    item=items[0]
    assert item['messages'][0]['content']=='  Hi\nthere! '
    assert item['official_split']=='validation' and item['content_category']=='unreviewed'
    assert item['lineage']==['u','a']
    assert item['validation_results']['dialogue_candidate']['raw_nodes'][0]['review_result'] is True
    assert not item['validation_results']['dialogue_candidate']['training_eligible']


@pytest.mark.parametrize('field,value',[('deleted',True),('deleted',None),('review_result',False),
    ('review_result',None),('synthetic',True),('synthetic',None),('model_name','teacher'),('lang','es'),('text',' ')])
def test_invalid_ancestor_prunes_descendants_without_splicing(field,value):
    tree,source=fixture();tree['prompt'][field]=value
    items,reasons,_,_=module.extract(tree,source,projection(tree),'d'*64)
    assert not items and sum(reasons.values())==1


def test_maximal_valid_prefix_survives_rejected_later_turn_without_dropping_an_inner_turn():
    tree,source=fixture();a=tree['prompt']['replies'][0]
    bad=node('u2','prompter','a',[node('a2','assistant','u2')]);bad['review_result']=False;a['replies']=[bad]
    items,_,_,_=module.extract(tree,source,projection(tree),'d'*64)
    assert [i['lineage'] for i in items]==[['u','a']]
    bad['review_result']=True
    items,_,_,_=module.extract(tree,source,projection(tree),'d'*64)
    assert [i['lineage'] for i in items]==[['u','a','u2','a2']]


def test_tree_cap_is_deterministic_but_not_quality_approval():
    tree,source=fixture();tree['prompt']['replies']=[node('a'+str(i),'assistant','u') for i in range(6)]
    for i,n in enumerate(tree['prompt']['replies']):n['rank']=5-i
    first=module.extract(tree,source,projection(tree),'d'*64)
    tree['prompt']['replies'].reverse();second=module.extract(tree,source,projection(tree),'d'*64)
    assert [i['lineage'] for i in first[0]]==[i['lineage'] for i in second[0]]
    assert len(first[0])==4 and first[1]['eligible_paths_omitted_by_tree_cap']==2
    assert all(i['validation_results']['dialogue_candidate']['quality_assessment']=='unverified' for i in first[0])


@pytest.mark.parametrize('limit,value',[('max_messages_per_path',2),('max_characters_per_path',16)])
def test_path_limits_keep_only_an_actual_complete_prefix_without_message_truncation(monkeypatch,limit,value):
    tree,source=fixture();a=tree['prompt']['replies'][0]
    a['replies']=[node('u2','prompter','a',[node('a2','assistant','u2')])]
    monkeypatch.setitem(module.POLICY,limit,value)
    items,reasons,_,_=module.extract(tree,source,projection(tree),'d'*64)
    assert items[0]['lineage']==['u','a'] and reasons['path_size_attention']==1
    assert items[0]['messages']==[{'role':'user','content':'Hello u'},{'role':'assistant','content':'Hello a'}]


@pytest.mark.parametrize('defect',['projection','duplicate','role','parent'])
def test_raw_identity_defects_abort_including_on_ineligible_branches(defect):
    tree,source=fixture();proof=projection(tree);tree['prompt']['lang']='es'
    if defect=='projection':proof['messages']+=1
    elif defect=='duplicate':tree['prompt']['replies']*=2
    elif defect=='role':tree['prompt']['replies'][0]['role']='prompter'
    else:tree['prompt']['replies'][0]['parent_id']='missing'
    with pytest.raises(ValueError):module.extract(tree,source,proof,'d'*64)


def setup_snapshot(tmp_path):
    setup(tmp_path);snapshot=tmp_path/'snapshot';snapshot.mkdir()
    descriptor=json.loads((tmp_path/'source.json').read_text());descriptor['source_id']='OpenAssistant/oasst2'
    for field,name in [('card','card.txt'),('license','license.txt')]:
        (snapshot/name).write_bytes((tmp_path/descriptor['evidence_files'][field]).read_bytes())
        descriptor['evidence_files'][field]=name
    (snapshot/'source.json').write_text(json.dumps(descriptor))
    tree,_=fixture();rows=snapshot/'trees.jsonl';rows.write_text(json.dumps(tree)+'\n')
    acq=dict(source_revision=descriptor['revision'],decoded_sha256=sha(rows),messages=2,trees=1)
    (snapshot/'acquisition.json').write_text(json.dumps(acq))
    cache=tmp_path/'cache';cache.mkdir()
    (cache/'registry.json').write_text(json.dumps(dict(source_id=descriptor['source_id'],revision=descriptor['revision'])))
    (cache/'manifest.json').write_text(json.dumps(dict(version=1,kind='oasst-official-id-projection-v1',files={'registry.json':sha(cache/'registry.json')})))
    mapping=tmp_path/'mapping.json';mapping.write_text(json.dumps({'u':projection(tree)}))
    report=tmp_path/'partitions.json';report.write_text(json.dumps(dict(mapping_path=str(mapping),source_revision=descriptor['revision'],
        cached_projection_manifest_sha256=sha(cache/'manifest.json'),snapshot_sha256=sha(rows),mapping_sha256=sha(mapping),acquisition_sha256=sha(snapshot/'acquisition.json'))))
    return snapshot,report,cache


def test_preparation_binds_full_population_and_stays_sample_only(tmp_path):
    snapshot,report,cache=setup_snapshot(tmp_path)
    result=module.prepare(snapshot,report,cache,tmp_path/'out')
    assert result['candidate_paths']==1 and result['splits']=={'validation':1} and not result['training_eligible']
    with pytest.raises(FileExistsError):module.prepare(snapshot,report,cache,tmp_path/'out')


@pytest.mark.parametrize('defect',['raw_bytes','mapping_bytes','extra_root','message_count'])
def test_changed_or_incomplete_inputs_never_publish(tmp_path,defect):
    snapshot,report,cache=setup_snapshot(tmp_path)
    if defect=='raw_bytes':(snapshot/'trees.jsonl').write_text('{}\n')
    elif defect=='mapping_bytes':(tmp_path/'mapping.json').write_text('{}')
    else:
        if defect=='extra_root':
            p=tmp_path/'mapping.json';data=json.loads(p.read_text());data['extra']=deepcopy(data['u']);p.write_text(json.dumps(data))
            data=json.loads(report.read_text());data['mapping_sha256']=sha(p);report.write_text(json.dumps(data))
        else:
            p=snapshot/'acquisition.json';data=json.loads(p.read_text());data['messages']=3;p.write_text(json.dumps(data))
            data=json.loads(report.read_text());data['acquisition_sha256']=sha(p);report.write_text(json.dumps(data))
    with pytest.raises(ValueError):module.prepare(snapshot,report,cache,tmp_path/'out')
    assert not (tmp_path/'out').exists() and not list(tmp_path.glob('.dialogue-candidates-*'))

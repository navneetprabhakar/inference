# Creator: Navneet Prabhakar
import json
from pathlib import Path
import pytest
from slm.data.conversation_research import read_release
from slm.data.stream_hash import sha

def fixture(tmp_path):
    row=dict(source='smol-contraints',official_split='train',content_category='unreviewed',split_group='one')
    (tmp_path/'train.jsonl').write_text(json.dumps(row)+'\n')
    policy=dict(kind='private-local-conversation-research-v1',authorized_by='Navneet Prabhakar',training_approved=True,human_attestation=False,content_category='unreviewed',cloud_allowed=False,allowed_constituents=['smol-contraints','smol-summarize-20k','smollm-rewrite-30k'],max_physical_passes=2,maximum_new_sft_positions=542538,input_bindings={},train_sha256=sha(tmp_path/'train.jsonl'),train_rows=1)
    return row,policy

def write(tmp_path,row,policy):
    (tmp_path/'train.jsonl').write_text(json.dumps(row)+'\n');policy['train_sha256']=sha(tmp_path/'train.jsonl');(tmp_path/'admission.json').write_text(json.dumps(policy));return sha(tmp_path/'admission.json')

@pytest.mark.parametrize('field,value',[('cloud_allowed',True),('training_approved',False),('content_category','sfw'),('human_attestation',True),('max_physical_passes',3)])
def test_scope_escalation_refused(tmp_path,field,value):
    row,p=fixture(tmp_path);p[field]=value;h=write(tmp_path,row,p)
    with pytest.raises(ValueError):read_release(tmp_path,h)

@pytest.mark.parametrize('field,value',[('official_split','test'),('source','smol-magpie-ultra-short'),('content_category','sfw')])
def test_unadmitted_membership_refused(tmp_path,field,value):
    row,p=fixture(tmp_path);row[field]=value;h=write(tmp_path,row,p)
    with pytest.raises(ValueError):read_release(tmp_path,h)

def test_hash_tamper_refused(tmp_path):
    row,p=fixture(tmp_path);h=write(tmp_path,row,p);assert len(read_release(tmp_path,h)[0])==1
    (tmp_path/'train.jsonl').write_text('{}\n')
    with pytest.raises(ValueError):read_release(tmp_path,h)

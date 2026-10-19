"""No clipped language check or accidental approval of protected prose."""
# Creator: Navneet Prabhakar
from copy import deepcopy
import json
from slm.data import prose_intake_quality as mod
from slm.data.evaluation_exclusions import compile_inventory,EvaluationExclusions
from slm.data.tokenized import sha


REQUEST='Remember the purple cup and return only its color.'


def setup(tmp_path,monkeypatch,foreign=False):
    p=tmp_path/'inventory.json';p.write_text(json.dumps(compile_inventory([dict(kind='request',text=REQUEST,origin='fixture')],{'fixture':'0'*64})))
    guard=EvaluationExclusions(p,sha(p))
    def fake(binary,model,inp,out,limits):
        data=inp.read_text();assert '</s>' not in data
        lines=['__label__en 0.99 __label__es 0.01']*len(data.splitlines())
        if foreign:lines[-1]='__label__es 0.99 __label__en 0.01'
        out.write_text('\n'.join(lines)+'\n')
    monkeypatch.setattr(mod,'predict',fake)
    return guard,dict(binary='unused',model='unused'),dict(id='doc1',text=' '.join('word'+str(i) for i in range(300)),language='en',language_score=.99)


def test_original_payload_full_windows_and_eos_projection(tmp_path,monkeypatch):
    g,d,r=setup(tmp_path,monkeypatch);r['text']+=' </s> additional English text.';before=deepcopy(r)
    out=mod.assess([r],g,d,tmp_path,{},{});assert out[0]['decision']['candidate'] and len(out[0]['windows'])>1
    assert r==before and not out[0]['decision']['training_approved']


def test_foreign_tail_and_protected_request_fail(tmp_path,monkeypatch):
    g,d,r=setup(tmp_path,monkeypatch,True)
    assert 'window_english_signal' in mod.assess([r],g,d,tmp_path,{},{})[0]['decision']['reasons']
    r['text']+=' '+REQUEST
    assert mod.assess([r],g,d,tmp_path,{},{})[0]['isolation']['blocked']


def test_known_nonapproval_and_heldout_are_preserved(tmp_path,monkeypatch):
    g,d,r=setup(tmp_path,monkeypatch);group='HuggingFaceFW/fineweb-edu:doc1'
    out=mod.assess([r],g,d,tmp_path,{group:'defer'},{group:'test'})[0]
    assert not out['decision']['candidate'] and 'prior_direct_defer' in out['decision']['reasons']
    assert out['decision']['original_frozen_partition']=='test'


def test_oversized_original_is_rejected_not_truncated(tmp_path,monkeypatch):
    g,d,r=setup(tmp_path,monkeypatch);r['text']='x'*200001;before=r['text']
    out=mod.assess([r],g,d,tmp_path,{},{})[0]
    assert not out['decision']['candidate'] and not out['windows'] and r['text']==before

"""CPU regression for copy SFT loss, base transfer, conditional scoring and budget recovery."""
from copy import deepcopy
import json
from pathlib import Path
import random
import tempfile
import time
from unittest.mock import patch

import torch
from torch.nn import functional as F

import checkpoint
from copy_chat_curriculum import final_answer_row
from copy_gpt import CopyGPT2
import fit_copy_chat as fit
from fit_working import chat_row
from gpt2 import Config,GPT2
from guards import ResourceStop
from local_chat import encode_frame
from tokenizer import EOT,load


def model_checks():
    torch.manual_seed(35)
    cfg=Config(vocabulary=37,width=12,heads=3,depth=1,context=16)
    trunk=GPT2(cfg)
    aliases=list(range(37))
    aliases[5],aliases[9]=9,5
    model=CopyGPT2(cfg,copy_width=6,aliases=aliases)
    before={k:v.detach().clone() for k,v in model.state_dict().items() if k in fit.COPY_KEYS}
    fit.load_trunk(model,trunk.state_dict())
    assert all(torch.equal(v,model.state_dict()[k]) for k,v in trunk.state_dict().items())
    assert all(torch.equal(v,model.state_dict()[k]) for k,v in before.items()) and len(before)==6
    try:
        fit.load_trunk(model,{k:v for k,v in trunk.state_dict().items() if k!="positions.weight"})
    except ValueError:
        pass
    else:
        raise AssertionError("incomplete trunk accepted")
    x=torch.tensor([[1,5,7,9,2],[1,5,7,4,2],[2,9,7,4,3],[2,9,7,9,2],
                    [1,4,8,3,0],[1,4,8,9,2],[2,8,4,2,0],[2,8,4,3,0]])
    y=torch.tensor([[-100,-100,9,2,3],[-100,-100,4,2,-100],[-100,-100,4,3,2],[-100,-100,9,2,-100],
                    [-100,-100,3,2,-100],[-100,-100,9,3,2],[-100,-100,2,4,-100],[-100,-100,3,4,-100]])
    ref=deepcopy(model)
    full=ref(x)
    row_scores=[full[i][y[i]!=-100].gather(1,y[i][y[i]!=-100,None])[:,0] for i in range(len(x))]
    ce=-torch.cat(row_scores).mean()
    ce_fit,_=fit.objective(model,x,y,False)
    torch.testing.assert_close(ce_fit,ce)
    positive=-torch.cat(row_scores[::2]).mean()
    means=torch.stack([r.mean() for r in row_scores])
    gap=means[::2]-means[1::2]
    expected=positive+F.softplus(.5-gap).mean()
    trained,details=fit.objective(model,x,y,True)
    torch.testing.assert_close(trained,expected)
    torch.testing.assert_close(details["ce"],positive.detach())
    torch.testing.assert_close(details["gap"],gap.mean().detach())
    trained.backward()
    expected.backward()
    for (name,p),(_,q) in zip(model.named_parameters(),ref.named_parameters()):
        torch.testing.assert_close(p.grad,q.grad,rtol=2e-4,atol=2e-6)
        if name in fit.COPY_KEYS:assert p.grad.abs().sum()>0 and torch.isfinite(p.grad).all()
    return dict(masked_nll_dense_parity=True,paired_margin_dense_gradient_parity=True,six_copy_tensors_fresh=True)


def masking(tok):
    h=[dict(role="user",text="Rina packed a blue box."),dict(role="assistant",text="I heard that."),
       dict(role="user",text="Which color?"),dict(role="assistant",text="Blue.")]
    x,y=final_answer_row(tok,h,"Blue.")
    _,yf=final_answer_row(tok,h,"Red.")
    standard_x,standard_y=chat_row(tok,h)
    assert x==standard_x and sum(v!=-100 for v in standard_y)>sum(v!=-100 for v in y)
    _,correct=encode_frame(tok,"assistant",{"text":"Blue."})
    _,foil=encode_frame(tok,"assistant",{"text":"Red."})
    assert [t for t in y if t!=-100]==correct and [t for t in yf if t!=-100]==foil
    return True


class FakeGuard:
    def __init__(self,path):
        self.path=path
        self.wall_start=time.time()
        self.start=time.monotonic()

    def check(self,force=False):
        pass


class ScriptModel(torch.nn.Module):
    def __init__(self,outputs):
        super().__init__()
        self.marker=torch.nn.Parameter(torch.zeros(()))
        self.outputs=iter(outputs)
        self.inputs=0

    def next_logits(self,x):
        self.inputs+=x.numel()
        logits=torch.full((1,50257),-50.)
        logits[0,next(self.outputs)]=50
        return logits


def budget_probe(tok,root):
    guard=FakeGuard(root)
    ledger=fit.Ledger(guard)
    rng=random.Random(9)
    ledger.reserve(40,update=True)
    old=dict(ledger.status)
    checkpoint.save(root,dict(identity="tiny",step=0,status=old,rng=rng.getstate()))
    ledger.reserve(56,update=True)
    rng.random()
    prior=json.loads((root/"status.json").read_text())
    restored=fit.Ledger(guard,prior)
    saved=checkpoint.load(root,"tiny")
    restored.restore(saved)
    assert restored.reserved==96 and restored.reserved_steps==2 and restored.status["step"]==0
    replay=random.Random()
    replay.setstate(saved["rng"])
    assert replay.random()==random.Random(9).random()
    with patch.object(fit,"INPUT_CAP",100):
        try:restored.reserve(5)
        except ResourceStop:pass
        else:raise AssertionError("reserved inputs exceeded cap on resume")
    with patch.object(fit,"ACTIVE_CAP",0):
        try:restored.check()
        except ResourceStop:pass
        else:raise AssertionError("active cap ignored")
    pair=dict(family="fixture",form=0,pair=0,members=[])
    outputs=[]
    for color,reply in [("Teal","Teal"),("Green","Teal")]:
        h=[dict(role="user",text=f"My ribbon is {color}."),dict(role="assistant",text="Okay."),
           dict(role="user",text="What color?"),dict(role="assistant",text=color)]
        pair["members"].append(h)
        ids=fit.probe_prefix(tok,h)
        assert "Okay." in tok.decode(ids) and tok.decode(ids).endswith("Assistant:")
        outputs.extend(encode_frame(tok,"assistant",{"text":reply})[1])
    model=ScriptModel(outputs)
    checkpoint.save(root,dict(identity="tiny",step=17,model=model.state_dict()))
    before=restored.reserved
    hits,total=fit.conditional_probe(model,tok,[pair],restored,17)
    observed=json.loads((root/"conditional-000017.json").read_text())
    assert (hits,total)==(0,1) and observed["members_correct"]==1
    assert model.inputs==restored.reserved-before and restored.reserved<=fit.INPUT_CAP
    # A recovered completed probe reuses both members without more inference.
    fit.conditional_probe(model,tok,[pair],restored,17)
    assert model.inputs==restored.reserved-before
    return dict(replayed_reservations=True,conditional_member_accuracy="1/2",conditional_pair_accuracy="0/1",
                model_probe_inputs_charged=model.inputs,active_and_input_caps_enforced=True)


if __name__=="__main__":
    torch.set_num_threads(1)
    tok=load()
    result=model_checks()
    result["all_prior_frames_masked_for_contrast"]=masking(tok)
    with tempfile.TemporaryDirectory() as path:
        result.update(budget_probe(tok,Path(path)))
    with torch.device("meta"):
        full=CopyGPT2()
    result["full_parameters"]=sum(p.numel() for p in full.parameters())
    assert result["full_parameters"]==fit.CONFIG["output_parameters"]
    print(json.dumps(dict(state="passed",device="cpu",**result),indent=2))

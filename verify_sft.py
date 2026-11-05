"""Bounded CPU-only smoke of actual SFT data, update, optimizer checkpoint and inference."""
from dataclasses import asdict
import json
from pathlib import Path
import tempfile

import torch

import checkpoint
from types import SimpleNamespace
from dialogue import assistant_prompt
from evaluate import run_case, greedy
from evaluate_sft import DEVELOPMENT
from gpt2 import Config, GPT2
from prepare_sft import DEST
from sft import frozen_budget, load_teaching, schedule, update
from tokenizer import EOT, load
from train import optimizer_for


def main():
    torch.set_num_threads(1)
    spec=frozen_budget()
    tokenizer=load()
    rows=load_teaching(tokenizer,spec)
    batches=schedule(rows,spec)
    assert len(batches)==74 and batches==schedule(rows,spec)
    assert sorted(i for b in batches[:37] for i in b)==list(range(289))
    assert sorted(i for b in batches[37:] for i in b)==list(range(289))
    torch.manual_seed(spec["seed"])
    config=Config(width=12,heads=3,depth=1)
    model=GPT2(config)
    opt=optimizer_for(model)
    params_before=model.tokens.weight.detach().clone()
    chosen=[0,1,145]
    checks=[]
    metrics=update(model,opt,rows,chosen,0,len(batches),spec,lambda:checks.append(1))
    assert len(checks)==3 and metrics["train_ce"]>0 and metrics["gradient_norm"]>0
    assert not torch.equal(params_before,model.tokens.weight)
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)
        state=dict(identity={"purpose":"cpu-unit","config":asdict(config)},step=1,
                   model=model.state_dict(),optimizer=opt.state_dict(),cpu_rng=torch.get_rng_state())
        checkpoint.save(path,state)
        restored=checkpoint.load(path,state["identity"])
        replica=GPT2(config)
        replica.load_state_dict(restored["model"])
        replica_opt=optimizer_for(replica)
        replica_opt.load_state_dict(restored["optimizer"])
        update(model,opt,rows,chosen,1,len(batches),spec,lambda:None)
        update(replica,replica_opt,rows,chosen,1,len(batches),spec,lambda:None)
        assert all(torch.equal(a,b) for a,b in zip(model.parameters(),replica.parameters()))
    prefix=assistant_prompt(tokenizer,[{"role":"user","text":"Give only the item."}],reply_budget=2)
    generated=greedy(model,prefix,2,SimpleNamespace(check=lambda:None))
    assert 1<=len(generated)<=2
    def frame(body):
        return tokenizer.encode(json.dumps(body,separators=(",",":"))).ids+[EOT]
    cases={r["id"]:r for line in DEVELOPMENT.open() if (r:=json.loads(line))}
    def canned(case_id,responses):
        return run_case(cases[case_id],lambda prefix,budget:frame(next(responses)),tokenizer)
    correct={"op":"subtract","a":84,"b":39}
    call={"call":{"name":"calculate","arguments":correct}}
    out=canned("d09",iter([call,{"text":"44"},{"text":"44"}]))
    assert out["protocol_pass"] and len(out["turns"])==2
    assert out["trace"][0]["data"]["result"]==44 and out["trace"][0]["call_id"]=="c1"
    wrong={"call":{"name":"calculate","arguments":{"op":"subtract","a":80,"b":39}}}
    out=canned("d09",iter([wrong,{"text":"41"},{"text":"41"}]))
    assert out["trace"][0]["data"]["result"]==41
    outage={"call":{"name":"calculate","arguments":{"op":"subtract","a":58,"b":47}}}
    out=canned("d10",iter([outage,{"text":"Unavailable."},{"text":"No."}]))
    assert not out["trace"][0]["ok"]
    out=run_case(cases["d01"],lambda prefix,budget:[],tokenizer)
    assert not out["protocol_pass"] and len(out["turns"])==2
    evidence={"state":"passed","scope":"CPU smoke","updates_on_tiny_model":2,
              "checkpoint_resume_equal":True,"toy_generated_ids":generated,"smoke_metrics":metrics,
              "corpus_sha256":checkpoint.checksum(DEST),"training_rows":len(rows),"planned_updates":len(batches),
              "inputs_over_two_passes":spec["input_cap"],"assistant_targets_over_two_passes":spec["target_cap"],
              "offline_fixture_controls":["actual correlated counterfactual","wrong-call fallback","tool outage","malformed generation"]}
    print(json.dumps(evidence,indent=2))


if __name__=="__main__":
    main()

"""CPU-only proof of continuation initialization. Stop at step zero before optimizer work."""
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import tempfile
import time
from unittest.mock import patch

import numpy as np
import torch

from gpt2 import Config
from guards import ResourceStop
import checkpoint
import pretrain
import pretrained_base as lineage
from tokenizer import ASSETS


def reject(operation, message):
    try:
        operation()
    except ValueError as error:
        if message not in str(error):
            raise AssertionError(f"Unexpected rejection: {error}") from error
    else:
        raise AssertionError(f"Accepted invalid lineage: {message}")


class CPUGuard:
    def __init__(self, path):
        self.path = path
        path.mkdir()
        self.start = time.monotonic()
        self.wall_start = time.time()

    def check(self, force=False):
        pass


def fixture_budget(directory, parent):
    corpus = directory / "corpus"
    corpus.mkdir()
    shards = {}
    for name, size in (("fixture-train", pretrain.TOKENS_PER_STEP + 1), ("fixture-validation", pretrain.LENGTH + 1)):
        file = corpus / (name + ".u16")
        np.arange(size, dtype="<u2").tofile(file)
        shards[name] = dict(tokens=size, sha256=checkpoint.checksum(file))
    manifest = corpus / "manifest.json"
    manifest.write_text(json.dumps(dict(shards=shards)))
    return dict(budget_name="continuation-step-zero-cpu", parent_checkpoint=parent, corpus=str(corpus),
                manifest_sha256=checkpoint.checksum(manifest), target_tokens=pretrain.TOKENS_PER_STEP,
                active_seconds=300, elapsed_seconds=300, seed=803, mix={"fixture":pretrain.MICROBATCHES},
                primary="fixture", minimum_ce_improvement=.01, material_ce_regression=.1, warmup_steps=1,
                validation_rows_per_source=1)


def negative_lineage_checks(directory):
    """Corrupt one property at a time while keeping each fixture file's own digest valid."""
    root = directory / "stand-in"
    root.mkdir()
    identity = dict(model=asdict(Config()), tokenizer=ASSETS, spec={"target_tokens":4096}, dtype="fp32")
    status = dict(stage="extended pretraining", state="passed", step=1, target_tokens=4096)
    payload = dict(identity=identity, step=1, target_tokens=4096, terminal={"state":"passed"}, protected=True,
                   model={"example":torch.ones(1)})
    base = root / "fixture.pt"

    def write(data=payload, config=identity, run=status, pins=True):
        torch.save(data, base)
        (root / "config.json").write_text(json.dumps(config))
        (root / "status.json").write_text(json.dumps(run))
        (root / "protected.json").write_text(json.dumps([base.name] if pins else []))
        return checkpoint.checksum(base)

    terminal = dict(step=1, target_tokens=4096)
    variants = [
        (dict(pins=False), "protected by a passing"),
        (dict(run=dict(status,state="failed")), "protected by a passing"),
        (dict(config=dict(identity,dtype="bf16")), "lineage differs"),
        (dict(data=dict(payload,terminal=None)), "passing terminal checkpoint"),
        (dict(data=dict(payload,terminal={"state":"failed"})), "passing terminal checkpoint"),
        (dict(data=dict(payload,protected=False)), "passing terminal checkpoint"),
        (dict(data=dict(payload,step=2)), "passing terminal checkpoint"),
        (dict(data=dict(payload,target_tokens=512)), "passing terminal checkpoint"),
    ]
    for key,value,message in [("model",dict(asdict(Config()),width=24),"124M architecture"),
                              ("tokenizer",dict(ASSETS, extra="unknown"),"tokenizer mismatch"),
                              ("dtype","bf16","passing terminal checkpoint")]:
        changed=dict(identity, **{key:value})
        variants.append((dict(config=changed,data=dict(payload,identity=changed)),message))
    for edits,message in variants:
        sha=write(**edits)
        reject(lambda: lineage.load_base(base,sha,terminal=terminal),message)

    sha=write()
    reject(lambda: lineage.load_base(base,"0"*64,terminal=terminal),"hash mismatch")
    link=root/"link.pt"
    link.symlink_to(base)
    reject(lambda: lineage.load_base(link,sha,terminal=terminal),"hash mismatch")
    return len(variants)+2


def check():
    torch.set_num_threads(1)
    receipt=json.loads(lineage.PRE_SFT_REPORT.read_text())
    parent_file=lineage.PRE_SFT_RUN/receipt["base"]["file"]
    supplied=dict(path=str(parent_file),sha256=receipt["base"]["sha256"])
    proof={}
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp)
        spec=fixture_budget(root,supplied)
        used=lineage.continuation_parent(spec,Config())
        assert used["step"]==receipt["state"]["step"]
        blank=deepcopy(spec)
        blank["budget_name"]=" "
        reject(lambda: lineage.continuation_parent(blank,Config()),"named fresh budget")
        wrong=deepcopy(spec)
        wrong["parent_checkpoint"]["sha256"]="a"*64
        reject(lambda: lineage.continuation_parent(wrong,Config()),"exact reported local")
        wrong["parent_checkpoint"]=dict(supplied,path=str(root/"external.pt"))
        reject(lambda: lineage.continuation_parent(wrong,Config()),"exact reported local")
        reject(lambda: lineage.continuation_parent(spec,Config(width=24)),"GPT-2 small")

        # Read the original protected tensor map independently of the transfer loader.
        expected=torch.load(parent_file,map_location="cpu",mmap=True,weights_only=True)
        assert expected["optimizer"]["state"] and expected["step"]==used["step"]
        guard=CPUGuard(root/"child")
        initial_payload={}
        def stop_before_update(path, state):
            assert path==guard.path and state["step"]==state["target_tokens"]==state["reserved_target_tokens"]==0
            assert state["input_tokens"]==0 and state["offsets"]=={"fixture":0} and not state["optimizer"]["state"]
            assert state["identity"]["initialization"]["parent"]==used
            assert state["model"].keys()==expected["model"].keys()
            assert all(t.dtype==expected["model"][name].dtype and torch.equal(t,expected["model"][name])
                       for name,t in state["model"].items())
            initial_payload.update(state)
            proof.update(parent_sha256=used["sha256"],parent_step=used["step"],parent_target_tokens=used["target_tokens"],
                         checkpoint_payload_tensors=len(state["model"]), equal_parameters=sum(t.numel() for t in state["model"].values()),
                         child_step=0, child_target_tokens=0, child_optimizer_states=len(state["optimizer"]["state"]))
            raise ResourceStop("CPU proof reached step zero")
        with ExitStack() as mocks:
            mocks.enter_context(patch.object(pretrain,"evaluate", return_value={"validation":{"fixture":1.0}}))
            mocks.enter_context(patch.object(checkpoint,"save",side_effect=stop_before_update))
            mocks.enter_context(patch.object(pretrain,"backward_rows",side_effect=AssertionError("unexpected optimizer work")))
            assert not pretrain.candidate(guard,spec,Config(),"cpu",None)
        status=json.loads((guard.path/"status.json").read_text())
        assert status["state"]=="stopped" and status["reason"]=="CPU proof reached step zero"
        assert proof["equal_parameters"]==124_439_808
        del expected
        # Simulate an already-completed optimizer boundary in the child. A marker
        # weight and LR establish which state the resume path actually restores.
        own = dict(initial_payload, step=1, offsets={"fixture":pretrain.TOKENS_PER_STEP},
                   input_tokens=pretrain.TOKENS_PER_STEP, target_tokens=pretrain.TOKENS_PER_STEP,
                   reserved_target_tokens=pretrain.TOKENS_PER_STEP, protected=False)
        own["model"] = dict(initial_payload["model"])
        marker = "final_norm.bias"
        own["model"][marker] = own["model"][marker].clone() + 0.5
        own["optimizer"] = deepcopy(initial_payload["optimizer"])
        own["optimizer"]["param_groups"][0]["lr"] = 0.000123
        previous = dict(status, state="running", reserved_target_tokens=pretrain.TOKENS_PER_STEP)
        def stop_at_resumed_capture(path, state):
            assert torch.equal(state["model"][marker],own["model"][marker])
            assert state["optimizer"]["param_groups"][0]["lr"]==0.000123
            assert state["step"]==1 and state["offsets"]==own["offsets"]
            proof["restored_child_weights_optimizer_and_cursor"]=True
            raise ResourceStop("CPU proof restored its own child checkpoint")
        with ExitStack() as mocks:
            mocks.enter_context(patch.object(checkpoint,"load",return_value=own))
            mocks.enter_context(patch.object(pretrain,"load_base",side_effect=AssertionError("parent reloaded on resume")))
            mocks.enter_context(patch.object(pretrain,"evaluate",return_value={"validation":{"fixture":0.5}}))
            mocks.enter_context(patch.object(checkpoint,"save",side_effect=stop_at_resumed_capture))
            mocks.enter_context(patch.object(pretrain,"backward_rows",side_effect=AssertionError("unexpected optimizer work")))
            assert not pretrain.candidate(guard,spec,Config(),"cpu",previous)
        assert proof["restored_child_weights_optimizer_and_cursor"]
        proof["negative_lineage_cases"]=negative_lineage_checks(root)+4
        del own,initial_payload
        random_spec={k:v for k,v in spec.items() if k not in {"parent_checkpoint","budget_name"}}
        small=Config(width=4,heads=1,depth=1,context=256)
        def random_checkpoint(path,state):
            assert "initialization" not in state["identity"] and state["step"]==0
            assert state["identity"]["model"]==asdict(small) and not state["optimizer"]["state"]
            proof["random_start_without_parent"]=True
            raise ResourceStop("CPU random-initialization fixture reached step zero")
        with ExitStack() as mocks:
            mocks.enter_context(patch.object(pretrain,"load_base",side_effect=AssertionError("parent used for random run")))
            mocks.enter_context(patch.object(pretrain,"evaluate",return_value={"validation":{"fixture":1.0}}))
            mocks.enter_context(patch.object(checkpoint,"save",side_effect=random_checkpoint))
            mocks.enter_context(patch.object(pretrain,"backward_rows",side_effect=AssertionError("unexpected optimizer work")))
            assert not pretrain.candidate(CPUGuard(root/"random"),random_spec,small,"cpu",None)
        assert proof["random_start_without_parent"]
    print(json.dumps(dict(state="passed",device="cpu",**proof),indent=2))


if __name__=="__main__":
    check()

"""CPU regression for an optimizer-boundary resume after process exit and partial write."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import torch

import checkpoint
from guards import Guard, ResourceStop
from gpt2 import Config, GPT2, next_token_loss


def worker(stage, root):
    torch.set_num_threads(1)
    torch.manual_seed(512)
    model = GPT2(Config(vocabulary=32, width=12, heads=3, depth=1))
    opt = torch.optim.AdamW(model.parameters(),lr=.001)
    step = 0
    tokens = 0
    if stage == "resume":
        state = checkpoint.load(root, "resume-fixture")
        model.load_state_dict(state["model"])
        opt.load_state_dict(state["optimizer"])
        torch.set_rng_state(state["rng"])
        step, tokens = state["step"], state["tokens"]
    for _ in range(step,1 if stage == "interrupt" else 2):
        ids = torch.randint(0,32,(2,7))
        step += 1
        tokens += 12
        opt.param_groups[0]["lr"] = .001/step
        opt.zero_grad()
        next_token_loss(model,ids).backward()
        opt.step()
    checkpoint.save(root, dict(identity="resume-fixture", step=step, tokens=tokens,
                                model=model.state_dict(), optimizer=opt.state_dict(),
                                rng=torch.get_rng_state(), ids=ids))
    if stage == "interrupt":
        (root/"step-000002.tmp").write_bytes(b"incomplete")
        (root/"latest.tmp").write_text("incomplete")
        import os
        os._exit(17)


def check_retention(root):
    root.mkdir()
    state = dict(identity="rotation", step=1, model={"weight": torch.tensor([1.0])})
    checkpoint.save(root, state)
    pin = checkpoint.protect(root)
    for step in (2, 3):
        state["step"] = step
        checkpoint.save(root, state)
    assert (root / pin["file"]).exists()
    inventory = json.loads((root / "latest.json").read_text())
    assert len(inventory) == 2 and all((root / entry["file"]).exists() for entry in inventory)
    original = checkpoint.load(root, "rotation")
    # A process fails after writing changed bytes for the same optimizer step.
    state["model"] = {"weight": torch.tensor([9.0])}
    with patch.object(checkpoint, "_atomic_json", side_effect=OSError("interrupted publication")):
        try:
            checkpoint.save(root, state)
        except OSError:
            pass
        else:
            raise AssertionError("simulated interrupted publication completed")
    restored = checkpoint.load(root, "rotation")
    assert torch.equal(original["model"]["weight"], restored["model"]["weight"])
    file = root / inventory[0]["file"]
    # Avoid truncating a memory mapping while it is still held.
    del original, restored
    file.write_bytes(b"damaged")
    try:
        checkpoint.load(root, "rotation")
    except ValueError as error:
        assert "checksum" in str(error)
    else:
        raise AssertionError("corrupt current checkpoint accepted")


def check_guard(root):
    # Mock only host telemetry. The OS lock, STOP file, deadline and run state are real.
    with patch("guards.thermal", return_value=0), patch("guards.swap_mib", return_value=10), \
            patch("guards.torch.mps.current_allocated_memory", return_value=0):
        guard = Guard(root, 10)
        try:
            try:
                Guard(root.parent / "conflicting-run", 10)
            except BlockingIOError:
                pass
            else:
                raise AssertionError("exclusive resource lock ignored")
        finally:
            guard.close()
        resumed = Guard(root, 10, resume=True)
        assert resumed.wall_start == guard.wall_start
        (root / "STOP").touch()
        try:
            resumed.check()
        except ResourceStop as error:
            assert "STOP" in str(error)
        else:
            raise AssertionError("explicit STOP ignored")
        finally:
            resumed.close()
        (root / "STOP").unlink()
        with patch("guards.time.time", return_value=guard.wall_start + 11):
            try:
                Guard(root, 10, resume=True)
            except ResourceStop as error:
                assert "elapsed cap" in str(error)
            else:
                raise AssertionError("elapsed budget reset on resume")


def check():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        full, resumed = root/"full",root/"resumed"
        full.mkdir()
        resumed.mkdir()
        for mode, path, expected in [("full",full,0),("interrupt",resumed,17),("resume",resumed,0)]:
            proc = subprocess.run([sys.executable,__file__,mode,str(path)])
            assert proc.returncode == expected
        a,b = [checkpoint.load(p,"resume-fixture") for p in (full,resumed)]
        for k in ("ids","rng"):
            assert torch.equal(a[k],b[k])
        assert (a["step"],a["tokens"]) == (b["step"],b["tokens"]) == (2,24)
        assert all(torch.equal(v,b["model"][k]) for k,v in a["model"].items())
        assert a["optimizer"]["param_groups"] == b["optimizer"]["param_groups"]
        for i, tensors in a["optimizer"]["state"].items():
            assert all(torch.equal(t,b["optimizer"]["state"][i][key]) for key,t in tensors.items())
        check_retention(root/"retention")
        check_guard(root/"guard")
        print(json.dumps(dict(state="passed", device="cpu", steps=2, targets=24, bit_identical=True,
                              protected_retention=True, interrupted_same_step_safe=True,
                              corrupt_checkpoint_rejected=True, guard_resume_deadline=True)))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        worker(sys.argv[1],Path(sys.argv[2]))
    else:
        check()

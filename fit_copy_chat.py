"""One bounded MPS copy-model SFT run from a passing protected pretraining endpoint."""
import argparse
from dataclasses import asdict
import json
import math
import os
from pathlib import Path
import random
import shutil
import time

import torch
from torch.nn import functional as F

import checkpoint
from copy_chat_curriculum import ROOT, SEED, history_hash, prepare
from copy_gpt import CopyGPT2
from dialogue import parse_assistant
from fit_working import pack
from gpt2 import Config
from guards import Guard, ResourceStop
from local_chat import encode_frame
from pretrain import atomic_status
from pretrained_base import load_base
from tokenizer import ASSETS, EOT, load
from train import optimizer_for

STEPCAP=5500
BATCH=8
INPUT_CAP=7_500_000
ACTIVE_CAP=150*60
ELAPSED_CAP=180*60
PROBE_CAP=96
LR=.00012
MARGIN=.5
COPY_KEYS={"copy_query.weight","copy_key.weight","copy_gate.weight","copy_gate.bias",
           "copy_surface.weight","copy_surface.bias"}
CONFIG=dict(steps=STEPCAP,batch=BATCH,model_input_cap=INPUT_CAP,active_seconds=ACTIVE_CAP,elapsed_seconds=ELAPSED_CAP,
            seed=SEED,peak_lr=LR,contrast_every=5,margin_nats=MARGIN,rank_weight=1.,clip_norm=1.,
            probe_cap=PROBE_CAP,intermediate_probes=[1375,2750],copy_width=64,precision="fp32",
            output_parameters=124539650,checkpoint_steps=250,checkpoint_seconds=300,
            endpoint_time_reserve_seconds=180)
CODE=("fit_copy_chat.py","copy_chat_curriculum.py","copy_gpt.py","gpt2.py","fit_working.py","followon_curriculum.py",
      "compositional_teaching.py","chat_teaching.py","tool_teaching.py","tool_teaching_varied.py","broad_teaching.py",
      "scaled_teaching.py","squad_teaching.py","quac_teaching.py","taskmaster_teaching.py","no_robots_teaching.py",
      "checkpoint.py","guards.py","pretrain.py","pretrained_base.py","train.py","local_chat.py","dialogue.py","tokenizer.py")


def objective(model,x,y,contrast=False):
    scores,_,rows=model.supervised(x,y)
    if not contrast:
        ce=-scores.mean()
        return ce,dict(ce=ce.detach(),rank=None,gap=None)
    if len(x)%4:
        raise ValueError("contrast batches contain both paired contexts and both endings")
    counts=(y!=-100).sum(1)
    if bool((counts==0).any()):
        raise ValueError("contrast row lacks a final answer")
    totals=scores.new_zeros(len(x)).scatter_add(0,rows,scores)
    means=totals/counts
    gaps=means[::2]-means[1::2]
    ce=-totals[::2].sum()/counts[::2].sum()
    ranking=F.softplus(MARGIN-gaps).mean()
    return ce+ranking,dict(ce=ce.detach(),rank=ranking.detach(),gap=gaps.detach().mean())


def load_trunk(model,state):
    if set(state) & COPY_KEYS:
        raise ValueError("base already includes trainable copy parameters")
    result=model.load_state_dict(state,strict=False)
    if set(result.missing_keys)!=COPY_KEYS or result.unexpected_keys:
        raise ValueError(f"incomplete base transfer: {result}")
    if set(model.state_dict())-COPY_KEYS!=set(state):
        raise ValueError("base tensor map differs from GPT-2 trunk")


def parent_entry(directory,expected=None):
    if directory.is_symlink():raise ValueError("base run cannot be a symlink")
    directory=directory.resolve()
    if directory.parent!=(ROOT/"runs").resolve():
        raise ValueError("base must be a local run under runs/")
    status=json.loads((directory/"status.json").read_text())
    if status.get("stage")!="extended pretraining" or status.get("state")!="passed" or status.get("step",0)<=0:
        raise ValueError("base pretraining run has not passed")
    latest=json.loads((directory/"latest.json").read_text())[0]
    sha=latest["sha256"]
    file=directory/f"step-{status['step']:06d}-{sha}.pt"
    if (len(sha)!=64 or latest["file"]!=file.name or file.is_symlink() or file.stat().st_size!=latest["bytes"]
            or file.name not in json.loads((directory/"protected.json").read_text()) or (expected and sha!=expected)):
        raise ValueError("base does not match the protected terminal checkpoint")
    return dict(path=str(file),sha256=sha,step=status["step"],target_tokens=status["target_tokens"])


def choose_batch(rng,pools,weights,pairs,step):
    if step%5==0:
        choices=rng.choices(pairs,k=8)
        choices.sort(key=lambda p:max(len(x) for x,_ in p))
        start=rng.choice((0,2,4,6))
        return "contrast",[row for pair in choices[start:start+2] for row in pair]
    name=rng.choices(list(weights),weights=list(weights.values()))[0]
    choices=rng.choices(pools[name],k=BATCH*4)
    choices.sort(key=lambda row:len(row[0]))
    start=rng.choice(range(0,len(choices),BATCH))
    return name,choices[start:start+BATCH]


def probe_prefix(tok,history):
    ids=[]
    for message in history[:-1]:
        role=message["role"]
        if role=="user":value=message["text"]
        elif role=="assistant":value={"text":message["text"]}
        else:raise ValueError("unexpected role in compositional final-answer probe")
        head,body=encode_frame(tok,role,value)
        ids.extend(head+body)
    ids.extend(tok.encode("Assistant:").ids)
    if not len(ids)+PROBE_CAP<=1024:
        raise ValueError("probe exceeds model context")
    return ids


def verify_inputs(probe,split,info,provision=False):
    if (history_hash(split)!="4612fd3f0010c33a66e0a85416fc5b0401f4131eb5a9cb204ab1d9e8524a87b6"
            or history_hash(probe)!="190c1bdf20f90b076f7abf6405cdf1b0aac0cff2aa4ea944e125247cc4d72f9e"):
        raise ValueError("compositional form or member selection differs from its frozen pin")
    paths=(ROOT/"reports/copy-chat/form-split.json",ROOT/"reports/copy-chat/training-manifest.json",
           ROOT/"data/copy-chat-internal/probe.json")
    for file,value in zip(paths,(split,info,probe)):
        if file==paths[-1] and provision and not file.exists():
            if history_hash(probe)!=split["probe_sha256"]:
                raise ValueError("probe does not match tracked split digest")
            file.parent.mkdir(parents=True,exist_ok=True)
            atomic_status(file,probe)
        if not file.is_file() or history_hash(json.loads(file.read_text()))!=history_hash(value):
            raise ValueError(f"frozen training/probe manifest mismatch: {file}")


class Ledger:
    def __init__(self,guard,previous=None):
        self.guard=guard
        self.path=guard.path
        self.active_before=0.
        self.reserved=0
        self.reserved_steps=0
        self.prior_probe_inputs=0
        self.status=dict(stage="copy chat SFT",state="running",step=0,train_model_inputs=0,
                         nonpadding_train_inputs=0,positive_targets=0,foil_targets=0,probe_model_inputs=0,
                         tasks={},attempt=1)
        if previous:
            gap=max(0,time.time()-previous["timestamp"]) if previous["state"]=="running" else 0.
            self.active_before=previous["active_seconds"]+gap
            self.reserved=previous["reserved_model_inputs"]
            self.reserved_steps=previous["reserved_updates"]
            self.prior_probe_inputs=previous.get("probe_model_inputs",0)
            if not 0<=self.reserved<=INPUT_CAP or not 0<=self.reserved_steps<=STEPCAP:
                raise ValueError("invalid previous reservation watermark")
            self.status=dict(previous,state="running",attempt=previous["attempt"]+1,charged_resume_gap_seconds=gap)
            self.status.pop("reason",None)

    def active(self):
        return self.active_before+time.monotonic()-self.guard.start

    def check(self,force=False):
        self.guard.check(force=force)
        if self.active()>=ACTIVE_CAP:
            raise ResourceStop("active time cap")

    def publish(self):
        self.status.update(timestamp=time.time(),active_seconds=self.active(),
                           elapsed_seconds=time.time()-self.guard.wall_start,reserved_model_inputs=self.reserved,
                           reserved_updates=self.reserved_steps,remaining_model_inputs=INPUT_CAP-self.reserved,
                           remaining_updates=STEPCAP-self.reserved_steps,remaining_active_seconds=max(0,ACTIVE_CAP-self.active()),
                           remaining_elapsed_seconds=max(0,ELAPSED_CAP-(time.time()-self.guard.wall_start)))
        atomic_status(self.path/"status.json",self.status)

    def reserve(self,inputs,update=False):
        self.check()
        if inputs<=0 or self.reserved+inputs>INPUT_CAP or (update and self.reserved_steps>=STEPCAP):
            raise ResourceStop("reserved compute cap exhausted")
        self.reserved+=inputs
        self.reserved_steps+=int(update)
        self.publish()

    def restore(self,saved):
        prior=saved["status"]
        if not (saved["step"]==prior["step"]<=prior["reserved_updates"]<=STEPCAP
                and prior["train_model_inputs"]+prior["probe_model_inputs"]<=prior["reserved_model_inputs"]<=INPUT_CAP):
            raise ValueError("invalid stored SFT counters")
        attempt=self.status["attempt"]
        gap=self.status.get("charged_resume_gap_seconds",0.)
        self.status=dict(prior,attempt=attempt,charged_resume_gap_seconds=gap,state="running")
        self.status["probe_model_inputs"]=max(prior["probe_model_inputs"],self.prior_probe_inputs)
        self.active_before=max(self.active_before,prior["active_seconds"])
        self.reserved=max(self.reserved,prior["reserved_model_inputs"])
        self.reserved_steps=max(self.reserved_steps,prior["reserved_updates"])
        if self.reserved>INPUT_CAP or self.reserved_steps>STEPCAP:
            raise ValueError("invalid reservation watermark")


@torch.inference_mode()
def conditional_probe(model,tok,probe,ledger,step):
    anchors=ledger.status.setdefault("probe_model_checkpoints",{})
    key=str(step)
    if key not in anchors:
        latest=json.loads((ledger.path/"latest.json").read_text())[0]
        if not latest["file"].startswith(f"step-{step:06d}-"):
            raise ValueError("conditional probe requires a verified checkpoint at this optimizer boundary")
        anchors[key]=latest["sha256"]
    path=ledger.path/f"conditional-{step:06d}.json"
    digest=history_hash(probe)
    report=json.loads(path.read_text()) if path.exists() else dict(step=step,probe_sha256=digest,model_checkpoint_sha256=anchors[key],members=[])
    if (report["step"]!=step or report["probe_sha256"]!=digest or report.get("model_checkpoint_sha256")!=anchors[key]
            or len(report["members"])>2*len(probe)):
        raise ValueError("probe resume fingerprint mismatch")
    for i,pair in enumerate(probe):
        for j,history in enumerate(pair["members"]):
            if 2*i+j<len(report["members"]):
                previous=report["members"][2*i+j]
                if (previous["family"],previous["form"],previous["pair"],previous["variant"],previous["expected"])!=(
                        pair["family"],pair["form"],pair["pair"],j,history[-1]["text"]):
                    raise ValueError("incomplete or mismatched conditional probe transcript")
                if previous["correct"]!=(previous["answer"]==previous["expected"]):
                    raise ValueError("conditional probe score differs from transcript")
                continue
            ids=probe_prefix(tok,history)
            generated=[]
            for _ in range(PROBE_CAP):
                ledger.reserve(len(ids)+len(generated))
                row=torch.tensor([ids+generated],device=next(model.parameters()).device)
                token=int(model.next_logits(row)[0].argmax().item())
                ledger.status["probe_model_inputs"]+=row.numel()
                generated.append(token)
                if token==EOT:break
            answer=None
            error=None
            try:
                answer=parse_assistant(tok,generated).get("text")
            except (ValueError,RecursionError) as exc:
                error=str(exc)
            expected=history[-1]["text"]
            report["members"].append(dict(family=pair["family"],form=pair["form"],pair=pair["pair"],variant=j,
                                          raw=tok.decode([n for n in generated if n!=EOT]),ids=generated,
                                          answer=answer,expected=expected,correct=answer==expected,failure=error))
            atomic_status(path,report)
    members=report["members"]
    report.update(scope="Exact final assistant text conditioned on authentic prior gold frames",
                  members_correct=sum(m["correct"] for m in members),member_count=len(members),
                  pairs_correct=sum(a["correct"] and b["correct"] for a,b in zip(members[::2],members[1::2])),
                  pair_count=len(probe))
    atomic_status(path,report)
    ledger.publish()
    return report["pairs_correct"],len(probe)


def probe_reserve(tok,probe):
    return sum(PROBE_CAP*len(probe_prefix(tok,h))+PROBE_CAP*(PROBE_CAP-1)//2
               for pair in probe for h in pair["members"])


def export_weights(path,model):
    state=model.state_dict()
    need=sum(t.numel()*t.element_size() for t in state.values())
    if shutil.disk_usage(path).free < need+20*1024**3:
        raise ResourceStop("insufficient export disk reserve")
    tmp=path/"weights.tmp"
    with tmp.open("wb") as stream:
        torch.save(state,stream)
        stream.flush()
        os.fsync(stream.fileno())
    observed=torch.load(tmp,mmap=True,weights_only=True,map_location="cpu")
    if set(observed)!=set(state) or any(t.shape!=state[k].shape or t.dtype!=state[k].dtype for k,t in observed.items()):
        raise ValueError("invalid final copy-model export")
    del observed
    sha=checkpoint.checksum(tmp)
    os.replace(tmp,path/"weights.pt")
    checkpoint.sync_dir(path)
    return sha


def fit(base_dir,path,resume=False,base_sha=None):
    if path.is_symlink() or path.resolve().parent!=(ROOT/"runs").resolve() or path.resolve()==base_dir.resolve():
        raise ValueError("copy SFT needs a distinct run directory directly under the shared runs/ GPU lock")
    path=path.resolve()
    base=parent_entry(base_dir,base_sha)
    guard=Guard(path,ELAPSED_CAP,resume=resume)
    try:
        previous=json.loads((path/"status.json").read_text()) if resume else None
        if previous and previous["state"] not in ("running","interrupted"):
            raise ValueError("only an interrupted copy SFT run may resume")
        ledger=Ledger(guard,previous)
        return run_locked(base,ledger,resume)
    finally:
        guard.close()


def run_locked(base,ledger,resume):
    path=ledger.path
    verified_identity=False
    try:
        ledger.check(force=True)
        request=dict(spec=CONFIG,base=base,torch=str(torch.__version__),
                     source_sha256={f:checkpoint.checksum(ROOT/f) for f in CODE})
        request_path=path/"request.json"
        if request_path.exists():
            if json.loads(request_path.read_text())!=request:
                raise ValueError("bootstrap request differs from the interrupted run")
        else:
            if resume and (ledger.reserved or (path/"latest.json").exists()):
                raise ValueError("missing original bootstrap request for resumable work")
            atomic_status(request_path,request)
        ledger.publish()
        tok=load()
        pools,weights,pairs,probe,split,info=prepare(tok,ledger.check)
        verify_inputs(probe,split,info)
        identity=dict(spec=CONFIG,base=base,model=asdict(Config()),tokenizer=ASSETS,torch=str(torch.__version__),
                      curriculum=info,source_sha256=request["source_sha256"])
        has_checkpoint=(path/"latest.json").is_file()
        if resume and not has_checkpoint and (ledger.reserved or ledger.reserved_steps or ledger.status["step"]):
            raise ValueError("reserved work exists without a recoverable checkpoint")
        if resume and (path/"config.json").exists():
            if json.loads((path/"config.json").read_text())!=identity:
                raise ValueError("resume would change the frozen copy SFT run")
        else:
            atomic_status(path/"config.json",identity)
        verified_identity=True
        torch.manual_seed(SEED)
        rng=random.Random(SEED)
        model=CopyGPT2()
        if sum(p.numel() for p in model.parameters())!=CONFIG["output_parameters"]:
            raise ValueError("unexpected copy-model parameter count")
        if not has_checkpoint:
            trunk=load_base(Path(base["path"]),base["sha256"],terminal=base)
            load_trunk(model,trunk)
            del trunk
        ledger.check(force=True)
        model.to("mps")
        opt=optimizer_for(model)
        last_save=time.monotonic()
        terminal=None
        terminal_already_saved=False
        def capture():
            nonlocal last_save
            ledger.check(force=True)
            ledger.publish()
            checkpoint.save(path,dict(identity=identity,step=ledger.status["step"],model=model.state_dict(),
                                      optimizer=opt.state_dict(),rng=rng.getstate(),cpu_rng=torch.get_rng_state(),
                                      mps_rng=torch.mps.get_rng_state(),status=dict(ledger.status),terminal=terminal))
            last_save=time.monotonic()
            ledger.check()

        if resume and has_checkpoint:
            saved=checkpoint.load(path,identity)
            model.load_state_dict(saved["model"],strict=True)
            opt.load_state_dict(saved["optimizer"])
            rng.setstate(saved["rng"])
            torch.set_rng_state(saved["cpu_rng"])
            torch.mps.set_rng_state(saved["mps_rng"])
            ledger.restore(saved)
            terminal=saved["terminal"]
            terminal_already_saved=terminal is not None
            del saved
        else:
            capture()
        reserve=probe_reserve(tok,probe)
        model.train()
        while terminal is None:
            ledger.check()
            step=ledger.status["step"]
            if step in CONFIG["intermediate_probes"]:
                model.eval()
                conditional_probe(model,tok,probe,ledger,step)
                model.train()
            if step>=STEPCAP:
                terminal=dict(state="trained",reason="optimizer target reached")
            elif ledger.reserved_steps>=STEPCAP:
                terminal=dict(state="partial",reason="optimizer reservation cap reached")
            elif min(ACTIVE_CAP-ledger.active(),ELAPSED_CAP-(time.time()-ledger.guard.wall_start))<=CONFIG["endpoint_time_reserve_seconds"]:
                terminal=dict(state="partial",reason="time reserved for endpoint evaluation")
            if terminal is not None:break
            task,rows=choose_batch(rng,pools,weights,pairs,step+1)
            count=BATCH*max(len(row[0]) for row in rows)
            if ledger.reserved+count+reserve>INPUT_CAP:
                terminal=dict(state="partial",reason="input cap reached with endpoint probe reserve")
                break
            ledger.reserve(count,update=True)
            x,y=pack(rows)
            if x.numel()!=count or len(rows)!=BATCH:
                raise ValueError("batch accounting mismatch")
            contrast=task=="contrast"
            lr=LR*min(1,(step+1)/50)*(.15+.85*(1+math.cos(math.pi*step/STEPCAP))/2)
            for group in opt.param_groups:group["lr"]=lr
            opt.zero_grad(set_to_none=True)
            loss,details=objective(model,x,y,contrast)
            if not torch.isfinite(loss).item():raise ResourceStop("nonfinite objective")
            loss.backward()
            grad=torch.nn.utils.clip_grad_norm_(model.parameters(),1.,error_if_nonfinite=True)
            opt.step()
            torch.mps.synchronize()
            positive=rows[::2] if contrast else rows
            negative=rows[1::2] if contrast else ()
            st=ledger.status
            st.update(step=step+1,train_model_inputs=st["train_model_inputs"]+count,
                      nonpadding_train_inputs=st["nonpadding_train_inputs"]+sum(len(r[0]) for r in rows),
                      positive_targets=st["positive_targets"]+sum(sum(v!=-100 for v in r[1]) for r in positive),
                      foil_targets=st["foil_targets"]+sum(sum(v!=-100 for v in r[1]) for r in negative),
                      task=task,loss=loss.item(),lr=lr,gradient_norm=grad.item(),
                      **{k:(v.item() if v is not None else None) for k,v in details.items()})
            st["tasks"][task]=st["tasks"].get(task,0)+1
            ledger.publish()
            if st["step"]%25==0:
                with (path/"metrics.jsonl").open("a") as stream:stream.write(json.dumps(st,allow_nan=False)+"\n")
            if (st["step"]%CONFIG["checkpoint_steps"]==0 or st["step"] in CONFIG["intermediate_probes"]
                    or time.monotonic()-last_save>=CONFIG["checkpoint_seconds"]):
                capture()
                if st["step"] in CONFIG["intermediate_probes"]:
                    checkpoint.protect(path)
        if not terminal_already_saved:
            capture()
        checkpoint.protect(path)
        model.eval()
        pair_hits,pair_count=conditional_probe(model,tok,probe,ledger,ledger.status["step"])
        ledger.check(force=True)
        weights_sha=export_weights(path,model)
        ledger.check()
        ledger.status.update(**terminal,weights_sha256=weights_sha,endpoint_pairs_correct=pair_hits,endpoint_pair_count=pair_count)
    except KeyboardInterrupt:
        ledger.status.update(state="interrupted",reason="process interrupt; resume from latest verified boundary")
    except ResourceStop as exc:
        ledger.status.update(state="stopped",reason=str(exc))
    except Exception as exc:
        if resume and not verified_identity:
            atomic_status(path/"resume-refusal.json",dict(error=repr(exc),timestamp=time.time()))
        else:
            ledger.status.update(state="failed",reason=repr(exc))
        raise
    finally:
        if verified_identity or not resume:
            ledger.publish()
    return ledger.status["state"]=="trained"


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_run",type=Path,nargs="?",help="local passing pretraining run containing its protected terminal checkpoint")
    parser.add_argument("run",type=Path,nargs="?",help="fresh run directory, or the interrupted directory with --resume")
    parser.add_argument("--base-sha",help="additional expected terminal checkpoint SHA-256")
    parser.add_argument("--resume",action="store_true")
    parser.add_argument("--inspect",action="store_true",help="Verify or reconstruct the pinned data and forecast token counts on CPU only")
    args=parser.parse_args()
    if args.inspect:
        if args.resume or args.base_run or args.run or args.base_sha:
            parser.error("--inspect takes no run or base")
        torch.set_num_threads(1)
        tok=load()
        pools,weights,pairs,probe,split,info=prepare(tok)
        verify_inputs(probe,split,info,provision=True)
        rng=random.Random(SEED)
        planned=0
        for step in range(1,STEPCAP+1):
            _,rows=choose_batch(rng,pools,weights,pairs,step)
            planned+=BATCH*max(len(x) for x,_ in rows)
        print(json.dumps(dict(physical_training_inputs_at_full_steps=planned,one_probe_worst_inputs=probe_reserve(tok,probe),
                              steps=STEPCAP,input_cap=INPUT_CAP,ce_pool_rows=info["pool_rows"],contrast_pairs=len(pairs),
                              held_forms=sum(len(v) for v in split["held_forms"].values()),probe_pairs=len(probe)),indent=2))
        return
    if args.base_run is None or args.run is None:parser.error("base_run and run are required to fit")
    raise SystemExit(0 if fit(args.base_run,args.run,resume=args.resume,base_sha=args.base_sha) else 1)


if __name__=="__main__":
    main()

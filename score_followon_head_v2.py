"""One paired CPU evaluation using only the previously frozen internal 439 and ordinary negatives."""
from collections import Counter
import json

import torch

from fallback_head import ROOT, load_head, sha
from fit_followon_head_v2 import (PUBLIC,RUN,SPEC,digest,history_sha,negative_pools,split_turns)
from followon_head_v2 import PIN, from_file
from local_chat import NO_CALL
from tool_teaching_varied import internal_records
from tools import FixtureSession


def action(call):
    return "convert" if call["name"]=="convert" else call["arguments"]["op"]


def decide(head,version,user,trace,previous,last_call,phase):
    if version=="v1":
        return None if phase else head.decide(user,trace)
    return head.decide(user,trace,previous,last_call,phase)


def increment(metrics,tag,ok):
    metrics[tag+":n"]+=1
    metrics[tag+":correct"]+=int(ok)


def recorded_dependency(call,trace):
    if not trace or not trace[-1].get("ok"):return False
    observed=trace[-1]["data"]["result"]
    return any(type(v) in (float,int) and v==observed for v in call["arguments"].values())


def clean_event(event):
    return {k:v for k,v in event.items() if k!="timestamp"}


def run_one(head,version,lesson,metrics):
    broker=FixtureSession()
    previous=last_call=gold_last=None
    teacher_trace=[]
    rows=[]
    all_correct=True
    for i,turn in enumerate(split_turns(lesson.history)):
        user,wanted=turn["text"],turn["calls"]
        policy=lesson.policy[i]
        permit=policy["permit_calls"] and not bool(NO_CALL.search(user))
        broker.start_turn(**dict(policy,permit_calls=permit))
        made=[]
        attempts=[]
        offset=len(broker.trace)
        for phase in range(2):
            d=decide(head,version,user,broker.trace,previous,last_call,phase)
            if d is None:break
            attempts.append(dict(action=d.action,proposal=d.proposal))
            if d.proposal is None or not permit:break
            if broker.session_calls>=4 or broker.turn_calls>=2:break
            event=broker.propose(json.dumps(d.proposal),assistant_call_boundary=True)
            last_call=d.proposal
            made.append(d.proposal)
            if not event["ok"]:break
        if wanted:
            increment(metrics,"first_action",attempts[0]["action"]==action(wanted[0]))
            increment(metrics,"first_exact",bool(made) and made[0]==wanted[0])
        else:
            increment(metrics,"no_call",not made)
        increment(metrics,"turn_sequence",made==wanted)
        all_correct &= made==wanted
        metrics["forbidden_executions"]+=len(made) if not permit else 0
        teacher=[]
        for phase,call in enumerate(wanted):
            if recorded_dependency(call,teacher_trace):
                prediction=decide(head,version,user,teacher_trace,previous,gold_last,phase)
                got=prediction.proposal if prediction else None
                ok=got==call
                increment(metrics,"actual_result_followup",ok)
                if teacher_trace[-1]["source"]=="synthetic recorded fixture":
                    increment(metrics,"counterfactual_call_followup",ok)
                teacher.append(dict(required=call,predicted=got,observed=teacher_trace[-1]["data"]["result"],correct=ok))
            record=lesson.observations[len(teacher_trace)]
            teacher_trace.append(record)
            gold_last=call
        if not wanted and teacher_trace and teacher_trace[-1]["ok"]:
            try:
                is_recall=float(turn["answer"])==teacher_trace[-1]["data"]["result"]
            except ValueError:
                is_recall=False
            if is_recall:
                prediction=decide(head,version,user,teacher_trace,previous,gold_last,0)
                ok=prediction.action=="recall_number" and prediction.proposal is None
                increment(metrics,"numeric_recall_action",ok)
                if teacher_trace[-1]["source"]=="synthetic recorded fixture":
                    increment(metrics,"counterfactual_recall_action",ok)
        rows.append(dict(user=user,permit=permit,required=wanted,attempts=attempts,actual_proposals=made,
                         observed=[clean_event(e) for e in broker.trace[offset:]],teacher_conditioned_followups=teacher))
        previous=user
    increment(metrics,"history_sequence",all_correct)
    return dict(history_sha256=history_sha(lesson.history),family=lesson.family,turns=rows)


def fraction(metrics,key):
    return metrics[key+":correct"]/metrics[key+":n"]


def check_protocol(data,spec):
    base,candidate=data["v1"],data["v2"]
    g=spec["evaluation"]["gate"]
    if not all(base[k]==candidate[k] for k in base if k.endswith(":n")):
        raise ValueError("baseline and candidate denominators differ")
    delta=100*(fraction(candidate,"first_exact")-fraction(base,"first_exact"))
    return dict(first_exact_gain=delta>=g["strict_required_first_exact_gain_min_percentage_points"],
                first_action_nonregression=fraction(candidate,"first_action")>=fraction(base,"first_action"),
                actual_result_nonregression=fraction(candidate,"actual_result_followup")>=fraction(base,"actual_result_followup"),
                actual_result_absolute=fraction(candidate,"actual_result_followup")>=g["actual_result_followup_exact_min_fraction"],
                ordinary_absolute=candidate["negative_false_calls"]<=g["ordinary_false_calls_maximum"],
                ordinary_nonregression=candidate["negative_false_calls"]-base["negative_false_calls"]<=g["ordinary_false_calls_increase_max"],
                permission=candidate["forbidden_executions"]==0)


def score():
    torch.set_num_threads(1)
    spec=json.loads(SPEC.read_text())
    fit=json.loads((RUN/"fit.json").read_text())
    assert sha(SPEC)==fit["protocol_sha256"]
    assert sha(PUBLIC/"head-v2-split-amendment.json")==fit["split_amendment_sha256"]
    if (RUN/"paired.json").exists() or PIN.exists():
        raise ValueError("The paired panel has already been scored")
    baseline=load_head()
    assert json.loads((PUBLIC/"head.json").read_text())["sha256"]==spec["baseline_sha256"]
    candidate=from_file(ROOT/fit["weights"],fit["sha256"])
    panel=internal_records(spec["seed"])
    assert len(panel)==439
    assert digest(json.dumps([r.history for r in panel],sort_keys=True,ensure_ascii=False))==spec["evaluation"]["internal_history_digest"]
    train_ids=set(json.loads((RUN/"train-ids.json").read_text()))
    assert not train_ids.intersection(history_sha(r.history) for r in panel)
    _,negatives=negative_pools(spec)
    assert [dict(source=s,sha256=k) for s,k,_ in negatives]==fit["ordinary_negative_ids"]
    assert not train_ids.intersection(k for _,k,_ in negatives)
    results={}
    outputs={}
    for version,head in (("v1",baseline),("v2",candidate)):
        metrics=Counter()
        outputs[version]={"internal":[run_one(head,version,lesson,metrics) for lesson in panel],"ordinary":[]}
        for source,key,history in negatives:
            user=history[0]["text"]
            d=head.decide(user,[])
            dispatched=d.proposal is not None
            if dispatched:
                broker=FixtureSession()
                broker.start_turn(permit_calls=True)
                broker.propose(json.dumps(d.proposal),assistant_call_boundary=True)
            metrics["negative_false_calls"]+=int(dispatched)
            increment(metrics,"negative_text_action",d.action=="text")
            outputs[version]["ordinary"].append(dict(source=source,history_sha256=key,user=user,action=d.action,proposal=d.proposal))
        results[version]=dict(metrics)
    checks=check_protocol(results,spec)
    accepted=all(checks.values())
    report=dict(scope="Internal held-out head only, with actual broker traces; GPT-2 replies excluded",
                protocol_sha256=sha(SPEC), candidate_sha256=fit["sha256"],baseline_sha256=spec["baseline_sha256"],
                internal_histories=len(panel),ordinary_histories=len(negatives), counts=results,
                strict_first_gain_percentage_points=100*(fraction(results["v2"],"first_exact")-fraction(results["v1"],"first_exact")),
                accepted=accepted, checks=checks)
    (RUN/"paired-traces.json").write_text(json.dumps(outputs,indent=2,ensure_ascii=False)+"\n")
    (RUN/"paired.json").write_text(json.dumps(report,indent=2)+"\n")
    (PUBLIC/"head-v2-result.json").write_text(json.dumps(report,indent=2)+"\n")
    if accepted:
        pin={k:fit[k] for k in ("weights","sha256","bytes","parameters","combined_gpt2_head_parameters","protocol_sha256")}
        pin.update(version=2,evidence_sha256=sha(RUN/"paired.json"))
        PIN.write_text(json.dumps(pin,indent=2)+"\n")
    print(json.dumps(report,indent=2))


if __name__=="__main__":
    score()

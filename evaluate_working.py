"""Frozen sequential development evaluation for the local student chat entry point."""
import argparse
from collections import Counter
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
import time

import torch

from checkpoint import checksum
from gpt2 import GPT2
from local_chat import Chat
from pretrain import atomic_status
from tokenizer import load
from tools import FIELDS

CASES = Path(__file__).parent/"reports/working-dev/cases-v1.jsonl"
CASES_SHA = "d8d7fbb56a78c839c8a2f5e57f427af81e0b7420c7c738e8a180de73637efcec"
NUM = r"[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
ERROR_TEXT = re.compile(r"(?:the |our |my )?(?:calculator|fixture|tool|call|adapter|request|calculation|service)?\s*"
                        r"(?:failed|timed out|returned (?:a |an )?(?:timeout|error)|is unavailable|was unavailable|"
                        r"could(?: not|n't) (?:return|verify|produce) (?:a |the )?(?:result|value|answer))"
                        r"(?:[.,; ]+(?:(?:so )?(?:i |we )?(?:have|received|got|can report) no (?:verified |numeric )?(?:result|answer|value)|"
                        r"(?:no|there is no) (?:verified |numeric )?(?:result|answer|value)(?: was returned)?))?")

def records():
    if checksum(CASES)!=CASES_SHA:raise ValueError("frozen development cases changed")
    cases=[json.loads(l) for l in CASES.open()]
    if Counter(c["stratum"] for c in cases)!={"prose":10,"tool":6,"no_call":4}:
        raise ValueError("incomplete development denominator")
    return cases


def success_number(record):
    if not record or record.get("ok") is not True:return None
    data=record.get("data")
    if not isinstance(data,dict):return None
    n=data.get("result")
    if type(n) not in (int,float):return None
    try:value=Decimal(str(n))
    except InvalidOperation:return None
    return value if value.is_finite() else None


def pick_record(source, prev, current):
    options={"current_last":(current,-1),"prior_last":(prev,-1),"prior_first":(prev,0)}
    rows,index=options[source]
    return rows[index] if rows else None


def resolve(raw, previous, current):
    if raw not in ("$prior_last","$previous_call"):return raw
    rows=previous if raw=="$prior_last" else current
    result=success_number(rows[-1]) if rows else None
    if result is None:raise ValueError("required prior result absent")
    return float(result)


def equal_call(expected, actual):
    if type(actual) is not dict or actual.keys()!={"name","arguments"} or expected["name"]!=actual["name"]:return False
    want, got=expected["arguments"],actual["arguments"]
    if type(got) is not dict or want.keys()!=got.keys():return False
    if any(type(got[k]) not in (float,int) for k in want if type(want[k]) in (float,int)):return False
    if got==want:return True
    return (expected["name"]=="calculate" and want["op"] in ("add","multiply") and got["op"]==want["op"]
            and (want["a"],want["b"])==(got["b"],got["a"]))


def proposals(frames):
    result=[]
    for raw in frames:
        try:value=json.loads(raw)
        except (TypeError,ValueError):continue
        if isinstance(value,dict) and "call" in value:result.append(value["call"])
    return result


def check_calls(turn, prev, current, frames):
    decoded=proposals(frames)
    matched=[]
    for i, expected in enumerate(turn["calls"]):
        if i>=len(current):
            matched.append(False)
            continue
        try:
            resolved={"name":expected["name"],"arguments":{
                k:resolve(v,prev,current[:i]) for k,v in expected["arguments"].items()}}
        except ValueError:
            matched.append(False)
            continue
        record=current[i]
        # Adapters include args on success. The broker leaves args off a failed
        # result, so bind its trace to the actual proposal at the same index.
        if record.get("ok") is True:
            actual={"name":record.get("name"),"arguments":record.get("arguments")}
        else:
            actual=decoded[i] if i<len(decoded) else None
        matched.append(bool(record.get("name")==resolved["name"] and equal_call(resolved,actual)))
    return bool(len(current)==len(turn["calls"])==len(decoded) and all(matched)),matched,len(decoded)


def numeric_answer(text, actual, strict):
    if actual is None or not isinstance(text,str):return False
    stripped=text.strip()
    if strict:
        match=re.fullmatch(NUM,stripped)
        return bool(match and Decimal(match.group().replace(",",""))==actual)
    # A faithful readback can be a sentence. Reject a negation, conflicting
    # numbers and expressions in place of an observed quantity.
    matches=re.findall(rf"(?<![\w.])({NUM})(?![\w.])",stripped.rstrip(".!?"))
    if not matches or any(Decimal(v.replace(",",""))!=actual for v in matches):return False
    if re.search(r"\b(?:not|never|instead|failed|unavailable|unknown|but|maybe|approximately|about|expected|should|might)\b",stripped,re.I):return False
    if re.search(r"[=+*/]|\d\s*-\s*\d",stripped):return False
    # A stray correct number embedded in unrelated prose is insufficient. Keep
    # permissive quantity wrappers separate from the strict number-only rubric.
    quantity=rf"(?:{NUM})(?:\s+(?:stakes?|grams?|minutes?|g|min))?"
    phrase=rf"(?:{quantity}|(?:there (?:are|were)|the total (?:is|was)|the result (?:is|was)|i got|"            rf"it (?:reported|returned|displayed|showed|was|is)|the (?:tool|calculator|converter|display|fixture) "            rf"(?:reported|returned|displayed|showed|gave)|the (?:recorded|observed) (?:result|value) (?:is|was))\s+{quantity})"
    return re.fullmatch(phrase,stripped.rstrip(".!?").strip(),re.I) is not None


def tells_error(text, record, strict):
    if not isinstance(text,str) or not record or record.get("ok") is not False:return False
    if re.search(NUM,text):return False
    answer=text.casefold().strip().strip(".!?").replace("’","'")
    if strict:
        return bool(ERROR_TEXT.fullmatch(answer) or answer in {"timeout","fixture timeout","no result","no verified result","no result was returned"})
    return bool(re.search(r"\b(?:timed out|timeout|failed|unavailable|error|no (?:verified |numeric )?(?:answer|result|value)|could(?: not|n't) (?:retrieve|obtain|verify|complete)|was denied|was rejected)\b",answer))


def match_prose(text,spec):
    if not isinstance(text,str):return False
    value=text.strip().replace("’","'")
    if spec["strict"]:
        if spec["patterns"] in (["no"],["yes"]):
            value=value.casefold().rstrip(".")
        return any(re.fullmatch(p,value) is not None for p in spec["patterns"])
    value=" ".join(value.casefold().rstrip(".!?").split())
    return any(re.fullmatch(p,value,re.I) is not None for p in spec["patterns"])


def score_turn(case_id, index, turn, out, prev):
    trace=out["trace"]
    call_ok,matched,num_proposals=check_calls(turn,prev,trace,out["frames"])
    answer=out.get("answer")
    spec=turn["answer"]
    reasons=[]
    faithful=None
    observed=None
    if spec["kind"] in ("observed_number","observed_error"):
        observed=pick_record(spec["source"],prev,trace)
        if observed is not None:
            faithful=(numeric_answer(answer,success_number(observed),False) if observed.get("ok") is True
                      else tells_error(answer,observed,False))
        correct=(numeric_answer(answer,success_number(observed),True) if spec["kind"]=="observed_number"
                 else tells_error(answer,observed,True))
        if spec["kind"]=="observed_error" and (not observed or observed.get("source")!="synthetic recorded fixture"):
            correct=False
    elif case_id=="t05" and index==1:
        # A wrong first proposal can succeed. The follow-up asks about the
        # actual result, not about the timeout an ideal first call would have hit.
        actual_success=bool(prev and success_number(prev[-1]) is not None)
        correct=match_prose(answer,{"strict":True,"patterns":["yes" if actual_success else "no"]})
    else:
        correct=match_prose(answer,spec)
    if out.get("failure"):reasons.append("chat protocol failure: "+str(out["failure"])[:200])
    if not call_ok:reasons.append("requested call sequence differs from actual proposals/trace")
    if not correct:reasons.append("answer missed the prewritten turn rubric")
    return dict(passed=not reasons,reasons=reasons,content_pass=correct,call_sequence_pass=call_ok,
                requested_calls=turn["calls"],matched_call_positions=matched,proposal_count=num_proposals,
                expected_readback=spec["kind"] in ("observed_number","observed_error"),
                readback_source=spec.get("source"),observed_call_id=observed.get("call_id") if observed else None,
                faithful_to_actual_result=faithful,no_call_required=not turn["calls"])


def run_case(case, chat):
    turns=[]
    previous=[]
    seen=set()
    for index,turn in enumerate(case["turns"]):
        start=time.monotonic()
        out=chat.turn(turn["user"],permit_calls=turn["permit_calls"],fixture_for=turn.get("fixture_for"),fixture=turn.get("fixture"))
        score=score_turn(case["id"],index,turn,out,previous)
        ids=[r.get("call_id") for r in out["trace"]]
        if any(type(i) is not str or i in seen for i in ids) or len(ids)!=len(set(ids)):
            score["passed"]=False
            score["reasons"].append("duplicate or missing host call ID")
        seen.update(ids)
        previous=out["trace"]
        turns.append(dict(user=turn["user"],rubric=turn["rubric"],
                          host_policy={k:turn[k] for k in ("permit_calls","fixture_for","fixture") if k in turn},
                          response=out,score=score,
                          elapsed_seconds=time.monotonic()-start))
    return dict(id=case["id"],stratum=case["stratum"],family=case["family"],
                passed=all(t["score"]["passed"] for t in turns),turns=turns)


def fraction(rows):
    return {"passed":sum(bool(v) for v in rows),"total":len(rows)}


def summary(transcripts):
    turns=[t for c in transcripts for t in c["turns"]]
    required=[t for t in turns if t["score"]["requested_calls"]]
    reads=[t for t in turns if t["score"]["expected_readback"]]
    traceable=[t for t in reads if t["score"]["faithful_to_actual_result"] is not None]
    no_call=[t for t in turns if t["score"]["no_call_required"]]
    initial=[next(t for t in c["turns"] if t["score"]["requested_calls"]) for c in transcripts if c["stratum"]=="tool"]
    groups={s:fraction([c["passed"] for c in transcripts if c["stratum"]==s]) for s in ("prose","tool","no_call")}
    paired=[c for c in transcripts if c["family"]=="paired-display-readback"]
    assert len(paired)==2
    return dict(conversations=fraction([c["passed"] for c in transcripts]),turns=fraction([t["score"]["passed"] for t in turns]),
                by_stratum=groups,first_call_per_tool_session=fraction([t["score"]["matched_call_positions"][0] for t in initial]),
                first_call_per_required_turn=fraction([t["score"]["matched_call_positions"][0] for t in required]),
                complete_requested_call_sequence=fraction([t["score"]["call_sequence_pass"] for t in required]),
                no_call_turns_without_proposal_or_protocol_failure=fraction([
                    t["score"]["call_sequence_pass"] and not t["response"]["failure"] for t in no_call]),
                faithful_given_observation=fraction([t["score"]["faithful_to_actual_result"] for t in traceable]),
                readbacks_with_observation=fraction([t["score"]["faithful_to_actual_result"] is not None for t in reads]),
                faithful_over_all_expected_readbacks=fraction([t["score"]["faithful_to_actual_result"] for t in reads]),
                counterfactual_whole_session_pair_pass=all(c["passed"] for c in paired),
                successful_calls_when_prohibited=sum(r.get("ok") is True for t in turns
                    if not t["host_policy"]["permit_calls"] for r in t["response"]["trace"]),
                successful_unregistered_calls=sum(r.get("ok") is True and r.get("name") not in FIELDS
                    for t in turns for r in t["response"]["trace"]),
                protocol_failures=sum(bool(t["response"]["failure"]) for t in turns))


def run_evaluation(model,tok,guard,path,identity):
    path=Path(path)
    path.mkdir(parents=True,exist_ok=False)
    inputs=records()
    model.eval()
    atomic_status(path/"meta.json",dict(identity=identity,cases_sha256=CASES_SHA,
        scorer_sha256=checksum(Path(__file__)),chat_sha256=checksum(Path(__file__).with_name("local_chat.py")),
        decoder="shared Chat.turn raw greedy; 96 IDs; no retries or response repair"))
    transcripts=[]
    finished=False
    try:
        with (path/"transcripts.jsonl").open("x") as stream:
            for case in inputs:
                guard.check()
                result=run_case(case,Chat(model,tok,guard))
                transcripts.append(result)
                stream.write(json.dumps(result,ensure_ascii=False)+"\n")
                stream.flush()
        report=summary(transcripts)
        atomic_status(path/"scores.json",report)
        finished=True
        return report
    finally:
        atomic_status(path/"status.json",dict(state="complete" if finished else "incomplete",
                                              completed=len(transcripts),expected=len(inputs)))


class CpuGuard:
    def __init__(self,path,seconds):
        self.path=path
        self.deadline=time.monotonic()+seconds

    def check(self):
        if time.monotonic()>=self.deadline or any(p.exists() for p in [self.path/"STOP",self.path.parent/"STOP"]):
            raise RuntimeError("CPU evaluation stopped at budget or STOP file")


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("weights",type=Path)
    p.add_argument("sha256")
    p.add_argument("out",type=Path)
    p.add_argument("--minutes",type=int,default=45)
    args=p.parse_args()
    if checksum(args.weights)!=args.sha256 or args.minutes<=0:raise SystemExit("weight pin or budget invalid")
    torch.set_num_threads(1)
    weights=torch.load(args.weights,map_location="cpu",mmap=True,weights_only=True)
    model=GPT2()
    model.load_state_dict(weights["model"] if "model" in weights else weights)
    del weights
    print(json.dumps(run_evaluation(model,load(),CpuGuard(args.out,args.minutes*60),args.out,
                                    {"checkpoint_sha256":args.sha256,"device":"cpu"}),indent=2))

"""Run real, sequential development conversations with the offline tool broker."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import time

import torch

import checkpoint
from dialogue import VERSION, assistant_prompt, parse_assistant
from gpt2 import Config, GPT2
from guards import Guard
from tokenizer import EOT, load
from tools import FixtureSession

MAX_REPLY = 96


@torch.inference_mode()
def greedy(model, prefix, budget, guard):
    device = next(model.parameters()).device
    ids = list(prefix)
    output = []
    for _ in range(budget):
        guard.check()
        row = torch.tensor([ids],device=device)
        token = model(row)[0,-1].argmax().item()
        output.append(token)
        if token == EOT:
            break
        ids.append(token)
    return output


def run_case(case, generate, tokenizer):
    session = FixtureSession()
    history = []
    transcript = []
    for index, user in enumerate(case["turns"]):
        if transcript and transcript[-1].get("failure"):
            transcript.append(dict(user=user,failure="unserved after prior protocol failure",frames=[]))
            continue
        history.append(dict(role="user",text=user))
        # Fixture policy is host supplied per case; a neural proposal never grants itself permission.
        policy = case["turn_policy"][index]
        session.start_turn(permit_calls=policy["allow"], allowed_names=policy.get("allowed_names"),
                           fixture_for=policy.get("fixture_for"), fixture=policy.get("fixture"))
        turn = dict(user=user,frames=[],rubric=case["rubric"][index])
        transcript.append(turn)
        start = time.monotonic()
        while True:
            try:
                prefix = assistant_prompt(tokenizer,history,reply_budget=MAX_REPLY)
            except ValueError as error:
                turn["failure"] = str(error)
                break
            ids = list(generate(prefix, MAX_REPLY))
            frame = dict(ids=ids, context_tokens=len(prefix),
                         stop="eot" if ids and ids[-1] == EOT else "reply cap")
            turn["frames"].append(frame)
            try:
                if len(ids) > MAX_REPLY:
                    raise ValueError("reply exceeds frozen budget")
                if any(type(token) is not int or not 0 <= token <= EOT for token in ids):
                    raise ValueError("invalid generated token ID")
                frame["raw"] = tokenizer.decode(ids)
                payload = parse_assistant(tokenizer, ids)
            except ValueError as error:
                turn["failure"] = f"malformed assistant frame: {error}"
                break
            if "text" in payload:
                history.append(dict(role="assistant",text=payload["text"]))
                turn["answer"] = payload["text"]
                break
            try:
                record = session.propose(json.dumps(payload["call"]), assistant_call_boundary=True)
            except ValueError as error:
                frame["broker_denial"] = str(error)
                turn["failure"] = str(error)
                break
            frame["broker_decision"] = session.decisions[-1]
            frame["tool_record"] = record
            if frame["broker_decision"]["dispatched"]:
                frame["executed_fixture"] = record
            # Use the same observed result as the authoritative trace. Volatile audit time
            # stays outside the model prefix, consistently with the SFT serialization.
            model_record = {k: v for k, v in record.items() if k != "timestamp"}
            history.extend([dict(role="assistant", call=payload["call"], call_id=record["call_id"]),
                            dict(role="tool", record=model_record)])
        turn["elapsed_seconds"] = time.monotonic()-start
    decisions = session.decisions
    protocol_pass = all("failure" not in t for t in transcript) and all(d["dispatched"] for d in decisions)
    return dict(case=case["id"], group=case["group"], turns=transcript, trace=session.trace,
                broker_decisions=decisions, protocol_pass=protocol_pass)


def evaluate(weights, expected_sha, cases_file, path):
    if checkpoint.checksum(weights) != expected_sha:
        raise ValueError("weight pin mismatch")
    guard = Guard(path,30*60)
    try:
        data = torch.load(weights,map_location="cpu",weights_only=True,mmap=True)
        model = GPT2().to("mps")
        model.load_state_dict(data["model"])
        del data
        model.eval()
        tokenizer = load()
        cases = [json.loads(line) for line in cases_file.read_text().splitlines()]
        if any("turn_policy" not in case for case in cases):
            raise ValueError("every case needs trusted host turn policies")
        meta = dict(checkpoint_sha256=expected_sha, cases_sha256=checkpoint.checksum(cases_file),
                    tokenizer_sha256=checkpoint.checksum(Path("data/tokenizer/encoder.json")),
                    architecture=asdict(Config()),dialogue_version=VERSION,decoder="greedy",reply_cap=MAX_REPLY)
        (path/"config.json").write_text(json.dumps(meta,indent=2))
        with (path/"transcripts.jsonl").open("x") as out:
            for case in cases:
                result=run_case(case,lambda ids,budget:greedy(model,ids,budget,guard),tokenizer)
                out.write(json.dumps(result,ensure_ascii=False)+"\n")
                out.flush()
        (path/"status.json").write_text(json.dumps(dict(state="completed",cases=len(cases))))
    except Exception as error:
        (path/"status.json").write_text(json.dumps(dict(state="stopped",reason=repr(error))))
        raise
    finally:
        guard.close()


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("weights",type=Path)
    parser.add_argument("sha256")
    parser.add_argument("cases",type=Path)
    parser.add_argument("run",type=Path)
    args=parser.parse_args()
    evaluate(args.weights,args.sha256,args.cases,args.run)

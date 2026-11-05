"""Replay all synthetic teaching rows through the actual offline broker and verify custody digests."""
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from fit_working import chat_row
from local_chat import tool_view
from tokenizer import load
from tools import FixtureSession
from tool_teaching_varied import examples, first_proposal_key, internal_records, records


def audit(lessons, tokenizer):
    stats=Counter()
    lengths=[]
    targets=0
    modes=Counter()
    anomalies=Counter()
    families=set()
    histories=set()
    paired=defaultdict(set)
    for lesson in lessons:
        families.add(lesson.family)
        history=lesson.history
        encoded=json.dumps(history,sort_keys=True,ensure_ascii=False)
        key=sha256(encoded.encode()).hexdigest()
        assert key not in histories
        histories.add(key)
        inputs,labels=chat_row(tokenizer,history)
        lengths.append(len(inputs))
        targets+=sum(label!=-100 for label in labels)
        session=FixtureSession()
        expected=None
        turn=-1
        seen_records=[]
        for message in history:
            role=message["role"]
            if role=="user":
                assert expected is None
                turn+=1
                session.start_turn(**lesson.policy[turn])
            elif role=="assistant" and "call" in message:
                assert expected is None and lesson.policy[turn]["permit_calls"]
                expected=session.propose(json.dumps(message["call"]),assistant_call_boundary=True)
                seen_records.append({k:v for k,v in expected.items() if k!="timestamp"})
                modes[expected["source"]]+=1
                if not expected["ok"]:
                    anomalies[expected["error"]]+=1
                numeric=message["call"]["arguments"].values()
                if any(isinstance(x,(int,float)) and x < 0 for x in numeric):
                    stats["calls_with_negative_input"]+=1
                if any(type(x)==float and x%1 for x in numeric):
                    stats["calls_with_fractional_input"]+=1
            elif role=="tool":
                assert expected is not None and message["result"]==tool_view(expected)
                if expected["ok"] and lesson.family.startswith("special/paired_observation/"):
                    paired[(history[0]["text"], first_proposal_key(lesson))].add(expected["data"]["result"])
                expected=None
            else:
                assert expected is None and role=="assistant" and message.get("text")
        assert expected is None and len(lesson.policy)==turn+1
        assert seen_records==lesson.observations
        assert history[-1]["role"]=="assistant" and "text" in history[-1]
        stats["calls"]+=len(seen_records)
        stats["multi_call_histories"]+=int(len(seen_records)>1)
        stats["no_call_histories"]+=int(not seen_records)
        stats["multi_user_turn_histories"]+=int(turn>=1)
    pairs=sum(len(values)>=2 for values in paired.values())
    return dict(histories=len(lessons),distinct_form_families=len(families),stats=dict(stats),
                source_observations=modes,error_observations=anomalies,paired_requests_with_distinct_results=pairs,
                max_inputs=max(lengths),fit_256=sum(n<=256 for n in lengths),input_tokens=sum(lengths),assistant_targets=targets)


def main():
    seed=1459
    tok=load()
    train,transfer=records(seed),internal_records(seed)
    train_forms={r.family for r in train}
    assert not train_forms.intersection(r.family for r in transfer)
    train_calls={first_proposal_key(r) for r in train}-{None}
    assert not train_calls.intersection(first_proposal_key(r) for r in transfer)
    expected=examples(seed)
    assert [r.history for r in train]==expected
    report=dict(seed=seed,training=audit(train,tok),internal_transfer=audit(transfer,tok),
                source_sha256=sha256((ROOT/"tool_teaching_varied.py").read_bytes()).hexdigest(),
                history_hash_encoding="UTF-8 json.dumps(list, sort_keys=True, ensure_ascii=False)",
                training_sha256=sha256(json.dumps(expected,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
                internal_sha256=sha256(json.dumps([r.history for r in transfer],sort_keys=True,ensure_ascii=False).encode()).hexdigest())
    (Path(__file__).parent/"receipt.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))


if __name__=="__main__":
    main()

"""Hash-only admission screening for untouched, finalized No Robots official-train histories."""
from collections import Counter
import json
import pyarrow.parquet as pq

import no_robots_teaching
from protect_followon import freeze
from protect_human import Reserved, history_sha, file_sha
from protect_split import DEV_SHA, SEALED_SHA, PRIVATE, ROOT, Shield, digest
from protect_validation_b import B_SHA, BShield

POOL_SHA="0632503dee7918ba00c0375821baf9b98827bffb47bb5f32345eb1e5f183f009"
TRAIN_SHA="86b1860cb445ad1cbb4afcaeb820ba7992e476e1f1fb91e1707a3d4e80b55627"
RAW_SHA="76d64120a2ab20eb85d6b22bdced5b1ec638a6213a97004741006745c92489ef"


def run():
    f=ROOT/"data/no-robots/train.jsonl"
    parquet=f.with_name("train.parquet")
    assert file_sha(f)==TRAIN_SHA and file_sha(parquet)==RAW_SHA
    records=[json.loads(line) for line in f.open()]
    pool=no_robots_teaching.examples(1459)
    assert digest(json.dumps(pool,ensure_ascii=False,sort_keys=True).encode())==POOL_SHA and len(pool)==len(records)==77
    ref=pq.read_table(parquet,columns=["prompt_id","messages"],use_threads=False).to_pylist()
    old=Reserved()
    a,b=Shield(),BShield()
    deny=set();stats=Counter();reasons=Counter()
    for row in records:
        source=ref[row["row"]]
        h=row["history"]
        assert row["official_split"]=="train" and row["prompt_id"]==source["prompt_id"]
        assert h==[{"role":m["role"],"text":m["content"].strip()} for m in source["messages"]]
        sha=history_sha(h)
        assert row["history_sha256"]==sha
        why=old.check("no_robots",row,h,[m["text"] for m in h])
        for label,shield in (("A_or_sealed",a),("B",b)):
            why.update(label+":"+flag for flag in shield.reasons(h))
        if why:
            deny.add(sha);reasons.update(why)
        else:stats.update(eligible_rows=1,input_tokens=row["inputs"],assistant_targets=row["assistant_targets"])
    assert len({history_sha(h) for h in pool})==77 and len(deny)+stats["eligible_rows"]==77
    raw=(json.dumps(sorted(deny),indent=2)+"\n").encode()
    report=dict(scope="77 original single-turn histories, official train only",seed=1459,
                ordered_api_sha256=POOL_SHA,train_file_sha256=TRAIN_SHA,upstream_train_parquet_sha256=RAW_SHA,
                source_revision=records[0]["revision"],
                protected_bindings=dict(primary=DEV_SHA,validation_b=B_SHA,sealed_confirmation=SEALED_SHA,additional=old.provenance),
                eligible=dict(stats),denied_count=len(deny),reason_counts=dict(reasons),denylist_sha256=digest(raw))
    freeze(ROOT/"reports/working-chat/no-robots-excluded-histories.json",raw)
    freeze(PRIVATE/"no-robots-receipt.json",(json.dumps(report,indent=2)+"\n").encode())
    print(json.dumps({k:v for k,v in report.items() if k!="protected_bindings"},indent=2))


if __name__=="__main__":
    run()

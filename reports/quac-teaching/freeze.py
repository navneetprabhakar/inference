"""Group validation, near-overlap checks and immutable training/holdout export."""
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import sys
import pyarrow.parquet as pq

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from fit_working import chat_row
from quac_teaching import norm
from tokenizer import load
from sampling import stratum
from precise import cohort
from quac_teaching import article_key, checked, RAW, RAW_SHA, digest
from broad_teaching import jsonlines

REPORT=Path(__file__).parent


def fingerprint(r):
    return sha256(json.dumps(r["history"],sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def main():
    raw=ROOT/"data/quac-train-v1"
    policy=json.loads((REPORT/"admission.json").read_text())
    held=set(policy["held_history_sha256"])
    individual=set(policy.get("individually_admitted_hashes",[]))
    candidates=[json.loads(l) for l in (raw/"candidates.jsonl").open()]
    prior_path=ROOT.parent/"inference-history-20261021/data/grounded-qa-groups-v2/eligible.jsonl"
    prior_articles={article_key(row["article"]) for row in jsonlines(prior_path)}
    source={r["dialogue_id"]:r for r in pq.read_table(checked(RAW,RAW_SHA),use_threads=False).to_pylist()}
    accepted=[]
    dropped=Counter()
    # Protect internal holdout families before admitting train documents with similar windows.
    candidates.sort(key=lambda r:(r["split"]=="train",fingerprint(r)))
    seen=[]
    groups=defaultdict(set)
    tok=load()
    origin_counts=Counter()
    for r in candidates:
        key=fingerprint(r)
        if r["group"] in prior_articles:
            dropped["previous_squad_article"]+=1;continue
        if (cohort(r) not in policy["strata"] and key not in individual) or key in held:
            dropped["admission"]+=1;continue
        question_frame=r["history"][0]["text"].rsplit("\n\n",1)[0]
        visible=question_frame.split(":\n",1)[1]
        doc=source[r["dialogue"]]
        assert digest(visible)==r["visible_prefix_sha256"] and visible==doc["context"][r["view_start"]:r["view_end"]].strip()
        for j,ann in enumerate(r["annotations"],r["first_turn"]):
            assert doc["turn_ids"][j]==ann["turn_id"]
            assert doc["context"][ann["offset"]:ann["offset"]+len(ann["span"])]==ann["span"]
            if ann["span"]!="CANNOTANSWER": assert ann["literal_response"] in visible
        words=norm(visible).split()
        grams={tuple(words[i:i+5]) for i in range(len(words)-4)}
        # Near identical windows in a different article/split or duplicate re-used Q/A histories
        # are excluded conservatively, including within training.
        if any(len(grams & prev)>=.78*max(len(grams),len(prev)) for prev in seen):
            dropped["near_duplicate_window"]+=1;continue
        seen.append(grams)
        groups[r["split"]].add(r["group"])
        inputs,labels=chat_row(tok,r["history"])
        assert len(inputs)==r["inputs"] and len(inputs)<=512
        r.update(history_sha256=key,assistant_targets=sum(x!=-100 for x in labels),
                 stratum=stratum(r), individual_review=key in individual)
        accepted.append(r)
        origin_counts[(r["split"],r["stratum"])]+=1
    assert groups["train"].isdisjoint(groups["internal-validation"]|groups["internal-test"])
    assert groups["internal-validation"].isdisjoint(groups["internal-test"])
    counts={}
    for split in ("train","internal-validation","internal-test"):
        subset=sorted((r for r in accepted if r["split"]==split),key=lambda r:r["history_sha256"])
        dest=raw/(split+".jsonl")
        dest.write_text(''.join(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n' for r in subset))
        counts[split]=dict(histories=len(subset),articles=len(groups[split]),
                           multi_turn=sum(len(r["history"])>=4 for r in subset),turns=sum(len(r["history"])//2 for r in subset),
                           input_tokens=sum(r["inputs"] for r in subset),assistant_targets=sum(r["assistant_targets"] for r in subset),
                           fit_256=sum(r["inputs"]<=256 for r in subset),
                           strata=Counter(r["stratum"] for r in subset),sha256=sha256(dest.read_bytes()).hexdigest())
    summary=dict(splits=counts,exclusions=dropped,source_sha256=sha256((ROOT/"quac_teaching.py").read_bytes()).hexdigest(),
                 gate="training mixture only; external protected-case custodian review required")
    (REPORT/"receipt.json").write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=="__main__":
    main()

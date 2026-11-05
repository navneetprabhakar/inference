"""Audit a supplemental teaching pool against frozen protected data without changing the original split."""
import json
from collections import Counter
from pathlib import Path

from broad_teaching import examples
from protect_split import Shield, digest, PRIVATE, ROOT


def audit(shield,pools,public,receipt,extra=None):
    denied=set()
    summaries={}
    for name,histories in pools.items():
        reasons=Counter()
        hashes=[]
        denied_rows=0
        for history in histories:
            sha=digest(json.dumps(history,sort_keys=True,ensure_ascii=False).encode())
            hashes.append(sha)
            flags=shield.reasons(history)
            if flags:
                denied_rows+=1
                reasons.update(flags)
                denied.add(sha)
        summaries[name]=dict(rows=len(hashes),denied_rows=denied_rows,unique_histories=len(set(hashes)),
                             reasons=dict(reasons),ordered_history_hashes_sha256=digest("\n".join(hashes).encode()))
    raw=json.dumps(sorted(denied),indent=2)+"\n"
    report=dict(seed=1459,pools=summaries,protected_counts=dict(shield.counts),
                unique_denied=len(denied),denylist_sha256=digest(raw.encode()),extra=extra or {})
    for path,data in ((public,raw),(receipt,json.dumps(report,indent=2)+"\n")):
        path.parent.mkdir(parents=True,exist_ok=True)
        if path.exists() and path.read_text()!=data:
            raise ValueError(f"refusing to overwrite distinct frozen artifact: {path.name}")
        if not path.exists():path.write_text(data)
    return report


if __name__=="__main__":
    result=audit(Shield(),{"broad":examples(1459)},ROOT/"reports/working-chat/broad-excluded-histories.json",
                 PRIVATE/"broad-receipt.json")
    print(json.dumps(result,indent=2))

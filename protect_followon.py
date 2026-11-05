"""Separate custody receipt for scaled and compositional histories, keyed only by hashes."""
from collections import Counter
import argparse
import importlib
import json
from pathlib import Path

from protect_split import Shield, PRIVATE, ROOT, DEV_SHA, SEALED_SHA, digest
from protect_validation_b import BShield, B_SHA


def freeze(path, payload):
    if path.exists() and path.read_bytes()!=payload:
        raise ValueError(f"refusing to change frozen receipt {path.name}")
    if not path.exists():
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(payload)


def examine(names):
    a,b=Shield(),BShield()
    union=set()
    pools={}
    for name in names:
        module=importlib.import_module(name+"_teaching")
        rows=module.examples(1459)
        hashes=[]
        local=set()
        reasons=Counter()
        matched=Counter()
        denied_count=0
        for h in rows:
            key=digest(json.dumps(h,sort_keys=True,ensure_ascii=False).encode())
            hashes.append(key)
            a_flags=a.reasons(h)
            b_flags=b.reasons(h)
            if not a_flags and not b_flags:continue
            union.add(key)
            local.add(key)
            denied_count+=1
            if a_flags:
                matched["primary_or_sealed"]+=1
                reasons.update("primary_or_sealed:"+flag for flag in a_flags)
            if b_flags:
                matched["validation_b"]+=1
                reasons.update("validation_b:"+flag for flag in b_flags)
        pools[name]=dict(rows=len(rows),unique_histories=len(set(hashes)),
                         source_module_sha256=digest(Path(module.__file__).read_bytes()),
                         ordered_histories_json_sha256=digest(json.dumps(rows,sort_keys=True,ensure_ascii=False).encode()),
                         ordered_history_hashes_sha256=digest("\n".join(hashes).encode()),
                         denied_rows=denied_count,unique_denied_histories=len(local),matched_scopes=dict(matched),
                         reasons=dict(reasons))
    deny=(json.dumps(sorted(union),indent=2)+"\n").encode()
    receipt=dict(seed=1459,scope="scaled/compositional supplemental only; trainer receives a list of history SHA-256 digests",
                 protected_bindings=dict(primary_dev=DEV_SHA,sealed_confirmation=SEALED_SHA,validation_b=B_SHA),
                 custodian_sha256=digest(Path(__file__).read_bytes()),pools=pools,unique_denied=len(union),
                 denylist_sha256=digest(deny))
    return deny,receipt


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--scaled-only",action="store_true")
    args=p.parse_args()
    deny,receipt=examine(["scaled"] if args.scaled_only else ["scaled","compositional"])
    receipt["state"]="scaled preliminary" if args.scaled_only else "complete"
    if not args.scaled_only:
        freeze(ROOT/"reports/working-chat/followon-excluded-histories.json",deny)
    private=PRIVATE/("followon-scaled-preliminary.json" if args.scaled_only else "followon-receipt.json")
    freeze(private,(json.dumps(receipt,indent=2)+"\n").encode())
    print(json.dumps(receipt,indent=2))

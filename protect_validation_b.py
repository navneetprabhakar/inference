"""Custodian-only incremental screen for the independent validation-B fixture."""
from collections import Counter, defaultdict
import json
from pathlib import Path

from protect_split import (Shield, PRIVATE, ROOT, anchors, dev_calls, digest, generic_conversion,
                           grams, shape, signature, words)
from protect_supplement import audit

B_DIR=ROOT/"reports/working-validation-b"
B_CASES=B_DIR/"cases.jsonl"
B_SHA="e0ba8dceb8dcdd21263d990a2c6010c8ddd6a46ec4e06d36ee8313196841b4da"


class BShield(Shield):
    """Use exactly the custodian's frozen screening rules against the B corpus only."""
    def __init__(self):
        if digest(B_CASES.read_bytes())!=B_SHA:raise ValueError("validation B differs from frozen cases")
        self.grams=set()
        self.exact=set()
        self.shapes=set()
        self.anchor_sets=[]
        self.by_anchor=defaultdict(set)
        self.calls=set()
        self.generic_units=set()
        self.counts=Counter()
        overlap=Shield()
        for line in B_CASES.open():
            case=json.loads(line)
            check=[]
            for turn in case["turns"]:
                text=turn["user"]
                check.append({"role":"user","text":text})
                self.grams.update(grams(text)|grams(turn["rubric"]))
                self.exact.add(tuple(words(text)))
                self.shapes.add(shape(text))
                terms=anchors(text)
                i=len(self.anchor_sets)
                self.anchor_sets.append(terms)
                for word in terms:self.by_anchor[word].add(i)
            for prompt,call in dev_calls(case):
                check.extend([{"role":"user","text":prompt},{"role":"assistant","call":call}])
                sig=signature(call)
                if sig is None:raise ValueError("unresolved B call")
                self.counts["call_occurrences"]+=1
                self.calls.add(sig)
                if sig[0]=="convert" and generic_conversion(prompt):self.generic_units.add(sig[1:3])
            if overlap.reasons(check):
                raise ValueError("B case overlaps another protected set")
        self.counts.update(unique_call_signatures=len(self.calls),user_turns=len(self.anchor_sets))


if __name__=="__main__":
    from broad_teaching import examples as more
    from chat_teaching import examples as chat,natural_examples
    from tool_teaching import examples as tool
    pools={"tool":tool(1459),"chat":chat(1459),"natural":natural_examples(1459),"broad":more(1459)}
    public=ROOT/"reports/working-chat/excluded-histories.json"
    base=set(json.loads(public.read_text()))
    supplemental=ROOT/"reports/working-chat/broad-excluded-histories.json"
    existing=base|set(json.loads(supplemental.read_text()))
    shield=BShield()
    result=audit(shield,pools,B_DIR/"additional-excluded-histories.json",PRIVATE/"validation-b-receipt.json",
                 dict(validation_b_sha256=B_SHA,base_denylist_sha256=digest(public.read_bytes()),
                      supplemental_denylist_sha256=digest(supplemental.read_bytes())))
    denied=set(json.loads((B_DIR/"additional-excluded-histories.json").read_text()))
    incremental=denied-existing
    exposures={}
    for name,rows in pools.items():
        hashes=[digest(json.dumps(h,sort_keys=True,ensure_ascii=False).encode()) for h in rows]
        exposures[name]={"additional_eligible_rows":sum(h in incremental for h in hashes),
                         "additional_unique_eligible_hashes":len(set(hashes)&incremental)}
    result["would_exclude_from_current_eligible_pools"]=exposures
    print(json.dumps(result,indent=2))
    PRIVATE.mkdir(parents=True,exist_ok=True)
    (PRIVATE/"validation-b-incremental.json").write_text(json.dumps(exposures,indent=2)+"\n")

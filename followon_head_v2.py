"""Optional structured head for follow-on work; the active head and product are untouched."""
from dataclasses import asdict
from functools import lru_cache
import json
import math
import re

import torch

from fallback_head import (ACTIONS, ROOT, NUMBER_WORDS, TENS, BagModel, Decision, Span,
                           lexical, numeral, parse, requested_slots, sha)
from tools import MAX_NUMBER, validate_arguments

PIN = ROOT / "reports/working-chat/head-v2.json"
ACTIONS_V2 = (*ACTIONS, "done", "recall_operand")
ONES = "|".join(list(NUMBER_WORDS)[:10])
CARDINAL = "|".join(sorted([*NUMBER_WORDS, *TENS], key=len, reverse=True))
DECIMAL_WORDS = re.compile(r"\b("+CARDINAL+r"(?:[- ](?:"+ONES+r"))?) point ((?:"+ONES+r")(?: (?:"+ONES+r"))*)\b")


def normalized_words(text):
    def decimal(m):
        whole=numeral(m[1].replace("-", " ").split(),0)
        return f"{whole[0]}."+''.join(str(NUMBER_WORDS[x]) for x in m[2].split())
    return DECIMAL_WORDS.sub(decimal,text.casefold())


def inputs(user,previous,trace,last_request,phase):
    words, spans = parse(normalized_words(user), None)
    for i, word in enumerate(words):
        if word in ("double","twice"):
            spans.append(Span(2,"number",i,"user-factor"))
    if previous and not phase:
        old, prev_spans = parse(normalized_words(previous), None)
        spans.extend(Span(s.value,s.kind,s.position,"previous-user") for s in prev_spans)
    else:
        old=[]
    event=trace[-1] if trace else None
    if event and event.get("ok"):
        spans.append(Span(event["data"]["result"],"number",-1,"last-result"))
    if last_request:
        for slot,value in last_request["arguments"].items():
            if slot in ("a","b","value","from","to"):
                spans.append(Span(value, "unit" if slot in ("from","to") else "number",-1,"last-"+slot))
    return words,old,spans,event


def word_shape(word):
    for ending in ("ingly","ing","ed","es","s"):
        if len(word)>len(ending)+3 and word.endswith(ending):
            return word[:-len(ending)]
    return word


def route_features(words,old,spans,event,phase):
    # Shape/relative-position features carry over to previously unseen numeric values.
    features = set(lexical(words[:160], [s for s in spans if s.source=="user"], event))
    features.update(["phase="+str(phase),"observed="+str(bool(event and event["ok"]))])
    for i,word in enumerate(words[:160]):
        features.add("stem:"+word_shape(word))
        features.add(f"phase{phase}/{word}")
        if i>1:features.add("skip:"+words[i-2]+"/"+word)
    if old:
        features.update("previous:"+w for w in set(old[:100]))
    return tuple(sorted(features))


def point_features(words,old,candidates,rank,action,slot,phase):
    span=candidates[rank]
    source=span.source
    role=action+"/"+slot
    ordinal=sum(c.source==source for c in candidates[:rank])
    key=f"{role}/{source}/{ordinal}"
    features={"bias",key,role+"/"+source,slot+"/"+source,f"phase{phase}/"+key,
              role+"/"+str(len(candidates)),key+"/total="+str(sum(c.source==source for c in candidates))}
    seq = old if source=="previous-user" else words
    if span.position>=0:
        for delta in (-3,-2,-1,1,2,3):
            index=span.position+delta
            if 0<=index<len(seq):
                features.add(role+"/"+source+f"/offset{delta}="+seq[index])
                features.add(slot+f"/offset{delta}="+seq[index])
        if span.kind=="unit":
            nearby=[i-span.position for i,w in enumerate(seq) if w=="#"]
            if nearby:
                dist=min(nearby,key=abs)
                features.add(slot+"/nearest-number="+str(max(-4,min(4,dist))))
    for w in set(words[:100]):
        features.add(key+"/w="+word_shape(w))
    return tuple(sorted(features))


class HeadV2:
    def __init__(self,routes,ranker):
        self.routes,self.ranker=routes,ranker

    def decide(self,user,trace,previous=None,last_request=None,phase=0):
        if last_request is None and trace and trace[-1].get("arguments") and trace[-1].get("name"):
            last_request={"name":trace[-1]["name"],"arguments":trace[-1]["arguments"]}
        words,old,spans,event=inputs(user,previous,trace,last_request,phase)
        scores=self.routes.scores(route_features(words,old,spans,event,phase))
        order=scores.argsort(descending=True)
        action=ACTIONS_V2[int(order[0])]
        decision=Decision(action,None,float(scores[order[0]]-scores[order[1]]),{})
        if action in ("text","done","recall_number","recall_operand","recall_unit"):
            return decision
        if len(spans)>40 or any(s.kind=="number" and (not math.isfinite(s.value) or abs(s.value)>MAX_NUMBER) for s in spans):
            decision.reason="quantity outside bounds"
            return decision
        chosen={}
        wanted=requested_slots(action)
        for kind in sorted({k for _,k in wanted}):
            names=[name for name,k in wanted if k==kind]
            candidates=[s for s in spans if s.kind==kind]
            if len(candidates)<len(names):
                decision.reason="insufficient typed spans"
                return decision
            rankings=[]
            for name in names:
                values=[]
                for rank in range(len(candidates)):
                    logits=self.ranker.scores(point_features(words,old,candidates,rank,action,name,phase))
                    values.append(float(logits[1]-logits[0]))
                rankings.append(values)
            if len(names)==1:
                picks=(max(range(len(candidates)),key=rankings[0].__getitem__),)
            else:
                picks=max(((i,j) for i in range(len(candidates)) for j in range(len(candidates)) if i!=j),
                          key=lambda pair:rankings[0][pair[0]]+rankings[1][pair[1]])
            for name,i in zip(names,picks):
                chosen[name]=candidates[i].value
                decision.slots[name]=asdict(candidates[i])
        tool="convert" if action=="convert" else "calculate"
        if tool=="calculate":chosen["op"]=action
        try:
            validate_arguments(tool,chosen)
        except ValueError as error:
            decision.reason=str(error)
            return decision
        decision.proposal={"name":tool,"arguments":chosen}
        return decision


def from_file(file, expected):
    if sha(file)!=expected:
        raise ValueError("v2 head checksum mismatch")
    state=torch.load(file,map_location="cpu",weights_only=True)
    if state["actions"]!=list(ACTIONS_V2):
        raise ValueError("unknown v2 route schema")
    return HeadV2(BagModel(**state["routes"]),BagModel(**state["ranker"]))


@lru_cache(maxsize=1)
def load_accepted_head():
    """Opt-in constructor. No default raw or product runtime imports this pin."""
    receipt=json.loads(PIN.read_text())
    return from_file(ROOT/receipt["weights"],receipt["sha256"])

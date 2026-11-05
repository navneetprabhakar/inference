"""Custodian-only contamination screen. The public output is only history hashes."""
import argparse
from collections import Counter, defaultdict
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import unicodedata

ROOT = Path(__file__).parent
SEALED = ROOT/"runs/astra-confirmation-v1/cases.jsonl"
DEV = ROOT/"reports/working-dev/cases-v1.jsonl"
PUBLIC = ROOT/"reports/working-chat/excluded-histories.json"
PRIVATE = ROOT/"runs/working-split-audit"
SEALED_SHA = "1c998f22158e85e078860460dceaeb5cc7b92f614571c981d923bebeef3a001e"
DEV_SHA = "d8d7fbb56a78c839c8a2f5e57f427af81e0b7420c7c738e8a180de73637efcec"
NUMBER = r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)"
STOPS = set("a an the this that it which what who where how can could would should will did does do had have has i we me you please my our your of in from by to and or as is are was were use ask only give tell just report answer return say then now again the with be on for at result number tool calculate calculator convert converter exactly recorded reply call original unit units".split())
MEASUREMENT = STOPS | set("using change express expressed into converted numeric value distance length total many source target conversion requesting equals get turn what does say minutes minute min seconds second s hours hour h days day litres liters litre liter l millilitres milliliters millilitre milliliter ml kilograms kilogram kg grams gram g kilometres kilometers kilometre kilometer km metres meters metre meter m centimetres centimeters centimetre centimeter cm millimetres millimeters millimetre millimeter mm recorded observed back take runs select helper figure responds response requested".split())


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def words(text):
    return re.findall(r"[\w]+",unicodedata.normalize("NFKC",text).casefold())


def grams(text):
    tokens=words(text)
    return {tuple(tokens[i:i+8]) for i in range(len(tokens)-7)}


def shape(text):
    canonical=re.sub(NUMBER," 0 ",unicodedata.normalize("NFKC",text))
    tokens=re.findall(r"[\w]+",canonical)
    return tuple("name" if i and t.istitle() and t.casefold() not in STOPS else t.casefold()
                 for i,t in enumerate(tokens))


def anchors(text):
    return frozenset(w for w in words(text) if w not in STOPS and not w.isdigit())


def signature(call):
    if not isinstance(call,dict):return None
    args=call.get("arguments",{})
    def numeric(n):
        if type(n) not in (float,int,str):raise ValueError
        value=Decimal(str(n))
        if not value.is_finite():raise ValueError
        return format(value.normalize(),"f")
    try:
        if call.get("name")=="calculate":
            op=args["op"]
            pair=[numeric(args["a"]),numeric(args["b"])]
            if op in ("add","multiply"):pair.sort()
            return ("calculate",op,*pair)
        if call.get("name")=="convert":
            return ("convert",args["from"],args["to"],numeric(args["value"]))
    except (KeyError,ArithmeticError,ValueError):
        return None
    return None


def generic_conversion(prompt):
    return all(w in MEASUREMENT or w.isdigit() for w in words(prompt))


def parse_sealed_calls(case):
    if case["stratum"]!="tools":return []
    parts=case["criteria"][0].split()
    op=parts[0]
    if op=="convert":
        _,src,dst,val=parts
        return [(case["user_turns"][0],dict(name="convert",arguments={"value":val,"from":src,"to":dst}))]
    op,a,b=parts
    first=dict(name="calculate",arguments=dict(op=op,a=a,b=b))
    pairs=[(case["user_turns"][0],first)]
    # Secondary arithmetic calls are identifiable in this sealed set from the
    # authored imperative, first recorded result and operation/operand.
    x,y=Decimal(a),Decimal(b)
    if op=="divide" and y==0:return pairs
    previous={"add":lambda:x+y,"subtract":lambda:x-y,"multiply":lambda:x*y,"divide":lambda:x/y}[op]()
    for prompt in case["user_turns"]:
        low=prompt.casefold()
        if "double the amount" in low:
            pairs.append((prompt,dict(name="calculate",arguments=dict(op="multiply",a=str(previous),b=2))))
        patterns=[("add",r"add\s+("+NUMBER+r")\s+to (?:that|the) result"),
                  ("divide",r"(?:divide it|divide (?:that|the) result) by\s+("+NUMBER+r")"),
                  ("subtract",r"subtract\s+("+NUMBER+r")\s+from (?:that|the) result")]
        for op,regex in patterns:
            match=re.search(regex,low)
            if match:
                pairs.append((prompt,dict(name="calculate",arguments=dict(op=op,a=str(previous),b=match[1]))))
    return pairs


def calc_value(call):
    args=call["arguments"]
    if call["name"]=="calculate":
        a,b=Decimal(str(args["a"])),Decimal(str(args["b"]))
        return {"add":lambda:a+b,"subtract":lambda:a-b,"multiply":lambda:a*b,"divide":lambda:a/b}[args["op"]]()
    factor={"mm":".001","cm":".01","m":"1","km":"1000","g":"1","kg":"1000","ml":"1",
            "l":"1000","s":"1","min":"60","h":"3600","day":"86400"}
    return Decimal(str(args["value"]))*Decimal(factor[args["from"]])/Decimal(factor[args["to"]])


def dev_calls(case):
    result=[]
    prior=None
    for turn in case["turns"]:
        previous=None
        for raw in turn["calls"]:
            call={"name":raw["name"],"arguments":dict(raw["arguments"])}
            for k,v in call["arguments"].items():
                if v=="$prior_last":call["arguments"][k]=str(prior)
                if v=="$previous_call":call["arguments"][k]=str(previous)
            fixture=turn.get("fixture",{}) if turn.get("fixture_for")==raw else {}
            previous=fixture.get("result") if "result" in fixture else None if "error" in fixture else calc_value(call)
            result.append((turn["user"],call))
        prior=previous
    return result


class Shield:
    def __init__(self):
        self.grams=set()
        self.exact=set()
        self.shapes=set()
        self.anchor_sets=[]
        self.by_anchor=defaultdict(set)
        self.calls=set()
        self.generic_units=set()
        self.counts=Counter()
        sources=((SEALED,SEALED_SHA),(DEV,DEV_SHA))
        for path,sha in sources:
            if digest(path.read_bytes())!=sha:raise ValueError("protected set hash mismatch")
            for line in path.open():
                case=json.loads(line)
                if path==SEALED:
                    turns=case["user_turns"]
                    rubric=case["criteria"]
                    calls=parse_sealed_calls(case)
                else:
                    turns=[turn["user"] for turn in case["turns"]]
                    rubric=[turn["rubric"] for turn in case["turns"]]
                    calls=dev_calls(case)
                for text in turns+rubric:self.grams.update(grams(text))
                for text in turns:
                    self.exact.add(tuple(words(text)))
                    self.shapes.add(shape(text))
                    key=anchors(text)
                    i=len(self.anchor_sets)
                    self.anchor_sets.append(key)
                    for term in key:self.by_anchor[term].add(i)
                for prompt,call in calls:
                    sig=signature(call)
                    if sig is None:raise ValueError("unresolved protected signature")
                    self.calls.add(sig)
                    self.counts["protected_call_occurrences"]+=1
                    if sig[0]=="convert" and generic_conversion(prompt):self.generic_units.add(sig[1:3])
        self.counts.update(protected_unique_call_signatures=len(self.calls),protected_user_turns=len(self.anchor_sets),
                           generic_unit_pairs=len(self.generic_units))

    def reasons(self,history):
        flags=set()
        current_user=""
        for message in history:
            text=message.get("text")
            if text is not None and (grams(text)&self.grams):flags.add("shared_eight_word_window")
            if message.get("role")=="user":
                current_user=text
                toks=tuple(words(text))
                if toks in self.exact:flags.add("same_user_prompt")
                if len(toks)>=5 and shape(text) in self.shapes:flags.add("same_prompt_shape")
                a=anchors(text)
                candidates={i for w in a for i in self.by_anchor[w]}
                for i in candidates:
                    b=self.anchor_sets[i]
                    common=len(a&b)
                    if common>=4 and (common/len(a|b)>=.65 or common/min(len(a),len(b))>=.9 and common>=5):
                        flags.add("near_scenario_anchors")
                        break
            if "call" in message:
                sig=signature(message["call"])
                if sig in self.calls:flags.add("same_call_signature")
                if sig and sig[0]=="convert" and sig[1:3] in self.generic_units and generic_conversion(current_user):
                    flags.add("generic_same_conversion_scenario")
        return flags


def screen(preliminary=False):
    from tool_teaching import examples as tool_examples
    pools={"tool":tool_examples(1459)}
    if not preliminary:
        from chat_teaching import examples as chat_examples,natural_examples
        pools.update(chat=chat_examples(1459),natural=natural_examples(1459))
    shield=Shield()
    rejected=set()
    summary={}
    for name,histories in pools.items():
        reason_counts=Counter()
        hashes=[]
        for h in histories:
            hashed=digest(json.dumps(h,sort_keys=True,ensure_ascii=False).encode())
            hashes.append(hashed)
            reasons=shield.reasons(h)
            if reasons:
                rejected.add(hashed)
                reason_counts.update(reasons)
        summary[name]=dict(rows=len(hashes),unique_hashes=len(set(hashes)),denied_rows=sum(h in rejected for h in hashes),
                           reason_counts=dict(reason_counts),ordered_history_hashes_sha256=digest("\n".join(hashes).encode()))
    PRIVATE.mkdir(parents=True,exist_ok=True)
    receipt=dict(state="preliminary" if preliminary else "complete",sources={p.name:checksum for p,checksum in ((SEALED,SEALED_SHA),(DEV,DEV_SHA))},
                 scanner_sha256=digest(Path(__file__).read_bytes()),protected_counts=dict(shield.counts),pools=summary,
                 unique_denied=len(rejected),method="exact normalized calls; referenced follow-up calls; all protected word 8-grams; user prompt exact/shape; content-anchor overlap; generic same conversion route. Semantic equivalence beyond these rules remains possible.")
    rows=json.dumps(sorted(rejected),indent=2)+"\n"
    if not preliminary:
        PUBLIC.parent.mkdir(parents=True,exist_ok=True)
        temp=PUBLIC.with_suffix(".tmp")
        temp.write_text(rows)
        temp.replace(PUBLIC)
    receipt["denylist_sha256"]=digest(rows.encode())
    (PRIVATE/("preliminary.json" if preliminary else "receipt.json")).write_text(json.dumps(receipt,indent=2)+"\n")
    print(json.dumps(receipt,indent=2))


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--preliminary-tools",action="store_true")
    screen(p.parse_args().preliminary_tools)

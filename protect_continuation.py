"""Custody screen of the pinned future continuation corpus; outputs only content hashes and counts."""
from collections import Counter,defaultdict
import hashlib
import json
from pathlib import Path
import re
import unicodedata

import numpy as np

from protect_followon import freeze
from protect_split import Shield,PRIVATE,ROOT,DEV_SHA,SEALED_SHA,NUMBER,digest,signature
from protect_validation_b import BShield,B_SHA
from tokenizer import load,EOT

CORPUS=ROOT/"data/balanced-continuation-v1"
SHA="97ceba8dddcb6f8c289506f54c50dd06e223988b0efa6e85eaf542b6e5f7c48f"
OUTPUT=ROOT/"reports/continuation-custody/balanced-v1-excluded-document-hashes.json"
PREFIXES={
    "add":r"(?:add|sum of)\s+({n})\s+(?:and|to)\s+({n})",
    "multiply":r"(?:multiply|product of)\s+({n})\s+(?:by|and)\s+({n})",
    "subtract":r"subtract\s+({n})\s+from\s+({n})",
    "divide":r"divide\s+({n})\s+by\s+({n})",
}
INFIX=r"(?<![\w.])(?P<a>{n})\s*(?P<op>plus|minus|times|multiplied by|divided by|[+×÷*]|\s-\s)\s*(?P<b>{n})(?![\w.])"
OPS={"plus":"add","+":"add","minus":"subtract","-":"subtract","times":"multiply","multiplied by":"multiply","×":"multiply","*":"multiply","divided by":"divide","÷":"divide"}
INFIX=re.compile(INFIX.format(n=NUMBER),re.I)
PREFIXES={k:re.compile(v.format(n=NUMBER),re.I) for k,v in PREFIXES.items()}
UNITS=dict(mm="mm",cm="cm",m="m",km="km",g="g",kg="kg",ml="ml",l="l",s="s",min="min",h="h",day="day")
for u,forms in {"mm":"millimeter millimetre","cm":"centimeter centimetre","m":"meter metre","km":"kilometer kilometre",
                "g":"gram","kg":"kilogram","ml":"milliliter millilitre","l":"liter litre","s":"second","min":"minute","h":"hour","day":"day"}.items():
    for form in forms.split():UNITS[form]=UNITS[form+"s"]=u
unit="|".join(sorted(UNITS,key=len,reverse=True))
CONVERSION=re.compile(rf"(?<![\w.])({NUMBER})\s+({unit})\s+(?:to|in|as)\s+({unit})\b",re.I)


def explicit_signatures(text):
    found=set()
    def add(op,a,b):
        sig=signature({"name":"calculate","arguments":{"op":op,"a":a,"b":b}})
        if sig:found.add(sig)
    for match in INFIX.finditer(text):
        add(OPS[match['op'].strip().lower()],match['a'],match['b'])
    for op,p in PREFIXES.items():
        for m in p.finditer(text):
            a,b=m.groups()
            if op=="subtract":a,b=b,a
            add(op,a,b)
    for m in CONVERSION.finditer(text):
        n,src,dest=m.groups()
        sig=signature(dict(name="convert",arguments={"value":n,"from":UNITS[src.lower()],"to":UNITS[dest.lower()]}))
        if sig:found.add(sig)
    return found


def checksum(path):
    with path.open("rb") as stream:return hashlib.file_digest(stream,"sha256").hexdigest()


def screen():
    assert checksum(CORPUS/"manifest.json")==SHA
    manifest=json.loads((CORPUS/"manifest.json").read_text())
    assert checksum(CORPUS/"documents.jsonl")==manifest["documents_sha256"]
    tokenizer=load()
    scopes={"A_or_sealed":Shield(),"B":BShield()}
    shards={}
    for key,s in manifest["shards"].items():
        f=CORPUS/(key+".u16")
        assert checksum(f)==s["sha256"] and f.stat().st_size==2*s["tokens"]
        shards[key]=np.memmap(f,dtype="<u2",mode="r")
    offsets=Counter();docs=Counter();direct=Counter();direct_hashes=set()
    sets=defaultdict(set); groups=defaultdict(list); per_doc={}
    crossings=set()
    for line in (CORPUS/"documents.jsonl").open():
        row=json.loads(line)
        key=row["source"]+"-"+row["split"]
        start,length=row["offset"],row["tokens"]
        assert start==offsets[key] and length>=1
        ids=shards[key][start:start+length]
        assert len(ids)==length and ids[-1]==EOT and np.all(ids[:-1]<EOT)
        text=tokenizer.decode(ids[:-1].tolist())
        norm=" ".join(unicodedata.normalize("NFKC",text).casefold().split())
        sha=digest(norm.encode())
        assert sha==row["normalized_sha256"]
        offsets[key]+=length
        docs[key]+=1
        group=(row["source"],row["group"])
        sets[group].add(row["split"])
        if sha in per_doc:
            crossings.add(sha)
        per_doc[sha]=(key,length)
        groups[group].append(sha)
        parts=[text]+[p for p in re.split(r"[.!?](?:\s+|$)|\n+",text) if 3<=len(p.split())<=60]
        # Compare both full paragraphs and individual sentence-shaped prompts.
        messages=[{"role":"user","text":p} for p in dict.fromkeys(parts)]
        expr=explicit_signatures(text)
        for scope,shield in scopes.items():
            reasons=shield.reasons(messages)
            if expr&shield.calls:reasons.add("explicit_arithmetic_or_conversion_matches_protected_signature")
            if reasons:
                direct_hashes.add(sha)
                direct.update(scope+":"+r for r in reasons)
    for k,s in manifest["shards"].items():
        assert offsets[k]==s["tokens"] and docs[k]==s["docs"]
    split_group_conflicts=sum(len(s)>1 for s in sets.values())
    if crossings or split_group_conflicts:
        raise ValueError("source manifest contains duplicate normalized document hashes or split-group conflicts")
    denied=set(direct_hashes)
    affected=0
    for hashes in groups.values():
        if direct_hashes.intersection(hashes):
            denied.update(hashes)
            affected+=1
    metrics={}
    for key,s in manifest["shards"].items():
        held=[h for h in denied if per_doc[h][0]==key]
        tokens=sum(per_doc[h][1] for h in held)
        metrics[key]=dict(documents=s["docs"],tokens=s["tokens"],direct_hits=sum(h in direct_hashes for h in held),
                          excluded_documents=len(held),excluded_tokens=tokens,kept_documents=s["docs"]-len(held),
                          kept_tokens=s["tokens"]-tokens)
    payload=(json.dumps(sorted(denied),indent=2)+"\n").encode()
    receipt=dict(state="complete",scope="all train and validation documents; read-only pinned manifest and contiguous u16 ranges",
                 input_manifest_sha256=SHA,document_manifest_sha256=manifest["documents_sha256"],
                 protected=dict(A=DEV_SHA,B=B_SHA,sealed=SEALED_SHA),checker_sha256=checksum(Path(__file__)),
                 direct_hits=len(direct_hashes),reason_counts=dict(direct),affected_source_groups=affected,
                 group_expanded_exclusions=len(denied),denylist_sha256=digest(payload),denied_key="normalized_sha256",
                 split_group_conflicts=split_group_conflicts,duplicate_text_hashes=len(crossings),shards=metrics,
                 limits="Complete decoded text and sentences checked for lexical/shape/anchor overlap and unambiguous explicit numeric operations matching protected calls. This screen cannot establish universal semantic independence.")
    freeze(OUTPUT,payload)
    freeze(PRIVATE/"balanced-continuation-v1-receipt.json",(json.dumps(receipt,indent=2)+"\n").encode())
    print(json.dumps(receipt,indent=2))


if __name__=="__main__":
    screen()

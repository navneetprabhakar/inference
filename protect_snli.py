"""Hash-only overlap audit; original premise/hypothesis direction, labels and votes remain immutable."""
from collections import Counter,defaultdict
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import unicodedata

from protect_split import Shield,PRIVATE,ROOT,DEV,DEV_SHA,SEALED,SEALED_SHA,digest,grams,words
from protect_validation_b import BShield,B_CASES,B_SHA
from protect_human import Reserved, file_sha
from protect_followon import freeze
from protect_continuation import explicit_signatures
from tokenizer import load

DIRECTORY=ROOT/"data/snli-semantic"
TRAIN_SHA="e243539f21faa5bec5fb2f680102bd48d34346e53cfedd4635beea9892d3384a"
VALID_SHA="27f536c77558016f90aba28470abfb409a2e0c1fde4d11aeeef211d3bbe307d9"
MEMBER_SHA="ee95dfbc57800f7b1f62b7602ad2b176c2b983210435a49238e660324a01e963"
def source_norm(text):
    return " ".join(re.findall(r"[a-z0-9]+(?:'[a-z]+)?",unicodedata.normalize("NFKC",text).casefold().replace("’","'")))
def rows(path):
    with path.open() as f:
        for line in f:yield json.loads(line)


def one_edit(a,b):
    if len(b)<len(a):a,b=b,a
    if len(b)-len(a)>1:return False
    if len(a)==len(b):return sum(x!=y for x,y in zip(a,b))<=1
    i=j=0
    while i<len(a) and a[i]==b[j]:i+=1;j+=1
    return a[i:]==b[j+1:]


class Spans:
    def __init__(self):
        self.sequences=[]
        self.exact=set()
        self.eight=set()
        self.three=defaultdict(set)

    def add(self,text):
        w=tuple(words(text))
        if not w or w in self.exact:return
        self.exact.add(w)
        self.eight.update(tuple(w[i:i+8]) for i in range(len(w)-7))
        # Long protected passages are tested via contiguous windows. Short
        # independent statements can also be near repeats with one changed word.
        if 6<=len(w)<=43:
            i=len(self.sequences)
            self.sequences.append(w)
            for j in range(len(w)-2):self.three[w[j:j+3]].add(i)

    def match(self,text):
        w=tuple(words(text))
        if w in self.exact:return "exact_span"
        if any(w[i:i+8] in self.eight for i in range(len(w)-7)):return "copied_8word_span"
        if len(w)<6:return None
        keys={k for j in range(len(w)-2) for k in self.three.get(w[j:j+3],())}
        for i in keys:
            other=self.sequences[i]
            if abs(len(w)-len(other))<=1 and one_edit(w,other):return "one_edit_span"
        return None


def span_indexes(held):
    indices={k:Spans() for k in ("A","B","sealed","legacy_or_human","SNLI_internal")}
    for path,label in ((DEV,"A"),(B_CASES,"B")):
        for c in rows(path):
            for turn in c["turns"]:
                indices[label].add(turn["user"])
                indices[label].add(turn["rubric"])
    for c in rows(SEALED):
        for t in c["user_turns"]+c["criteria"]:indices["sealed"].add(t)
    old=indices["legacy_or_human"]
    for c in rows(ROOT/"reports/dialogue-readiness/counterfactual-dev-v1.jsonl"):
        for m in c["members"]:
            for t in m["history"]:
                if "text" in t:old.add(t["text"])
    for c in rows(ROOT/"runs/astra-dev-v1/cases.jsonl"):
        for t in c["turns"]+c["rubric"]:old.add(t)
    for local in ("squad-training-v1/validation.jsonl","quac-train-v1/internal-validation.jsonl",
                  "quac-train-v1/internal-test.jsonl","taskmaster2/sft-internal-dev.jsonl","taskmaster2/pretrain-only-internal-dev.jsonl"):
        for r in rows(ROOT/"data"/local):
            for m in r["history"]:old.add(m["text"])
            if r.get("context"):old.add(r["context"])
            for q in r.get("questions",[]):old.add(q["question"]);old.add(q["answer"])
    for r in held:
        indices["SNLI_internal"].add(r["premise"]);indices["SNLI_internal"].add(r["hypothesis"])
    return indices


def run():
    fp=DIRECTORY/"train.jsonl"; holdfile=DIRECTORY/"internal-validation.jsonl"
    assert file_sha(fp)==TRAIN_SHA and file_sha(holdfile)==VALID_SHA
    train=list(rows(fp));held=list(rows(holdfile))
    assert len(train)==51415 and len(held)==2754
    assert all(r["split"]=="train" and r["official_split"]=="train" for r in train)
    assert all(r["split"]=="validation" and r["official_split"]=="train" for r in held)
    official={r["official_row"]:r for r in train}
    verified=0;h=hashlib.sha256()
    with (DIRECTORY/"official-train.jsonl").open("rb") as stream:
        for i,line in enumerate(stream):
            h.update(line)
            if i not in official:continue
            r=official[i];s=json.loads(line)
            assert (r["pair_id"],r["caption_id"],r["premise"],r["hypothesis"],r["label"],r["recorded_votes"])==(
                s["pairID"],s["captionID"],s["sentence1"].strip(),s["sentence2"].strip(),s["gold_label"],s["annotator_labels"])
            assert len(s["annotator_labels"])==r["annotation_count"] and set(s["annotator_labels"])=={s["gold_label"]}
            assert r["label"] in ("entailment","neutral","contradiction")
            tier=r["annotation_tier"]
            assert (tier=="single-recorded" and r["annotation_count"]==1) or (tier=="multi-unanimous" and r["annotation_count"]>=3)
            assert r["pair_sha256"]==digest((source_norm(r["premise"])+"\0"+source_norm(r["hypothesis"])).encode())
            verified+=1
    assert verified==len(train) and h.hexdigest()==MEMBER_SHA
    held_ids={k:{r[k] for r in held} for k in ("pair_sha256","pair_id","caption_id","image_id","group")}
    headings={source_norm(r[k]) for r in held for k in ("premise","hypothesis")}
    a,b=Shield(),BShield()
    known=Reserved()
    indexes=span_indexes(held)
    @lru_cache(maxsize=140000)
    def screen_text(text):
        reasons=set()
        for scope,idx in indexes.items():
            hit=idx.match(text)
            if hit:reasons.add(scope+":"+hit)
        for label,idx in (("A_or_sealed",a),("B",b)):
            flags=idx.reasons([dict(role="user",text=text)])
            reasons.update(label+":"+f for f in flags)
            if explicit_signatures(text)&idx.calls:reasons.add(label+":explicit_numeric_signature")
        if digest(source_norm(text).encode()) in known.paragraphs:reasons.add("previous_protected_paragraph_hash")
        return frozenset(reasons)
    direct={};groups_hit=set();counts=Counter();seen_pairs=set();pair_ids=set()
    key_conflicts=Counter()
    for r in train:
        pair=r["pair_sha256"]
        assert pair not in seen_pairs and r["pair_id"] not in pair_ids
        seen_pairs.add(pair);pair_ids.add(r["pair_id"])
        flags=set()
        for k,old in held_ids.items():
            if r[k] in old:flags.add("SNLI_internal:same_"+k);key_conflicts[k]+=1
        for field in ("premise","hypothesis"):
            if source_norm(r[field]) in headings:key_conflicts["exact_source_sentence"]+=1
            flags.update(field+":"+x for x in screen_text(r[field]))
        if flags:
            direct[pair]=flags;counts.update(flags);groups_hit.add(r["group"])
    # Preserve the entire connected image/premise component after a single
    # protected collision; no class/tier corrections and no direction swaps.
    deny=[];strata=defaultdict(Counter);tokenizer=load()
    @lru_cache(maxsize=140000)
    def toklen(text):return len(tokenizer.encode(text).ids)
    eligible_groups=set(); unique_texts={}
    for r in train:
        key=r["annotation_tier"]+"/"+r["label"]
        stats=strata[key];stats["total"]+=1
        if r["group"] in groups_hit:
            deny.append(r["pair_sha256"]);stats["denied"]+=1
            if r["pair_sha256"] in direct:stats["direct_hits"]+=1
        else:
            stats["eligible"]+=1;eligible_groups.add(r["group"])
            stats["eligible_raw_token_positions"]+=toklen(r["premise"])+toklen(r["hypothesis"])
            for k in ("premise","hypothesis"):unique_texts.setdefault(source_norm(r[k]),r[k])
    raw=(json.dumps(sorted(deny),indent=2)+"\n").encode()
    report=dict(state="complete",pool="future auxiliary directed NLI only; no student training or candidate scoring",
                train_sha256=TRAIN_SHA,internal_source_holdout_sha256=VALID_SHA,verified_official_training_member_sha256=MEMBER_SHA,
                verified_original_train_pairs=verified,heldout_metadata_only_pairs=len(held),protected=dict(A=DEV_SHA,B=B_SHA,sealed=SEALED_SHA,
                    additional=known.provenance),checker_sha256=file_sha(Path(__file__)),direct_flagged_pairs=len(direct),
                direct_flags=dict(counts),source_image_or_premise_groups_held=len(groups_hit),source_identity_overlap_checks=dict(key_conflicts),
                all_source_groups=len({r["group"] for r in train}),eligible_source_groups=len(eligible_groups),total=len(train),denied=len(deny),
                approved=len(train)-len(deny),by_annotation_tier_and_label={k:dict(v) for k,v in sorted(strata.items())},
                eligible_unique_norm_input_strings=len(unique_texts),
                eligible_unique_text_token_positions=sum(toklen(t) for t in unique_texts.values()),
                denylist_key="pair_sha256 = SHA-256(normalized premise + NUL + normalized hypothesis); direction preserved",
                denylist_sha256=digest(raw),method="Source pair/image/caption/premise-component and label/vote identity verified; exact sentences, copied 8-word spans, one token edit on 6–43 word protected statements, A/B/sealed protocol near-scenario screens. Propagate any hit to the full source image/premise group.",
                limits="Singletons have only one recorded vote. No unverified label inversions or balanced-class claims. This source supplies directed NLI supervision, not original chat turns; lexical and source-group checks cannot prove universal semantic independence.")
    freeze(ROOT/"reports/snli-semantic/protected-excluded-pair-hashes.json",raw)
    freeze(PRIVATE/"snli-protected-receipt.json",(json.dumps(report,indent=2)+"\n").encode())
    print(json.dumps({k:report[k] for k in ("direct_flagged_pairs","source_image_or_premise_groups_held","source_identity_overlap_checks",
                        "total","approved","denied","by_annotation_tier_and_label","eligible_unique_text_token_positions","denylist_sha256")},indent=2))


if __name__=="__main__":
    run()

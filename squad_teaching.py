"""Prepare train-only, exact-span SQuAD 1.1 histories with article-level holdouts."""
from collections import Counter,defaultdict
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
import random
import re
from urllib.parse import quote,unquote

import pyarrow.parquet as pq

from broad_teaching import checked, jsonlines
from local_chat import encode_frame
from quac_teaching import article_key, known_articles, norm, NOTICE, NOISY, SENSITIVE
from tokenizer import load

ROOT=Path(__file__).resolve().parent
OLD=ROOT.parent/"inference-history-20261021/data"
REPORT=ROOT/"reports/squad-teaching"
OUT=ROOT/"data/squad-training-v1"
REVISION="eee5fdbf62f8613a7812b03419e6b29617b74fd1"
PINS={
    "grounded-qa-intake-v1/train-v1.1.json":"3527663986b8295af4f7fcdff1ba1ff3f72d07d61a20f487cb238a6ef92fd955",
    "grounded-qa-intake-v1/index.pug":"f576095c38cb63a7d110442bdd17bc6877f46a51a96af6d8f06ec09d20ccd886",
    "grounded-qa-groups-v2/eligible.jsonl":"9f4c2135dcf6185c296295677008666cb67ddf470514f25516e44b08b587bf35",
    "grounded-conversations-v1/candidates.jsonl":"5cdd0e46ff0a54be3dd09eb9e884018b7a40e8ee47f793dbf92c3ee1d8650e1d",
    "grounded-conversations-v1/sample.jsonl":"676b170cd4041ee7ca0e96135094a16190669d6d3ddfd21b1a90444f6694f133",
    "grounded-replay-sft-v1/train.jsonl":"3654cf8a29bef4fd10b4817f5f2686730c55aedd6ca37928faee6177bc855771",
}
QUAC_SHA="067c94373d1a622339a73f16032d8060bb5dd989cd8ce2b3647363a8bc1d5b5f"
SALT="astra-squad-group-v1"
SENSITIVE_TITLE=re.compile(r'Beyonc|Chopin|Avicenna|Napoleon|Athanasius|Virgil|Arnold Schwarzenegger|John Kerry|Gamal Abdel|Gaddafi|Elizabeth II|George VI|John von Neumann|John, King|$^',re.I)
JUNK=re.compile(r'\[(?:citation|clarification)|\[\d+\]|\b(?:currently|right now|as of today|according to you)\b|[{}<>]|\.{3}',re.I)
NUM=re.compile(r'\d|\b(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|hundred|thousand|million|dozen|half|quarter|percent)\b',re.I)
YEAR=re.compile(r'\d|\b(?:January|February|March|April|May|June|July|August|September|October|November|December|century|decade|spring|summer|autumn|winter|early|late|after|before|during|year)\b',re.I)
STOP=set("a an the of is are was were be been that did does do which what who whom whose when where how why had has have for to on in at by and or from with as passage article many much number long type name known".split())


# Title admission is explicit. Screening only individual words missed ancestry and
# religious articles during the preliminary source review.
EDUCATIONAL_TITLES = set("""Antenna_(radio) Mosaic Lighting Institute_of_technology Neptune IPod
BBC_Television Bird_migration USB Computer Aspirated_consonant Incandescent_light_bulb
Daylight_saving_time Gothic_architecture Copper BeiDou_Navigation_Satellite_System Elevator
Vacuum List_of_numbered_streets_in_Manhattan Capacitor Macintosh Mandolin Geography_of_the_United_States
Railway_electrification_system Film_speed University Planck_constant Database Comprehensive_school
Royal_Institute_of_British_Architects Wayback_Machine Comics Software_testing Cubism
Textual_criticism Gymnastics University_of_Kansas Estonian_language Group_(mathematics)
Renewable_energy_commercialization Transistor Annelid Nintendo_Entertainment_System
Clothing Literature Exhibition_game Geological_history_of_Earth Imperial_College_London
A_cappella Infrared Glass House_music Hard_rock Insect Post-punk Poultry Marvel_Comics
Xbox_360 Pitch_(music) Matter Gregorian_calendar Russian_language Iranian_languages
London Paris Saint_Helena Mexico_City Houston Portugal Nanjing Oklahoma Montevideo Detroit
Melbourne British_Isles Estonia Montana Miami Alaska Cyprus Sichuan Guam Zhejiang
Guinea-Bissau Norfolk_Island Lancashire Samoa Tristan_da_Cunha Rajasthan Namibia Alsace
Brigham_Young_University University_of_Notre_Dame Yale_University Hokkien""".split())
TOPIC_RISK = re.compile(
    r"\b(?:genetic\w*|racial\w*|multiracial|ancestry|coloniali\w*|indigenous|slave\w*|squaw\w*|"
    r"church\w*|christian\w*|muslim\w*|jewish|judaism|islam\w*|buddhis\w*|hindu\w*|ethnic\w*|"
    r"missionar\w*|catholic\w*|protestant\w*|imperial\w*|governments?|prime minister|ministries|"
    r"monetary|austerity|refugee\w*|conflict\w*|combat\w*|weapons?|battle\w*|earthquake\w*|"
    r"sex\w*|caste|martial|treatment|dosage|corruption|lethal|poison\w*|deport\w*|terror\w*|"
    r"pesticid\w*|hazard\w*|x-rays?|radioactive|radiation|specied|epidemi\w*|stocks?|investment\w*|"
    r"patient\w*|resident population|political|abortion|slaughter\w*|extinct\w*|nickname\w*)\b",re.I)


def digest(text):
    return sha256(text.encode()).hexdigest()


def shingles(text,n):
    words=re.findall(r"\w+",norm(text))
    return {tuple(words[i:i+n]) for i in range(len(words)-n+1)}


def prior_language():
    # Collect only text already used in this branch's supervised mixtures.
    from broad_teaching import records as broad
    from scaled_teaching import records as scaled
    histories=[h for _,h in broad()]+[r["history"] for r in scaled()]
    eight=set()
    for h in histories:
        for m in h:
            eight.update(shingles(m["text"],8))
    return eight


def provenance():
    groups={r["split_group"] for r in jsonlines(OLD/"grounded-conversations-v1/candidates.jsonl")}
    excluded={r["paragraph_component"] for r in jsonlines(OLD/"grounded-replay-sft-v1/train.jsonl")}
    excluded.update(r["record"]["paragraph_component"] for r in jsonlines(OLD/"grounded-conversations-v1/sample.jsonl"))
    if len(groups)!=204:
        raise ValueError("Historical train component frame changed")
    return groups,excluded


def wh_type(question):
    lead=re.match(r'^(what|which|who|whom|whose|when|where|why|how)\b',question.strip(),re.I)
    if not lead:return None
    first=lead[1].lower()
    if first in ("whom","whose"):return "who"
    if re.match(r'^how (many|much|long|far|old|often|large|big|high|tall|fast)\b',question,re.I):return "how-quantity"
    return first


def usable_question(context,qa):
    q=qa["question"].strip()
    category=wh_type(q)
    if not category or not q.endswith("?") or not 4<=len(q.split())<=26:return None
    if SENSITIVE.search(q) or NOISY.search(q) or JUNK.search(q):return None
    refs=qa["answers"]
    if not refs:return None
    for ans in refs:
        start=ans["answer_start"];value=ans["text"]
        if start<0 or context[start:start+len(value)]!=value:return None
    ans=refs[0];v=ans["text"]
    if not v.strip() or v!=v.strip() or len(v.split())>12 or len(v)>90 or v.casefold() in STOP:return None
    if norm(v) in norm(q) and len(v)>4:return None
    if category=="how-quantity" and not NUM.search(v):return None
    if category=="when" and not YEAR.search(v):return None
    if category in ("who","where") and not re.search(r'\b[A-Z][\w-]+',v):return None
    if category=="why" and not re.search(r'\b(because|due to|since|to|for|so|as a result)\b',v,re.I):return None
    # Exclude ambiguous substrings or arbitrary fragments inside words.
    start=ans["answer_start"];end=start+len(v)
    if (start and context[start-1].isalnum() and v[0].isalnum()) or (
            end<len(context) and context[end].isalnum() and v[-1].isalnum()):return None
    return dict(id=qa["id"],question=q,answer=v,answer_start=start,answer_end=end,wh=category)


def split(group):
    return "validation" if int(digest(SALT+":"+group)[:12],16)%10==0 else "train"


def build():
    REPORT.mkdir(exist_ok=True)
    OUT.mkdir(exist_ok=False)
    for name,pin in PINS.items():checked(OLD/name,pin)
    if "CC BY-SA 4.0" not in (OLD/"grounded-qa-intake-v1/index.pug").read_text():
        raise ValueError("Missing dataset license reference")
    src=json.loads((OLD/"grounded-qa-intake-v1/train-v1.1.json").read_text())
    if src["version"]!="1.1" or len(src["data"])!=442:raise ValueError("Unexpected raw SQuAD training split")
    tok=load()
    blocked=known_articles()
    quac_path=checked(ROOT/"data/quac-train-v1/train.parquet",QUAC_SHA)
    qtitles=pq.read_table(quac_path,columns=["wikipedia_page_title"],use_threads=False).column(0).to_pylist()
    blocked.update(article_key(t) for t in qtitles)
    shared_eight=prior_language()
    groups,excluded=provenance()
    # Whole articles are excluded for any training overlap from other branch sources.
    eligible=list(jsonlines(OLD/"grounded-qa-groups-v2/eligible.jsonl"))
    input_groups=defaultdict(set)
    for r in eligible:
        if r["split_group"] in groups and shingles(r["context"],8)&shared_eight:
            input_groups[r["split_group"]].add("previous_branch_word_overlap")
    hashed=set()
    found=[]
    counts=Counter()
    for row in eligible:
        gid=row["split_group"]
        if gid not in groups or row["official_split"]!="train" or gid in input_groups:
            counts["prior_partition_or_other_training_overlap"]+=1
            continue
        if row["paragraph_component"] in excluded:
            counts["previous_replay_or_review_paragraph"]+=1
            continue
        title=row["article"]
        if article_key(title) in blocked or SENSITIVE_TITLE.search(unquote(title).replace("_"," ")) or SENSITIVE.search(unquote(title).replace("_"," ")):
            counts["cross_source_or_sensitive_article"]+=1
            continue
        raw_article=src["data"][row["article_index"]]
        raw=raw_article["paragraphs"][row["paragraph_index"]]
        ctx=raw["context"]
        if raw_article["title"]!=title or ctx!=row["context"] or digest(json.dumps(ctx,ensure_ascii=False,separators=(",",":")))!=row["source_paragraph_sha256"]:
            raise ValueError("Original paragraph identity differs")
        if SENSITIVE.search(ctx) or NOTICE.search(ctx) or NOISY.search(ctx) or JUNK.search(ctx):
            counts["paragraph_content_or_notice"]+=1
            continue
        if not 28<=len(tok.encode(ctx).ids)<=200:
            counts["paragraph_length"]+=1
            continue
        if digest(norm(ctx)) in hashed:raise ValueError("Duplicate eligible paragraph escaped historical grouping")
        hashed.add(digest(norm(ctx)))
        items=[item for qa in raw["qas"] if (item:=usable_question(ctx,qa)) is not None]
        # Stable selection, at most three distinct original Q/A pairs per paragraph.
        items.sort(key=lambda item:digest(SALT+item["id"]))
        chosen=[]
        while items and len(chosen)<3:
            taken_types={item["wh"] for item in chosen}
            i=next((j for j,t in enumerate(items) if t["wh"] not in taken_types),0)
            item=items.pop(i)
            if any(norm(item["answer"])==norm(other["answer"]) or item["question"].casefold()==other["question"].casefold() for other in chosen):continue
            chosen.append(item)
        if not chosen:
            counts["no_suitable_QA"]+=1
            continue
        history=[]
        for i,item in enumerate(chosen):
            prompt=f"Passage:\n{ctx}\n\n{item['question']}" if i==0 else item["question"]
            history.extend((dict(role="user",text=prompt),dict(role="assistant",text=item["answer"])))
        length=0
        for message in history:
            body={"text":message["text"]} if message["role"]=="assistant" else message["text"]
            hdr,tokens=encode_frame(tok,message["role"],body)
            length+=len(hdr)+len(tokens)
        if length>420:counts["serialized_length"]+=1;continue
        found.append(dict(group=gid,article=title,article_url="https://en.wikipedia.org/wiki/"+quote(unquote(title),safe="_()"),
                          dataset_revision=REVISION,official_split="train",split=split(gid),context=ctx,context_sha256=digest(ctx),
                          paragraph_index=row["paragraph_index"],article_index=row["article_index"],paragraph_component=row["paragraph_component"],
                          questions=chosen,history=history,input_tokens=length-1,history_sha256=digest(json.dumps(history,ensure_ascii=False,sort_keys=True))))
    found.sort(key=lambda x:x["history_sha256"])
    raw_receipt=dict(source_pins=PINS,quac_source_sha=QUAC_SHA,old_train_article_components=len(groups),excluded_prior_paragraphs=len(excluded),
                     cross_source_word_overlap_groups=len(input_groups),excluded_title_count=len(blocked),counts=counts,
                     source="SQuAD v1.1 by Rajpurkar, Zhang, Lopyrev and Liang; crowdworker questions about Wikipedia paragraphs",license="CC BY-SA 4.0",
                     transformation="Original paragraphs and answer offsets, at most three distinct answers/questions per paragraph; new framing and group split.")
    (OUT/"candidates.jsonl").write_text("".join(json.dumps(r,ensure_ascii=False)+"\n" for r in found))
    (OUT/"intake.json").write_text(json.dumps(raw_receipt,indent=2)+"\n")
    print("candidate histories",len(found),"answers",sum(len(r["questions"]) for r in found),"train",sum(r["split"]=="train" for r in found))


def safe_for_review(r):
    text=" ".join([r["context"]]+[item["question"] for item in r["questions"]])
    return (r["article"] in EDUCATIONAL_TITLES and not TOPIC_RISK.search(text)
            and r["context"].rstrip().endswith((".", "!", "?", '."', ".”"))
            and not re.search(r'[|]|\b\w+\(\s*[,)]',r["context"]))



def secondary_questions(row):
    # Some gold spans omit modifiers that materially change the answer. Exclude
    # these turns and additionally require a direct location cue for WHERE.
    out=[]
    for q in row["questions"]:
        left=row["context"][max(0,q["answer_start"]-40):q["answer_start"]]
        if re.search(r"(?:over[- ]|under[- ]|nearly |roughly |at (?:least|most) |fewer than |approximately |almost |less than |more than |up to |near (?:the )?|about )$",left,re.I):
            continue
        if q["wh"]=="where":
            if not re.search(r"\b(?:in|at|from|into|within|through|on|headquartered at|located in|part of|outside|inside) (?:the )?$",left,re.I):
                continue
            if re.search(r"relative to|in relation to",q["question"],re.I):
                continue
        out.append(q)
    return out


def with_questions(row,questions):
    if not questions:return None
    result=dict(row)
    result["questions"]=questions
    history=[]
    for index,q in enumerate(questions):
        text=f"Passage:\n{row['context']}\n\n{q['question']}" if index==0 else q["question"]
        history.extend((dict(role="user",text=text),dict(role="assistant",text=q["answer"])))
    result["history"]=history
    result["history_sha256"]=digest(json.dumps(history,ensure_ascii=False,sort_keys=True))
    tok=load_tokenizer()
    n=0
    for m in history:
        value={"text":m["text"]} if m["role"]=="assistant" else m["text"]
        header,body=encode_frame(tok,m["role"],value)
        n+=len(header)+len(body)
    result["input_tokens"]=n-1
    return result


@lru_cache(maxsize=1)
def load_tokenizer():
    return load()


def sample_for_review():
    by_type=defaultdict(list)
    for row in jsonlines(OUT/"candidates.jsonl"):
        if row["split"]=="train" and safe_for_review(row):
            for item in row["questions"]:by_type[item["wh"]].append((row,item))
    result=[]
    for typ,group in sorted(by_type.items()):
        group.sort(key=lambda pair:digest("astra-squad-human-review-1"+pair[1]["id"]))
        for r,q in group[:4]:
            result.append(dict(wh=typ,id=q["id"],paragraph_sha=r["context_sha256"],article=r["article"],
                               question=q["question"],answer=q["answer"],passage=r["context"]))
    return result


def freeze():
    policy=json.loads((REPORT/"review.json").read_text())
    banned=set(policy["held_paragraph_hashes"]);exclude_types=set(policy["held_wh_types"])
    counts={}
    article_groups=defaultdict(set)
    candidates=list(jsonlines(OUT/"candidates.jsonl"))
    candidates=[new for r in candidates if safe_for_review(r) and r["context_sha256"] not in banned
                and (new:=with_questions(r,[q for q in secondary_questions(r) if q["wh"] not in exclude_types])) is not None]
    for part in ("train","validation"):
        rows=[r for r in candidates if r["split"]==part and r["context_sha256"] not in banned and not any(
            item["wh"] in exclude_types for item in r["questions"])]
        for r in rows:
            article_groups[part].add(r["group"])
            assert r["split"]==split(r["group"])
            for item in r["questions"]:assert r["context"][item["answer_start"]:item["answer_end"]]==item["answer"]
        dest=OUT/(part+".jsonl")
        dest.write_text("".join(json.dumps(r,ensure_ascii=False,sort_keys=True)+"\n" for r in rows))
        counts[part]=dict(histories=len(rows),questions=sum(len(r["questions"]) for r in rows),max_input_tokens=max(r["input_tokens"] for r in rows),
                          input_tokens=sum(r["input_tokens"] for r in rows),articles=len({r["article"] for r in rows}),groups=len(article_groups[part]),
                          wh_types=Counter(item["wh"] for r in rows for item in r["questions"]),multi_turn=sum(len(r["questions"])>1 for r in rows),
                          sha256=sha256(dest.read_bytes()).hexdigest())
    assert not article_groups["train"]&article_groups["validation"]
    receipt=dict(splits=counts,script_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
                 candidate_sha256=sha256((OUT/"candidates.jsonl").read_bytes()).hexdigest(),
                 review_sha256=sha256((REPORT/"review.json").read_bytes()).hexdigest(),intake=json.loads((OUT/"intake.json").read_text()),
                 status="Training-only selection, pending separate protected-case custody; evaluation cases never read here.")
    (REPORT/"receipt.json").write_text(json.dumps(receipt,indent=2)+"\n");print(json.dumps(counts,indent=2))


@lru_cache(maxsize=1)
def records():
    receipt=json.loads((REPORT/"receipt.json").read_text())
    raw=checked(OUT/"train.jsonl",receipt["splits"]["train"]["sha256"])
    rows=list(jsonlines(raw))
    if any(r["official_split"]!="train" or split(r["group"])!="train" or r["split"]!="train" for r in rows):
        raise ValueError("Unexpected SQuAD split")
    return rows


def examples(seed):
    rows=[json.loads(json.dumps(r["history"])) for r in records()]
    random.Random(seed).shuffle(rows)
    return rows


if __name__=="__main__":
    import sys
    {"build":build,"freeze":freeze}[sys.argv[1]]()

"""An audited, offline natural instruction pool from named training splits."""
from collections import defaultdict
from copy import deepcopy
from functools import lru_cache
from hashlib import sha256
import json
import random
import re
import unicodedata

from broad_teaching import DATA, DOLLY_DIR, DOLLY_SHA, OASST_DIR, OASST_SHA, MAP_SHA, NEGATIVE_LABELS, ROOT, checked, jsonlines, message

REPORT = ROOT / "reports/scaled-teaching"
EVERYDAY_SHA = "4750214d12b4b92d07fca953e0b5cc59e313c575282d08b605c639aa87531daa"
TOPICS = {
    "everyday-practical": {"Home", "Education", "Technology", "Work", "everyday objects", "communication", "Shopping"},
    "everyday-creative": {"Hobbies", "Music", "Fashion", "Entertainment", "arts and music", "culture", "Family", "language"},
    "everyday-science": {"basic math concepts", "physics basics", "measurement", "shapes", "colors", "forces",
                        "geography", "space", "sound", "light", "time", "matter", "numbers", "water cycle",
                        "earth", "plants", "simple machines", "seasons", "energy", "astronomy", "ecosystems",
                        "magnets", "life cycles", "food chains", "geology", "chemistry basics", "animals"},
    "everyday-leisure": {"Sports", "Cooking", "Food", "history"},
}
RISK = re.compile(
    r'https?://|www\.|[\w.+-]+@[\w.-]+|\b\d{3}[-. ]\d{3}[-. ]\d{4}\b|'
    r'\b(?:abuse\w*|addict\w*|alcohol\w*|anxiet\w*|bomb\w*|blood|cancer|celebrity|diagnos\w*|'
    r'diet\w*|diseas\w*|doctor|drug\w*|explo[s]\w*|financ\w*|firearm\w*|gun\w*|hiv|insurance|'
    r'invest\w*|lawyer|legal\w*|medicin\w*|medical\w*|mental health|murder\w*|patient\w*|politic\w*|'
    r'president|racial|religio\w*|suicid\w*|terror\w*|therap\w*|treatments?|unsafe|vaccin\w*|'
    r'violent|violence|weapon\w*|weight loss|wire transfer|password\w*|phone number|taxes|'
    r'sex\w*|rape|nazi\w*|execution|enslav\w*|warfare|earthquake|cook.+(?:chicken|pork|beef)|'
    r'bleach|electroc\w*|carbon monoxide|asthma|pregnan\w*|divorc\w*|poison\w*|prescription\w*|'
    r'psycholog\w*|psychiatr\w*|criminal|prosecut\w*|calorie\w*|burn\w*|mold|gunpowder|phishing)\b', re.I)
FABRICATED = re.compile(
    r"\b(?:I|we)(?:'ve|’ve| have)?\s+(?:personally|recently|usually|often|once|visited|traveled|tried|grew up|"
    r"love|like|enjoy|prefer|remember when|own|live|bought|watched|played|use|wear|work at|used to|am wearing)\b|"
    r"\b(?:my|our) (?:favorite|favourite|family|friend|parents?|children|kids|home|birthday|pet|dog|cat|"
    r"husband|wife|school|job|hometown|company|website|products?|store|team|business|experience)\b|"
    r"\b(?:I|we)(?:'ll|’ll| will| can| have| just)\s+(?:book|notify|order|reserve|track|monitor|alert|remind|send|"
    r"show you|schedule|call|contact|access|ship|deliver|check your|look (?:that|it) up|look up|search for you)\b|"
    r"\b(?:I|we) (?:offer|sell|stock|guarantee|provide a warranty|carry|have .*in stock)\b|\b(?:as an ai|as an assistant)\b", re.I)
VOLATILE = re.compile(r'\b(?:current(?:ly)?|latest|right now|breaking news|today.s|tomorrow.s|local forecast|'
                      r'near me|this weekend|on sale|available now|stock market|most popular|most visited|ranked number one)\b',re.I)
LOCAL_OR_HEALTH = re.compile(
    r"\b(?:in (?:my|your|our|the) area|nearby|neighbou?rhood|local (?:store|park|concert|event|festival|library|station|bus|route|weather)|this (?:season|year|summer|winter|week|month)|"
    r"tonight|forecast|season.s popular|opening hours|how much does .*cost|tickets?|traffic (?:lights?|signals?)|"
    r"vet(?:erinar\w*)?|pet food|health\w*|nutriti\w*|cholesterol|superfoods?|allerg\w*|medicat\w*|"
    r"insomnia|ears? infect\w*|cholesterol|free trial|sale|scan(?:ning)? (?:a page|text)|"
    r"passports?|census records|feel (?:dizzy|pain)|do you (?:own|have|live|wear|use|personally|enjoy)|"
    r"where (?:are you|do you live)|I(?:'m|’m| am) (?:wearing|from|a (?:big )?fan|a member)|we (?:have (?:a|an|several)|host)|local|in our area|alert you|remind you|track (?:your|my) expenses|transport schedule|safety|oldest sport|most widely celebrated|capital of|in stock|happening soon|average.{0,20}days|price|pricing|costs?|selling|concerts?|festival|transportation fares|popular types of|danger|vet|pot roast|tender meat|oiling|oil changes|oil change|car trouble|floor lamps?)\b", re.I)
SENSITIVE_HISTORY = re.compile(r"\b(?:civil war|massacre|genocide|NATO|annex|invasion|elections?|presidential|hunger strike|suicide|alleged|allegations|convicted|capital punishment|murder|victims?|killed|terrorism|violent)\b", re.I)
STOP = set("a an and the is are was were to for in at on from of this that as by it its who which be when where with they their what about name there how only the passage text reference provided according answer".split())


def normalized(text):
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def tokens(text):
    return set(re.findall(r"[\w'-]+", normalized(text))) - STOP


def digest(text):
    return sha256(text.encode()).hexdigest()


def prompt_ok(history):
    for m in history:
        text = m["text"]
        if not text or RISK.search(text) or VOLATILE.search(text) or len(text) > 1800:
            return False
        if any(c in text for c in ("<|", "[assistant]", "[tool]", "[system]", "\ufffd", "http://", chr(96)*3)):
            return False
        if m["role"] == "assistant" and FABRICATED.search(text):
            return False
    return True


def everyday_records(excluded):
    import pyarrow.parquet as pq
    source = checked(ROOT / "data/everyday/train.parquet", EVERYDAY_SHA)
    rows = pq.read_table(source, use_threads=False).to_pylist()
    if len(rows) != 2260:
        raise ValueError("Unexpected Everyday train row count")
    strata = {topic: name for name, topics in TOPICS.items() for topic in topics}
    for index, r in enumerate(rows):
        if index in excluded or r["topic"] not in strata:
            continue
        turns = r["messages"][2:6]
        if [m["role"] for m in turns] != ["user", "assistant", "user", "assistant"]:
            continue
        history = [message(m["role"],m["content"]) for m in turns]
        if any(LOCAL_OR_HEALTH.search(m["text"]) for m in history):
            continue
        if strata[r["topic"]]=="everyday-practical" and not re.search(
                r"how (?:can|should|do|could)|tips|organize|organizing|looking for ideas|help me|trouble|trying to|suggestions",
                " ".join(m["text"] for m in history if m["role"]=="user"), re.I):
            continue
        if not prompt_ok(history) or any(not 3 <= len(m["text"].split()) <= 70 for m in history):
            continue
        if normalized(history[0]["text"]) == normalized(history[2]["text"]):
            continue
        yield dict(source="everyday", id=str(index), topic=r["full_topic"], stratum=strata[r["topic"]], history=history)


@lru_cache(maxsize=1)
def dolly_train_pairs():
    stage = DATA / "complete-small-source-v1/staged"
    manifest = json.loads((stage/"manifest.json").read_text())["files"]
    pairs = set()
    for shard in sorted(stage.glob("train-*.jsonl")):
        for row in jsonlines(checked(shard, manifest[shard.name])):
            if row["source"] == "databricks/databricks-dolly-15k" and row["official_split"] == row["split"] == "train":
                q = row["messages"][0]["content"].split("\n\nContext:\n")[0]
                pairs.add((q.strip(), row["messages"][-1]["content"].strip()))
    return pairs


WRITING = re.compile(r"\b(?:write|compose|design|poem|limerick|letter|joke|make up|invent|imagine|story|name for|tagline|slogan|describe|caption|dialogue|create a|email|e-mail|haiku)\b",re.I)
IDEAS = re.compile(r"\b(?:ideas?|uses|suggest|brainstorm|ways to|what can|how (?:can|could)|fun things|possible|titles?|names?)\b",re.I)
CLASS = re.compile(r"\b(?:classify|group|categorize|separate|sort|which (?:of these|of the following))\b",re.I)
CATEGORIES = re.compile(r"\b(?:fruits?|vegetables?|instruments?|colors?|colours?|animals?|birds?|mammals?|reptiles?|solids?|liquids?|gases?|odd|even|vowels?|consonants?|prim(?:e|ary)|planets?|stars?|numbers?|shapes?|tools?|materials?|sports?|metals?|woods?|grammatical|adjectives?|nouns?|verbs?|adverbs?|furniture|rooms?|natural|man.?made|alphabetical|countries|continents|plants?|trees|cities|vehicles)\b",re.I)
OUTLIER = re.compile(r"\b(?:diet|health\w*|train(?:ing)? for|workout|fat|toxic|climate model|electri\w*|medical|medicine|physical condition|financial|home security|private|stock|shortage|vandal\w*|sex\w*|indecent|cigarettes?|whisky|whiskey|weed|marijuana|opioid|harm\w*|exploit\w*|bomb|bare hands|cheat|who (?:won|is the)|best|most successful|recommended|famous|latest|president|movie titles? from|historical figures|wife|gun|discrimination|religion|political|actresses|singers?|poison|biological|exercises?|famine|exam questions)\b",re.I)


def dolly_open_records(excluded):
    raw=checked(DOLLY_DIR/"rows.jsonl",DOLLY_SHA)
    train=dolly_train_pairs()
    for index,row in enumerate(jsonlines(raw)):
        q=row["instruction"].strip()
        a=row["response"].strip()
        c=row["category"]
        if index in excluded or row["context"].strip() or (q,a) not in train:
            continue
        if not 5<=len(q.split())<=55 or not 3<=len(a.split())<=70 or q.count("?")>1:
            continue
        combined=q+" "+a
        if OUTLIER.search(combined) or LOCAL_OR_HEALTH.search(combined) or SENSITIVE_HISTORY.search(combined):
            continue
        h=[message("user",q),message("assistant",a)]
        if not prompt_ok(h):
            continue
        if c=="creative_writing" and WRITING.search(q) and not re.search(r"haiku|review|raven|advertis|scariest|\bin the style of\b",q,re.I):
            stratum="dolly-original-writing"
        elif c=="brainstorming" and IDEAS.search(q) and not re.search(r"\b(?:real|known|companies|names of|schools|countries|countries in|why did|name (?:some|five|the)|titles of|films|league|asteroid|comet)\b",q,re.I):
            stratum="dolly-open-ideas"
        elif c=="classification" and CLASS.search(q) and CATEGORIES.search(q):
            stratum="dolly-classification"
        else:
            continue
        yield dict(source="dolly",id=str(index),topic=c,stratum=stratum,history=h)


def dolly_records(excluded):
    raw = checked(DOLLY_DIR/"rows.jsonl", DOLLY_SHA)
    train = dolly_train_pairs()
    raw_rows = list(jsonlines(raw))
    prior_contexts = {normalized(raw_rows[index]["context"]) for index in excluded}
    groups = defaultdict(list)
    for index, r in enumerate(raw_rows):
        if index in excluded or r["category"] not in {"closed_qa","summarization","information_extraction"}:
            continue
        q,c,a = (r[k].strip() for k in ("instruction","context","response"))
        if (q,a) not in train or not 3 <= len(q.split()) <= 70 or not 12 <= len(c.split()) <= 170 or not 1 <= len(a.split()) <= 60:
            continue
        if normalized(c) in prior_contexts or SENSITIVE_HISTORY.search(c) or "[citation needed]" in c:
            continue
        if r["category"] == "closed_qa" and (
            q.count("?") > 1 or re.search(r"\band (?:when|where|who|what|how|which)\b", q, re.I)
            or re.search(r"\b(?:largest|tallest|fastest|oldest|most|highest|first in the world|nationality|ethnic|nationalities)\b", q, re.I)
            or (q.lower().startswith("what is") and len(a.split())<7 and normalized(a) not in normalized(c))
            or len(a.split()) > 38 or a.endswith((",", ";", ":"))
        ):
            continue
        if r["category"]=="information_extraction":
            if len(a.split())>28 or re.search(r"\b(?:all|what are the|largest|tallest|oldest|most|nationalit\w*|race|religion)\b",q,re.I):
                continue
            if normalized(a).strip(" .") not in normalized(c):
                # List members must occur literally, not just distribute their component words through a paragraph.
                values=[part.strip(" .") for part in re.split(r",|\n| and ", a.casefold())]
                if len(values)<2 or any(not v or v not in c.casefold() for v in values):
                    continue
        history = [message("user",f"Passage:\n{c}\n\n{q}"),message("assistant",a)]
        if not prompt_ok(history) or len(c)>1500 or re.search(r'\b(?:best|greatest|worst|richest|wealt\w*)\b',q,re.I):
            continue
        answer = tokens(a)
        support = tokens(c)
        # Numbers must occur in the passage. Require most content words to occur
        # there too; the sample audit checks whether the question is answered.
        if not answer or not set(re.findall(r'\d+',a)) <= set(re.findall(r'\d+',c)):
            continue
        extras = answer-support
        if len(extras)>2 or len(extras)>.16*len(answer):
            continue
        groups[normalized(c)].append((index,r["category"],q,a,history))
    for key, group in groups.items():
        group.sort(key=lambda x:digest("dolly-source-v1:"+str(x[0])))
        first = group[0]
        history = list(first[4])
        ids = [first[0]]
        for row in group[1:]:
            if normalized(row[2]) != normalized(first[2]) and normalized(row[3])!=normalized(first[3]):
                history.extend((message("user",row[2]),message("assistant",row[3])))
                ids.append(row[0])
                break
        yield dict(source="dolly", id="+".join(map(str,ids)), topic=digest(key)[:16],
                   stratum="dolly-"+first[1],history=history)


OASST_CREATIVE = re.compile(r"\b(?:write|compose|generate|give|tell|create|imagine|suggest|invent|continue|make|think of)\b.*?\b(?:poem|story|riddle|limerick|joke|dialogue|name|slogan|caption|list|metaphor|analogy|ideas|titles?)\b", re.I|re.S)
OASST_EDIT = re.compile(r"\b(?:rewrite|rephrase|paraphrase|spelling|grammar|fix (?:my|this) sentence|summari[sz]e|shorten|sort|alphabetical|translate|synonyms?|antonyms?|in other words|in a sentence)\b",re.I)
OASST_PRACTICAL = re.compile(r"\b(?:how (?:do|can|would|should)|what (?:can|should)|tips (?:for|to)|help me|what is (?:a good|the difference)|could you (?:help|give)|give me (?:advice|tips))\b",re.I)
OASST_SKIP = re.compile(r"\b(?:software versions?|install|command|execute|shell|terminal|deploy|crypto|diet|workouts?|exercise|psycholog\w*|argument with|recipe for|credentials?|vpn|server|database|machine learning|AI model|latest|election|party leader|think of me|who are you|my (?:girlfriend|wife|husband|address)|take the role|pretend to be|in the style of|copyright|lyrics|emergency|interview question|online shop)\b",re.I)
OASST_NONFICTION = re.compile(r"\b(?:electri\w*|chemical\w*|financial|pharm\w*|gasoline|incendiary|disappear|illegal|violent|weapons?|fire|computer virus|exploits?|breach|identity document|licen[sc]e plate|prescription|racis\w*|car maintenance|surgery|fasting|in (?:New York|London|Berlin))\b",re.I)


def oasst_records():
    stage=DATA/"iteration-two-dialogue-preparation-v1/staged"
    manifest=json.loads((stage/"manifest.json").read_text())["files"]
    training_trees=set()
    for shard in sorted(stage.glob("train-*.jsonl")):
        for row in jsonlines(checked(shard,manifest[shard.name])):
            if row["source"]=="OpenAssistant/oasst2" and row["split"]==row["official_split"]=="train":
                training_trees.add(row["lineage"][0])
    previous=json.loads((ROOT/"reports/broad-teaching/selection.json").read_text())
    known={s["tree"] for s in previous if s["source"]=="oasst"}
    known.update(r["tree"] for r in jsonlines(ROOT/"reports/chat-teaching/oasst-selected.jsonl"))
    splits=json.loads(checked(DATA/"iteration-two-oasst2-partitions-v1/mapping.json",MAP_SHA).read_text())

    def eligible(node,role):
        text=node["text"].strip()
        return (node["lang"]=="en" and node["role"]==role and node["review_result"] is True
                and node["deleted"] is False and node["synthetic"] is False and 2<=len(text.split())<=85
                and all(node["labels"].get(k,{}).get("value",0)==0 for k in NEGATIVE_LABELS)
                and (role=="prompter" or node["labels"].get("quality",{}).get("value",0)>=.6))

    for tree in jsonlines(checked(OASST_DIR/"trees.jsonl",OASST_SHA)):
        tid=tree["message_tree_id"]
        if tid not in training_trees or tid in known or splits[tid]["split"]!="train":
            continue
        root=tree["prompt"]
        if not eligible(root,"prompter"):
            continue
        q=root["text"].strip()
        if OASST_EDIT.search(q):
            stratum="oasst-edit"
        elif OASST_CREATIVE.search(q):
            stratum="oasst-creative"
        elif OASST_PRACTICAL.search(q):
            stratum="oasst-practical"
        else:
            continue
        paths=[]
        for answer in root["replies"]:
            if answer["parent_id"]!=tid or not eligible(answer,"assistant"):
                continue
            history=[message("user",q),message("assistant",answer["text"])]
            joined=" ".join(m["text"] for m in history)
            if not prompt_ok(history) or LOCAL_OR_HEALTH.search(joined) or OASST_SKIP.search(joined) or OASST_NONFICTION.search(joined):
                continue
            score=answer["labels"]["quality"]["value"]
            paths.append((0,score,answer["message_id"],history))
            for b in answer["replies"]:
                if b["parent_id"]!=answer["message_id"] or not eligible(b,"prompter"):
                    continue
                for z in b["replies"]:
                    if z["parent_id"]!=b["message_id"] or not eligible(z,"assistant"):
                        continue
                    longer=history+[message("user",b["text"]),message("assistant",z["text"])]
                    joined=" ".join(m["text"] for m in longer)
                    if prompt_ok(longer) and not any(rx.search(joined) for rx in (LOCAL_OR_HEALTH,OASST_SKIP,OASST_NONFICTION)) and len(joined.split())<175:
                        paths.append((1,min(score,z["labels"]["quality"]["value"]),z["message_id"],longer))
        if paths:
            turns,quality,reply,history=max(paths,key=lambda x:x[:3])
            yield dict(source="oasst",id=reply,topic=tid,stratum=stratum,history=history)


SMOLTALK_SHA="8161a0a428a1fbcb89551578cd3c84f3d869780bb8f93db3e35512ae25534259"
MAGPIE_SKIP=re.compile(r"\b(?:assume the role|pretend|acting as|play the role|you're an? (?:expert|senior)|you are an? (?:expert|senior)|as if you were|impersonate|kitchen knife|deliberately|secretly|foreign policy|worldwide sales|article mentions|news today|calendar appointment|at my location|access my|from your own experience|my (?:wife|husband|boss)|your (?:own |personal )?experience|based on your own)\b",re.I)
MAGPIE_EXPLAIN=re.compile(r"\b(?:explain|difference between|in simple terms|how does|how do|in your own words|what is the difference|why does|analogy|for beginners|for a child|give me an example)\b",re.I)
MAGPIE_WRITE=re.compile(r"\b(?:rewrite|rephrase|edit|brainstorm|ideas|suggest names|give me some names|short story|poem|create an example|shorter|in a sentence|more concise|draft a|more formal|change the|generate a title)\b",re.I)
NAME=re.compile(r"\b(?:[A-Z][a-z]+(?: [A-Z][a-z]+)+|[A-Z]{2,})\b")


def smoltalk_records():
    train_path=checked(DATA/"conversation-parquet-intake-v3/train.jsonl",SMOLTALK_SHA)
    for row in jsonlines(train_path):
        if row["official_split"]!="train":
            raise ValueError("SmolTalk split mismatch")
        src=row["source"]
        messages=row["messages"]
        if src=="smollm-rewrite-30k" and [m["role"] for m in messages]==["system","user","assistant"]:
            instruction=messages[0]["content"]
            start=instruction.find("Rewrite the input text")
            if start<0:
                continue
            instruction=instruction[start:]
            draft=messages[1]["content"].strip()
            answer=messages[2]["content"].strip()
            if not 15<=len(draft.split())<=180 or not 6<=len(answer.split())<=145:
                continue
            bodies=draft+" "+answer
            if RISK.search(bodies) or SENSITIVE_HISTORY.search(bodies) or MAGPIE_SKIP.search(bodies) or OASST_NONFICTION.search(bodies):
                continue
            if set(re.findall(r"\d+",answer))-set(re.findall(r"\d+",draft)):
                continue
            named_words={word.casefold() for phrase in NAME.findall(answer) for word in phrase.split()
                         if word.casefold() not in {"dear","hi","hello","thank","you","thanks","best","regards",
                                                    "kind","sincerely","hey","subject","to","from","the","at","re","us"}}
            if named_words-set(re.findall(r"\w+",draft.casefold())) or re.search(r"(?<!\w)@\w+|#\w+",bodies):
                continue
            if normalized(draft)==normalized(answer) or len(tokens(answer)&tokens(draft))/max(1,len(tokens(answer)))<.45:
                continue
            # In this task a first-person response is explicitly a rewrite of the quoted draft.
            history=[message("user",instruction+"\n\nDraft:\n"+draft),message("assistant",answer)]
            if any(marker in bodies for marker in ("<|","[assistant]","[system]","\ufffd",chr(96)*3)):
                continue
            stratum="smoltalk-rewrite"
        elif src=="smol-magpie-ultra-short":
            turns=messages[:4]
            if [m["role"] for m in turns]!=["user","assistant","user","assistant"]:
                continue
            history=[message(m["role"],m["content"]) for m in turns]
            if not prompt_ok(history) or any(not 3<=len(m["text"].split())<=75 for m in history):
                continue
            combined=" ".join(m["text"] for m in history)
            if len(combined.split())>175 or any(rx.search(combined) for rx in (MAGPIE_SKIP,OASST_SKIP,OASST_NONFICTION,LOCAL_OR_HEALTH,SENSITIVE_HISTORY)):
                continue
            q=history[0]["text"]+" "+history[2]["text"]
            if MAGPIE_WRITE.search(q):
                stratum="smoltalk-writing-dialogue"
            elif MAGPIE_EXPLAIN.search(q):
                stratum="smoltalk-explanation-dialogue"
            else:
                continue
        else:
            continue
        yield dict(source="smoltalk",id=str(row["row_index"]),topic=src,stratum=stratum,history=history)


@lru_cache(maxsize=1)
def eligible_records():
    previous = json.loads((ROOT/"reports/broad-teaching/selection.json").read_text())
    previous_rows = {i for rec in previous if rec["source"]=="dolly" for i in rec["rows"]}
    everyday_ids = {int(r["row_id"]) for r in jsonlines(ROOT/"reports/chat-teaching/everyday-selected.jsonl")}
    records = []
    seen = set()
    for source in (everyday_records(everyday_ids),dolly_records(previous_rows),dolly_open_records(previous_rows),oasst_records(),smoltalk_records()):
        for rec in source:
            signature = tuple(normalized(m["text"]) for m in rec["history"])
            if signature not in seen:
                records.append(rec)
                seen.add(signature)
    return records


@lru_cache(maxsize=1)
def records():
    policy=json.loads((REPORT/"admission.json").read_text())
    approved=set(policy["admitted_strata"])
    held=set(policy["held_records"])
    reviewed=set(policy["individually_admitted"])
    accepted=[]
    seen_prompt=set()
    seen_grams=[]
    for row in eligible_records():
        identity=f"{row['source']}:{row['id']}"
        if identity in held or (identity not in reviewed and row["stratum"] not in approved):
            continue
        all_users=" ".join(normalized(t["text"]) for t in row["history"] if t["role"]=="user")
        if all_users in seen_prompt:
            continue
        words=all_users.split()
        grams=frozenset(tuple(words[i:i+5]) for i in range(len(words)-4))
        if grams and any(len(grams & prior) >= .8*max(len(prior),len(grams)) for prior in seen_grams):
            continue
        seen_prompt.add(all_users)
        if grams:
            seen_grams.append(grams)
        accepted.append(row)
    return accepted


def examples(seed):
    result=[deepcopy(r["history"]) for r in records()]
    random.Random(seed).shuffle(result)
    return result


if __name__ == "__main__":
    # Verify the frozen source population and output through the real training serializer.
    from dialogue import training_row
    from tokenizer import load

    historical = json.loads((REPORT / "receipt.json").read_text())
    expected = list(jsonlines(REPORT / "selected-ids.jsonl"))
    rebuilt = records()
    actual = [(r["source"], r["id"], digest(json.dumps(r["history"], sort_keys=True, ensure_ascii=False)))
              for r in rebuilt]
    reference = [(r["source"], r["id"], r["history_sha256"]) for r in expected]
    if actual != reference:
        raise ValueError("Selection or rebuilt history differs from the frozen receipt")
    tokenizer = load()
    encoded = [training_row(tokenizer, row["history"]) for row in rebuilt]
    print(json.dumps({
        "histories": len(encoded),
        "input_tokens": sum(len(row.inputs) for row in encoded),
        "assistant_targets": sum(row.target_count for row in encoded),
        "max_inputs": max(len(row.inputs) for row in encoded),
        "fit_256": sum(len(row.inputs) <= 256 for row in encoded),
    }, indent=2))
    canonical = json.dumps(examples(historical["seed"]),sort_keys=True,ensure_ascii=False)
    if digest(canonical) != historical["runtime_sha256"]:
        raise ValueError("Rebuilt ordering or messages differ from the frozen hash")

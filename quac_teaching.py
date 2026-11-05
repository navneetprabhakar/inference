"""Train-only QuAC span-grounded conversation preparation. No network operations."""
from collections import Counter
from copy import deepcopy
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
from random import Random
import re
import unicodedata
from urllib.parse import quote, unquote

import pyarrow.parquet as pq

from broad_teaching import checked, jsonlines
from local_chat import encode_frame
from tokenizer import load

ROOT=Path(__file__).resolve().parent
REPORT=ROOT/"reports/quac-teaching"
RAW=ROOT/"data/quac-train-v1/train.parquet"
RAW_SHA="067c94373d1a622339a73f16032d8060bb5dd989cd8ce2b3647363a8bc1d5b5f"
SALT="astra-quac-by-article-1"
# Family-domain holdouts are additional to the publisher's untouched validation split.
MAX_CONTEXT_TOKENS=180
MAX_HISTORY_TOKENS=512

SENSITIVE=re.compile(
    r'\b(?:abuse\w*|addict\w*|sexual\w*|sex|rape\w*|gay|bisexual|lesbian|homosex\w*|'
    r'womaniz\w*|transgender|diagnos\w*|clinic\w*|medical\w*|diseas\w*|cancer|pregnan\w*|'
    r'mental health|suicid\w*|assault\w*|murder\w*|kill\w*|assassin\w*|convict\w*|arrest\w*|'
    r'charged with|accused|victim\w*|divorc\w*|marri\w*|spouse|wife|husband|children|daughter|'
    r'son of|sons of|family life|personal life|politic\w*|elections?|electoral|religio\w*|racis\w*|ethni\w*|'
    r'died|death|dead|born|birth\w*|drug\w*|overdos\w*|health|alcohol\w*|shootings?|gunshot|wars?|warfare|'
    r'bankrupt\w*|lawsuit|homeless|depress\w*|persecut\w*|injur\w*|intoxic\w*|bull(?:y|i)\w*|sibling\w*|younger brother|older brother|younger sister|older sister|mother|father|teenager|underage|atomic bomb|nazi\w*|bombing|ailment|symptom|theft|racism|criminal|ethnicity|extremis\w*|gang\w*|boyfriend|girlfriend|harass\w*|racial\w*|segregat\w*|drunk\w*|beer|alcohol\w*|anxiet\w*|parents?|schoolgirl|presidential|military|invasion|imperialism|alleg\w*|controvers\w*|republican|democrat\w*|congress\w*|libertarian\w*|liberalism|conservatism|governor|president|communis\w*|bribe\w*|extortion|cheats|gangster|fraud|harassment)\b|'
    r'[\w.+-]+@[\w.-]+|\b\d{3}[-. ]\d{3}[-. ]\d{4}\b',re.I)
NOTICE=re.compile(r'incorporat(?:es|ed|ing) text|all rights reserved|used with permission|copyright|translated from|reprinted|reproduced (?:from|by)|CC BY|creative commons|printed with permission',re.I)
NOISY=re.compile(r'https?://|<\||\[assistant\]|\[tool\]|\ufffd|\[citation needed\]|\{\{|\}\}|\|\||\(\s*[,;)]',re.I)
VAGUE=re.compile(r"\b(?:anything else|any other interesting|anything interesting|find interesting|is there anything|what else|tell me something interesting|give me more|what did you find interesting)\b",re.I)
CLOSED=re.compile(r'^(?:is|are|am|was|were|does|do|did|has|have|had|can|could|will|would|may)\b',re.I)
DATE=re.compile(r'\d|\b(?:January|February|March|April|May|June|July|August|September|October|November|December|years?|days?|months?|seasons?|early|late|after|before|during|spring|summer|winter|autumn)\b',re.I)
STOP_WORDS=set("a an and are as at be by did do does doing during for from had has have he her here him his how i in into is it its of on or she that the their them then there these they this those to was were what when where which who why with would you".split())


def norm(text):
    return " ".join(unicodedata.normalize("NFKC",text).casefold().split())


def article_key(title):
    return re.sub(r'\s*\([^()]*\)\s*$', '',norm(unquote(title).replace("_"," "))).strip()


def digest(text):
    return sha256(text.encode()).hexdigest()


def known_articles():
    """Only previously used corpus provenance is read. Protected conversation files stay closed."""
    titles=set()
    for p in [ROOT/"data/feasibility-v1/documents.jsonl",ROOT/"data/extended-trial-v3/documents.jsonl"]:
        for r in jsonlines(p):
            if r["source"]=="wiki":
                titles.add(article_key(r.get("title",r["group"].split("/wiki/")[-1])))
    return titles


def split(group):
    value=int(digest(SALT+group)[:12],16)%100
    return "train" if value<90 else "internal-validation" if value<95 else "internal-test"


def windows(tokenizer,section):
    """Fixed, non-overlapping source windows; segmentation never consults a gold answer."""
    spans=list(re.finditer(r'.+?(?:[.!?](?=\s|$)|$)',section,re.S))
    start=None
    stop=None
    for match in spans:
        a,b=match.span()
        if not section[a:b].strip():
            continue
        if SENSITIVE.search(section[a:b]) or len(tokenizer.encode(section[a:b]).ids)>MAX_CONTEXT_TOKENS:
            if start is not None:yield start,stop
            start=stop=None
            continue
        if start is not None and len(tokenizer.encode(section[start:b]).ids)>MAX_CONTEXT_TOKENS:
            yield start,stop
            start=stop=None
        if start is None:start=a
        stop=b
    if start is not None:yield start,stop


EXTRA_STOP=set("a any anything about more other else tell me know next things thing find different part situation happen happened did anything do does was were this that these them did doing did did someone something somebody people person article context section exactly then interesting could can could would give get got as his her their there what when where who how why which yes no he she they him it used use one first any did say talk information else really very good was well known do get but other another did did most much many according here following besides after before did start began beginning early during well this time those way as like much".split())
STOP_WORDS|=EXTRA_STOP
NEG=re.compile(r"\b(?:not|never|without|cannot|unable|no|refused|denied|declined|failed|didn't|wasn't|weren't|although)\b",re.I)
DURATION=re.compile(r"\b(?:seconds?|minutes?|hours?|days?|weeks?|months?|years?|decades?|seasons?|kilomet(?:re|er)s?|miles?|met(?:re|er)s?|feet|foot|inches)\b",re.I)
LOCATIVE=re.compile(r"\b(?:in|at|near|from|to|on|outside) (?:the )?[A-Z][\w'-]+")
CAUSAL=re.compile(r"\b(?:because|since|so that|due to|as a result|in order to|reason|to avoid|wanted|inspired|motivated|led to)\b",re.I)


def stems(text):
    out=set()
    for token in re.findall(r"[a-z]+|\d+",text.casefold()):
        if token in STOP_WORDS or len(token)<3:continue
        if token in {"retirement", "retiring", "retired", "retire"}:token="retir"
        if token in {"release","released","releasing"}:token="releas"
        if token in {"singing","sang","sung"}:token="sing"
        if token in {"recordings","recorded","records","recording"}:token="record"
        if token in {"begin","began","begun","beginning"}:token="begin"
        if token.endswith("ies") and len(token)>4:token=token[:-3]+"y"
        elif token.endswith("ing") and len(token)>5:token=token[:-3]
        elif token.endswith("ed") and len(token)>4:token=token[:-2]
        elif token.endswith("s") and len(token)>4:token=token[:-1]
        out.add(token)
    return out


def strict_alignment(question,answer,sentence,first,prior):
    if not question.rstrip().endswith("?") or len(question.split())<3:
        return False
    keys=stems(question)
    if not keys:return False
    sentence_keys=stems(sentence)
    overlap=keys & sentence_keys
    if not overlap or len(overlap)<max(1,(len(keys)+1)//2):
        return False
    if len(keys)==1 and len(answer.split())>9 and keys==stems(answer):
        return False
    q=question.lower()
    if not first and prior and not stems(prior)&sentence_keys and q.startswith(("when was that","where was that","how many of them")):
        return False
    if q.startswith(("where ","what city","what country")):
        if not LOCATIVE.search(sentence) or ((len(answer.split())<=3) and not re.search(r'\b(?:in|at|near|from|to|on|outside) (?:the )?'+re.escape(answer.strip(' .,;'))+r'\b',sentence,re.I)):
            return False
    if q.startswith("how long") and not DURATION.search(answer):return False
    if q.startswith("why") and not CAUSAL.search(sentence):return False
    if q.startswith(("what year","what date","when ")) and not DATE.search(answer):return False
    if q.startswith(("who ", "what person")) and not re.search(r'\b[A-Z][a-z]{2,}',answer):
        return False
    return True


def sequence_cost(tokenizer, history):
    size=0
    for m in history:
        value={"text":m["text"]} if m["role"]=="assistant" else m["text"]
        header,body=encode_frame(tokenizer,m["role"],value)
        size+=len(header)+len(body)
    return size-1


def align_turn(row,i,section,begin,end,first,prior):
    question=row["questions"][i].strip()
    answer=row["orig_answers"]["texts"][i]
    offset=row["orig_answers"]["answer_starts"][i]
    yes=row["yesnos"][i]
    follow=row["followups"][i]
    if (not 3<=len(question.split())<=28 or SENSITIVE.search(question) or VAGUE.search(question)
            or NOISY.search(question) or not question.endswith("?") or not stems(question)):
        return None
    if first and i>0 and (not re.search(r"\b[A-Z][a-z]+",question[1:]) or
                         re.search(r"\b(?:he|she|his|her|they|their|it|that|then|these|those|this|them)\b",question,re.I)):
        return None
    if question.lower().startswith(("any other","was there anything","anything that")):return None
    meta=dict(turn_id=row["turn_ids"][i],offset=offset,span=answer,yesno=yes,teacher_followup=follow)
    if answer=="CANNOTANSWER":
        if row["context"][offset:offset+12]!="CANNOTANSWER" or yes!=2 or first:return None
        # A missing attribute must be lexical and specific; ambiguous pronoun-only
        # questions and answers inferable from overlapping source terms are withheld.
        if not stems(question)-stems(section) or stems(question)&stems(section):return None
        return question,"The passage does not say.",meta
    if (offset<begin or offset+len(answer)>end or section[offset:offset+len(answer)]!=answer
            or not 1<=len(answer.split())<=28 or NOISY.search(answer)):return None
    sentence=next((m.group().strip() for m in re.finditer(r'.+?(?:[.!?](?=\s|$)|$)',section,re.S)
                   if m.start()<=offset and offset+len(answer)<=m.end()),None)
    if not sentence or not strict_alignment(question,answer,sentence,first,prior):return None
    frame=norm((row["wikipedia_page_title"]+" "+section[begin:end]))
    quoted=re.findall(r'"([^"]{2,80})"|“([^”]{2,80})”',question)
    if any(norm(left or right) not in frame for left,right in quoted):
        return None
    named=re.findall(r"\b[A-Z][a-z]+(?: [A-Z][a-z]+)+\b",question)
    for phrase in named:
        cleaned=re.sub(r"^(?:When|Where|Which|What|Who|Did|Was|Were|Is|Are|How)\s+","",phrase)
        if cleaned and (norm(cleaned) not in frame or norm(cleaned) not in norm(sentence)):
            return None
    # Require a referent plus an answer type. Broad event narration is much noisier.
    if re.match(r"^(?:what happened|how did .+ (?:go|do|impact)|what (?:can|did) you|what is significant|what did this|what did it|how was|what was this|what was it)\b",question,re.I):
        return None
    definition=re.match(r"^what (?:is|was|are|were) (?:a |an |the )?(.+?)\?$",question,re.I)
    if definition and not re.search(r"\b(?:name|role|title|purpose|reason|job|position|date|year|album|song|film|work|team|group|company|occupation|function|meaning|difference|relationship|connection|result|score|project|band|career)\b",definition[1],re.I):
        entity=norm(definition[1]).strip(' ".')
        if not re.search(re.escape(entity)+r"\s*(?:,\s+an?\s|(?:is|was|are|were)\s+(?:the|an?)\s|means\b|refers\b)",norm(sentence)):
            return None
    if any(answer.count(a)!=answer.count(b) for a,b in [("(",")"),("[","]")]) or answer.count('"')%2:return None
    trimmed=answer.strip().rstrip(",;:")
    if re.search(r'\b(?:and|or|the|a|an|from|of|but|to|by|with|for|that|his|her|their|as)$',trimmed,re.I):return None
    if q_is_number(question) and not re.search(r'\d|\b(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|dozen|several|many|hundred|thousand|million|few)\b',answer,re.I):
        return None
    # Repair clipped answers using their own complete literal source sentence only.
    # Do not invent an explanation, summarize another passage, or infer a value.
    sentence_start=section.rfind(sentence,begin,offset+len(sentence)+1)
    if (len(trimmed.split())>4 and trimmed.rstrip(".!?")!=sentence.rstrip(".!?")
            and len(sentence.split())<=32 and sentence_start>=begin and sentence_start+len(sentence)<=end):
        trimmed=sentence
    if trimmed.endswith((" after"," back"," which"," such"," following"," during"," across"," about")):
        return None
    if len(trimmed.split())>=9 and trimmed[-1] not in ".!?”'" and trimmed==answer.strip().rstrip(",;:") and trimmed!=sentence:
        return None
    if not trimmed.strip(" .,:;()[]"):
        return None
    if re.search(r"\bwhat year\b",question,re.I):
        years=re.findall(r"\b(?:1[0-9]{3}|20[0-2][0-9])\b",answer)
        if len(set(years))!=1:return None
        trimmed=years[0]
    if prior and norm(prior)==norm(trimmed):return None
    if q_is_number(question) and not re.search(r"\d|\b(?:one|two|three|four|five|six|seven|eight|nine|ten|hundred|thousand|million)\b",trimmed,re.I):return None
    meta["literal_response"]=trimmed
    prefix=""
    if CLOSED.match(question) and yes in (0,1):
        if (yes==1) != bool(NEG.search(sentence)) or stems(question)-stems(sentence):return None
        prefix="Yes. " if yes==0 else "No. "
    return question,prefix+trimmed,meta


def q_is_number(q):
    return q.lower().startswith(("how many","how much"))


def prepare():
    tokenizer=load()
    prior=known_articles()
    table=pq.read_table(checked(RAW,RAW_SHA),use_threads=False)
    if len(table)!=11567:raise ValueError("Unexpected train split row count")
    rows=sorted(table.to_pylist(),key=lambda r:digest("quac-pick-v2"+r["dialogue_id"]))
    counts=Counter()
    selected={}
    for r in rows:
        article=r["wikipedia_page_title"]
        group=article_key(article)
        section=r["context"].removesuffix(" CANNOTANSWER").rstrip()
        if group in prior:
            counts["prior_article"]+=1;continue
        if SENSITIVE.search(article+" "+r["section_title"]) or NOTICE.search(section) or NOISY.search(section):
            counts["sensitive_header_or_source_notice"]+=1;continue
        section_key=digest(norm(section))
        for begin,end in windows(tokenizer,section):
            visible=section[begin:end].strip()
            if len(visible.split())<28 or SENSITIVE.search(visible):
                counts["unsafe_or_short_visible_window"]+=1;continue
            window_key=(section_key,begin,end)
            best=selected.get(window_key)
            for start in range(len(r["questions"])):
                history=[]
                annotations=[]
                for i in range(start,min(start+3,len(r["questions"]))):
                    prior_reply=history[-1]["text"] if history else None
                    turn=align_turn(r,i,section,begin,end,i==start,prior_reply)
                    if turn is None:break
                    q,answer,meta=turn
                    user=("Passage from "+article+" — "+r["section_title"]+":\n"+visible+"\n\n"+q if not history else q)
                    updated=history+[{"role":"user","text":user},{"role":"assistant","text":answer}]
                    if sequence_cost(tokenizer,updated)>MAX_HISTORY_TOKENS:break
                    history=updated
                    annotations.append(meta)
                if not history:continue
                # Prefer genuine consecutive turns within the predetermined source window;
                # ties prefer original dialog starts. No missing middle turn is spliced out.
                rank=(len(history),start==0,-start,digest(r["dialogue_id"]))
                if best and rank<=best[0]:continue
                best=(rank,dict(split=split(group),group=group,source_url="https://en.wikipedia.org/wiki/"+quote(article.replace(" ","_")),
                                title=article,section=r["section_title"],section_sha256=section_key,
                                dialogue=r["dialogue_id"],first_turn=start,view_start=begin,view_end=end,
                                visible_prefix_sha256=digest(visible),history=history,annotations=annotations,
                                inputs=sequence_cost(tokenizer,history)))
            if best:selected[window_key]=best
    return [x[1] for x in selected.values()],counts


@lru_cache(maxsize=1)
def records():
    """Read only the frozen training file. No test/dev paths are enumerated here."""
    receipt=json.loads((REPORT/"receipt.json").read_text())
    data=checked(ROOT/"data/quac-train-v1/train.jsonl",receipt["splits"]["train"]["sha256"])
    result=list(jsonlines(data))
    if any(r["split"]!="train" or split(r["group"])!="train" for r in result):
        raise ValueError("Train loader received a held-out article")
    return result


def examples(seed):
    histories=[deepcopy(r["history"]) for r in records()]
    Random(seed).shuffle(histories)
    return histories


if __name__=="__main__":
    records,counts=prepare()
    dest=ROOT/"data/quac-train-v1/candidates.jsonl"
    dest.write_text("".join(json.dumps(r,ensure_ascii=False)+"\n" for r in records))
    print(json.dumps(dict(candidates=len(records),splits=Counter(r["split"] for r in records),
                          unique_articles=len({r["group"] for r in records}),rejections=counts),indent=2))

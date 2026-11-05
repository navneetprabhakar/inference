"""Separate train-only custody audit. Held-out rows are consumed solely to build exclusion keys."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import unicodedata

import pyarrow.parquet as pq

import quac_teaching
import squad_teaching
import taskmaster_teaching
from local_chat import encode_frame
from protect_split import Shield, PRIVATE, ROOT, DEV_SHA, SEALED_SHA, digest, grams, words, shape, signature
from protect_validation_b import BShield, B_SHA
from protect_followon import freeze
from tokenizer import load

POOL_PINS={"squad":(702,"10a859362b1c7ff43d4f0caa8031c2cc85df26c3e4199fa8cd0bf3578fb2012b"),
           "quac":(83,"72ad58169cafe4bd05629a1641ac06074899478ab049b716e2d00e681cfa912b"),
           "taskmaster_sft":(1295,"4f7af74c2f74cd06fee49cb8452a9c899493c5cf5adc8b3614e20665fc170ffe")}
TRAIN_FILES={"squad":("data/squad-training-v1/train.jsonl","ade7233021dd7beff1b6d54ee941e4735a56bb7060c1948a2b1149ea06329761"),
             "quac":("data/quac-train-v1/train.jsonl","0ce76fb60191a538e551e8c3c8a1dce4c30cb51a68da8799708c73ee24659957"),
             "taskmaster_sft":("data/taskmaster2/sft-train.jsonl","0cc45ce7a55fb2e732867ec94212d3bbd194b94e2ba5915c40deafc3f6faec91"),
             "taskmaster_pretrain":("data/taskmaster2/pretrain-only-train.jsonl","0466f10cad43ef5c2094778fb90e8a05d10233f1bb66b3e2d4d764d16d38515c")}
SENSITIVE=re.compile(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}|\b\d{3}[- .]\d{3}[- .]\d{4}\b|\b(?:\d[ -]?){15,18}\d\b|\b\d{1,5}\s+[A-Za-z]+\s+(?:Street|Road|Avenue|Lane)\b",re.I)
def htext(s):return digest(s.encode())
def norm(s):return " ".join(unicodedata.normalize("NFKC",s).casefold().split())
def history_sha(h):return htext(json.dumps(h,ensure_ascii=False,sort_keys=True))
def rows(path):return [json.loads(l) for l in path.open()]
def file_sha(path):
    with path.open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()
def verify(path,sha):
    if file_sha(path)!=sha:raise ValueError(f"pinned source mismatch: {path.name}")


class Reserved:
    def __init__(self):
        self.words=set(); self.prompts=set(); self.articles=set(); self.paragraphs=set(); self.histories=set()
        self.goals=set();self.conversations=set();self.paragraph_components=set();self.provenance={}
        self.questions=set();self.section_ids=set();self.calls=set();self.squad_groups=set();self.squad_qa=set()
        self.sha_sources={}
        # Previous selected corpus metadata includes original article identities and per-document hashes.
        for local in ("data/feasibility-v1/documents.jsonl","data/extended-trial-v3/documents.jsonl"):
            path=ROOT/local
            self.provenance[local]=file_sha(path)
            for r in rows(path):
                self.paragraphs.add(r["normalized_sha256"])
                if r.get("raw_sha256"):self.paragraphs.add(r["raw_sha256"])
                if r["source"]=="wiki":
                    self.articles.add(quac_teaching.article_key(r.get("title",r["group"].split("/wiki/")[-1])))
        # Official validation/test splits are never read. These are local, independently withheld partitions only.
        splits=[("squad","validation"),("quac","internal-validation"),("quac","internal-test"),
                ("taskmaster","sft-internal-dev"),("taskmaster","pretrain-only-internal-dev")]
        for source,part in splits:
            folder={"squad":"squad-training-v1","quac":"quac-train-v1","taskmaster":"taskmaster2"}[source]
            label={"squad":"squad-teaching","quac":"quac-teaching","taskmaster":"taskmaster2"}[source]
            path=ROOT/"data"/folder/(part+".jsonl")
            rec=json.loads((ROOT/"reports"/label/"receipt.json").read_text())
            sha=rec["files"][path.name]["sha256"] if source=="taskmaster" else rec["splits"][part]["sha256"]
            verify(path,sha)
            self.provenance[str(path.relative_to(ROOT))]=sha
            for r in rows(path):
                self.histories.add(r["history_sha256"])
                for m in r["history"]:
                    self.words.update(grams(m["text"]))
                    if m["role"]=="user":self.prompts.add(tuple(words(m["text"])))
                for k in ("context_sha256","section_sha256","visible_prefix_sha256"):
                    if k in r:self.paragraphs.add(r[k])
                if source=="squad":
                    self.articles.add(quac_teaching.article_key(r["article"]))
                    self.squad_groups.add(r["group"])
                    self.paragraph_components.add(r["paragraph_component"])
                    self.squad_qa.update(q["id"] for q in r["questions"])
                if source=="quac":
                    self.articles.add(quac_teaching.article_key(r["title"]))
                    self.section_ids.add(r["dialogue"])
                if source=="taskmaster":
                    self.goals.add(r["goal_group"]);self.conversations.add(r["conversation_id"])
        # Independently bind the previous diagnostic conversations and paired probes.
        prev=[("reports/dialogue-readiness/counterfactual-dev-v1.jsonl","8d0c56f7d02608bcfaf7b304cbc053637dd6d86d219f4257db8c736522320ab8"),
              ("runs/astra-dev-v1/cases.jsonl","6b954fb54d2520a43b2f342f2a6968f773b41429645866c93a9b5d0549f04535")]
        for local,sha in prev:
            path=ROOT/local;verify(path,sha);self.provenance[local]=sha
            for r in rows(path):
                if "members" in r:
                    for member in r["members"]:
                        for m in member["history"]:
                            if m.get("text"):self.words.update(grams(m["text"]))
                            if m["role"]=="user":self.prompts.add(tuple(words(m["text"])))
                            if "call" in m:self.calls.add(signature(m["call"]))
                else:
                    for text in r["turns"]+r["rubric"]:self.words.update(grams(text))
                    self.prompts.update(tuple(words(t)) for t in r["turns"])
        # Prior reviewed/replayed SQuAD paragraph components are excluded separately.
        for local in ("grounded-replay-sft-v1/train.jsonl","grounded-conversations-v1/sample.jsonl"):
            p=squad_teaching.OLD/local;verify(p,squad_teaching.PINS[local])
            self.provenance["archived/"+local]=squad_teaching.PINS[local]
            for r in rows(p):self.paragraph_components.add((r.get("record") or r)["paragraph_component"])

    def check(self,pool,r,messages,texts):
        why=set()
        if r["history_sha256"] in self.histories:why.add("protected_history_hash")
        if any(htext(norm(t)) in self.paragraphs or htext(t) in self.paragraphs for t in texts if t):
            why.add("protected_source_text_hash")
        if self.words & set().union(*(grams(m["text"]) for m in messages)):why.add("legacy_or_internal_heldout_8gram")
        if any(tuple(words(m["text"])) in self.prompts for m in messages if m["role"]=="user"):
            why.add("legacy_or_internal_exact_prompt")
        if SENSITIVE.search("\n".join(texts+[m["text"] for m in messages])):why.add("contact_or_sensitive_identifier")
        if pool in ("squad","quac"):
            if quac_teaching.article_key(r.get("article",r.get("title",""))) in self.articles:why.add("protected_source_article")
            if {r[k] for k in ("context_sha256","section_sha256","visible_prefix_sha256") if k in r}&self.paragraphs:
                why.add("protected_source_paragraph_or_section_hash")
        if pool=="squad":
            if r["group"] in self.squad_groups:why.add("protected_source_component_group")
            if r["paragraph_component"] in self.paragraph_components:why.add("protected_paragraph_component")
            if any(q["id"] in self.squad_qa for q in r["questions"]):why.add("protected_question_id")
        if pool=="quac" and r["dialogue"] in self.section_ids:why.add("protected_quac_dialogue_id")
        if pool.startswith("taskmaster"):
            if r["goal_group"] in self.goals:why.add("protected_taskmaster_goal")
            if r["conversation_id"] in self.conversations:why.add("protected_conversation_id")
        return why


def source_texts(training):
    material={}
    sources={}
    raw=squad_teaching.OLD/"grounded-qa-intake-v1/train-v1.1.json"
    verify(raw,squad_teaching.PINS["grounded-qa-intake-v1/train-v1.1.json"])
    sources["squad_official_train_sha256"]=file_sha(raw)
    originals=json.loads(raw.read_text())["data"]
    for r in training["squad"]:
        assert r["official_split"]=="train"
        para=originals[r["article_index"]]["paragraphs"][r["paragraph_index"]]
        text=para["context"]
        assert text==r["context"] and htext(text)==r["context_sha256"]
        lookup={q["id"]:q for q in para["qas"]}
        for q in r["questions"]:
            assert q["id"] in lookup and text[q["answer_start"]:q["answer_end"]]==q["answer"]
            assert q["question"]==lookup[q["id"]]["question"].strip()
        material[r["history_sha256"]]=[text]
    raw=quac_teaching.RAW;verify(raw,quac_teaching.RAW_SHA)
    sources["quac_official_train_sha256"]=file_sha(raw)
    include={r["dialogue"] for r in training["quac"]}
    paragraphs={}
    for batch in pq.ParquetFile(raw).iter_batches(columns=["dialogue_id","context"],batch_size=256,use_threads=False):
        for original in batch.to_pylist():
            if original["dialogue_id"] in include:
                paragraphs[original["dialogue_id"]]=original["context"].removesuffix(" CANNOTANSWER").rstrip()
    for r in training["quac"]:
        section=paragraphs[r["dialogue"]]
        visible=section[r["view_start"]:r["view_end"]].strip()
        assert htext(norm(section))==r["section_sha256"] and htext(visible)==r["visible_prefix_sha256"]
        assert visible in r["history"][0]["text"]
        material[r["history_sha256"]]=[section,visible]
    # Resolve each admitted Taskmaster history to its exact role-preserving raw utterance offsets.
    tm=ROOT/"data/taskmaster2"
    index=tm/"source-offsets.jsonl"
    expected=json.loads((ROOT/"reports/taskmaster2/verification.json").read_text())["source_offsets_sha256"]
    verify(index,expected);sources["taskmaster_offset_index_sha256"]=expected
    by_id={r["conversation_id"]:r for r in rows(index)}
    required={r["conversation_id"]:r for k in ("taskmaster_sft","taskmaster_pretrain") for r in training[k]}
    matched=set()
    for meta in json.loads((ROOT/"reports/taskmaster2/files.json").read_text()):
        path=tm/Path(meta["path"]).name;blob=path.read_bytes()
        assert hashlib.sha1(f"blob {len(blob)}\0".encode()+blob).hexdigest()==meta["sha"] and len(blob)==meta["size"]
        sources[meta["path"]]=digest(blob)
        for source in json.loads(blob):
            ident=source["conversation_id"]
            if ident not in required:continue
            info=by_id[ident];r=required[ident]
            assert meta["path"]==info["source_path"] and info["history_sha256"]==r["history_sha256"]
            msgs=[]
            for turn in source["utterances"][info["first_utterance"]:info["last_utterance"]+1]:
                role=turn["speaker"].casefold()
                if msgs and msgs[-1]["role"]==role:msgs[-1]["text"]+=" "+turn["text"].strip()
                else:msgs.append(dict(role=role,text=turn["text"].strip()))
            assert msgs==r["history"]
            matched.add(ident)
            material[r["history_sha256"]]=["\n".join(m["text"] for m in msgs)]
    assert matched==required.keys()
    return material,sources


def audit():
    reserved=Reserved(); primary=Shield(); secondary=BShield();tok=load()
    training={};sources_api={}
    for key,(local,sha) in TRAIN_FILES.items():
        path=ROOT/local;verify(path,sha);training[key]=rows(path)
        assert all(r["split"]=="train" and r["history_sha256"]==history_sha(r["history"]) for r in training[key])
        if key.endswith("pretrain"):
            assert len(training[key])==4378 and all(r["usage"]=="pretrain-only" for r in training[key])
            continue
        api={"squad":squad_teaching,"quac":quac_teaching,"taskmaster_sft":taskmaster_teaching}[key]
        histories=api.examples(1459)
        expected_n,expected_sha=POOL_PINS[key]
        assert len(histories)==expected_n and htext(json.dumps(histories,ensure_ascii=False,sort_keys=True))==expected_sha
        assert {history_sha(h) for h in histories}=={r["history_sha256"] for r in training[key]}
        sources_api[key]=dict(seed=1459,ordered_pool_sha256=expected_sha,source_module_sha256=file_sha(Path(api.__file__)))
    material,raw_hashes=source_texts(training)
    summaries={}
    blocked=defaultdict(set);refs=defaultdict(set)
    def cluster(pool,row):
        if pool=="squad":return "squad-paragraph:"+row["paragraph_component"]
        if pool=="quac":return "quac-section:"+row["section_sha256"]
        return "taskmaster-dialogue:"+row["conversation_id"]
    for pool,rs in training.items():
        for r in rs:
            sha=r["history_sha256"]
            extra=material[sha]
            msgs=list(r["history"])
            if pool=="squad":msgs.extend(dict(role="user",text=q["question"]) for q in r["questions"])
            if pool=="quac":
                first=r["history"][0]["text"].rsplit("\n\n",1)[-1]
                msgs.append(dict(role="user",text=first))
            why=reserved.check(pool,r,msgs,extra)
            for scope,index in (("A_or_sealed",primary),("B",secondary)):
                why.update(scope+":"+flag for flag in index.reasons(msgs))
                if any(grams(t)&index.grams for t in extra):why.add(scope+":source_passage_8gram")
            blocked[sha].update(why)
            refs[cluster(pool,r)].add(sha)
    for ids in refs.values():
        if any(blocked[sha] for sha in ids):
            for sha in ids:
                if not blocked[sha]:blocked[sha].add("related_source_paragraph_or_dialogue")
    sft_denied=set();plain_denied=set();seen_history=set();all_texts=set()
    for pool,rs in training.items():
        c=Counter(); reasons=Counter();simple={}; assistant={}
        for r in rs:
            sha=r["history_sha256"]
            if sha in seen_history:blocked[sha].add("duplicate_cross_pool_history")
            seen_history.add(sha)
            h=r["history"]
            if blocked[sha]:
                c["denied"]+=1;reasons.update(blocked[sha])
                (plain_denied if pool.endswith("pretrain") else sft_denied).add(sha)
                continue
            c["eligible"]+=1
            for m in h:
                t=m["text"];nt=norm(t)
                simple.setdefault(nt,t)
                if m["role"]=="assistant":assistant.setdefault(nt,t)
            if pool.endswith("pretrain"):
                txt="\n".join(m["role"].capitalize()+": "+m["text"] for m in h)
                c["one_pass_pretrain_tokens_including_doc_eot"]+=len(tok.encode(txt).ids)+1
            else:
                fields=[]
                for m in h:
                    value={"text":m["text"]} if m["role"]=="assistant" else m["text"]
                    prefix,body=encode_frame(tok,m["role"],value)
                    fields.extend(prefix+body)
                    if m["role"]=="assistant":c["one_pass_assistant_targets"]+=len(body)
                c["one_pass_framed_inputs"]+=len(fields)-1
            all_texts.update(norm(m["text"]) for m in h)
        c["distinct_normalized_utterances"]=len(simple)
        c["tokens_in_distinct_utterances"]=sum(len(tok.encode(t).ids) for t in simple.values())
        c["tokens_in_distinct_assistant_utterances"]=sum(len(tok.encode(t).ids) for t in assistant.values())
        summaries[pool]=dict(file_sha256=TRAIN_FILES[pool][1],train_rows=len(rs),counts=dict(c),reason_counts=dict(reasons))
    outputs={}
    for key,items in (("human-sft",sft_denied),("human-pretrain",plain_denied)):
        data=(json.dumps(sorted(items),indent=2)+"\n").encode()
        path=ROOT/f"reports/working-chat/{key}-excluded-histories.json"
        freeze(path,data);outputs[key]=dict(count=len(items),sha256=digest(data))
    report=dict(state="complete",protected_bindings=dict(primary=DEV_SHA,validation_b=B_SHA,sealed_confirmation=SEALED_SHA,
         additional_hashes=reserved.provenance),train_raw_pins=raw_hashes,api_pins=sources_api,pools=summaries,
         protected_article_count=len(reserved.articles),protected_paragraph_and_document_hashes_count=len(reserved.paragraphs),
         protected_source_components_count=len(reserved.paragraph_components),protected_taskmaster_goals=len(reserved.goals),
         source_groups_scanned=len(refs),denylist_pins=outputs,scope="Only frozen official-train-derived local train rows were candidates. Internal heldout rows supplied custody fingerprints only; no official upstream validation/test files were opened.",
         limitations="Group, hash, exact-word and selected near-scenario checks cannot certify semantic independence. Human does not mean every sample is high quality; role-marked pretraining excerpts are never assistant targets. Listed token counts are one pass under the current GPT-2 tokenizer and include within-source repetitions.")
    freeze(PRIVATE/"human-receipt.json",(json.dumps(report,indent=2)+"\n").encode())
    print(json.dumps(dict(pools=summaries,denylist_pins=outputs),indent=2))


if __name__=="__main__":
    audit()

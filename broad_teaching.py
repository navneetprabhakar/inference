"""Rebuild a curated offline instruction set from specific Dolly and OASST training records."""
from collections import Counter
from copy import deepcopy
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
from random import Random

ROOT = Path(__file__).resolve().parent
DATA = ROOT.parent / "inference-history-20261021/data"
REPORT = ROOT / "reports/broad-teaching"
OASST_DIR = DATA / "iteration-two-oasst2-snapshot-v1"
DOLLY_DIR = DATA / "dolly-complete-v1"
DOLLY_SHA = "2df9083338b4abd6bceb5635764dab5d833b393b55759dffb0959b6fcbf794ec"
OASST_SHA = "93092c0f05695da0306d7ea78bfc10a25b00396a7b4625a2d18a1377fb0aae04"
MAP_SHA = "acbd9a26b69767511f25d7e54acc0b5652473508946012da396cf77f976dff2a"
SELECTION_SHA = "85bac8506c5d9e794c268b6b165aeacbd0a6f47c2be95dcc2c04371aaa55f2ea"
NEGATIVE_LABELS = ("pii", "lang_mismatch", "hate_speech", "sexual_content", "not_appropriate", "violence", "spam")


def checked(path, digest):
    from hashlib import file_digest
    with path.open("rb") as stream:
        if file_digest(stream, "sha256").hexdigest() != digest:
            raise ValueError(f"Source hash mismatch: {path.name}")
    return path


def jsonlines(path):
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            yield json.loads(line)


def message(role, text):
    return {"role": role, "text": text.strip()}


def source_train_membership(prefix, name, wanted):
    """Read only staged training files. Verify their hashes against the archived source manifest."""
    stage = DATA / prefix / "staged"
    manifest = json.loads((stage / "manifest.json").read_text())["files"]
    found = set()
    for path in sorted(stage.glob("train-*.jsonl")):
        checked(path, manifest[path.name])
        for row in jsonlines(path):
            if row["source"] != name or row["split"] != "train" or row["official_split"] != "train":
                continue
            if name == "OpenAssistant/oasst2":
                key = row["lineage"][-1]
            else:
                prompt = row["messages"][0]["content"].split("\n\nContext:\n")[0].strip()
                key = (prompt, row["messages"][-1]["content"].strip())
            if key in wanted:
                found.add(key)
    if found != wanted:
        raise ValueError(f"{len(wanted-found)} {name} selections missing a verified train designation")


def oasst_path(tree, reply_id):
    def search(node, path):
        if node["message_id"] == reply_id:
            return path + [node]
        for child in node["replies"]:
            if child["parent_id"] != node["message_id"]:
                raise ValueError("OASST tree lineage mismatch")
            result = search(child, path + [node])
            if result:
                return result
        return None

    nodes = search(tree["prompt"], [])
    if not nodes or len(nodes) != 4 or nodes[0]["message_id"] != tree["message_tree_id"]:
        raise ValueError("Expected an original two-exchange OASST parent chain")
    for index, node in enumerate(nodes):
        if node["role"] != ("assistant" if index % 2 else "prompter"):
            raise ValueError("Unexpected OASST speaker order")
        if (node["lang"] != "en" or node["review_result"] is not True or node["deleted"] or
                node["synthetic"] or any(node["labels"].get(k, {}).get("value", 0) > 0 for k in NEGATIVE_LABELS)):
            raise ValueError("OASST source moderation or language gate failed")
        if index % 2 and node["labels"].get("quality", {}).get("value", 0) < 0.5:
            raise ValueError("OASST assistant response failed source quality threshold")
    return [message("user" if n["role"] == "prompter" else "assistant", n["text"]) for n in nodes]


@lru_cache(maxsize=1)
def records():
    selection_path = checked(REPORT / "selection.json", SELECTION_SHA)
    selections = json.loads(selection_path.read_text())
    for folder in (DOLLY_DIR, OASST_DIR):
        source = json.loads((folder / "source.json").read_text())
        checked(folder / "card.txt", source["card_sha256"])
        checked(folder / "license.txt", source["license_text_sha256"])
    dolly_path = checked(DOLLY_DIR / "rows.jsonl", DOLLY_SHA)
    dolly = list(jsonlines(dolly_path))
    wanted = {idx for s in selections if s["source"] == "dolly" for idx in s["rows"]}
    source_train_membership("complete-small-source-v1", "databricks/databricks-dolly-15k",
                            {(dolly[i]["instruction"].strip(), dolly[i]["response"].strip()) for i in wanted})
    wanted_trees = {s["tree"] for s in selections if s["source"] == "oasst"}
    wanted_replies = {s["reply"] for s in selections if s["source"] == "oasst"}
    source_train_membership("iteration-two-dialogue-preparation-v1", "OpenAssistant/oasst2", wanted_replies)
    official_map = checked(DATA / "iteration-two-oasst2-partitions-v1/mapping.json", MAP_SHA)
    splits = json.loads(official_map.read_text())
    if any(splits[tid]["split"] != "train" for tid in wanted_trees):
        raise ValueError("Selected OASST tree lacks official training membership")
    tree_path = checked(OASST_DIR / "trees.jsonl", OASST_SHA)
    trees = {r["message_tree_id"]: r for r in jsonlines(tree_path) if r["message_tree_id"] in wanted_trees}
    output = []
    for selection in selections:
        if selection["source"] == "oasst":
            history = oasst_path(trees[selection["tree"]], selection["reply"])
        else:
            rows = [dolly[i] for i in selection["rows"]]
            reference = rows[0]["context"].strip()
            history = []
            for index, row in enumerate(rows):
                if row["context"].split() != reference.split():
                    raise ValueError("Joined Dolly turns require an identical source passage")
                user = row["instruction"].strip()
                if index == 0 and reference:
                    user = f"Passage:\n{reference}\n\n{user}"
                history.extend((message("user", user), message("assistant", row["response"])))
            if "editorial_followup" in selection:
                user, answer = selection["editorial_followup"]
                history.extend((message("user", user), message("assistant", answer)))
        output.append((selection, history))
    return output


def examples(seed):
    """Return independent mutable histories in deterministic seed order."""
    result = [deepcopy(history) for _, history in records()]
    Random(seed).shuffle(result)
    return result


if __name__ == "__main__":
    from dialogue import training_row
    from tokenizer import load
    tokenizer = load()
    encoded = [training_row(tokenizer, history) for _, history in records()]
    seed = 713
    histories = examples(seed)
    serialized = json.dumps(histories, sort_keys=True, ensure_ascii=False).encode()
    if len({json.dumps(history, sort_keys=True) for history in histories}) != len(histories):
        raise ValueError("Duplicate final histories")
    report = dict(seed=seed, histories=len(histories), runtime_sha256=sha256(serialized).hexdigest(),
                  selection_sha256=sha256((REPORT / "selection.json").read_bytes()).hexdigest(),
                  sources=dict(Counter(s["source"] for s, _ in records())),
                  categories=dict(Counter(s["category"] for s, _ in records())),
                  turns=dict(Counter(len(h) // 2 for h in histories)),
                  authored_followups=sum("editorial_followup" in s for s, _ in records()),
                  joined_passages=sum(len(s.get("rows", [])) > 1 for s, _ in records()),
                  total_inputs=sum(len(row.inputs) for row in encoded), target_tokens=sum(row.target_count for row in encoded),
                  max_input_tokens=max(len(row.inputs) for row in encoded),
                  under_256=sum(len(row.inputs) <= 256 for row in encoded))
    (REPORT / "receipt.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))

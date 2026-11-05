"""Prepare a bounded offline feasibility corpus. Run once per immutable output path."""
import argparse
import hashlib
import json
import random
import re
import tarfile
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import unquote, urlsplit

import numpy as np
import pyarrow.parquet as pq

from tokenizer import document_ids, load

SALT = "astra-feasibility-v1"
WIKI = {"en.wikipedia.org", "en.m.wikipedia.org", "simple.wikipedia.org", "simple.m.wikipedia.org"}
EMAIL = re.compile(r"\b[\w.+-]+@[\w.-]+\.\w+|\b\d{3}[-. ]\d{3}[-. ]\d{4}\b")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_hash(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def normalized(text):
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def prepare(manifest, out):
    paths = [Path(p) for p in json.loads(manifest.read_text())["raw_sources"]]
    raw_hashes = {p.name: file_hash(p) for p in paths}
    if raw_hashes[paths[0].name] != paths[0].stem:
        raise ValueError("FineWeb source hash mismatch")
    archive = paths[1].parent.with_suffix(".tar.gz")
    if file_hash(archive) != "26cf7605aca15bc4ea6fa637256400d9d01317b28ed296172b2d1dd160cd7699":
        raise ValueError("TinyStories archive hash mismatch")
    with tarfile.open(archive) as tar:
        for p in paths[1:]:
            member = next(m for m in tar.getmembers() if Path(m.name).name == p.name)
            with tar.extractfile(member) as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != raw_hashes[p.name]:
                    raise ValueError("TinyStories member hash mismatch")
    tokenizer = load()
    counts = Counter()
    seen, groups = set(), set()
    # Shared word shingles nominate cross-source near matches; exact Jaccard decides.
    index = defaultdict(list)
    shingles = []
    records = []
    examples = []

    def add(source, group, raw_id, content, raw_bytes):
        text = normalized(content)
        words = text.split()
        if len(words) < 40 or EMAIL.search(content) or len(words) > 2500:
            counts["length_or_contact"] += 1
            return
        key = digest(text.encode())
        if group in groups or key in seen:
            counts["same_group_or_exact"] += 1
            return
        grams = {hashlib.blake2b(" ".join(words[i:i+5]).encode(), digest_size=8).digest()
                 for i in range(len(words)-4)}
        # Index the bottom 16 hashes. A near-duplicate can still evade this screen.
        signature = sorted(grams)[:16]
        matches = {i for shingle in signature for i in index[shingle]}
        for i in matches:
            score = len(grams & shingles[i]) / len(grams | shingles[i])
            if score >= 0.7:
                counts["near_duplicate"] += 1
                if len(examples) < 10:
                    examples.append([raw_id, records[i]["document_id"], score])
                return
        for shingle in signature:
            index[shingle].append(len(records))
        shingles.append(grams)
        groups.add(group)
        seen.add(key)
        split = "validation" if int(digest((SALT + group).encode())[:8],16) % 20 == 0 else "train"
        ids = document_ids(tokenizer, content)
        records.append(dict(source=source, group=group, document_id=raw_id, normalized_sha256=key,
                            raw_bytes=raw_bytes, split=split, ids=ids))

    for batch in pq.ParquetFile(paths[0]).iter_batches(batch_size=512):
        for r in batch.to_pylist():
            url = urlsplit(r["url"])
            if url.hostname not in WIKI or not url.path.startswith("/wiki/") or r["language"] != "en":
                counts["outside_english_wiki_slice"] += 1
                continue
            title = unquote(url.path[6:])
            if ":" in title or title.startswith("List_of_") or r["language_score"] < 0.85:
                counts["outside_article_slice"] += 1
                continue
            # Retain complete prose paragraphs and skip tables, quotes and attribution notices.
            paragraphs = [line.strip() for line in r["text"].splitlines() if
                          len(line.split()) >= 12 and "|" not in line and line.strip().endswith((".", "!", "?"))]
            if any(x in r["text"].lower() for x in ["all rights reserved", "used with permission"]):
                counts["third_party_notice"] += 1
                continue
            group = (url.hostname.replace(".m.", ".") + "/wiki/" + title).casefold()
            add("wiki", group, r["id"], "\n".join(paragraphs), len(r["text"].encode()))
    for path in paths[1:]:
        rows = json.loads(path.read_text())
        for i, r in enumerate(rows[:2500]):
            content = r["story"]
            key = digest(normalized(content).encode())
            add("stories", key, f"{path.name}:{i}", content, len(content.encode()))
        counts["outside_narrative_slice"] += len(rows) - 2500
    rng = random.Random(50256)
    rng.shuffle(records)
    out.mkdir(parents=True, exist_ok=False)
    stats = {}
    windows = {}
    with (out / "documents.jsonl").open("w") as manifest_file:
        for source in ("wiki", "stories"):
            for split in ("train", "validation"):
                name = f"{source}-{split}"
                dest = out / (name + ".u16")
                offset = 0
                with dest.open("wb") as writer:
                    docs = [r for r in records if r["source"] == source and r["split"] == split]
                    for r in docs:
                        ids = r.pop("ids")
                        assert min(ids) >= 0 and max(ids) == 50256 and ids[-1] == 50256
                        assert 50256 not in ids[:-1]
                        writer.write(np.asarray(ids, dtype="<u2").tobytes())
                        manifest_file.write(json.dumps(dict(r, offset=offset, tokens=len(ids)))+"\n")
                        offset += len(ids)
                stats[name] = dict(tokens=offset, docs=len(docs), sha256=file_hash(dest))
                arr = np.memmap(dest, mode="r", dtype="<u2")
                borders = np.flatnonzero(arr == 50256)[:-1]
                windows[name] = [tokenizer.decode(arr[max(0,b-8):b+9].tolist()) for b in rng.sample(list(borders),3)]
    summary = dict(split_salt=SALT, raw_sha256=raw_hashes, shards=stats, rejections=counts,
                   examples=examples, boundary_windows=windows, documents_sha256=file_hash(out/"documents.jsonl"),
                   sources={"wiki":"FineWeb-Edu 87f09149ef4734204d70ed1d046ddc9ca3f2b8f9, ODC-By collection; selected English Wikipedia article prose, attribution by canonical article group, CC BY-SA",
                            "stories":"TinyStories f54c09fd23315a6f9c86f9dc80f725de7d8f9c64, CDLA-Sharing 1.0, English synthetic stories"})
    (out / "manifest.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    prepare(args.manifest, args.out)

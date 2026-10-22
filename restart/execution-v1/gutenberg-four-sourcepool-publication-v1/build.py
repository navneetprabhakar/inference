"""Publish four individually reviewed source records; never launch training."""
import datetime
import hashlib
import json
import os
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE / "m2-intake"
FINAL = ROOT / "gutenberg-individual-admissions-v1"
STAGING = ROOT / ".gutenberg-individual-admissions-v1.preparing"
PROPOSAL = ROOT / "gutenberg-four-individual-admission-proposal-v1/proposal.json"
CLOSURE = ROOT / "gutenberg-four-individual-admission-matrix-closure-v1/closure.json"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(name, obj):
    raw = (json.dumps(obj, ensure_ascii=False, indent=2) + "\n").encode()
    write_bytes(name, raw)


def write_bytes(name, raw):
    path = STAGING / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def main():
    assert not FINAL.exists() and not STAGING.exists(), "Existing publication: do not rerun"
    assert digest(PROPOSAL) == "494851648497b6b70436120c6fc2770b261d270d918db1c9eb5bff7963cbc8d8"
    assert digest(CLOSURE) == "be29a6cd67ab210ca8006b102639ed0de94578be70042713604e67a65b2daeca"
    proposal = json.loads(PROPOSAL.read_text())
    closure = json.loads(CLOSURE.read_text())
    assert closure["ready_for_parent_atomic_publication"]["ebook_IDs"] == [3028, 34616, 2521, 8530]
    evidence_names = [
        "gutenberg-four-individual-admission-proposal-v1/proposal.json",
        "gutenberg-four-individual-admission-matrix-closure-v1/closure.json",
        "gutenberg-seven-nominees-source-resolution-v1/review.json",
        "gutenberg-eighteen-quality-scope-audit-v1/review.json",
        "gutenberg-first-complete-units-v1/documents.json",
        "gutenberg-four-current-custody-v3/result.json",
        "gutenberg-four-current-custody-v3/source-coverage.json",
        "gutenberg-four-current-custody-v3/family-custody.json",
        "gutenberg-four-custody-parent-terminal-verification-v3/verification.json",
        "gutenberg-four-new29-delta-v1/result.json",
        "gutenberg-four-new29-delta-v1/comparisons.json",
        "gutenberg-four-longWB-delta-v1/result.json",
        "gutenberg-four-longWB-delta-v1/comparisons.json",
        "gutenberg-four-longWB-delta-independent-verification-v1/verification.json",
    ]
    evidence = {str((ROOT / name).resolve()): digest(ROOT / name) for name in evidence_names}
    for folder, pairs in [("gutenberg-four-new29-delta-v1", 116), ("gutenberg-four-longWB-delta-v1", 16)]:
        result = json.loads((ROOT / folder / "result.json").read_text())
        assert result["candidate_document_pairs"] == pairs and result["matched_pairs"] == 0
        assert digest(ROOT / folder / "comparisons.json") == result["comparisons_SHA256"]
    screen = json.loads((ROOT / "gutenberg-four-current-custody-v3/result.json").read_text())
    assert screen["status"] == "COMPLETE_TARGETED_SCREEN_NOT_ADMISSION_OR_UNKNOWN_ANCESTRY_CLEARANCE"
    assert screen["protected_component_holds"] == [] and screen["coverage_holds_must_be_reviewed"] == 4
    legacy_paths = [BASE / "m0-registry-v1/registry.json", BASE / "data-train/manifest.json",
                    BASE.parent / "fineweb-salvage-reviewed-v1/accepted-manifest.csv"]
    legacy_before = {str(path.resolve()): digest(path) for path in legacy_paths}
    STAGING.mkdir()
    records, reservations = [], []
    for item in proposal["records"]:
        candidate = item["exact_candidate"]
        ebook_id = candidate["ebook_ID"]
        unit = Path(candidate["file"]).read_bytes()
        ancestor = candidate["captured_raw_source_ancestor"]
        original = Path(ancestor["path"]).read_bytes()
        interval = candidate["original_source_interval"]
        assert hashlib.sha256(unit).hexdigest() == candidate["text_SHA256"]
        assert hashlib.sha256(original).hexdigest() == ancestor["SHA256"]
        assert original[interval["start"]:interval["end_exclusive"]] == unit
        assert item["language_and_tokens"]["raw_strict_language_pass"] is True
        assert item["source_rights_and_original_English"]["status"] == "SOURCE_SUPPORTED_NO_IDENTIFIED_COMPONENT_BLOCKER"
        receipt_path = Path(ancestor["path"]).parent / f"pg{ebook_id}-receipt.json"
        receipt = json.loads(receipt_path.read_text())
        assert receipt["raw_or_partial_sha256"] == ancestor["SHA256"]
        evidence[str(receipt_path.resolve())] = digest(receipt_path)
        local_file = f"units/pg{ebook_id}.txt"
        write_bytes(local_file, unit)
        records.append({
            "document_id": f"m2:pg:{ebook_id}:first-complete:{candidate['text_SHA256']}",
            "ebook_ID": ebook_id, "source_group": "Project Gutenberg",
            "title": candidate["title"], "authors": candidate["authors"],
            "family_component_ID": candidate["family_component_ID"], "split": "train",
            "admission": "INDIVIDUAL_REVIEWED_PASS_LOCAL_RESEARCH_SOURCE_POOL",
            "text": unit.decode("utf-8", errors="strict"), "file": local_file,
            "text_SHA256": candidate["text_SHA256"], "UTF8_bytes": len(unit),
            "M1_content_tokens": item["language_and_tokens"]["M1_content_tokens_existing"],
            "EOS_separate": 1, "token_counts_recomputed": False,
            "source_URL": receipt["hops"][-1]["url"],
            "source_requested_URL": receipt["requested_native_URL"],
            "captured_raw_source_ancestor": ancestor, "original_source_interval": interval,
            "primary_genre": item["primary_genre_proposed"], "subgenre": item["source_subgenre"],
            "contextual_risks": item["known_risks_and_context"],
            "retained_source_features": item["retained_minor_format_or_dependency"],
            "source_rights_and_original_English": item["source_rights_and_original_English"],
            "training_execution_authorized_by_this_pool": False,
        })
        reservations.append(item["family_train_assignment_proposed"])
    assert len(records) == 4 and sum(r["M1_content_tokens"] for r in records) == 23090
    dataset = b"".join((json.dumps(r, ensure_ascii=False) + "\n").encode() for r in records)
    write_bytes("documents.jsonl", dataset)
    write_json("family-train-overlay.json", {
        "scope": "Separate train-only source-pool custody; original M0 is unchanged.",
        "reservations": reservations,
        "future_acquisitions_automatically_admitted": False,
        "future_confirmed_aliases_and_quote_work_edges_must_be_reconciled": True,
    })
    counts = {"admitted_documents": 4, "primary_family_components": 4,
              "M1_content_tokens": 23090, "EOS_separate": 4, "M1_targets_with_EOS": 23094,
              "UTF8_bytes": sum(r["UTF8_bytes"] for r in records), "split": "train",
              "primary_genres": {"everyday_narrative": {"documents": 3, "content_tokens": 16585},
                                 "exposition_reference": {"documents": 1, "content_tokens": 6505}},
              "tokenizer_scope": "Existing M1 8192-token BPE. Final M3 tokenizer recount remains required.",
              "final_M2_mixture_or_cohort_acceptance_claimed": False,
              "training_updates": 0}
    write_json("counts.json", counts)
    write_json("admission-decision.json", {
        "UTC": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "decision": "PARENT_ADMITS_EXACT4_INDIVIDUAL_SOURCE_RECORDS",
        "authority": "MILESTONE_PLAN.md:47 explicitly permits individual passes without cohort extrapolation.",
        "evidence_SHA256": evidence, "unchanged_legacy_artifacts_SHA256": legacy_before,
        "builder_SHA256": digest(Path(__file__)),
        "scope": "Known source lineage, bounded local-research source/component disposition, complete individual quality reviews, strict language, frozen literal overlap policies and train-only family custody. Minor source features are explicitly retained. No source-wide yield, universal factual correctness, unknown semantic-paraphrase, model-weight licensing or redistribution claim.",
        "remaining_M2": "Full source mixture, broader cohort samples, evaluation domains, final-tokenizer counts and final release-wide dedup remain incomplete.",
        "training_or_new_weights_authorized": False,
    })
    assert {str(p.resolve()): digest(p) for p in legacy_paths} == legacy_before
    loaded = [json.loads(line) for line in (STAGING / "documents.jsonl").read_text().splitlines()]
    assert len(loaded) == 4
    for record in loaded:
        assert record["text"].encode() == (STAGING / record["file"]).read_bytes()
    files = {str(p.relative_to(STAGING)): {"bytes": p.stat().st_size, "SHA256": digest(p)}
             for p in STAGING.rglob("*") if p.is_file()}
    write_json("manifest.json", {"status": "ADMITTED_INDIVIDUAL_SOURCE_POOL_NOT_FINAL_M2",
                                 "files": files, "counts": counts})
    assert sum(p.stat().st_size for p in STAGING.rglob("*") if p.is_file()) < 8000000
    for path in STAGING.rglob("*"):
        if path.is_file():
            path.chmod(0o444)
    STAGING.rename(FINAL)
    fd = os.open(ROOT, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    print(json.dumps({"status": "PUBLISHED", "pool": str(FINAL), "counts": counts,
                      "manifest_SHA256": digest(FINAL / "manifest.json")}))


if __name__ == "__main__":
    main()

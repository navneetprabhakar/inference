#!/usr/bin/env python3
"""Publish the frozen second-iteration local foundation research decision."""
# Creator: Navneet Prabhakar
import json
import time
from pathlib import Path
from slm.data.foundation_research import RULE,release
from slm.data.schema import digest
from slm.data.tokenized import sha


def main():
    population=Path('data/iteration-two-foundation-candidates-v1/staged')
    audit=Path('data/iteration-two-foundation-candidates-v1/quality')
    review=Path('reports/milestone-forty-seven-foundation-review.json')
    legacy=Path('data/delegated-dialogue-review-v2/decisions.json')
    recent=Path('reports/milestone-forty-five-dialogue-review.json')
    recent_sample=Path('data/iteration-two-dialogue-preparation-v1/quality/sample.jsonl')
    sources=json.loads((population/'sources.json').read_text())
    decisions={
        'OpenAssistant/oasst2': 'Pinned Apache-2.0 source card/license evidence permits this private bounded language-foundation experiment. Publisher language/review metadata and the delegated readings support research selection, not verified authorship, factual correctness, privacy clearance or conversation-SFT certification. Preserve source attribution and notices.',
        'databricks/databricks-dolly-15k': 'Pinned CC-BY-SA-3.0 card/license evidence permits the bounded private training experiment. Preserve attribution, license and share-alike obligations for adapted dataset distributions. Do not infer that training automatically resolves every downstream model-license question. Employee-written and Wikipedia-derived content assertions are publisher claims, not independent verification.'}
    policy=dict(version=1,kind='two-source-foundation-research-v1',status='accepted_for_bounded_research',scope='local_foundation_pilot',
        authorized_by='Navneet Prabhakar',authorization_instruction='Execute the project goal from scratch and review source material as the delegated expert. This decision authorizes only bounded private local foundation research; no human attestation, production/SFT approval or new cloud spend.',
        review_mode='delegated_expert',human_attestation=False,population_manifest_sha256=sha(population/'manifest.json'),
        audit_manifest_sha256=sha(audit/'manifest.json'),development_review_sha256=sha(review),legacy_review_sha256=sha(legacy),
        recent_review_sha256=sha(recent),recent_sample_sha256=sha(recent_sample),eligibility_rule_sha256=digest(RULE),
        source_bindings={name:digest(sources[name]) for name in decisions},source_decisions=decisions,
        research_assumptions='Frozen canonical population and pinned source/card/license evidence are trusted local inputs. Reconstruct deterministic eligibility, whole-group exclusions and exact released payloads; do not independently re-download or re-derive upstream adapters. All 68 newly selected train paths were read, but most population rows were not individually read. Publisher English plus complete language windows and a lack of strong contradictory evidence are research proxies, not English certification. The clustered sample does not yield a source-wide error estimate.',
        risk_acceptance='Accept residual factual errors, weak prose, imperfect language/scope/privacy screens and unknown row-level rights for this finite private language-foundation experiment. Quarantine known prior graded nonapprovals, new excluded groups, privacy/structural/scope/identity/template/code attention and strong non-English evidence. Do not call remaining rows factual gold, conversation-SFT approved, comprehensively SFW or privacy cleared. Retain heldouts and separate later SFT admission. No production distribution or capability acceptance follows.',
        limits=dict(processed_positions=10485760,updates=12288,max_passes=2,max_parameters=100000000))
    policy_path=Path('configs/iteration-two-foundation-research-v1.json')
    if policy_path.exists():
        if json.loads(policy_path.read_text())!=policy:raise ValueError('Existing frozen policy differs')
    else:policy_path.write_text(json.dumps(policy,indent=2,sort_keys=True)+'\n')
    output=Path('data/iteration-two-foundation-research-v1');started=time.monotonic()
    report=release(population,audit,review,legacy,recent,recent_sample,policy_path,output)
    receipt=dict(creator='Navneet Prabhakar',report=report,release_manifest_sha256=sha(output/'manifest.json'),
        policy_file_sha256=sha(policy_path),script_sha256=sha(__file__),elapsed_seconds=time.monotonic()-started,
        release_bytes=sum(p.stat().st_size for p in output.iterdir()),second_iteration_training_started=False,
        production_accepted=False,conversation_sft_accepted=False)
    with Path('reports/milestone-forty-seven-foundation-release.json').open('x') as out:out.write(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    print(json.dumps(receipt,indent=2,sort_keys=True))


if __name__=='__main__':main()

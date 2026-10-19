#!/usr/bin/env python3
"""Publish recorded expert decisions for a hash-frozen sample, never infer new judgments."""
# Creator: Navneet Prabhakar
import hashlib
import json
from pathlib import Path
from slm.data.schema import digest
from slm.data.review_stream import export_packet,release,open_checked,DEFAULT_LIMITS

SOURCE='databricks/databricks-dolly-15k'
SAMPLE_SHA='00ee5fc7111956d760711132e6f560d15d1b4e237b283ca304d0ac5745318d5c'
# Each line is an actual decision from reading this frozen sample. Rejected
# high-stakes rows 30/31 were screened by topic, not fully fact-checked.
# This table is not a classifier and must not be applied to other populations.
DECISIONS='''
A|Responsive historical band description; minor spelling noise acceptable for research.
R|Financial-contract explanation excluded from this first general-language subset; not a finding that the definition is false.
R|Reference contains an undated current-world-champion assertion; keep out of this subset.
R|Fragmentary answer and misspelled proper name; weak English target.
R|Animal-care prescription includes water restriction; excluded from first subset without domain review.
R|Requested exhaustive extraction omits Barin Ghosh from the supplied passage.
R|Long copied navigation/reference boilerplate makes the input unsuitable for this small subset.
R|Infant-development advice contains unsupported warning criteria; exclude medical advice.
R|Opening instrument list omits clarinet and tool list omits scissors; later prose does not fully fix the requested classification.
A|Correct concise solution to the minimum-three-ducks arrangement.
A|Simple responsive botanical classification.
A|Complete requested formal/informal clothing classification.
R|Niche instrument classification has no supplied supporting context; defer verification.
A|Coherent explanation of four ACID properties; introductory simplification acceptable.
A|Requested birthplace extracted correctly from supplied context.
A|Single village correctly extracted from supplied context.
A|Requested films consistently partitioned; no unrelated material.
R|Long target contains malformed quarter-circle explanation and extensive copy-editing defects.
R|Unqualified sleep and narcolepsy advice; excluded from initial general-language subset.
A|Director extracted correctly from supplied context.
A|Responsive explanation of the three IAU criteria and the uncleared-orbit condition.
A|Summary follows provided context and preserves explicit historical dates.
A|Toppings extracted correctly from supplied context.
R|Vague response blends categorization with sentiment without clearly defining either.
A|Dredger definition follows supplied reference.
R|Third-law summary loses its absolute-zero claim; first-law closed-system wording is also misleading.
A|Complete string/wind partition; one minor spelling error acceptable for research.
A|Answer resolves the place as a village and locates it in the supplied county.
A|Four requested Galilean moons extracted exactly.
R|Summary has multiple spelling defects and garbles the count of other shows in its source.
R|Screened out by health-topic scope; not a full factual assessment of this record.
R|Screened out as dated pension/legal data; misspelled output key; full source table not fact-checked.
R|Niche instrument classification has no supplied supporting context; defer verification.
A|Summary preserves the context's explicit 2021 adoption qualification.
R|Garbled film titles and unexplained subjective ranking; poor English target.
A|Concise fictional-character identification grounded in provided reference.
R|Answer contradicts source award categories and event; reject unsupported additions.
A|Complete ten-item city suggestion list; treated as subjective suggestions, not a factual ranking.
R|Asserts that outcome disparity establishes both kinds of bias without sufficient evidence; overgeneralized causal explanation.
R|Current election-resource guidance deferred from the first subset; URL and current procedure not independently verified.
A|Balanced pros/cons extracted from supplied dredging reference.
R|Niche instrument classification has no supplied supporting context; defer verification.
A|Responsive context-grounded club description; near-verbatim answer retained as a known diversity limitation.
A|Correctly repairs the question's president premise by identifying the prime-minister role.
R|Invents company activities without framing them as hypothetical brainstorming.
A|Historical manager and trophy count extracted from supplied reference.
R|Unsupported fixed water-use percentage omits flow-rate and bath-volume assumptions.
A|Singles list faithfully extracts supplied discography; not claimed independently exhaustive today.
A|Correctly rejects inconsistent square-angle premise.
R|Scully is misidentified as an antagonist; wrong target.
A|Complete comparative animal-speed classification at the coarse level requested.
R|Inconsistent classification of Western and European honey bees; unsupported wild/domesticated partition.
A|Complete Clue classification with explicit classic-edition qualification for distractors.
R|Infant developmental guidance deferred from initial general-language subset.
R|Niche instrument classification has no supplied supporting context; defer verification.
R|Unfocused summary with substantial grammar defects; not selected as a clean English target.
A|Responsive summary of the supplied water boundaries and hills.
A|Historical primary winner correctly extracted from the supplied passage.
A|Coherent digital-twin definition and illustrative manufacturing use.
R|Unqualified lawn-mower classification ignores common nonmotorized variants; ambiguous target.
A|Complete original-game starter list and type associations.
R|Biomedical classification deferred from initial subset; no clinical or taxonomic verification claimed.
A|Responsive subjective television suggestions; no precision-ranking claim.
R|Pain advice and movement prescription excluded without domain review.
A|Complete requested game-franchise partition.
R|Target changes the source's 454 bird species to a hundred and contains fragments.
R|Does not explain the requested popularity causes and ends with an incomplete sentence.
A|Concise historical state-admission sequence.
A|Answer preserves source's more-than-sixty qualification.
R|Adult-topic branding excluded from the initial SFW subset; not a global adult-content prohibition.
R|Regional resort snowfall substituted for city weather without enough qualification.
A|Responsive varied cold-coffee list; non-English beverage names are proper names within English text.
R|Blanket statewide gardening recommendations omit material climate/season distinctions; weak target.
R|Adds room/hall/seating quantities absent from the reference; not admitted without further verification.
R|Historical first-camera claim depends on unstated category boundaries and lacks sufficient corroboration.
R|Changes lack of government experience to lack of political experience and drops the other stated concern.
A|Correctly identifies 2021 and the nine-million population from the supplied reference.
R|Unanchored all-time sports record; current-record claim not verified for this release.
R|Long essay contains unverified quotations and reference debris; unsuitable for this first clean subset.
A|Appropriately identifies multiple sizing factors and points to manufacturer guidance.
R|Target says 4.51 years instead of 4.51 billion years; critical factual corruption.
R|Changes seventh century to seventeenth and misdescribes check/checkmate; multiple source contradictions.
R|Unanchored latest-team claim and ambiguous team identity; not verified for this release.
A|Concise responsive author identification.
R|Health summary mislabels DID as DIS and distorts identity-count information; exclude.
A|Plot summary faithfully follows the provided reference.
R|Unanchored career totals, unsupported additions and grammar defects; reject current target.
A|Complete named-character extraction from supplied fictional plot; non-graphic crime references remain SFW here.
A|Responsive historically anchored 2023 award answer; promotional final clause is a known style limitation.
R|Answers with a narrow competition subevent and extra details without support; defer verification.
R|Clinical COVID/vaping guidance requires current domain verification; excluded from this subset.
R|Several requested banana associations are unexplained and arbitrary; weak instructional target.
R|Attributes C++ speed to static typing alone; misleading causal explanation.
'''.strip().splitlines()


def main():
    sample=Path('data/complete-small-source-v1/quality/sample.jsonl')
    if hashlib.sha256(sample.read_bytes()).hexdigest()!=SAMPLE_SHA:raise ValueError('Frozen review sample differs')
    rows=[json.loads(line) for line in sample.read_text().splitlines()]
    dolly=[r['record'] for r in rows if r['record']['source']==SOURCE]
    if len(dolly)!=93 or len(DECISIONS)!=93:raise ValueError('Recorded decision coverage differs')
    folder=Path('data/delegated-source-review-v1')
    if folder.exists():raise FileExistsError(folder)
    packet=json.loads(Path('data/complete-small-source-review-v1/pending-master.json').read_text())
    packet.update(review_mode='delegated_expert',reviewer='delegated_expert',human_attestation=False,
        review_authorization=dict(version=1,authorized_by='Navneet Prabhakar',recorded_on='2026-10-19',scope='explicit_rows_only',
            dataset_manifest_sha256=packet['dataset_manifest_sha256'],instruction='this is a simple problem statement, you can review as expert'))
    for name,source in packet['source_reviews'].items():
        if name==SOURCE:
            source.update(approved=True,terms_reviewed=True,allowed_categories=['sfw'],evidence_note=
                'Pinned publisher card explicitly permits academic/commercial LLM training under CC-BY-SA-3.0 and describes employee-written responses and Wikipedia contexts. Preserve source/license/attribution evidence; no unrestricted or exclusive-rights guarantee. Approval covers explicitly accepted SFW rows only, for private research; no unsampled population or distribution clearance.')
        else:
            reason={'HuggingFaceFW/fineweb-edu':'Underlying web-content rights and CommonCrawl terms need a distinct source-specific admission policy.',
                'HuggingFaceH4/ultrachat_200k':'Synthetic conversation provenance and applicable upstream generation terms remain unresolved.',
                'OpenAssistant/oasst2':'Publisher Apache-2.0 evidence retained; row quality, privacy and multi-turn context still require separate review.'}[name]
            source.update(approved=None,terms_reviewed=None,allowed_categories=[],evidence_note='Deferred from this research release. '+reason)
    for entry in packet['examples'].values():
        entry['decision'].update(approved=False,note='Excluded from this release because source/row review is deferred; content not graded.')
    for record,line in zip(dolly,DECISIONS):
        code,note=line.split('|',1);entry=packet['examples'][record['example_id']]
        if entry['record']!=record:raise ValueError('Decision content binding differs')
        approved=code=='A'
        entry['decision'].update(approved=approved,english_verified=True if approved else None,
            privacy_verified=True if approved else None,quality_verified=True if approved else False,
            content_category='sfw' if approved else None,upstream_partition=record['split'],
            partition_evidence='Preserve frozen curated partition and entire split-group boundary; no new publisher split asserted.',note=note)
    folder.mkdir();packet_file=folder/'decisions.json'
    packet_file.write_text(json.dumps(packet,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
    export_packet(packet_file,folder/'stream')
    result=release('data/complete-small-source-v1/staged',folder/'stream',folder/'release',limits=DEFAULT_LIMITS)
    with open_checked(folder/'release') as checked:train_rows=len(checked)
    result.update(creator='Navneet Prabhakar',review_mode='delegated_expert',human_attestation=False,
        authorization=packet['review_authorization'],sample_sha256=SAMPLE_SHA,dolly_rows_disposed=93,
        dolly_full_text_assessed=91,dolly_topic_screened_without_full_fact_check=2,
        other_source_rows_excluded_without_content_grade=194,
        explicitly_approved=sum(line.startswith('A|') for line in DECISIONS),checked_train_rows=train_rows,
        unsampled_rows_approved=0,whole_corpus_admission=False,neural_updates=0,new_teacher_launches=0,cloud_jobs=0,
        limitation='Purposive/stratified sample, not an unbiased quality-rate estimate. Source-grounded judgments are not independent fact verification. Privacy judgment means no visible private identifiers in these texts, not proof of provenance. Too little data for a 1M-position language pilot without excessive replay.',
        release_manifest_sha256=hashlib.sha256((folder/'release/manifest.json').read_bytes()).hexdigest(),
        packet_sha256=digest(packet),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    Path('reports/milestone-thirty-seven-source-review.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,indent=2,sort_keys=True))


if __name__=='__main__':main()

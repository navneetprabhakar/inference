#!/usr/bin/env python3
"""Replay full-text judgments for this exact 64-row packet only."""
# Creator: Navneet Prabhakar
from collections import Counter
import json
from pathlib import Path
from slm.data.schema import digest
from slm.data.review_stream import export_packet, release, open_checked, DEFAULT_LIMITS
from slm.data.tokenized import sha

ROOT = Path('data/iteration-three-sft-review-v2')
READABLE = 'c5e424e7c6bd42edbce16fd81f77bc84e44a906286e002589102714ae5c7503b'
PENDING = '57352cbb6b5bbb4fb4b02c57ef42b8bd400e3795d035f1873df6ae0e0faa9241'
# A: admit explicit row. R: observed response defect. D: verification/scope deferral.
# Every indexed complete dialogue was read; no unseen row is classified.
JUDGMENTS = '''
0|R|Generic prompt/filter advice does not explain how to ground answers in the supplied website content; opens with an unsupported diagnosis of unstable responses.
1|R|Second joke has a weak disconnected Zamboni ending after a request for improvement; not selected as a clean first humor target. No population humor judgment.
2|D|Substance-consumption preference advice is outside this initial SFW subset; no health/legal accuracy assessment or alternate category admission.
3|D|Game construction instructions and displayed geometry need independent technical verification; no factual approval assigned.
4|D|Health/weight-loss guidance is outside this first general-language subset; clinical accuracy not assessed.
5|R|Initial target confidently answers five instead of the three-in-line solution supplied only after challenge. Keep the entire flawed dialogue unadmitted.
6|R|Nonstandard advices and misspelled assignmens weaken this short English target. The closing allocate some time to having fun phrase is valid English; this corrects the first review note, with the non-admission unchanged.
7|A|Both replies explicitly ask for rephrasing rather than inventing meaning for random input; no factual answer or private identifying content. Intentional user gibberish is retained as clarification context.
8|D|Initial live-weather limitation is appropriate, but the later precise historical temperature range has not been independently checked.
9|A|Provides five then ten distinct size-related alternatives, responsive to follow-up. Alternatives are sense-dependent; ascending scale is approximate rather than a calibrated ranking.
10|R|Malformed phrases such as in the following how and leaning fishing weaken otherwise relevant suggestions; not a clean first English target.
11|R|Initial sorting is correct, but the closing response asks whether this is an intelligence test instead of acknowledging the user naturally.
12|R|Starts by defining a crane-mounted wrecking ball, then lists broad earthmoving/farming uses without explaining the shift in equipment.
13|R|Unsupported claims about instructGPT screening, rate limits and training-set contents would teach false self-description; spelling defects remain.
14|D|Unanchored current vehicle ranking and price need dated evidence. Not admitted as a timeless factual answer.
15|R|After being asked for project ideas, repeats a demand for examples instead of offering ideas or clarifying the unspecified software.
16|A|Asks for budget, car preferences and requirements before recommending a purchase; no unverified product recommendation or cost claim.
17|D|Absolute claim that HDMI audio will not work lacks converter/input qualification; hardware-specific correctness not established.
18|R|Fails to identify the cheer pilot anagram, substitutes rotor speculation and an unsupported Wikipedia uniqueness claim.
19|R|Corrects one requested typo but retains several grammatical defects and unverified precise historical details in earlier supervised turns.
20|A|Correctly factors the difference of squares as (x-y)(x+y); direct expansion recovers x squared minus y squared. Explanatory repetition retained.
21|R|Addresses acoustics only and omits most explicit bedroom layout, gaming, guitar-space and black-color requests; partial advice is insufficient for this subset.
22|R|Minimal opening acknowledgment and awkward weight your intelligence wording make this a weak language target; no intelligence rating is endorsed.
23|R|Alliteration is present, but a long run-on about selling a soul lacks a connected business story.
24|D|Adds a precise nursery-rhyme publication year not independently checked in this batch; no historical approval.
25|A|Accepted plural alternatives and Greek-origin distinction checked against the dictionary publisher. Preference wording is general, not a quantified expert survey. Evidence: https://www.merriam-webster.com/grammar/the-many-plurals-of-octopus-octopi-octopuses-octopodes
26|A|Offers a virtual guide and interactive historical characters as proposed AR features; a brief creative suggestion, not a claim that an implemented system can supply any information accurately.
27|D|Botanical premise and broad scientific-evidence claims are not independently assessed in this batch; no factual approval or assertion that this row is false.
28|A|Explicitly labels the interpretation as an assumption and supplies a proposed archaic wording, followed by a polite close. Creative style example, not verified historical Shakespeare usage.
29|A|Concise historical identification and 1978-2002 tenure corroborated by Kenya's presidential library. Evidence: https://www.presidentiallibrary.go.ke/presidents/he-daniel-toroitich-arap-moi
30|A|Responsive tongue-twister continuation and alliterative reply; language play rather than a numerical wood-volume claim.
31|R|Initial event date omits the year; later response gives the specific television-series start rather than resolving the franchise-origin question.
32|A|Direct coherent general advice to focus a story summary on main ideas and important details; limited but responsive.
33|A|Describes common seasonal observations with typically/often qualifiers. Temperate-season bias retained as a limitation; not a universal climate or forecast claim.
34|D|Several title identities and the ambiguous Luther classification require separate film/series verification; no genre-taxonomy approval.
35|D|Blanket credit-card and home-ownership financial advice is outside this initial general-language subset; suitability and financial accuracy not assessed.
36|A|All listed characters assigned to their corresponding films; checked against the three official Disney film pages. No franchise-exclusivity claim. Evidence: https://movies.disney.com/the-lion-king ; https://movies.disney.com/frozen ; https://movies.disney.com/finding-nemo
37|A|All twelve ordinary objects are placed in their usual kitchen/bathroom groups without omissions or added items; context-dependent uses do not change this requested everyday classification.
38|D|Specialist instrument classification has not been verified; no technical taxonomy approval.
39|D|Transit services and connection details need current local evidence; no route recommendation or current availability endorsement.
40|A|Responsive elementary extinct-versus-living species distinction; not a current conservation-status or population estimate.
41|D|Undated local restaurant recommendations lack current evidence and criteria; no restaurant endorsement.
42|R|Answer says an America instead of American; supported nationality context does not repair the malformed target.
43|D|Unanchored current popularity, product properties and price claims require dated product evidence; not admitted as timeless knowledge.
44|D|Specialist tailoring and armhole/mobility claims are not independently checked; no technical approval.
45|D|Book/movie classification depends on precise titles, adaptation types and versions; no independent bibliographic verification in this batch.
46|D|Adds detailed surfboard-origin/history claims beyond the use question without verification; whole response deferred rather than silently shortened.
47|R|Unanchored 2023 prediction, unsupported easy-sweep and greatest-player assertions are unsuitable as an enduring factual target.
48|R|Includes the malformed country name Austra; do not silently repair the requested ten-country list.
49|D|Unsupported strongest-character judgment lacks explanation and has a grammatical defect; fictional-lore ranking not assessed.
50|A|Location answer faithfully follows the supplied paragraph; contextual extraction only, not independent verification of the geography/etymology.
51|R|Last-five framing is undated and the answer adds years despite the requested song-and-artist-only format; not a current winner list.
52|D|Exclusive living-descendant claim depends on the story timeline and perspective; full fictional-lore assertion not verified.
53|A|Extracts December 25 while explicitly retaining the supplied 1973-1999 interval and leap-day exclusion; no present-day distribution claim.
54|A|All fifteen listed animals are correctly assigned to the requested ordinary mammal/amphibian categories; punctuation inconsistency retained.
55|D|External search found secondary corroboration, but the attempted primary publisher page returned 403; this batch does not admit the fictional-lore fact from that failed primary check.
56|A|Both nicknames are directly supported by the supplied paragraph; minor missing opening quotation mark retained, no semantic repair.
57|R|Exact age sixteen assumes birthday timing not supplied by birth year and album year alone; could be fifteen or sixteen at release.
58|R|Uses rotate where orbit/revolve is intended and awkward the sun is how we refer phrasing; not a clean first scientific-language target.
59|A|Conference and league extracted directly from the supplied text; no assertion of independently checked current affiliation.
60|A|Brief summary preserves the provided wealthy-man/servant comedy premise without unsupported additions.
61|R|Adds model year 2018, absent from the provided paragraph, even though the 134 horsepower value is supported.
62|R|Supplies an unreliable book title and spelling; not a clean literary reference target and no silent correction.
63|A|Lists exactly the six chess-piece types in the supplied paragraph; no omitted or added category.
'''


def main():
    if sha(ROOT/'pending.json') != PENDING or sha(ROOT/'readable.jsonl') != READABLE:
        raise ValueError('Exact reviewed packet required')
    packet = json.loads((ROOT/'pending.json').read_text())
    rows = [json.loads(v) for v in (ROOT/'readable.jsonl').read_text().splitlines()]
    receipts = json.loads((ROOT/'raw-receipts.json').read_text())
    judgments = {}
    for line in JUDGMENTS.strip().splitlines():
        i, code, reason = line.split('|', 2)
        i = int(i)
        if i in judgments or code not in ('A', 'R', 'D') or not reason.strip():
            raise ValueError('Invalid explicit judgment')
        judgments[i] = code, reason
    if set(judgments) != set(range(64)) or len(rows) != 64 or len(receipts) != 64:
        raise ValueError('Complete exact review coverage required')
    counts = Counter()
    for i, row in enumerate(rows):
        entry = packet['examples'][row['example_id']]
        if (row['index'] != i or row['messages'] != entry['record']['messages']
                or receipts[i]['example_id'] != row['example_id']
                or receipts[i]['record_sha256'] != digest(entry['record'])):
            raise ValueError('Full-text review binding differs')
        code, reason = judgments[i]
        approved = code == 'A'
        entry['decision'].update(approved=approved, english_verified=True if approved else None,
            privacy_verified=True if approved else None, quality_verified=True if approved else (False if code == 'R' else None),
            content_category='sfw' if approved else None, note=reason+' Full dialogue read; no text repair; raw receipt '+digest(receipts[i]))
        receipts[i].update(full_text_read=True, judgment=code, reason=reason)
        counts[code+'|'+row['source']+'|'+row['split']] += 1
    output = ROOT/'decisions.json'
    with output.open('x') as f:
        f.write(json.dumps(packet, indent=2, sort_keys=True, ensure_ascii=False)+'\n')
    (ROOT/'read-receipts.json').write_text(json.dumps(receipts, indent=2, sort_keys=True)+'\n')
    export_packet(output, ROOT/'stream')
    limits = {**DEFAULT_LIMITS, 'max_input_bytes': 256*1024**2, 'max_records': 50000}
    result = release('data/iteration-two-foundation-research-v1', ROOT/'stream', ROOT/'release', limits=limits)
    with open_checked(ROOT/'release') as index:
        actual = index.db.execute('SELECT split,count(*) FROM approved GROUP BY split').fetchall()
        train = list(index.values())
    report = dict(creator='Navneet Prabhakar', version=1, full_dialogues_read=64, human_attestation=False,
        review_mode='delegated_expert', judgments=dict(counts), release=result, checked_split_counts=dict(actual),
        checked_train_rows=len(train), decision_sha256=sha(output), read_receipts_sha256=sha(ROOT/'read-receipts.json'),
        release_manifest_sha256=sha(ROOT/'release/manifest.json'), readable_sha256=READABLE,
        script_sha256=sha(__file__), scope='Explicit row-only SFW research judgments. D is scope/verification deferral, R an observed defect; non-admission is not a population factual-error count. No neural update or corpus-wide SFT admission. Prior separate 49-row release is not implicitly merged.')
    (ROOT/'review-report.json').write_text(json.dumps(report, indent=2, sort_keys=True)+'\n')
    Path('reports/milestone-fifty-four-sft-review.json').write_text(json.dumps(report, indent=2, sort_keys=True)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Replay explicit judgments on a frozen sample; never grade unseen rows."""
# Creator: Navneet Prabhakar
import json
from pathlib import Path
import unicodedata
from slm.data.schema import digest
from slm.data.review_stream import export_packet, release, open_checked, DEFAULT_LIMITS
from slm.data.tokenized import sha

SOURCE = 'OpenAssistant/oasst2'
PARENT = '1c50b116a72202c6ed8c10eb41a1a4b3ce411f4d308c713f0a3d1c804558e730'
SAMPLE_SHA = '00ee5fc7111956d760711132e6f560d15d1b4e237b283ca304d0ac5745318d5c'
RAW_SHA = '0e3429b62d3ee3c2b2560cdbe374b3e987477ca6ec2bcff5f5c4bcbec7fc7f3b'

# Indices refer ONLY to this immutable packet's source-filtered, ID-sorted rows.
# Full text was read for these 56 rows; omitted rows receive no content grade.
# R includes scope/verification deferral, not solely a finding of factual error.
JUDGMENTS = '''
0|R|Opening asserts an unqualified first-century institutional continuity; later qualifications need historical/canonical verification. Not selected as a grounded target.
1|R|Final assistant turn changes topic to an Indonesian Ramadan song rather than answering the discrimination question.
2|R|The recovery explanation calls vinegar an emulsifier; an overly loose causal account in an otherwise useful cooking conversation.
3|R|Final answer gives dongle construction materials instead of selection criteria; initial navigation compatibility is also asserted without OS/browser qualification.
4|R|Overgeneralized causal claims about attention, addiction and radicalization; vague follow-up is answered by repetition rather than clarification.
5|R|Broad unsourced historical/comparative discrimination judgments and copy-editing defects; deferred rather than independently fact-checked.
6|R|Follow-up explicitly requests an example, but the answer supplies only a population-variance identity.
7|R|Unanchored current-leadership framing and broad institutional value judgments; not selected as a first grounded conversation target.
8|R|Initial response vaguely suggests ingredient ratios or spoilage without a practical emulsion-recovery explanation. The later discard advice does not repair that weak first target.
9|R|Revision retains unexplained technical jargon after the user asks for a nontechnical sales-director outline.
10|R|Asserts a Microsoft Store Google Maps app and offline/navigation capabilities without platform support evidence.
11|R|GDP table omits monetary units; follow-up assumes total GDP despite the user's request to emphasize richest. No independent economic-data verification.
12|A|Coherent general explanation of spatial interpolation and a relevant polite closing; no exposure diagnosis or numerical claim. Repetitive wording retained as a limitation.
13|R|Initial game setup includes a stock association between mental illness and a murder suspect and excessive scenario inventory; not selected as a clean first dialogue target.
14|A|Responsive introductory identification of Socrates and death in 399 BC; broad historical summary, not a specialist reference.
15|R|Final assistant response switches to a Chinese greeting and ignores the question; a raw path also lacks uniformly positive upstream review.
16|R|Snide initial challenge and a telepathic-chat suggestion do not give coherent help within the fictional premise.
17|R|The initial assistant response violates the explicit requirement to supply four options every time.
18|A|Five coherent situation-action-outcome interview-question sets relevant to data engineering; no claimed real incident or externally verified ranking.
19|A|Relevant request for game-setting preferences before starting; minor grammatical awkwardness retained, not rewritten.
20|R|Evasive follow-up claims to be designed unbiased and does not provide a useful reasoned assessment; repetitive opening.
21|R|Initial definition calls variance a sum of deviations and average L2 distance; inconsistent with its squared-deviation formula.
22|R|Conflates a static type checker with a compilation/performance method; does not distinguish mypy from a compiler such as mypyc.
23|R|Unqualified first-century institutional claim and oversimplified papal qualification discussion; no specialist verification.
24|R|Incorrect initial verbal definition of variance remains despite a later normalization explanation.
25|R|Confuses condensed cloud droplets with lighter-than-air vapor and gives an incorrect buoyancy/cloud-support explanation.
26|R|Unverified precise lifetime sales claim; defer this otherwise readable historical-computing answer rather than treat the number as established.
27|R|Child-injury and medication guidance is outside the first general-dialogue subset; full text read but clinical accuracy not assessed.
28|R|Navigation support is asserted without establishing how the USB GPS provider reaches the browser/app location service.
29|R|Cardano derivation discards original coefficients; proposed root 1 does not satisfy the original polynomial.
30|R|Initial clarification is malformed; later suggestions mix listening with binocular scanning and contain repeated language defects.
31|R|Current-model recommendations and comparative energy assertions are unanchored; deferred, not an independently verified energy comparison.
32|R|Produces an elaborate engine description instead of a playable adventure and repeats it after the complaint; does not satisfy the original task.
33|R|Inventories unverified study/journal claims after a simple thank-you; unnecessary unsupported factual additions.
34|R|Says Socrates refused the death penalty and was instead sentenced to death, an incoherent account; unsupported theological generalization follows.
35|R|Historical speculation mixes model capabilities and interface features; not selected as an enduring factual target despite its explicit March 2023 date.
36|R|JSON conversion loses orders of magnitude for Germany, UK and Italy; the initial ranking also places 73500 above 83880.
37|R|Claims to have analyzed unspecified data and invents demographic/geographic fruit-preference conclusions.
38|R|First assistant turn omits the four required options even though the final turn supplies them.
39|R|Unanchored GPT-5 not-announced claim would teach a stale current-state answer.
40|R|Repeats the opening menu after the user selects option 1; fails to advance conversation state.
41|R|GDP units are absent and follow-up responds pedantically instead of resolving the requested meaning of richest.
42|A|Coherent overview of interpolation, spatial correlation, kriging, inverse-distance weighting and splines. Introductory explanation, not calibrated environmental-risk advice.
43|R|Several spelling defects and unverified film-specific descriptions; not chosen as a clean target. No mature-content grade is assigned.
44|R|Continuous-expectation integral has infinity as both limits; correct die arithmetic does not repair the malformed definition.
45|R|Film example combines the opening castle encounter with a later French-guard sequence; avoid teaching a confident conflation.
46|R|Child-injury advice and awkward grammar; outside first subset, with no clinical assessment claimed.
47|R|Follow-up supplies two four-item category menus instead of four response options as requested.
48|R|Useful initial fictional search ideas end with speculative satellite-control access that is not grounded in the scenario's available capabilities.
82|R|First story is overly long for the requested dinner-table duration, and the later streamer fiction ends with an unanchored still-playing claim.
88|R|Fruit production and consumption rankings are asserted without dated evidence; production volume is also used as a proxy for preferences.
94|R|Changes from correcting the abacus premise to accepting it under user pressure; lack of electricity does not establish practical deep-learning efficiency.
101|A|Follow-up correctly narrows situation-action-outcome questions to data warehouses and pipelines while retaining the requested structure.
111|R|Says alliance commitments automatically drew allies into war; an overgeneralized account of decisions and varying treaty obligations.
117|R|Attributes cloud-base height to balanced upward/downward forces rather than condensation conditions; later color explanation cannot repair the first target.
119|A|Responsive list of problem synonyms; sense-dependent alternatives are acceptable for a general vocabulary request.
'''


def main():
    sample = Path('data/complete-small-source-v1/quality/sample.jsonl')
    raw = Path('data/audit-v1/oasst2/sample/rows.jsonl')
    if sha(sample) != SAMPLE_SHA or sha(raw) != RAW_SHA:
        raise ValueError('Frozen review inputs differ')
    packet = json.loads(Path('data/delegated-source-review-v1/decisions.json').read_text())
    if packet['dataset_manifest_sha256'] != PARENT:
        raise ValueError('Parent dataset differs')
    frozen = json.loads(Path('data/complete-small-source-review-v1/pending-master.json').read_text())
    if any(entry['record'] != frozen['examples'][key]['record'] for key, entry in packet['examples'].items()):
        raise ValueError('Recorded source content differs')
    rows = [entry['record'] for _, entry in sorted(packet['examples'].items()) if entry['record']['source'] == SOURCE]
    nodes = {}
    def walk(node):
        if node['message_id'] in nodes:
            raise ValueError('Repeated raw message identity')
        nodes[node['message_id']] = node
        for child in node.get('replies', []):
            walk(child)
    for line in raw.open():
        walk(json.loads(line)['prompt'])
    judgments = {}
    for line in JUDGMENTS.strip().splitlines():
        index, code, note = line.split('|', 2)
        index = int(index)
        if index in judgments or code not in ('A', 'R'):
            raise ValueError('Invalid explicit decision table')
        judgments[index] = (code, note)
    if len(rows) != 120 or len(judgments) != 56:
        raise ValueError('Frozen review coverage differs')
    metadata = []
    approved = []
    for i, row in enumerate(rows):
        path = [nodes[k] for k in row['lineage']]
        if len(path) != len(row['messages']):
            raise ValueError('Incomplete raw lineage')
        for j, (node, msg) in enumerate(zip(path, row['messages'])):
            role = 'user' if node['role'] == 'prompter' else 'assistant'
            if (node['parent_id'] != (path[j-1]['message_id'] if j else None)
                or role != msg['role'] or unicodedata.normalize('NFC', node['text']).strip() != msg['content']):
                raise ValueError('Raw message path/text differs')
        eligible = all(n.get('synthetic') is False and not n.get('model_name') and n.get('review_result') is True
                       and not n.get('deleted') and n.get('lang') == 'en' for n in path)
        receipt = dict(example_id=row['example_id'], record_sha256=digest(row), raw_path_sha256=digest(path),
                       raw_messages_sha256=RAW_SHA, eligible_metadata=eligible,
                       synthetic_flags=[n.get('synthetic') for n in path],
                       model_names=[n.get('model_name') for n in path],
                       review_results=[n.get('review_result') for n in path],
                       assistant_ranks=[n.get('rank') for n in path if n['role'] == 'assistant'],
                       full_text_read=i in judgments)
        metadata.append(receipt)
        decision = packet['examples'][row['example_id']]['decision']
        if i not in judgments:
            decision.update(approved=False, quality_verified=None, note='Not admitted: full dialogue not content-graded in this batch. Raw lineage/metadata only checked; this is not a negative content-quality finding.')
            continue
        code, note = judgments[i]
        accept = code == 'A'
        if accept and not eligible:
            raise ValueError('Accepted path fails raw metadata scope')
        decision.update(approved=accept, english_verified=True if accept else None,
                        privacy_verified=True if accept else None, quality_verified=True if accept else False,
                        content_category='sfw' if accept else None,
                        upstream_partition=row['validation_results']['upstream_mapping']['split'],
                        partition_evidence='Preserve frozen parent split group and official OASST ID-projection evidence; no partition is moved.',
                        note=note+' Raw path receipt: '+digest(receipt))
        if accept:
            approved.append(row['example_id'])
    source = packet['source_reviews'][SOURCE]
    if source['source_record']['card_sha256'] != '52bd472cf3cae04a4b21ecd5316f929741c47d991d4763b041c3a94de072dc31':
        raise ValueError('Publisher card differs')
    source.update(approved=True, terms_reviewed=True, allowed_categories=['sfw'], evidence_note=
        'Pinned publisher card identifies Apache-2.0 and conversation-tree structure, including mixed human/synthetic possibilities. Explicitly accepted SFW rows only, private research, with license/provenance retained. Raw pinned sample '+RAW_SHA+' has synthetic=false, null model_name, positive review and English metadata on every accepted path. These publisher annotations support this bounded decision; they are not independent proof of exclusively human authorship or blanket rights/privacy/factual quality. No unsampled or full-corpus approval. Path-receipt-set SHA256: '+digest(metadata))
    folder = Path('data/delegated-dialogue-review-v2')
    if folder.exists():
        raise FileExistsError(folder)
    folder.mkdir()
    packet_file = folder/'decisions.json'
    packet_file.write_text(json.dumps(packet, indent=2, sort_keys=True, ensure_ascii=False)+'\n')
    (folder/'raw-path-receipts.json').write_text(json.dumps(metadata, indent=2, sort_keys=True)+'\n')
    export_packet(packet_file, folder/'stream')
    result = release('data/complete-small-source-v1/staged', folder/'stream', folder/'release', limits=DEFAULT_LIMITS)
    with open_checked(folder/'release') as checked:
        train_rows = len(checked)
    result.update(creator='Navneet Prabhakar', review_mode='delegated_expert', human_attestation=False,
                  parent_manifest_sha256=PARENT, source_sample_sha256=SAMPLE_SHA, raw_tree_sample_sha256=RAW_SHA,
                  oasst_full_text_read=56, oasst_metadata_only=64, oasst_approved=len(approved),
                  approved_oasst_ids=approved, raw_path_receipts_sha256=digest(metadata),
                  checked_train_rows=train_rows, unsampled_rows_approved=0, neural_updates=0,
                  model_scores_observed=0, teacher_launches=0, cloud_jobs=0,
                  release_manifest_sha256=sha(folder/'release/manifest.json'), script_sha256=sha(__file__),
                  limitations='First-200-tree, family-correlated purposive sample, not a population quality-rate estimate. Rejections include scope/verification deferrals. Privacy review means no visible private identifiers in accepted text, not proof of origin. Three additional train dialogues cannot supply a language pilot or demonstrate learned dialogue capability.')
    Path('reports/milestone-forty-one-dialogue-review.json').write_text(json.dumps(result, indent=2, sort_keys=True)+'\n')
    print(json.dumps({k: result[k] for k in ('oasst_full_text_read', 'oasst_approved', 'checked_train_rows', 'release_manifest_sha256')}))


if __name__ == '__main__':
    main()

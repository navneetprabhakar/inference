"""Bind a bounded rights/provenance review to immutable local candidate bytes.

No corpus admission or legal certification. Run with the project root as cwd.
"""
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('restart/execution-v1/m2-intake')
OUT = ROOT / 'rights-review-parallel-v1'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

# All descriptions below are review paraphrases. No missing permission is
# treated as evidence that reuse is prohibited in every possible circumstance.
NOTES = {
 (1,0): ('hold_unresolved_permission', 'Original geometry page was inaccessible through the web tool. No exact-text license was established.', [], 'Retrieve historical page and owner terms or replace with an explicitly licensed source.'),
 (1,5): ('hold_unresolved_permission', 'Source article and privacy/terms page were inspected. The privacy statement does not establish a content reuse grant; factual agreement with a Federal Reserve source does not license this private explanatory wording.', ['https://www.usinflationcalculator.com/terms-privacy-policy/'], 'Establish permission for captured private prose; do not inherit Federal Reserve rights.'),
 (1,7): ('hold_unresolved_permission', 'Original dated classroom blog page was inaccessible through the web tool; no captured-version content license established.', [], 'Recover historical author/license evidence.'),
 (1,11): ('hold_unresolved_permission', 'Current original activity page is available and carries Penn State copyright in its footer. No express reuse grant was found on this inspected page. Its invitation to adapt activity prompts is not treated as a general model-training license.', ['https://www.shaverscreek.org/public-programs-and-events/nature-activities-to-go/amphibian-habitat-search/'], 'Check the actual center activity license or obtain permission; do not inherit the unrelated EMS course license.'),
 (1,22): ('hold_unresolved_permission', 'Original dated training-activity blog page was inaccessible through the web tool; no captured-version content license established.', [], 'Recover historical author/license evidence.'),
 (1,15): ('hold_third_party_ancestry', 'Dental-site page fetch timed out. Prior factual review identifies originating HHMI reporting. Agreement with HHMI facts establishes neither ownership of the dental-site wording nor a reuse grant from either party.', ['https://www.hhmi.org/news/how-teeth-sense-cold'], 'Resolve syndication/author ancestry and exact-copy terms.'),
 (1,25): ('hold_third_party_ancestry', 'Academy source could not be opened in this review. The design principles are attributed in factual evidence to EL Education. Institutional framework attribution is not evidence of permission to reproduce the wording.', ['https://eleducation.org/documents/20/ELED-Design_Principles-0915.pdf'], 'Resolve originating principles license and school modifications.'),
 (1,34): ('hold_mixed_original_and_quoted_text', 'Current school page is available with school copyright footer. Some prose reproduces national-curriculum framing, but original school commitments and Crown-derived wording have not been separated by exact spans. An OGL-compatible source passage would not clear the whole school document.', ['https://www.clevelandroadpri.uk/geography/', 'https://www.gov.uk/government/publications/national-curriculum-in-england-geography-programmes-of-study/national-curriculum-in-england-geography-programmes-of-study'], 'Identify exact licensed spans and school-owned additions without rewriting this frozen record.'),
 (1,18): ('hold_scope_restricted_grant', 'UW Medicine current policy permits specified nonprofit educational/library copying with author/source acknowledgement, notice and cost conditions, and requires permission for commercial use. Legacy hsnewsbeat page applicability and model-use scope are unresolved. Captured text also includes illustration credits; no image bytes are reviewed.', ['https://www.uwmedicine.org/about/compliance/disclaimer'], 'Resolve legacy-site policy scope, historical version and intended model/weights use; retain attribution and exceptions.'),
 (1,19): ('hold_third_party_ancestry', 'TV-site article is inaccessible through the web tool. Its factual support is a PLOS primary paper, whose license does not automatically license broadcaster reporting.', ['https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0221287'], 'Identify original report author/syndication and captured-text permission.'),
 (2,0): ('hold_publisher_abstract_rights', 'Record is a PNAS research abstract served by ADS. ADS terms require a browser challenge; PMC primary page also returned a challenge. Neither access through an index nor open availability establishes abstract-text reuse rights.', ['https://ui.adsabs.harvard.edu/help/terms/', 'https://pmc.ncbi.nlm.nih.gov/articles/PMC187748/'], 'Check exact 2003 PNAS article/abstract license and ADS metadata-vs-abstract terms.'),
 (2,7): ('hold_authorship_and_jurisdiction', 'Current Senate history page supports source identity. A guessed Senate copyright URL was inaccessible; no applicable explicit policy was obtained. Federal host alone is insufficient: confirm government authorship of narrative, quoted-source exceptions and applicability to intended use in India.', ['https://www.senate.gov/artandhistory/history/minute/Kansas_Nebraska_Act.htm'], 'Resolve government-work status from actual authorship/policy and any third-party quotation exceptions.'),
 (2,11): ('hold_unresolved_permission', 'Current Kenyon department page fetch timed out. Prior factual correspondence does not establish a content license.', ['https://www.kenyon.edu/academics/departments-and-majors/anthropology/'], 'Retrieve applicable university and captured-page content terms.'),
 (2,21): ('hold_scope_restricted_grant', 'WHOI copyright policy describes scholarly use by academic/scientific community and requires prior consent for commercial purposes. This does not establish an unrestricted foundation-model training or weights-distribution grant. NDSF subsite applicability and captured-version ownership remain to verify.', ['https://www.whoi.edu/press-room/copyright/', 'https://ndsf.whoi.edu/seeking-an-abundance-of-abyssal-life/'], 'Resolve NDSF author rights, permitted purpose and dissemination scope.'),
 (2,24): ('hold_publisher_and_endorsement_rights', 'Originating Iowa Press book page is available, carries university copyright, and links permission requests. It contains promotional description, sample questions and third-party endorsements. The Chicago-distributed captured copy needs its own chain; book availability is not a license to this copy.', ['https://uipress.uiowa.edu/books/medical-readers-theater-guide-and-scripts'], 'Resolve publisher-copy and quoted-review terms separately.'),
 (2,29): ('hold_scope_restricted_grant', 'Harvard expressly allows selected individual Gazette republication under conditions, including attribution, original links, limited edits, no endorsement and no automatic/wholesale republication; photos need separate permission. This is a real limited grant, not demonstrated permission for corpus processing or model/weights dissemination.', ['https://www.harvard.edu/media-relations/resources-for-media/content-from-the-harvard-gazette/'], 'Resolve model-use compatibility and exact captured-version exceptions/attribution.'),
 (2,30): ('hold_modern_curatorial_text', 'Current originating Bridwell exhibit prose is available. The seventeenth/eighteenth-century subject or book does not make modern exhibit commentary public domain. No exact commentary reuse license was established on the inspected exhibit page.', ['https://bridwell.omeka.net/exhibits/show/heresyerror/indexexpurgations'], 'Establish SMU/curator commentary license independently of historical objects.'),
 (2,33): ('hold_unresolved_permission', 'Original essay is available on an alternate Ohr URL. Religious subject matter and ancient source quotations do not establish a license to this modern English commentary; no reuse grant found on inspected essay.', ['https://ohr.edu/special/chanukah/yomi202a.htm'], 'Establish author/site permission for exact commentary.'),
 (2,40): ('conditional_reuse_candidate_not_cleared', 'NIST explicit policy permits copying/distribution of NIST information except material marked copyrighted, and requests proper credits. Current original report is available; retained body matches its narrative and contains NIST-researcher quotations. No third-party copyright marker was observed on that report body. This is stronger positive evidence than a .gov inference, but current policy alone does not prove historical captured-version exceptions or all jurisdiction/use details.', ['https://www.nist.gov/copyrights-disclaimers', 'https://www.nist.gov/news-events/news/2008/09/nist-studies-how-new-helium-ion-microscope-measures'], 'Record historical-version/exception check, exact attribution and intended-use basis before any admission. No images, logos or commercial endorsement rights inferred.'),
 (2,41): ('hold_explicit_noncommercial_sharealike_license', 'Original URL redirects to Penn State EMS course. Current footer identifies Cris Livecchi and Leanne Sulewski and CC BY-NC-SA 4.0 unless otherwise noted. Captured navigation differs from current version. This is explicit current-site licensing, with attribution, noncommercial and share-alike conditions; no determination of compatibility with intended training or weights use is made.', ['https://www.e-education.psu.edu/geog571/node/323', 'https://courses.ems.psu.edu/geog571/node/323', 'https://creativecommons.org/licenses/by-nc-sa/4.0/'], 'Verify captured-version license/exceptions and decide use/distribution compatibility before admission.'),
 (2,44): ('hold_guest_author_and_quotation_rights', 'Original Library of Congress post explicitly names student guest author Bryn Walker and includes an Edward Linenthal quotation. LOC general copyright guidance places reuse determination on users. Federal hosting is not proof of government authorship or permission to every quote; archive URL also differs from single-post canonical URL.', ['https://blogs.loc.gov/families/2021/07/history-in-our-backyards-monuments-and-memorials/', 'https://www.loc.gov/legal/security-copyright-and-privacy/understanding-copyright/'], 'Resolve guest-author employment/assignment/license and quotation provenance; no image rights inferred.'),
}

def main():
    assert len(NOTES) == 21
    inputs = {}
    judgments = []
    for v, count in [(1,4),(2,5)]:
        base = ROOT / f'individual-salvage-v{v}'
        candidate_path = base / 'candidates.jsonl'
        inputs[str(candidate_path)] = sha(candidate_path)
        candidates = [json.loads(x) for x in candidate_path.read_text().splitlines()]
        for i in range(1,count+1):
            fact_path = base / f'factual-risk-v{i}/judgments.jsonl'
            inputs[str(fact_path)] = sha(fact_path)
            for line_no, line in enumerate(fact_path.read_text().splitlines(),1):
                f = json.loads(line)
                if f['disposition'] != 'no_material_issue_identified':
                    continue
                n = f['candidate']
                c = candidates[n]
                assert c['normalized_sha'] == f['normalized_sha']
                assert c['tokens'] == f['tokens'] and c['url'] == f['url']
                actual_text_sha = hashlib.sha256(c['text'].encode()).hexdigest()
                assert actual_text_sha == c['text_sha256'] == c['original_sha']
                disposition, note, sources, next_action = NOTES[(v,n)]
                judgments.append({
                    'salvage_version':v, 'candidate':n,
                    **{k:c[k] for k in ['source','source_cohort','source_id','row_index','url','original_sha','normalized_sha','text_sha256','tokens']},
                    'factual_judgment_path':str(fact_path), 'factual_judgment_line':line_no,
                    'factual_judgment_sha256':sha(fact_path),
                    'rights_disposition':disposition, 'reason':note,
                    'primary_evidence_urls':sources, 'next_action':next_action,
                    'exact_captured_text_license_proven':False,
                    'training_admitted':False,
                })
    assert len(judgments)==21 and len({(d['salvage_version'],d['candidate']) for d in judgments})==21
    path=OUT/'judgments.jsonl'
    path.write_text(''.join(json.dumps(d,sort_keys=True)+'\n' for d in judgments))
    for p,h in inputs.items():
        assert sha(Path(p))==h
    supporting=[Path('restart/MILESTONE_PLAN.md'),Path('restart/milestone-policy.json'),Path('restart/approval-v1/PLAN.md'),ROOT/'metadata/odc-by-license',ROOT/'metadata/fineweb-edu-api-card-87f09149ef4734204d70ed1d046ddc9ca3f2b8f9']
    inputs.update({str(p):sha(p) for p in supporting})
    summary={
        'created_at_utc':datetime.now(timezone.utc).isoformat(),
        'status':'BOUNDED_RIGHTS_PROVENANCE_REVIEW_COMPLETE_NO_ADMISSION',
        'scope':'All 21 no_material_issue_identified records across salvage v1 factual batches 1-4 and salvage v2 batches 1-5. Current primary-source policies are evidence, not proof of historical exact-version licensing or legal certification.',
        'documents':len(judgments), 'provisional_content_tokens':sum(d['tokens'] for d in judgments),
        'by_rights_disposition':{k:{'documents':sum(d['rights_disposition']==k for d in judgments),'provisional_content_tokens':sum(d['tokens'] for d in judgments if d['rights_disposition']==k)} for k in sorted(Counter(d['rights_disposition'] for d in judgments))},
        'positive_reuse_candidate':{'salvage_version':2,'candidate':40,'documents':1,'provisional_content_tokens':1030,'cleared':False},
        'cleared_documents':0,'new_admitted_documents':0,'new_admitted_tokens':0,
        'database_vs_content_license':'Local ODC-BY license explicitly distinguishes database rights from individual contents. FineWeb-Edu collection licensing is not treated as a blanket grant for captured site prose.',
        'review_limits':['Web-fetch errors are recorded as missing evidence, not universal legal prohibition.','No contacting rights holders, no corpus downloads, no rewriting, no policy changes, no split assignment.','No full historical WARC-page/license reconciliation or jurisdiction-specific legal certification.','No public-domain inference from .gov, .edu, funding or historical subject alone.'],
        'input_sha256':inputs, 'judgments_sha256':sha(path),
    }
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({'documents':21,'tokens':summary['provisional_content_tokens'],'judgments_sha256':sha(path),'summary_sha256':sha(OUT/'summary.json')},indent=2))

if __name__=='__main__':
    main()

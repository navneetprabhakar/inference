# Independent English source audit: cleaned Wikipedia

Creator: Navneet Prabhakar

Date: 19 October 2026

## Decision

Do **not** add the unchanged cleaned Wikipedia snapshot to the next training mix yet. A bounded audit finds useful prose alongside missing numeric/template content, empty tables and low-density stubs. This is an observed extraction-quality issue; an encyclopedia label does not establish training quality. Licensing evidence also needs reconciliation before admission.

Actual acquisition: **64 complete cleaned dataset records /25,028 student-BPE content tokens**, from four distant clusters, using **105,325 successful page-body bytes**. Directly read 16 complete selected records /22,107 characters: **seven considered, seven excluded, two deferred**. These are clustered, length-conditioned sample outcomes, not a population quality estimate or a causal comparison against FineWeb.

No source admission, model updates, teacher calls, cloud resources or paid work. Existing FineWeb research policy/release/token bytes remain unchanged; the conversational control still scores 10/100 and zero of eight tasks.

## Pinned source and acquisition

Dataset: `wikimedia/wikipedia`; Git revision `b04c8d1ceb2f5cd4588862100d08de323dccfbaa`; configuration `20231101.en`, train split. [Pinned dataset card](https://huggingface.co/datasets/wikimedia/wikipedia/blob/b04c8d1ceb2f5cd4588862100d08de323dccfbaa/README.md).

The pinned card describes dump-derived cleaned text and removal of markup/unwanted sections. A complete viewer record is therefore **not proof that the original article's tables, templates or quantities survived preprocessing**. The audit verifies complete dataset cells and records the observed upstream loss rather than silently repairing it.

The viewer reports 6,407,814 rows. Four deterministic 16-row clusters begin at row offsets **800,976 /2,402,930 /4,004,883 /5,606,837**, the centers of four broad octile pairs. Each page requires exact `x-revision`, row indices, field schema, nonempty complete text, unique IDs and English article URLs. Caps are 4 MiB per successful page body /16 MiB total; metadata/license requests and HTTP overhead are separate. No Parquet shard or complete corpus is downloaded.

Article ID, title, URL, configuration, raw-record hash and row position are retained. Audit family keys use `wikimedia/wikipedia:en:<article-id>` so language-specific numeric IDs are namespaced; snapshot/configuration stays separate. Dataset Git revision is not an article revision ID, and this schema supplies no article author/history record. A future adapter/admission must preserve appropriate snapshot/attribution/history context rather than inventing it. No generic numeric-ID adapter or split assignment is applied in this audit.

The existing ancestral family map is pinned; no audit row becomes train data or changes a frozen partition.

## Full-text review and observed failures

Review eligibility is **500–12,000 characters**, then up to four records per cluster by frozen hash priority. Eligible counts are 14, eight, nine and four. All four clusters supply four full-text reviews. This deliberately bounds reading and excludes very short/long articles from the review population; it cannot support corpus-wide acceptance claims or conclusions about long-form coverage. Nearby records are often topically related, further limiting independence.

Observed whole-capture exclusions:

- Missing village/nation lists after explicit introductions and empty pronunciation fields.
- Empty numeric specification slots, or length/width values removed from an otherwise grammatical definition.
- Empty schedule, medal, track-format and chart sections dominating short captures.
- Repeated grammar/name-form defects in one entertainment article.
- A disambiguation directory rather than sustained explanatory prose.

Seven considerations include short definitions/geography, an institution overview, an artist biography, album history and a musician biography. Minor empty-coordinate parentheses, reference/category tails and missing ancillary sections remain explicitly observed where the connected prose is still readable. No considered document is called clean factual gold. Exclusions distinguish actual missing values from a perfectly grammatical spatial relation that does not require an explicit numeric distance.

Two deferrals concern snapshot-dependent incumbency framing and biomedical diagnostic claims. The review neither names the current officeholder nor verifies clinical efficacy. Military, religious, entertainment or national subject matter is not itself an exclusion criterion.

Journal flags remain `human_attestation:false`, `training_approved:false`, with factual and underlying-rights verification false. Whole-capture exclusions are retained; no unreviewed body-only derivative is substituted. A later extractive approach would need exact character-span lineage, explicit decisions and protection against carrying false or incomplete assertions into the derived data.

## License and attribution evidence

The pinned card declares CC BY-SA 3.0/GFDL options. Wikimedia's current dump guide instead names CC BY-SA 4.0/GFDL and discusses exceptions; its linked terms control over the general guide. [Official dump licensing guide](https://dumps.wikimedia.org/legal.html).

The audit retains the card, its declared 3.0 license text, supplemental 4.0/GFDL 1.3 text, and the actual current guide bytes/hash. The source registry's `license_id` records the card's declared primary label **for audit only**. `source/licensing-review.json` explicitly marks operative-license/downstream-obligation reconciliation unresolved and keeps training approval false. Supplemental text filenames do not decide which grant applies to any particular article. No legal certainty, blanket underlying-rights clearance or conclusion about future model-distribution obligations is implied.

This preserves evidence rather than silently rewriting the card declaration or pretending all versions are interchangeable. Source remains `sample_only`; the FineWeb-specific schema-6 reader does not admit Wikipedia. No funding request or additional user approval is created by this source review.

## Verification and next step

`scripts/check-wikipedia-audit.py` reopens exact page bodies and source/license bytes, reconstructs all 64 raw records and language-namespaced identities, checks ancestral-map integrity, recomputes the deterministic 16-document selection, verifies every direct journal binding/count, and recomputes actual BPE tokens. It passes. This is an actual data/provenance check, not independent subjective/factual/legal certification or live HTTP replay; model tests are not repeated for an audit-only change.

Private source/raw/packet/journal artifacts: `data/wikipedia-distributed-audit-v1`. Raw articles and license bundles remain ignored. Compact committed evidence: `reports/milestone-seventy-two-{wikipedia-acquisition,wikipedia-review,audit-check}.json`.

Next assess the plan's other independent foundation sources, especially coherent explanatory/narrative coverage, before selecting a larger finite mix. For Wikipedia specifically, address extraction/quantity fidelity and snapshot/attribution/license context before any admission. Do not replace a flawed small source with a larger unchecked one or silently redistribute proposed source quotas.

The previously prepared FineWeb ingredient remains available, with its 758 unread train documents and residual-risk boundary. The next actual main-learning run still requires a larger diverse admitted population, durable intake/physical-exposure accounting, frozen model/optimizer/resource/learning/retention/portability contracts and actual terminal conversation/direct scoring. Main cloud-budget decision remains pending; validation-only and teacher constraints stay separate. Full original goal remains active/incomplete.

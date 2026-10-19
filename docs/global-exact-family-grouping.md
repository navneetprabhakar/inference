# Global exact-family consolidation

Creator: Navneet Prabhakar

Date: 19 October 2026

- **235,779 records are consolidated into 229,606 exact-family components**, with 12,794 witnessed text/family links. Raw source wording remains unchanged; no new split assignment or training admission occurs.
- All 153,692 provisionally passing source rows are represented alongside rejected rows, complete official validation stories, ancestral heldouts, existing/upstream evaluation text and explicit nonapproval anchors. Source records retain metadata, original byte/payload references and earlier token counts.
- A component containing any heldout witness is unavailable for future training. Individual original validation/test labels remain unchanged even when a component has both labels. Known nonapproval flags also propagate through components.

## Witness recovery found by actual execution

The first attempt stops after processing 5,797 ancestral shard records: the protected map has 2,862 families, but its retained shards represent only 2,860 parent IDs. The missing two Dolly families were still protected despite having no retained row in those shards.

- Both original records are recovered from the already-local complete Dolly export at zero-based lines 8,054 and 12,165. Their complete raw-record hashes reproduce the exact protected family IDs. Instruction, context and response text are retained as witnesses with the original map partitions.
- The original failed script, plan and partial database remain intact. A separate v2 full rebuild adds the two recovered witnesses and binds the original failure and raw export. Its report records all 5,797 attempted prefix rows in addition to 235,779 rebuilt rows: 241,576 attempted row insertions across both attempts, not training positions.
- No network fetch, student update or paid resource is involved in the recovery. This is a newly observed limitation of the earlier map-plus-retained-shards representation; no historical result is retroactively certified or rewritten.

## Consolidated membership

| Record kind | Count |
| --- | ---: |
| Retained ancestral shard rows | 5,797 |
| Recovered ancestral raw rows | 2 |
| Earlier FineWeb source witnesses | 1,048 |
| New general-prose source rows | 48,000 |
| Explicit rejected Cosmopedia family anchors | 16 |
| Textbook-format rows, including old audit witnesses | 35,859 |
| Other Cosmopedia rows, including old audit witnesses | 13,207 |
| Official narrative validation stories | 49,620 |
| Acquired narrative training stories | 81,703 |
| Prior/upstream evaluation text witnesses | 527 |

The database includes all 29 observed FineWeb nonapprovals, all three observed narrative nonapprovals, the existing Cosmopedia rejected prompt/seed family keys and their available old audit texts. A consideration remains distinct from approval.

## Actual additional exclusion

One previously provisional Cosmopedia row joins a rejected component through normalized whole-text/family links. Its acquired identity is `cosmopedia-v2/train-00103-of-00104.parquet`, group15, row380; its original raw-record digest is `fe312bc93970c255695df02375db11c96eb0079d55f472cc0be7f681f9bc82b7`. Its format is in the other-Cosmopedia pool, not the proposed textbook subset. Preserve the component-level exclusion in all subsequent phases. No still-provisional row joins a heldout component under these exact rules; this does not establish near-family or seed-containment isolation.

## Verification and limits

- Four focused tests pass: transitive exact-body/seed linkage, nonapproval propagation, refusal at finite bounds, short-label handling and preservation of mixed validation/test witness labels.
- The actual read-only audit verifies the SQLite integrity result and database hash; independently rebuilds exact components from every consolidated text/family anchor; verifies all 12,794 recorded links and 229,606 component identities/flags; and checks all original input hashes and witness partition metadata. It does not independently replay the complete source-consolidation generator.
- Each attempt has a 260K-record cap, 8 GiB database cap, 30-minute independently supervised worker-process deadline and 30 GiB free-disk reserve. The completed database is about 1 GiB. These controls are not a hard RSS sandbox. Prior failed work remains separately recorded.
- Normalization uses the existing NFKC/case/punctuation/whitespace word key. Whole facets shorter than four words or 16 normalized characters are not global text anchors; a short answer such as “blue” must not link unrelated records. Explicit family anchors remain effective regardless of text length.

## Remaining required phases

Near-duplicate grouping at the declared shingle threshold and verified excerpt containment between Cosmopedia seeds and original source documents remain incomplete. Different excerpts from the same latent upstream document are not assigned an invented identity. The consolidated database retains complete content/prompt/seed facets and source references for those phases.

Then preserve all resulting protected/nonapproved components, assign new family splits, audit a finite corpus admission and freeze the realized 60/20/20 exposure schedule. Original local-only prose policy and all learning/portability/resource gates remain unchanged. Student weights and failed conversation baselines remain unchanged; no teacher call, cloud resource or new training occurred.

Evidence: `reports/global-exact-families.json`, `reports/global-exact-families-check.json`, `reports/exact-families-tests.xml`, both execution configs/scripts and the ignored failed/completed databases. The full project remains active and incomplete.

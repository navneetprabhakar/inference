# Future manifest binding and family custody validator

This is an offline preparation component for M0. It has no model imports, network
client, training launcher or admission authority. Run `python3 check_synthetic.py`
from this directory. The fixtures are artificial labels, not training examples.

`validate(bundle)` requires nonempty records with exact UTF-8 payloads and SHA256,
source identity/snapshot pin, known ancestry declaration, explicit upstream role,
stage/split/role, parent identities, required family namespaces and family keys.
Canonical JSON receipts pin all record fields except their own digest. These
receipts are supplied evidence bindings, not signatures or independent proof.

The validator unions shared family keys, exact payload copies, stable source
identities and parent versions transitively before checking splits. Derivatives
must retain every parent family and parent chains must be present and acyclic.
Protected sources/families/upstream holdouts propagate through whole components;
upstream development and excluded roles cannot silently become training or
acceptance. Tokenizer-fit records are train-only. Conversation/template/teacher
axes are mandatory for M5–M7, with schema/workflow axes additionally mandatory
for M6–M7. Original human examples may explicitly mark template/teacher axes
inapplicable with bound evidence, instead of inventing a shared `none` family;
synthetically generated examples cannot mark teacher ancestry inapplicable.
Unknown/missing ancestry, roles, required families, receipts or payload
bindings refuse rather than producing a passing empty release.

Real source-content integrity, license clearance, truth/completeness of ancestry,
semantic near-duplicate discovery, and OS custody require separate evidence.
This validator cannot establish those facts from assertions or hashes alone.
No real future conversation/tool payload registry has been certified here; M0
remains incomplete. Later-stage execution is still outside current authority.

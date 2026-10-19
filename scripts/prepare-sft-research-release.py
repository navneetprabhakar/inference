#!/usr/bin/env python3
"""Publish the separately approved bounded research selection and one-pass tokens."""
# Creator: Navneet Prabhakar
import json
from pathlib import Path
from slm.data.sft_research import release
from slm.data.sft_research_tokens import build_tokens
from slm.data.tokenized import sha


def main():
    root = Path('data/iteration-three-sft-research-v1')
    if root.exists():
        raise FileExistsError(root)
    policy = Path('configs/iteration-three-sft-research-admission-v1.json')
    root.mkdir()
    try:
        published = release('data/oasst-rated-sft-candidates-v1', 'data/oasst-rated-sft-review-v1',
            'data/iteration-two-oasst2-snapshot-v1', policy, root/'release',
            review_report='reports/milestone-sixty-oasst-sft-content-review.json')
        tokenized = build_tokens(root/'release', 'data/iteration-two-foundation-tokenizers-v1/vocab-16384',
                                 root/'tokens', sha(policy))
        receipt = dict(creator='Navneet Prabhakar', release=published, tokens=tokenized,
            policy_file_sha256=sha(policy), release_manifest_sha256=sha(root/'release/manifest.json'),
            token_manifest_sha256=sha(root/'tokens/manifest.json'), script_sha256=sha(__file__),
            reader_sha256=sha('src/slm/data/sft_research.py'),
            token_builder_sha256=sha('src/slm/data/sft_research_tokens.py'),
            student_training_started=False, individual_quality_verification_for_unread_rows=False,
            scope='Actual bounded research data publication/preparation; training entry point and experiment acceptance are separate.')
        (root/'preparation.json').write_text(json.dumps(receipt, indent=2, sort_keys=True)+'\n')
        Path('reports/milestone-sixty-one-sft-research-preparation.json').write_text(json.dumps(receipt, indent=2, sort_keys=True)+'\n')
        print(json.dumps(receipt, indent=2))
    except BaseException as error:
        (root/'failure.json').write_text(json.dumps(dict(complete=False, error_type=type(error).__name__,
            message=str(error), release_exists=(root/'release').exists(), tokens_exist=(root/'tokens').exists()), indent=2)+'\n')
        raise


if __name__ == '__main__':
    main()

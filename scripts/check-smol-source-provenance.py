#!/usr/bin/env python3
"""Retain constituent/generator evidence without granting training admission."""
# Creator: Navneet Prabhakar
import json
from pathlib import Path
from slm.data.acquire import fetch
from slm.data.tokenized import sha


def main():
    root = Path('data/smol-smoltalk-audit-v1')
    result = json.loads((root/'inspection.json').read_text())
    assert result['acquisition']['rows_sha256'] == sha(root/'sample/rows.jsonl')
    assert result['script_sha256'] == sha('scripts/inspect-smol-smoltalk.py')
    revision = '5feaf2fd3ffca7c237fc38d1861bc30365d48ffa'
    url = 'https://huggingface.co/datasets/HuggingFaceTB/smoltalk/raw/'+revision+'/README.md'
    card, _ = fetch(url, 256*1024)
    text = card.decode()
    if ('Llama-3.1-405B-Instruct' not in text
            or 'For the existing public datasets, please refer to the original dataset' not in text):
        raise ValueError('Expected upstream generator/constituent-license evidence differs')
    (root/'upstream-card.txt').write_bytes(card)
    revision_license = '1f0feb795a4130697ced243fb53051670d591653'
    license_url = 'https://raw.githubusercontent.com/meta-llama/llama-models/'+revision_license+'/models/llama3_1/LICENSE'
    license_text, _ = fetch(license_url, 128*1024)
    if b'outputs or results' not in license_text or b'at the beginning' not in license_text:
        raise ValueError('Expected generator-license evidence differs')
    (root/'generator-license.txt').write_bytes(license_text)
    evidence = dict(upstream_revision=revision, upstream_card_url=url, upstream_card_sha256=sha(root/'upstream-card.txt'),
        reported_core_generator='Llama-3.1-405B-Instruct, as stated by the upstream dataset card',
        constituent_policy='New upstream subsets are described as Apache-2.0; existing components refer to their own original licenses.',
        generator_license_url=license_url, generator_license_sha256=sha(root/'generator-license.txt'),
        generator_license_revision=revision_license,
        generator_terms_attention='Contains naming/use conditions for models trained using specified materials or outputs and distributed/made available; downstream applicability remains a source-specific admission/release question.',
        source_training_approved=False, constituent_training_approved=False, human_attestation=False,
        control_script_sha256=sha(__file__),
        scope='Observed source evidence only, no legal clearance, automatic agreement acceptance, new teacher call or model training.')
    (root/'provenance.json').write_text(json.dumps(evidence, indent=2, sort_keys=True)+'\n')
    result['provenance_review'] = evidence
    Path('reports/milestone-fifty-six-smol-source-inspection.json').write_text(json.dumps(result, indent=2, sort_keys=True)+'\n')
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    main()

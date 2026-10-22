"""Synthetic AST controls only; never reads retained source pages."""
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
BASE = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(BASE / 'tool-dependencies/mwparserfromhell-0.7.2'))
import mwparserfromhell as parser
import qualifier_core as core

passed = []
for source, expected in [
    ('{{As of|2011}}', 'As of 2011'),
    ('{{as of|2020}}', 'As of 2020'),
    ('{{ As of | 2011 }}', 'As of 2011'),
    ('{{As of|1=2011}}', 'As of 2011'),
]:
    node = parser.parse(source).nodes[0]
    result = core.literal_year_qualifier(node)
    assert result['raw'] == source and result['replacement'] == expected
    assert result['source_span_binding_required'] and result['temporal_scope_preserved']
    passed.append('supported:' + source)

for source in [
    '{{As of}}', '{{As of|2011|5}}', '{{As of|2011|lc=y}}',
    '{{As of|2011|since=y}}', '{{As of|2011|alt=present}}',
    '{{As of|2011|bare=yes}}', '{{As of|2011|post=,}}',
    '{{As of|2011|1=2012}}', '{{As of|year=2011}}',
    '{{As of|{{CURRENTYEAR}}}}', '{{As of|&#50;011}}',
    '{{As of|20xx}}', '{{As of|0000}}', '{{As of|２０１１}}',
    '{{As of?|date=May 2025}}', '{{convert|2011|m}}',
    '{{{{unknown}}|2011}}', 'ordinary text',
]:
    try:
        core.literal_year_qualifier(parser.parse(source).nodes[0])
    except core.Hold:
        passed.append('held:' + source)
    else:
        raise AssertionError('unsupported source accepted: ' + source)

# Exercise the intended source-bound operation interface on a synthetic whole
# section. A caller may never lose the prefix, suffix, qualifier or raw preimage.
source = '== Demographics ==\n{{As of|2011}}, the recorded total was 42.\n'
node = parser.parse(source).filter_templates()[0]
result = core.literal_year_qualifier(node)
start = source.index(result['raw']); end = start + len(result['raw'])
derived = source[:start] + result['replacement'] + source[end:]
restored = derived[:start] + result['raw'] + derived[start + len(result['replacement']):]
assert restored == source and 'As of 2011,' in derived
passed.append('whole_section_exact_operation_inverse_and_year_qualifier')
print(json.dumps({'status': 'PASS_SYNTHETIC_ONLY', 'checks': len(passed),
                  'cases': passed, 'retained_source_applications': 0}, indent=2))

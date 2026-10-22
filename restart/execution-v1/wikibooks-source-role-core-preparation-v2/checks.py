"""Synthetic DOM controls only; no retained article/archive is opened."""
import copy
import html
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
BASE = HERE.parent
sys.path.insert(0, '/Users/navneetprabhakar/.local/share/uv/tools/aider-chat/lib/python3.12/site-packages')
sys.path.insert(0, '/Users/navneetprabhakar/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages')
sys.path.insert(0, str(BASE / 'wikibooks-sharded-render-preparation-v2'))
sys.path.insert(0, str(HERE))
from bs4 import BeautifulSoup
import dom_renderer as renderer
import role_core as core

cases = []
FIRST = 'First disclaimer.'
SECOND = 'Second disclaimer.'
APPROVED = {core.sha(FIRST), core.sha(SECOND)}


def declaration(target=':Wikibooks:Medical_disclaimer', href='./Wikibooks:Medical_disclaimer', params=None, extra=None):
    parts = [{'template': {'target': {'wt': target, 'href': href}, 'params': params or {}, 'i': 0}}]
    if extra is not None:
        parts.append(extra)
    return html.escape(json.dumps({'parts': parts}), quote=True)


def fixture(body, approved=APPROVED):
    soup = BeautifulSoup('<body>' + body + '</body>', 'lxml')
    content = soup.body
    original = str(content)
    result = renderer.render_blocks(content)
    expected = []; cursor = 0
    for i, block in enumerate(result['blocks']):
        text = block['text']
        expected.append({'ordinal': i, 'kind': block['kind'], 'hash': block['sha256'],
                         'characters': len(text), 'start': cursor, 'end': cursor + len(text)})
        cursor += len(text) + 2
    output = core.inventory(content, result['text'], expected, renderer, approved)
    assert str(content) == original and output['source_nodes_removed'] == 0 and not output['text_changed']
    return content, result, expected, output


def passed(name, body, check, approved=APPROVED):
    context = fixture(body, approved)
    assert check(context[3]), name
    cases.append(name)


attr = declaration()
group = f'<p about="#mwt1" typeof="mw:Transclusion" data-mw="{attr}">{FIRST}</p>'
passed('direct_exact_target_and_reviewed_block', group,
       lambda x: x['blocks'][0]['role'] == 'verified_site_disclaimer_component')
passed('sibling_about_group_inherits_verified_ancestry', group + f'<p about="#mwt1">{SECOND}</p>',
       lambda x: all(b['role'] == 'verified_site_disclaimer_component' for b in x['blocks']))
passed('same_text_without_transclusion_not_boilerplate', f'<p>{FIRST}</p>',
       lambda x: x['blocks'][0]['role'] == 'subject_or_reference_candidate')
passed('known_target_but_new_unreviewed_text_not_verified', group + '<p about="#mwt1">New source text.</p>',
       lambda x: x['blocks'][1]['role'] == 'subject_or_reference_candidate')
passed('known_target_without_approved_hash_inventory', group,
       lambda x: x['blocks'][0]['role'] == 'subject_or_reference_candidate', set())
passed('unrelated_subject_prose_preserved', group + '<p>A complete subject explanation.</p>',
       lambda x: x['blocks'][1]['role'] == 'subject_or_reference_candidate')
passed('short_reference_definition_preserved', '<p>A short definition.</p>',
       lambda x: x['blocks'][0]['role'] == 'subject_or_reference_candidate')
passed('code_example_preserved', '<pre>x = 1\nprint(x)</pre>',
       lambda x: x['blocks'][0]['kind'] == 'pre' and x['blocks'][0]['role'] == 'subject_or_reference_candidate')
passed('link_only_item_is_diagnostic_not_deletion', '<ul><li><a href="./Chapter">Chapter</a></li></ul>',
       lambda x: x['blocks'][0]['link_only_candidate_diagnostic'] and x['blocks'][0]['role'] == 'subject_or_reference_candidate')
passed('instruction_with_link_is_subject_candidate', '<ol><li>Read the <a href="./Instructions">instructions</a> first.</li></ol>',
       lambda x: not x['blocks'][0]['link_only_candidate_diagnostic'])
passed('reference_work_list_not_automatically_removed', '<p>Other works include:</p><ul><li><a href="./Work">A work</a></li></ul>',
       lambda x: len(x['blocks']) == 2 and all(b['role'] == 'subject_or_reference_candidate' for b in x['blocks']))
passed('heading_empty_subtree_diagnostic', '<h2>Topic</h2><h3>Unfinished</h3><h2>Next</h2><p>Complete prose.</p>',
       lambda x: x['heading_diagnostics'][0]['empty_heading_subtree'] and x['heading_diagnostics'][1]['empty_heading_subtree'])
passed('whole_disclaimer_heading_payload_diagnostic', '<h2>Disclaimer</h2>' + group + f'<p about="#mwt1">{SECOND}</p>',
       lambda x: x['heading_diagnostics'][0]['all_payload_verified_site_disclaimer'])
passed('mixed_heading_payload_not_all_disclaimer', '<h2>Topic</h2>' + group + '<p>Actual subject prose.</p>',
       lambda x: not x['heading_diagnostics'][0]['all_payload_verified_site_disclaimer'])

for label, metadata in [
    ('different_target', declaration(target='Template:Medical advice')),
    ('different_href', declaration(href='./Template:Other')),
    ('nonempty_parameter', declaration(params={'1': {'wt': 'Subject text'}})),
    ('mixed_source_parts', declaration(extra='authored text')),
    ('malformed_metadata', '{not JSON'),
]:
    body = f'<p about="#mwt1" typeof="mw:Transclusion" data-mw="{metadata}">{FIRST}</p>'
    passed(label, body, lambda x: x['blocks'][0]['role'] == 'subject_or_reference_candidate')

passed('duplicate_declarations_ambiguous_not_verified', group + group,
       lambda x: not x['transclusion_groups']['#mwt1']['verified_known_target_structure'])
passed('nearer_unknown_about_scope_not_laundered',
       f'<div about="#mwt1" typeof="mw:Transclusion" data-mw="{attr}"><p about="#mwt2">{FIRST}</p></div>',
       lambda x: x['blocks'][0]['role'] == 'subject_or_reference_candidate')
passed('cross_parent_about_reuse_not_emitted_scope', group + f'<section><p about="#mwt1">{SECOND}</p></section>',
       lambda x: x['blocks'][0]['role'] == 'verified_site_disclaimer_component' and x['blocks'][1]['role'] == 'subject_or_reference_candidate')
passed('unrelated_same_parent_element_breaks_emitted_scope', group + '<p>Subject prose.</p>' + f'<p about="#mwt1">{SECOND}</p>',
       lambda x: x['blocks'][2]['role'] == 'subject_or_reference_candidate')
passed('nonwhite_text_breaks_emitted_scope', group + 'Actual unrelated text' + f'<p about="#mwt1">{SECOND}</p>',
       lambda x: x['blocks'][1]['role'] == 'subject_or_reference_candidate')
passed('whitespace_comments_allow_contiguous_emitted_siblings', group + '\n<!-- comment -->\n' + f'<p about="#mwt1">{SECOND}</p>',
       lambda x: all(row['role'] == 'verified_site_disclaimer_component' for row in x['blocks']))
passed('declaration_ancestor_binds_actual_descendant',
       f'<div about="#mwt1" typeof="mw:Transclusion" data-mw="{attr}"><p>{FIRST}</p></div>',
       lambda x: x['blocks'][0]['role'] == 'verified_site_disclaimer_component')
passed('preceding_about_node_does_not_inherit_future_anchor', f'<p about="#mwt1">{SECOND}</p>' + group,
       lambda x: x['blocks'][0]['role'] == 'subject_or_reference_candidate')
passed('DOM_paths_disambiguate_identical_siblings', '<p>Same.</p><p>Same.</p>',
       lambda x: x['blocks'][0]['DOM_path'] != x['blocks'][1]['DOM_path'])
passed('unicode_character_ranges', '<p>é 中文.</p><p>Next.</p>',
       lambda x: x['blocks'][0]['original_Unicode_range'] == [0, 5])

content, rendered, expected, _ = fixture('<p>Same.</p><p>Same.</p>')
for label, changed in [('wrong_hash', lambda x: x[0].update(hash='0' * 64)),
                       ('duplicate_span', lambda x: x[1].update(start=0, end=5)),
                       ('wrong_kind', lambda x: x[0].update(kind='li'))]:
    broken = copy.deepcopy(expected); changed(broken)
    try:
        core.inventory(content, rendered['text'], broken, renderer, APPROVED)
    except ValueError:
        cases.append(label + '_refused')
    else:
        raise AssertionError(label)

print(json.dumps({'status': 'PASS_SYNTHETIC_DOM_ONLY', 'checks': len(cases), 'cases': cases,
                  'retained_source_applications': 0, 'text_transformations': 0}, indent=2))

"""Read-only roles for the exact DOM handed to the frozen text renderer.

The caller must pin the parser/renderer, original HTML and original block receipt.
This module never removes nodes, changes text, or certifies semantic quality.
"""
import hashlib
import json
import re

TARGET = 'Wikibooks:Medical disclaimer'


def sha(text):
    return hashlib.sha256(text.encode('utf8')).hexdigest()


def tokens(value):
    return value.split() if isinstance(value, str) else list(value or [])


def dom_path(node, root):
    path = []
    while node is not root:
        parent = node.parent
        if parent is None or len(path) >= 64:
            raise ValueError('unbound_or_deep_DOM_path')
        path.append(next(i for i, child in enumerate(parent.children) if child is node))
        node = parent
    return list(reversed(path))


def declaration(node):
    """A known transclusion target is insufficient without its exact structure."""
    raw = node.get('data-mw')
    result = {'raw_data_mw': raw, 'known_site_disclaimer': False}
    try:
        value = json.loads(raw)
        parts = value['parts']
        if len(parts) != 1 or not isinstance(parts[0], dict):
            return result
        template = parts[0]['template']
        wt = template['target']['wt']
        href = template['target']['href']
        normalized = wt[1:] if wt.startswith(':') else wt
        normalized = normalized.replace('_', ' ')
        result['known_site_disclaimer'] = (
            normalized == TARGET
            and href == './Wikibooks:Medical_disclaimer'
            and template['params'] == {}
        )
        result['target_wt'] = wt
        result['target_href'] = href
    except (KeyError, TypeError, ValueError, AttributeError):
        result['unresolved_declaration'] = True
    return result


def emitted_roots(anchor, about):
    """A Parsoid output group stays within its anchor subtree/contiguous siblings."""
    roots = [anchor]
    for sibling in anchor.next_siblings:
        if getattr(sibling, 'name', None) is None:
            if type(sibling).__name__ == 'Comment' or not str(sibling).strip():
                continue
            break
        if sibling.get('about') != about:
            break
        roots.append(sibling)
    return roots


def inventory(content, expected_text, expected_blocks, renderer, approved_disclaimer_hashes):
    """Map exact original blocks; invoke only on the frozen renderer's DOM.

    approved hashes are separately reviewed and pinned, not a keyword rule.
    All link-only and empty-heading findings are diagnostics, never deletions.
    """
    approved = set(approved_disclaimer_hashes)
    if len(approved) > 100 or any(re.fullmatch('[a-f0-9]{64}', h) is None for h in approved):
        raise ValueError('invalid_reviewed_disclaimer_hash_inventory')
    groups = {}
    anchors = {}
    for node in [content] + list(content.find_all(True)):
        if 'mw:Transclusion' not in tokens(node.get('typeof')):
            continue
        about = node.get('about')
        if not isinstance(about, str) or re.fullmatch(r'#[A-Za-z0-9_-]{1,128}', about) is None:
            continue  # unbound contexts cannot grant a verified role
        groups.setdefault(about, []).append({'DOM_path': dom_path(node, content), **declaration(node)})
        anchors.setdefault(about, []).append(node)
    group_records = {
        key: {'declarations': values,
              'verified_known_target_structure': len(values) == 1 and values[0]['known_site_disclaimer']}
        for key, values in groups.items()
    }
    bound_scope_ids = {}
    for about, record in group_records.items():
        roots = emitted_roots(anchors[about][0], about) if record['verified_known_target_structure'] else []
        record['bound_emitted_root_DOM_paths'] = [dom_path(node, content) for node in roots]
        bound_scope_ids[about] = {id(node) for node in roots}
        for root in roots:
            bound_scope_ids[about].update(id(child) for child in root.find_all(True))
    rows = []
    for node in content.find_all(list(renderer.STRUCTURAL_TAGS)):
        if any(parent.name in renderer.STRUCTURAL_TAGS for parent in node.parents if parent is not content):
            continue
        text = renderer.render_block_text(node)
        if not text:
            continue
        if len(rows) >= 10000:
            raise ValueError('block10000cap')
        scopes = []
        for ancestor in [node] + list(node.parents):
            if ancestor is content.parent:
                break
            value = ancestor.get('about') if getattr(ancestor, 'name', None) else None
            if value is not None:
                scopes.append(value)
            if ancestor is content:
                break
        nearest = scopes[0] if scopes else None
        context = group_records.get(nearest)
        digest = sha(text)
        in_emitted_scope = nearest in bound_scope_ids and id(node) in bound_scope_ids[nearest]
        known = bool(context and context['verified_known_target_structure'] and in_emitted_scope)
        role = 'heading' if re.fullmatch('h[1-6]', node.name) else 'subject_or_reference_candidate'
        if known and digest in approved:
            role = 'verified_site_disclaimer_component'
        outside_link = []
        for child in node.descendants:
            if getattr(child, 'name', None) is not None or type(child).__name__ == 'Comment':
                continue
            parents = []
            for parent in child.parents:
                if parent is node:
                    break
                parents.append(parent)
            if not any(parent.name == 'a' for parent in parents):
                outside_link.append(str(child))
        links = [{'href': a.get('href'), 'rel': a.get('rel', []),
                  'visible_text_SHA256': sha(renderer.render_block_text(a))}
                 for a in node.find_all('a')]
        rows.append({'ordinal': len(rows), 'kind': node.name, 'text_SHA256': digest,
                     'characters': len(text), 'DOM_path': dom_path(node, content),
                     'DOM_id': node.get('id'), 'about_scopes_nearest_first': scopes,
                     'nearest_about_group': nearest,
                     'within_bound_emitted_scope': in_emitted_scope,
                     'known_site_disclaimer_target': known, 'role': role,
                     'link_only_candidate_diagnostic': bool(links) and not ''.join(outside_link).strip(),
                     'links': links, 'text': text})
    reconstructed = '\n\n'.join(row['text'] for row in rows)
    if reconstructed != expected_text or len(rows) != len(expected_blocks):
        raise ValueError('frozen_renderer_whole_text_or_block_count_mismatch')
    cursor = 0
    for row, expected in zip(rows, expected_blocks):
        if (expected['ordinal'] != row['ordinal'] or expected['kind'] != row['kind']
                or expected['hash'] != row['text_SHA256']
                or expected['characters'] != row['characters']
                or expected['start'] != cursor or expected['end'] != cursor + row['characters']
                or expected_text[expected['start']:expected['end']] != row['text']):
            raise ValueError('original_block_receipt_mismatch')
        row['original_Unicode_range'] = [expected['start'], expected['end']]
        cursor = expected['end'] + 2
        row.pop('text')
    # Linear heading-stack analysis: structure is a review aid, not a grammar test.
    prefix = [0]
    disclaimer_prefix = [0]
    for row in rows:
        prefix.append(prefix[-1] + (row['role'] != 'heading'))
        disclaimer_prefix.append(disclaimer_prefix[-1] + (row['role'] == 'verified_site_disclaimer_component'))
    stack = []
    boundaries = {}
    for index, row in enumerate(rows):
        if row['role'] == 'heading':
            level = int(row['kind'][1])
            while stack and stack[-1][1] >= level:
                previous, _ = stack.pop(); boundaries[previous] = index
            stack.append((index, level))
    for index, _ in stack:
        boundaries[index] = len(rows)
    heading_diagnostics = []
    for index, end in sorted(boundaries.items()):
        payload_count = prefix[end] - prefix[index + 1]
        disclaimer_count = disclaimer_prefix[end] - disclaimer_prefix[index + 1]
        heading_diagnostics.append({'heading_ordinal': index, 'subtree_end_exclusive': end,
                                    'nonheading_blocks': payload_count,
                                    'empty_heading_subtree': payload_count == 0,
                                    'all_payload_verified_site_disclaimer': payload_count > 0 and disclaimer_count == payload_count})
    return {'whole_original_text_SHA256': sha(expected_text), 'blocks': rows,
            'transclusion_groups': group_records, 'heading_diagnostics': heading_diagnostics,
            'source_nodes_removed': 0, 'text_changed': False,
            'navigation_and_empty_headings_are_diagnostics_only': True,
            'semantic_quality_rights_factual_or_admission_clearance': False,
            'new_admitted_documents': 0}

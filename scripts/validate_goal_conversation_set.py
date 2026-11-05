"""Structural gates only; passing never certifies semantic quality.

Canonical goal evaluation uses real sequential student replies, never gold
assistant turns. Each record has id, family, scenario, and 2..4 user turns.
"""
import argparse
import collections
import hashlib
import json
import re
from pathlib import Path


def normalized(text):
    return ' '.join(re.findall(r'\w+', text.casefold()))


def split_overlap(path, other):
    """Ignore IDs/split labels: identical text is leakage even with fresh IDs."""
    a = [json.loads(s) for s in Path(path).read_text().splitlines() if s.strip()]
    b = [json.loads(s) for s in Path(other).read_text().splitlines() if s.strip()]
    sequences = {tuple(normalized(t['user']) for t in r['turns']): r['id'] for r in b}
    openings = {normalized(r['turns'][0]['user']): r['id'] for r in b}
    return [{'id': r['id'], 'other_id': sequences.get(tuple(normalized(t['user']) for t in r['turns'])) or openings[normalized(r['turns'][0]['user'])]}
            for r in a if tuple(normalized(t['user']) for t in r['turns']) in sequences or normalized(r['turns'][0]['user']) in openings]


def validate(path, expected):
    rows = [json.loads(s) for s in Path(path).read_text().splitlines() if s.strip()]
    errors = []
    warnings = []
    if len(rows) != expected:
        errors.append(f'Expected {expected} cases, got {len(rows)}')
    seen_ids, seen_scenarios, seen_sequences, seen_openings = set(), set(), set(), set()
    family_counts = collections.Counter()
    tool_cases = 0
    for r in rows:
        ident = r.get('id')
        if not ident or ident in seen_ids:
            errors.append(f'Missing/duplicate id {ident}')
        seen_ids.add(ident)
        scenario = normalized(r.get('scenario', ''))
        if len(scenario.split()) < 4 or scenario in seen_scenarios:
            errors.append(f'{ident}: missing or repeated scenario')
        seen_scenarios.add(scenario)
        turns = r.get('turns', [])
        if not 2 <= len(turns) <= 4:
            errors.append(f'{ident}: must test 2..4 actual student replies')
        if 'messages' in r or 'assistant' in r:
            errors.append(f'{ident}: no prefilled assistant history permitted')
        sequence = []
        for t in turns:
            if not isinstance(t.get('user'), str) or not t['user'].strip():
                errors.append(f'{ident}: missing user turn')
                continue
            if any(k in t for k in ('assistant', 'assistant_reply', 'messages')):
                errors.append(f'{ident}: gold history must not be supplied')
            if not isinstance(t.get('criteria'), list) or not t['criteria'] or not all(isinstance(c, str) and c.strip() for c in t['criteria']):
                errors.append(f'{ident}: every turn requires explicit semantic criteria')
            sequence.append(normalized(t['user']))
            if 'expected_calls' in t:
                if not isinstance(t['expected_calls'], list):
                    errors.append(f'{ident}: expected_calls must be a list')
                for call in t['expected_calls']:
                    if set(call) != {'name', 'arguments'} or not isinstance(call['arguments'], dict):
                        errors.append(f'{ident}: malformed expected call')
        if sequence:
            seq = tuple(sequence)
            if seq in seen_sequences or sequence[0] in seen_openings:
                errors.append(f'{ident}: duplicate episode or opening')
            seen_sequences.add(seq)
            seen_openings.add(sequence[0])
        family_counts[r.get('family', '')] += 1
        if r.get('tool_mode'):
            tool_cases += 1
            if not r.get('available_tools') or not any('expected_calls' in t for t in turns):
                errors.append(f'{ident}: tool cases need tools and call/abstention criteria')
    if expected == 100:
        if len(family_counts) < 10:
            errors.append('Need at least 10 distinct conversation families')
        if any(n > 15 for n in family_counts.values()):
            warnings.append('A family exceeds 15%: review coverage, but never relabel scenarios merely to satisfy a numerical quota.')
        if not 20 <= tool_cases <= 40:
            errors.append('Use 20..40 real tool/abstention conversations, not a token tool sample')
    return dict(path=str(path), cases=len(rows), families=dict(family_counts),
                tool_conversations=tool_cases, errors=errors, warnings=warnings,
                sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                limitations=['Structural check only; scenario diversity, semantic criteria and actual student rollout still require review.'])


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('path')
    p.add_argument('--expected', type=int, default=100)
    p.add_argument('--disjoint-from')
    a = p.parse_args()
    result = validate(a.path, a.expected)
    if a.disjoint_from:
        result['cross_split_overlaps'] = split_overlap(a.path, a.disjoint_from)
        if result['cross_split_overlaps']:
            result['errors'].append('Development and confirmation share actual user text; labels/IDs do not make them disjoint.')
    print(json.dumps(result, indent=2))
    raise SystemExit(bool(result['errors']))

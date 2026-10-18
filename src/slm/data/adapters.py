"""Strict adapters for prose, message arrays, Dolly, and OASST message trees."""
from collections import defaultdict
from slm.data.schema import make_example, digest


def rows(source, records, kind, official_split=None):
    if kind == 'oasst':
        flattened = []
        for tree in records:
            if tree.get('tree_state') != 'ready_for_export' or 'prompt' not in tree:
                raise ValueError('OASST adapter requires complete ready-tree exports, not flat slices')
            if tree['message_tree_id'] != tree['prompt']['message_id']:
                raise ValueError('Tree root identity mismatch')
            def flatten(node, parent=None):
                if not isinstance(node.get('replies'), list):
                    raise ValueError('Tree replies must be explicit, including empty leaves')
                row = {k:v for k,v in node.items() if k != 'replies'}
                if 'parent_id' in row and row['parent_id'] != parent:
                    raise ValueError('Tree parent identity mismatch')
                row['parent_id'] = parent
                flattened.append(row)
                for child in node['replies']: flatten(child,node['message_id'])
            flatten(tree['prompt'])
        return trees(source, flattened, official_split)
    output = []
    for row in records:
        row_id = str(row.get('id', row.get('prompt_id', digest(row))))
        if kind == 'prose':
            messages = [{'role': 'text', 'content': row['text']}]
        elif kind == 'messages':
            # Drop identifying or source-specific metadata, retain only model content.
            messages = [{'role': m['role'], 'content': m['content']} for m in row['messages']]
        elif kind == 'dolly':
            prompt = row['instruction']
            if row.get('context'):
                prompt += '\n\nContext:\n'+row['context']
            messages = [{'role': 'user', 'content': prompt},
                        {'role': 'assistant', 'content': row['response']}]
        else:
            raise ValueError(f'Unknown adapter: {kind}')
        output.append(make_example(source, row_id, str(row.get('parent_group_id', row_id)),
                                   messages, official_split=official_split,
                                   language=row.get('language', 'unknown'),
                                   upstream_references=[row['url']] if isinstance(row.get('url'),str) else [],
                                   task='prose' if kind == 'prose' else 'conversation'))
    return output


def trees(source, records, official_split=None, max_paths_per_tree=8):
    """Internal flat-tree validator; public ingestion requires nested ready-tree exports."""
    if max_paths_per_tree < 1:
        raise ValueError('Positive path cap required')
    nodes = {}
    for row in records:
        key = row['message_id']
        if key in nodes:
            raise ValueError('Duplicate tree message ID')
        nodes[key] = row
    children = defaultdict(list)
    for key, row in nodes.items():
        parent = row.get('parent_id')
        if parent is not None and parent not in nodes:
            raise ValueError('Incomplete tree: missing parent')
        children[parent].append(key)
    for key in nodes:
        seen, cursor = set(), key
        while cursor is not None:
            if cursor in seen:
                raise ValueError('Cyclic conversation tree')
            seen.add(cursor)
            cursor = nodes[cursor].get('parent_id')
    output = []
    for root in sorted(children[None]):
        candidates = []
        def walk(key, path):
            row = nodes[key]
            # Removing a turn would change context. Discard its whole descendant branch.
            if row.get('deleted') or row.get('lang') != 'en':
                return
            role = {'prompter': 'user', 'assistant': 'assistant'}.get(row['role'])
            if role is None or role != ('user' if len(path)%2 == 0 else 'assistant'):
                raise ValueError('Invalid tree role sequence')
            path = path+[key]
            if role == 'assistant' and not children[key]:
                rank = row.get('rank')
                candidates.append((rank if isinstance(rank, int) else 1_000_000, tuple(path)))
            for child in sorted(children[key]):
                walk(child, path)
        walk(root, [])
        for _, path in sorted(candidates)[:max_paths_per_tree]:
            messages = [{'role': 'user' if nodes[k]['role'] == 'prompter' else 'assistant',
                         'content': nodes[k]['text']} for k in path]
            output.append(make_example(source, path[-1], root, messages,
                                       official_split=official_split, language='en', lineage=list(path)))
    return output

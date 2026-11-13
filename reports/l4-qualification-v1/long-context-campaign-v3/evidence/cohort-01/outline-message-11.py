def outline(records):
    records = list(records)
    nodes = {}

    for record in records:
        node_id = record['id']
        if node_id is None:
            raise ValueError('None cannot be a record ID')
        if node_id in nodes:
            raise ValueError(f'Duplicate ID: {node_id!r}')
        nodes[node_id] = {**record, 'children': []}

    for record in records:
        parent_id = record['parent_id']
        if parent_id is not None and parent_id not in nodes:
            raise ValueError(f'Missing parent ID: {parent_id!r}')

    complete = set()
    for record in records:
        current = record['id']
        chain = set()
        while current is not None and current not in complete:
            if current in chain:
                raise ValueError(f'Cycle involving ID: {current!r}')
            chain.add(current)
            current = nodes[current]['parent_id']
        complete.update(chain)

    roots = []
    for record in records:
        node = nodes[record['id']]
        parent_id = record['parent_id']
        if parent_id is None:
            roots.append(node)
        else:
            nodes[parent_id]['children'].append(node)
    return roots

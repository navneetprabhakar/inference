def outline(records):
    nodes = {}
    for record in records:
        node_id = record['id']
        if node_id in nodes:
            raise ValueError(f"Duplicate ID: {node_id!r}")
        nodes[node_id] = {**record, 'children': []}

    roots = []
    for record in records:
        node = nodes[record['id']]
        parent_id = record['parent_id']
        if parent_id is None:
            roots.append(node)
        else:
            if parent_id not in nodes:
                raise ValueError(f"Missing parent ID: {parent_id!r}")
            nodes[parent_id]['children'].append(node)
    return roots

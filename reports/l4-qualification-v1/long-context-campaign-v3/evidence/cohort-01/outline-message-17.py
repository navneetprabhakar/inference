import unittest


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

    for node in nodes.values():
        parent = node['parent_id']
        if parent is not None and parent not in nodes:
            raise ValueError(f'Missing parent ID: {parent!r}')

    complete = set()
    for node_id in nodes:
        current, chain = node_id, set()
        while current is not None and current not in complete:
            if current in chain:
                raise ValueError(f'Cycle involving ID: {current!r}')
            chain.add(current)
            current = nodes[current]['parent_id']
        complete.update(chain)

    roots = []
    for record in records:
        node = nodes[record['id']]
        parent = record['parent_id']
        if parent is None:
            roots.append(node)
        else:
            nodes[parent]['children'].append(node)
    return roots


class OutlineTests(unittest.TestCase):
    def test_order_and_child_before_parent(self):
        records = [
            {'id': 'c2', 'parent_id': 'p'},
            {'id': 'r', 'parent_id': None},
            {'id': 'c1', 'parent_id': 'p'},
            {'id': 'p', 'parent_id': None},
        ]
        roots = outline(iter(records))
        self.assertEqual([n['id'] for n in roots], ['r', 'p'])
        self.assertEqual([n['id'] for n in roots[1]['children']], ['c2', 'c1'])
        self.assertNotIn('children', records[0])

    def test_invalid_inputs(self):
        record = {'id': 'a', 'parent_id': None}
        cases = [
            [record, record.copy()],
            [{'id': None, 'parent_id': None}],
            [{'id': 'a', 'parent_id': 'missing'}],
            [{'id': 'a', 'parent_id': 'a'}],
            [record, {'id': 'b', 'parent_id': 'c'},
             {'id': 'c', 'parent_id': 'b'}],
        ]
        for records in cases:
            with self.subTest(records=records), self.assertRaises(ValueError):
                outline(records)

    def test_empty_and_deep(self):
        self.assertEqual(outline([]), [])
        records = [{'id': i, 'parent_id': i - 1 if i else None}
                   for i in range(5000)]
        node = outline(records)[0]
        for i in range(5000):
            self.assertEqual(node['id'], i)
            children = node['children']
            self.assertEqual(len(children), i < 4999)
            if children:
                node = children[0]


if __name__ == '__main__':
    unittest.main()

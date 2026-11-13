import unittest


def reduce_events(events, known_books):
    latest = {}
    for event in events:
        book_id = event['book_id']
        if book_id not in known_books:
            continue
        previous = latest.get(book_id)
        if previous is None or (event['revision'], event['event_id']) > (
            previous['revision'], previous['event_id']
        ):
            latest[book_id] = event
    return {
        book_id: event.get('title')
        for book_id, event in latest.items()
        if event['action'] != 'delete'
    }


class TestReduceEvents(unittest.TestCase):
    def test_regressions(self):
        def event(event_id, book_id, revision, action, title=None):
            return dict(event_id=event_id, book_id=book_id,
                        revision=revision, action=action, title=title)

        old = event('e1', 'b1', 1, 'upsert', 'Old')
        new = event('e2', 'b1', 2, 'upsert', 'New')
        tie = event('e2', 'b1', 1, 'upsert', 'Winner')
        delete = event('e2', 'b1', 2, 'delete')
        tie_delete = event('e2', 'b1', 1, 'delete')
        early_delete = event('e1', 'b1', 1, 'delete')
        unknown = event('e3', 'b2', 3, 'upsert', 'Unknown')
        cases = [
            ('out of order', [new, old], {'b1': 'New'}),
            ('tie', [tie, old], {'b1': 'Winner'}),
            ('tie reversed', [old, tie], {'b1': 'Winner'}),
            ('duplicate', [old, old.copy()], {'b1': 'Old'}),
            ('winning delete', [old, delete], {}),
            ('losing delete', [early_delete, new], {'b1': 'New'}),
            ('delete wins tie', [old, tie_delete], {}),
            ('unknown book', [unknown], {}),
            ('empty', [], {}),
        ]
        for name, events, expected in cases:
            with self.subTest(name=name):
                self.assertEqual(reduce_events(events, {'b1'}), expected)


if __name__ == '__main__':
    unittest.main()

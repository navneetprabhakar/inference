import csv
import io
import unittest


def decimal_value(s):
    # Small chunks avoid Python's integer-string conversion limit locally.
    value = 0
    for i in range(0, len(s), 9):
        chunk = s[i:i + 9]
        value = value * (10 ** len(chunk)) + int(chunk)
    return value


def read_catalogue(text):
    reader = csv.reader(io.StringIO(text, newline=''), strict=True)
    required = ('book_id', 'title', 'revision')
    errors = []
    records = {}
    start = 1
    try:
        header = next(reader, None)
        if header is None or any(name not in header for name in required):
            return None, ['Missing required header']
        # Ambiguous required columns cannot be mapped reliably.
        if any(header.count(name) != 1 for name in required):
            return None, ['Duplicate required header']
        indices = {name: header.index(name) for name in required}
        while True:
            start = reader.line_num + 1
            try:
                row = next(reader)
            except StopIteration:
                break
            if not row:  # Blank physical line; the next record starts later.
                continue
            missing = [name for name, i in indices.items() if i >= len(row)]
            if missing:
                errors.append(f'Row {start}: missing fields: {", ".join(missing)}')
                continue
            book_id, title, revision = (row[indices[n]] for n in required)
            problems = []
            if not book_id:
                problems.append('empty book_id')
            if not revision or any(c < '0' or c > '9' for c in revision):
                problems.append('invalid revision')
            if problems:
                errors.append(f'Row {start}: {", ".join(problems)}')
                continue
            rev = decimal_value(revision)
            if book_id not in records or rev > records[book_id][1]:
                records[book_id] = (title, rev)
    except csv.Error as exc:
        errors.append(f'CSV syntax error starting at physical row {start}: {exc}')
    return (None, errors) if errors else (records, [])


class CatalogueTests(unittest.TestCase):
    def test_original_all_or_nothing(self):
        text = ('book_id,title,revision\nA1,"Map, Moon",1\nB2,,2\n'
                'A1,"Map, Moon Revised",3\nC3,Quiet Harbor,not-a-number\n'
                'A1,Tied Edition,3\n')
        result, errors = read_catalogue(text)
        self.assertIsNone(result)
        self.assertEqual(len(errors), 1)
        self.assertIn('Row 5', errors[0])

    def test_header_and_blank_title(self):
        self.assertIsNone(read_catalogue('book_id,revision\nB2,2\n')[0])
        self.assertEqual(read_catalogue('book_id,title,revision\nB2,,2\n'),
                         ({'B2': ('', 2)}, []))

    def test_duplicates_and_extra_columns(self):
        text = ('revision,extra,title,book_id\n1,x,Old,A\n3,x,Winner,A\n'
                '3,x,Tie,A\n2,x,Later,A\n')
        self.assertEqual(read_catalogue(text), ({'A': ('Winner', 3)}, []))

    def test_multiline_start_and_multiple_errors(self):
        text = ('book_id,title,revision\n\nA,"two\nlines",bad\n'
                'B,ok,-1\n')
        result, errors = read_catalogue(text)
        self.assertIsNone(result)
        self.assertEqual(len(errors), 2)
        self.assertIn('Row 3', errors[0])
        self.assertIn('Row 5', errors[1])

    def test_malformed_csv(self):
        result, errors = read_catalogue('book_id,title,revision\nA,good,1\nB,"unfinished\nrecord')
        self.assertIsNone(result)
        self.assertTrue(any('CSV syntax error starting at physical row 3' in e for e in errors))

    def test_long_revision_then_invalid_row(self):
        digits = '9' * 4500
        result, errors = read_catalogue(
            'book_id,title,revision\nA,long,' + digits + '\nB,bad,no\n')
        self.assertIsNone(result)
        self.assertEqual(len(errors), 1)
        self.assertIn('Row 3', errors[0])
        result, errors = read_catalogue('book_id,title,revision\nA,long,' + digits + '\n')
        self.assertEqual(errors, [])
        self.assertEqual(result['A'][1], 10 ** 4500 - 1)


if __name__ == '__main__':
    unittest.main()

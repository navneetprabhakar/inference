import csv
import io
import re
import unittest


def read_catalogue(text):
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    required = ("book_id", "title", "revision")
    errors = []

    try:
        header = next(reader)
    except StopIteration:
        return None, ["Missing header"]
    except csv.Error as exc:
        return None, [f"Header CSV error: {exc}"]

    if len(header) != len(set(header)):
        return None, ["Duplicate header names"]
    missing = [name for name in required if name not in header]
    if missing:
        return None, [f"Missing required headers: {', '.join(missing)}"]
    positions = {name: header.index(name) for name in required}
    catalogue = {}

    while True:
        start = reader.line_num + 1
        try:
            row = next(reader)
        except StopIteration:
            break
        except csv.Error as exc:
            errors.append(f"Row {start}: CSV error: {exc}")
            break
        if not row:  # csv.reader returns [] for a blank physical line
            continue

        row_errors = []
        for name, index in positions.items():
            if index >= len(row):
                row_errors.append(f"missing {name}")
        if positions["book_id"] < len(row) and not row[positions["book_id"]]:
            row_errors.append("empty book_id")
        if positions["revision"] < len(row):
            revision_text = row[positions["revision"]]
            if not re.fullmatch(r"[0-9]+", revision_text):
                row_errors.append("invalid revision")

        if row_errors:
            errors.append(f"Row {start}: {', '.join(row_errors)}")
            continue

        book_id = row[positions["book_id"]]
        title = row[positions["title"]]
        revision = int(row[positions["revision"]])
        if book_id not in catalogue or revision > catalogue[book_id][1]:
            catalogue[book_id] = (title, revision)

    return (None, errors) if errors else (catalogue, [])


class CatalogueTests(unittest.TestCase):
    def test_original_is_all_or_nothing(self):
        text = ('book_id,title,revision\nA1,"Map, Moon",1\n'
                'B2,,2\nA1,"Map, Moon Revised",3\n'
                'C3,Quiet Harbor,not-a-number\nA1,Tied Edition,3\n')
        result, errors = read_catalogue(text)
        self.assertIsNone(result)
        self.assertEqual(errors, ["Row 5: invalid revision"])

    def test_missing_header(self):
        result, errors = read_catalogue('book_id,revision\nB2,2\n')
        self.assertIsNone(result)
        self.assertEqual(errors, ["Missing required headers: title"])

    def test_duplicates_and_empty_title(self):
        text = ('revision,title,book_id,extra\n1,First,A1,x\n'
                '3,Winner,A1,x\n3,Tie,A1,x\n2,,B2,x\n')
        self.assertEqual(read_catalogue(text),
                         ({"A1": ("Winner", 3), "B2": ("", 2)}, []))

    def test_multiline_start_and_all_rows_validated(self):
        text = ('book_id,title,revision\nA1,Good,9\n\n'
                'A1,"two\nlines",bad\nB2,Other,-1\n')
        result, errors = read_catalogue(text)
        self.assertIsNone(result)
        self.assertEqual(errors, ["Row 4: invalid revision", "Row 6: invalid revision"])

    def test_malformed_csv(self):
        result, errors = read_catalogue('book_id,title,revision\nA1,Good,1\nB2,"unfinished')
        self.assertIsNone(result)
        self.assertTrue(errors[0].startswith("Row 3: CSV error:"))


if __name__ == "__main__":
    unittest.main()

"""Read-only metadata replay of frozen development selector; no native XML."""
import json,sqlite3
from pathlib import Path
from selection import select
HERE=Path(__file__).resolve().parent
if __name__=='__main__':
    s=json.loads((HERE/'frozen-selection.json').read_text());p=Path(s['source_frame']['path']);db=sqlite3.connect(p.as_uri()+'?mode=ro&immutable=1',uri=True);db.execute('PRAGMA query_only=ON');db.row_factory=sqlite3.Row
    try:rows=[dict(r) for r in db.execute('SELECT p.*,g.group_ordinal FROM groups g JOIN pages p ON p.row_ordinal BETWEEN g.first_page_ordinal AND g.last_page_ordinal ORDER BY p.row_ordinal')]
    finally:db.close()
    for row in rows:row['raw_SHA256']=row['raw_SHA256'].hex()
    if select(rows)!=s['selected']:raise ValueError('frozen_metadata_selection_mismatch')
    print('PASS_EXACT20_METADATA_ONLY_SELECTION_NO_NATIVE_BODY')

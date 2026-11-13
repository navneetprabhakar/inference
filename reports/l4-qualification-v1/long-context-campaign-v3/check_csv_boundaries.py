import json,runpy,csv
from pathlib import Path
r=Path('runs/long-context-campaign-v3/patches-01');ns=runpy.run_path(str(r/'reviewed_csv.py'));fn=ns['read_catalogue'];limit=csv.field_size_limit()
for text,line in [('"bad\nheader',1),('book_id,title,revision\n\nB,"bad\nmore',3),('book_id,title,revision\nA,ok,bad\nB,"bad\nmore',3),('book_id,title,revision\nA,"'+'x'*(limit+1)+'",1\n',2)]:
 result,errors=fn(text);assert result is None and f'physical row {line}:' in errors[-1]
 if 'A,ok,bad' in text:assert errors[0]=='Row 2: invalid revision'
assert csv.field_size_limit()==limit
report={'result':'pass','independent_header_multiline_prior_error_and_field_limit_checks':4,'global_csv_limit_unchanged':True};(r/'csv-boundary-verification.json').write_text(json.dumps(report,indent=2));print(report)

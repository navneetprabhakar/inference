import json,sqlite3,pathlib,sys
p=pathlib.Path(__file__).parent
c=sqlite3.connect(f'file:{p.parent}/corpus-audit-v1/audit.sqlite?mode=ro',uri=True)
for x in json.load(open(p/'sample.json')):
 if int(sys.argv[1])<=x['review_index']<=int(sys.argv[2]):
  print('\n###',x['review_index'],'ID',x['audit_id'],'TOKENS',x['content_tokens'])
  print(c.execute('select text from docs where id=?',(x['audit_id'],)).fetchone()[0]);print('### END',x['review_index'])

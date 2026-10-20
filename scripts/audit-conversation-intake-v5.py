"""Read-only post-publication audit using JSONL newline boundaries, not splitlines."""
# Creator: Navneet Prabhakar
import hashlib,json
from pathlib import Path
from slm.data.stream_hash import sha
ROOT=Path('data/conversation-parquet-intake-v3');OLD=Path('data/conversation-corpus-intake-v1')

def main():
 target=ROOT/'audit-v5.json'
 if target.exists():raise FileExistsError('Retain previous audit')
 metadata=json.loads((ROOT/'metadata.json').read_text());failure=json.loads((ROOT/'failure.json').read_text())
 if failure['error_type']!='JSONDecodeError':raise ValueError('Retained post-publication JSONL diagnostic required')
 sources=[OLD/'train.jsonl',*sorted(ROOT.glob('rows-*.jsonl'))]
 if len(sources)!=21:raise ValueError('All20completed group files required')
 h=hashlib.sha256();expected=[];raw_hashes={}
 for path in sources:
  h.update(path.read_bytes());raw_hashes[str(path)]=sha(path)
  with path.open() as f:expected.extend(json.loads(line) for line in f)
 if h.hexdigest()!=sha(ROOT/'train.jsonl'):raise ValueError('Complete raw concatenation differs')
 with (ROOT/'train.jsonl').open() as f:actual=[json.loads(line) for line in f]
 if expected!=actual or len(actual)!=20100 or len({x['row_index'] for x in actual})!=20100:raise ValueError('Full intact unique source rows required')
 chosen={(x['file'],x['group']):x for x in metadata['selected']}
 for row in actual[100:]:
  g=chosen[row['source_file'],row['row_group']]
  if row['row_index']!=g['global_start']+row['offset_within_group'] or not 0<=row['offset_within_group']<g['rows']:raise ValueError('Pinned global row interval differs')
  if any(a<=row['row_index']<a+100 for a in metadata['original_attempted_api_offsets_excluded']):raise ValueError('Prior attempted page re-read')
 with (OLD/'upstream-test.jsonl').open() as f:test_count=sum(1 for line in f if json.loads(line)['official_split']=='test')
 if test_count!=24229:raise ValueError('Full original test protection required')
 attempts=failure['ledger']['attempts']
 for g in metadata['selected']:
  key='decode/'+g['file']+'/'+str(g['group']);a=next(x for x in attempts if x['key']==key)
  if a['state']!='complete' or a['charge']['rows']!=g['rows']:raise ValueError('Actual completed precharge required')
 if any(x['state']=='pending' for x in attempts):raise ValueError('Uncertain requests retained; cannot certify complete intake')
 report=dict(creator='Navneet Prabhakar',complete=True,source_rows=20100,upstream_test_rows=24229,train_sha256=sha(ROOT/'train.jsonl'),source_parts_sha256=raw_hashes,upstream_test_sha256=sha(OLD/'upstream-test.jsonl'),metadata_sha256=sha(ROOT/'metadata.json'),retained_failure_sha256=sha(ROOT/'failure.json'),auditor_sha256=sha(__file__),ledger=failure['ledger'],training_approved=False,scope='Actual20groups completed and combined stream exactly reconstructed. Original post-publication checker incorrectly used Python splitlines, which treats Unicode line separators inside JSON strings as record breaks. New read-only audit uses file-line iteration; no row edits/refetch/Parquet redecode/counter reset. Original failed script/receipt retained.')
 target.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');Path('reports/conversation-intake-audit-v5.json').write_text(json.dumps({k:v for k,v in report.items() if k!='ledger'},indent=2,sort_keys=True)+'\n');print('Full20100intact candidate rows and24229test rows audited; no admission')
if __name__=='__main__':main()

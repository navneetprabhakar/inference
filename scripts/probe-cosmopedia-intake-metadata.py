"""One bounded pinned Parquet metadata census with persistent global charges."""
# Creator: Navneet Prabhakar
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request
from slm.data.intake_ledger import IntakeLedger
from slm.data.parquet_ranges import BoundedParquet, ExactRanges, Limits
from slm.data.schema import digest
from slm.data.tokenized import sha

ROOT = Path('data/cosmopedia-intake-metadata-v1')
PLAN = Path('configs/cosmopedia-intake-metadata-probe-v1.json')


def save(p, v): p.write_text(json.dumps(v, indent=2, sort_keys=True) + '\n')


def worker():
    plan = json.loads(PLAN.read_text())
    for p, h in plan['input_bindings'].items():
        if sha(p) != h: raise ValueError('Pinned probe input changed')
    ledger = IntakeLedger(ROOT / 'charges', plan['ledger_contract'])
    try:
        n = plan['inventory_body_cap']
        ledger.reserve('pinned-inventory', requests=1, body_bytes=n+1, output_bytes=n)
        request = urllib.request.Request(plan['inventory_url'], headers={'Accept-Encoding':'identity'})
        with urllib.request.urlopen(request, timeout=45) as response:
            if response.status != 200 or response.headers.get('Content-Encoding','identity') != 'identity':
                raise ValueError('Identity JSON inventory required')
            if response.headers.get('Link'): raise ValueError('Unexpected paginated inventory')
            raw = response.read(n+1)
        if len(raw) > n: raise ValueError('Inventory exceeds body cap')
        (ROOT / 'inventory.json').write_bytes(raw); ledger.finish('pinned-inventory',raw=raw)
        inventory = json.loads(raw)
        expected = {f'cosmopedia-v2/train-{i:05d}-of-00104.parquet' for i in range(104)}
        if len(inventory)!=104 or {i['path'] for i in inventory}!=expected:
            raise ValueError('Exact pinned 104-file inventory required')
        if any(i['type']!='file' or type(i['size']) is not int or i['size']<12 or not i.get('xetHash') for i in inventory):
            raise ValueError('Complete file size/entity identities required')
        item = min(inventory,key=lambda i:digest([plan['selection_seed'],i['path']]))
        limits = Limits(**plan['range_limits'])
        class ChargedRanges(ExactRanges):
            def get(self, start, length):
                key = 'range/' + str(start) + '/' + str(length)
                ledger.reserve(key, requests=1, body_bytes=length+1, output_bytes=length)
                raw = super().get(start,length)
                # Retain all successful bounded intervals; no whole-file download.
                (ROOT / ('range-'+str(start)+'-'+str(length)+'.bin')).write_bytes(raw)
                ledger.finish(key,raw=raw)
                return raw
        url = f"https://huggingface.co/datasets/HuggingFaceTB/smollm-corpus/resolve/{plan['revision']}/{item['path']}"
        transport = ChargedRanges(url,item['size'],'"'+item['xetHash']+'"',limits)
        reader = BoundedParquet(transport)
        groups=[]
        for index in range(reader.metadata.num_row_groups):
            group=reader.metadata.row_group(index);columns=[group.column(i) for i in range(group.num_columns)]
            spans=[(c.dictionary_page_offset if c.has_dictionary_page else c.data_page_offset,c.total_compressed_size) for c in columns]
            start=min(s for s,n in spans);stop=max(s+n for s,n in spans)
            declared=sum(c.total_uncompressed_size for c in columns)
            compatible=(group.num_rows<=limits.group_rows and 0<=declared<=limits.group_declared_uncompressed_bytes
                and stop-start<=limits.group_compressed_bytes and start>=4 and stop<=reader.footer_start
                and all(not c.file_path and c.total_uncompressed_size>=0 and n>0 for c,(s,n) in zip(columns,spans)))
            groups.append(dict(index=index,rows=group.num_rows,declared_bytes=declared,compressed_interval_bytes=stop-start,compatible=compatible))
        chosen=min((g for g in groups if g['compatible']),key=lambda g:digest([plan['selection_seed'],item['path'],g['index']]),default=None)
        if chosen is None: raise ValueError('No row group fits unchanged candidate limits')
        save(ROOT / 'row-group-census.json',groups)
        snapshot=ledger.snapshot();save(ROOT/'ledger-snapshot.json',snapshot)
        if sum(p.stat().st_size for p in ROOT.iterdir() if p.is_file()) > plan['maximum_output_bytes']:
            raise ValueError('Finite output cap exceeded')
        for p,h in plan['input_bindings'].items():
            if sha(p)!=h: raise ValueError('Probe input changed during execution')
        result=dict(creator='Navneet Prabhakar',kind='actual-cosmopedia-intake-metadata-v1',complete=True,
            plan_sha256=sha(PLAN),inventory_sha256=sha(ROOT/'inventory.json'),pinned_revision=plan['revision'],
            inventory_files=104,inventory_bytes=len(raw),selected_file=item,range_limits=asdict(limits),
            row_groups=len(groups),compatible_row_groups=sum(g['compatible'] for g in groups),
            total_file_rows=reader.metadata.num_rows,row_group_row_histogram=dict(Counter(g['rows'] for g in groups)),
            selected_group_for_later_intake=chosen,census_sha256=sha(ROOT/'row-group-census.json'),
            ledger_snapshot_sha256=sha(ROOT/'ledger-snapshot.json'),reserved=snapshot['reserved'],
            successful_body_bytes=sum(r['actual_body_bytes'] or 0 for r in snapshot['attempts']),
            actual_requests=len(snapshot['attempts']),training_rows_decoded=0,training_approved=False,
            scope='One hash-selected file metadata only. No full shard, data-row decode, content screen or corpus admission; not compatibility proof for the other103files. Counters exclude redirect/HTTP overhead; hard RSS not enforced.')
        save(ROOT/'report.json',result);save(Path('reports/cosmopedia-intake-metadata.json'),result)
        print(json.dumps(result,indent=2),flush=True)
    except BaseException as error:
        save(ROOT/'failure.json',dict(error_type=type(error).__name__,message='Bounded metadata attempt failed; retain charges and evidence, no automatic retry.',ledger=ledger.snapshot()))
        raise SystemExit('Metadata probe failed; inspect retained sanitized evidence') from None
    finally:
        ledger.close()


def main():
    if '--worker' in sys.argv:
        worker();return
    if ROOT.exists(): raise FileExistsError('Metadata probe already attempted; no replay')
    plan=json.loads(PLAN.read_text())
    if shutil.disk_usage('.').free < plan['minimum_free_disk_bytes']:
        raise ValueError('Insufficient free disk before probe')
    ROOT.mkdir();save(ROOT/'plan.json',plan)
    try:
        subprocess.run([sys.executable,__file__,'--worker'],timeout=plan['ledger_contract']['wall_seconds'],check=True)
    except subprocess.TimeoutExpired:
        save(ROOT/'supervisor-timeout.json',dict(complete=False,independent_wall_stop=True,automatic_retry=False))
        raise SystemExit('Finite metadata supervisor stopped worker') from None


if __name__=='__main__':main()

"""Disk-backed token-reader timing and ordered content digest; no neural updates."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import resource
import time
import numpy as np
from slm.data.tokenized import ShardBatches


def run(dataset,tokenizer,output,start_cursor=0,steps=None):
    output=Path(output)
    if output.exists():raise FileExistsError(output)
    opened=time.perf_counter()
    with ShardBatches(dataset,tokenizer) as batches:
        if type(start_cursor) is not int or not 0<=start_cursor<len(batches):raise ValueError('Invalid reader start cursor')
        if steps is not None and (type(steps) is not int or steps<1):raise ValueError('Positive read step budget required')
        end=len(batches) if steps is None else min(len(batches),start_cursor+steps)
        initial=batches.counts(start_cursor);open_seconds=time.perf_counter()-opened
        started=time.perf_counter();tokens=supervised=0;checksum=hashlib.sha256()
        for index in range(start_cursor,end):
            values=batches[index];tokens+=values[0].size;supervised+=int(values[2].sum())
            for a,dtype in zip(values,('<i8','<i8','<f4')):checksum.update(np.asarray(a,dtype=dtype).tobytes())
        seconds=time.perf_counter()-started
        expected=batches.counts(end)
        if (tokens,supervised)!=(expected[0]-initial[0],expected[1]-initial[1]):raise AssertionError('Reader counts differ')
        rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        report={'passed':True,'dataset_hash':batches.fingerprint,'tokenizer_hash':batches.tokenizer_hash,
            'start_cursor':start_cursor,'next_cursor':end,'batches_read':end-start_cursor,
            'prediction_positions':tokens,'supervised_positions':supervised,'ordered_batches_sha256':checksum.hexdigest(),
            'open_and_index_verification_seconds':open_seconds,'read_and_hash_seconds':seconds,
            'prediction_positions_per_second':tokens/seconds,'process_peak_rss_bytes':int(rss if platform.system()=='Darwin' else rss*1024),
            'neural_updates':0,'scope':'Reader copies, integrity checks and digest only; OS page cache may be warm. Not model throughput or cold-disk performance.'}
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x') as file:file.write(json.dumps(report,indent=2)+'\n')
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset',required=True);p.add_argument('--tokenizer',required=True);p.add_argument('--output',required=True)
    p.add_argument('--start-cursor',type=int,default=0);p.add_argument('--steps',type=int)
    a=p.parse_args();print(json.dumps(run(a.dataset,a.tokenizer,a.output,a.start_cursor,a.steps),indent=2))


if __name__=='__main__':main()

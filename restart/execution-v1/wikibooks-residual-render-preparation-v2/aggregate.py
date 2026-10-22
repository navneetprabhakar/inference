"""Four one-shot shard reservations, total7200seconds; no retry/refund."""
import fcntl,json,os,shutil
from pathlib import Path
import reader_core as rc
import profile as effective_profile
RANGES={i:None for i in range(1,9)}

ROOT=rc.INTAKE_ROOT/'wikibooks-residual-render-v1'

def durable_write(path,state):
    """Publish crash-durably: fsync file, replace, fsync containing directory."""
    tmp=path.with_name(path.name+'.partial')
    with tmp.open('w') as f:
        f.write(json.dumps(state,indent=2)+'\n');f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)
    directory_fd=os.open(str(path.parent),os.O_RDONLY)
    try:os.fsync(directory_fd)
    finally:os.close(directory_fd)

def reserve(shard,output,start,root=ROOT):
    if shard not in RANGES or output.resolve()!=(root/('shard-'+str(shard))).resolve():raise ValueError('fixed_shard_output_required')
    profile=effective_profile.load();CANONICAL_SHA=profile['canonical_sha256'];job=profile['jobs_loaded'][shard-1]
    root.mkdir(parents=True,exist_ok=True)
    with (root/'aggregate.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        path=root/'aggregate-ledger.json'
        state=json.loads(path.read_text()) if path.exists() else {'canonical_manifest_sha256':CANONICAL_SHA,'aggregate_limit_seconds':7200,'attempts':{}}
        if state['canonical_manifest_sha256']!=CANONICAL_SHA:raise ValueError('aggregate_manifest_mismatch')
        if str(shard) in state['attempts']:raise ValueError('shard_attempt_already_reserved_no_retry')
        if sum(x['reserved_seconds'] for x in state['attempts'].values())+900>7200:raise ValueError('aggregate7200second_reservation_exhausted')
        # All four output slots are accounted conservatively before any launch.
        if rc.output_size(rc.INTAKE_ROOT)+8*rc.CAPS['output_bytes']>rc.PROCESSED_CEILING:raise ValueError('aggregate8GB_processed_reservation')
        if shutil.disk_usage(root).free<rc.FREE_RESERVE+8*rc.CAPS['output_bytes']:raise ValueError('aggregate8GB_disk_plus_weights_floor')
        state['attempts'][str(shard)]={'status':'RESERVED_NO_RETRY','reserved_seconds':900,'start_shared_monotonic':start,'pid':os.getpid(),'output':str(output),'fixed_ordinal_range':[min(job['ordinals']),job['end_source_ordinal']],'exact_residual_manifest_sha256':job['manifest']['sha256'],'profile_sha256':profile['profile_sha256']}
        durable_write(path,state)
        return state

def finish(shard,elapsed,status,root=ROOT):
    with (root/'aggregate.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX);path=root/'aggregate-ledger.json';state=json.loads(path.read_text());a=state['attempts'][str(shard)];a['status']=status;a['actual_elapsed_seconds']=elapsed
        state['actual_elapsed_sum_seconds']=sum(x.get('actual_elapsed_seconds',0) for x in state['attempts'].values());state['aggregate_actual_overrun']=state['actual_elapsed_sum_seconds']>7200
        durable_write(path,state)

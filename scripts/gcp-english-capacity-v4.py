"""Explicitly authorized b/c capacity failover over the retained frozen lifecycle."""
# Creator: Navneet Prabhakar
import importlib.util,json,sys
from datetime import datetime,timedelta,timezone
from pathlib import Path

OUT=Path('data/english-gcp-session-v4')
PROPOSAL=Path('configs/english-capacity-failover-proposal-v1.json')
AUTH=Path('configs/english-capacity-failover-authorization-v1.json')


def load_base():
    spec=importlib.util.spec_from_file_location('_retained_gcp_lifecycle_v3','scripts/gcp-english-session-v3.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def capacity_error(stderr):
    return 'ZONE_RESOURCE_POOL_EXHAUSTED' in stderr


def authorize(base):
    if not AUTH.exists():raise PermissionError('Explicit capacity-only failover approval is pending')
    a=base.read(AUTH);p=base.read(PROPOSAL)
    if (a.get('explicit_user_authorization') is not True or a.get('proposal_sha256')!=base.sha(PROPOSAL)
        or a.get('allowed_zones')!=p['proposed_zones_in_order']
        or a.get('maximum_additional_create_requests')!=2
        or a.get('absolute_delete_at_utc')!=p['absolute_delete_at_utc']):
        raise PermissionError('Exact bounded user authorization required')
    if datetime.now(timezone.utc)>=datetime.fromisoformat(p['absolute_delete_at_utc'])-timedelta(hours=2):
        raise TimeoutError('Original lifetime window no longer supports this proposal')
    return a,p


def main():
    m=load_base();m.OUT=OUT
    if len(sys.argv)>1 and sys.argv[1]=='monitor':
        p=m.read(OUT/'allocated-plan.json');m.ZONE=p['zone'];m.monitor(p);return
    authorization,proposal=authorize(m)
    old=m.read('data/english-gcp-session-v3/plan.json')
    if m.sha('scripts/gcp-english-session-v3.py')!=old['source_inputs']['scripts/gcp-english-session-v3.py']:
        raise ValueError('Retained base lifecycle source changed')
    if (proposal['creation_started_at_utc'] != old['creation_started_at_utc']
        or proposal['absolute_delete_at_utc'] != old['delete_at_utc']
        or proposal['original_attempt_sha256'] != m.sha('data/english-gcp-session-v3/plan.json')
        or proposal['cleanup_sha256'] != m.sha('data/english-gcp-session-v3/cleanup.json')
        or proposal['unchanged_archive_sha256'] != old['archive_sha256']):
        raise ValueError('Original lifetime, cleanup and sealed archive must remain unchanged')
    if not m.read('data/english-gcp-session-v3/cleanup.json')['complete']:
        raise ValueError('First rejected request must have verified zero owned resources')
    zones=proposal['proposed_zones_in_order'];m.ZONE=zones[0]
    original_gcloud=m.gcloud;original_save=m.save;actual_stamp=m.stamp
    clock_used=False
    def reservation_clock():
        # The frozen v3 main first reads stamp exactly once when fixing its
        # creation/deletion reservation. Subsequent observations use real UTC.
        nonlocal clock_used
        if not clock_used:
            clock_used=True
            return datetime.fromisoformat(proposal['creation_started_at_utc'])
        return actual_stamp()
    m.stamp=reservation_clock
    def save(path,value):
        if Path(path)==OUT/'plan.json':
            value.update(capacity_authorization_sha256=m.sha(AUTH),capacity_wrapper_sha256=m.sha(__file__),
                         allowed_capacity_zones=zones,actual_failover_invoked_at_utc=actual_stamp().isoformat(),
                         original_failed_attempt_retained='data/english-gcp-session-v3',
                         reservation_clock_scope='Original failed attempt clock retained conservatively; actual VM request time is recorded separately')
        if Path(path)==OUT/'cloud-launch.json':value['zone']=m.ZONE
        original_save(path,value)
    m.save=save
    def guarded_gcloud(args,name,timeout=120,check=True):
        if name!='create-single-l4':return original_gcloud(args,name,timeout,check)
        vm=args[args.index('create')+1]
        for i,zone in enumerate(zones):
            m.ZONE=zone
            attempt=[('--zone='+zone) if x.startswith('--zone=') else x for x in args]
            requested_at=actual_stamp().isoformat()
            original_save(OUT/('capacity-request-'+str(i+1)+'.json'),
                          dict(zone=zone,request_started_at_utc=requested_at,
                               original_delete_at_utc=proposal['absolute_delete_at_utc']))
            result=original_gcloud(attempt,name+'-'+zone,timeout,False)
            if result.returncode==0:
                allocated={**m.read(OUT/'plan.json'),'zone':zone,
                           'actual_vm_request_started_at_utc':requested_at,
                           'actual_vm_request_finished_at_utc':actual_stamp().isoformat(),
                           'create_requests_executed':i+1}
                original_save(OUT/'allocated-plan.json',allocated)
                return result
            if not capacity_error(result.stderr):raise RuntimeError('Non-capacity creation failure; no further request')
            live=json.loads(original_gcloud(['compute','instances','list','--filter=name='+vm,'--format=json'],
                                           'capacity-prove-no-vm-'+zone).stdout)
            if live:raise RuntimeError('Creation state is not empty; never request a second VM')
            disks=json.loads(original_gcloud(['compute','disks','list','--filter=name='+vm,'--format=json'],
                                            'capacity-disk-inventory-'+zone).stdout)
            for disk in disks:
                if disk.get('name')!=vm or disk.get('users') or disk.get('sourceImageId')!=m.IMAGE_ID or int(disk['sizeGb'])!=100:
                    raise RuntimeError('Unreconciled disk; capacity failover is blocked')
                disk_zone=disk['zone'].split('/')[-1]
                original_gcloud(['compute','disks','delete',vm,'--zone='+disk_zone],
                                'capacity-clean-owned-empty-disk-'+disk_zone)
            if datetime.now(timezone.utc)>=datetime.fromisoformat(proposal['absolute_delete_at_utc'])-timedelta(hours=2):
                raise TimeoutError('Original unchanged deletion window exhausted')
        raise RuntimeError('Both explicitly approved capacity requests rejected; no VM created/retry')
    m.gcloud=guarded_gcloud
    m.main()


if __name__=='__main__':main()

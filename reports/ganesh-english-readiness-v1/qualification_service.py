"""Render the qualification service for a future, separately authorized instance."""
import datetime as dt
import json
import sys
import time
from pathlib import Path
from cloud_training import nano_pilot_window as window

def command(config, approval, provider, python, now):
    for field in ('runtime_sha256','instance','lease_start_utc','provider_stop_utc'):
        if not config.get(field) or approval.get(field) != config[field]:
            raise ValueError('Approval identity mismatch: '+field)
    if (approval.get('approved') is not True or approval.get('approved_usd') != window.CAP
            or approval.get('machine') != 'a2-highgpu-1g' or approval.get('experiment') != 'ganesh-english-controlled-v2'):
        raise ValueError('Fresh scoped approval required')
    scheduling = provider['scheduling']
    if (provider['name'] != config['instance'] or provider['status'] != 'RUNNING'
            or scheduling['instanceTerminationAction'] != 'STOP' or scheduling['automaticRestart'] is not False
            or window.timestamp(scheduling['terminationTime']) != window.timestamp(config['provider_stop_utc'])
            or not provider['machineType'].endswith('/a2-highgpu-1g') or len(provider['disks']) != 1
            or provider['disks'][0]['autoDelete'] is not False or str(provider['disks'][0]['diskSizeGb']) != '200'):
        raise ValueError('Provider readback mismatch')
    deadline, runtime = window.qualification_window(config, now)
    root='/opt/ganesh-conversation'
    return ['systemd-run','--unit=ganesh-english-controlled-qual-v3','--property=WorkingDirectory='+root,
            '--property=RuntimeMaxSec='+str(runtime),'--property=TimeoutStopSec=10','--property=KillMode=control-group',
            '--setenv=GANESH_QUALIFICATION_STOP_UTC='+dt.datetime.fromtimestamp(deadline,dt.timezone.utc).isoformat(),
            '--setenv=PYTHONPATH='+':'.join([root+'/vendor',root,root+'/nanochat-source']),
            '--setenv=HF_HUB_OFFLINE=1','--setenv=WANDB_MODE=disabled',python,'-u',root+'/reports/ganesh-english-readiness-v1/gpu_qualify.py']

if __name__ == '__main__':
    root=Path('/opt/ganesh-conversation')
    load=lambda name: json.loads((root/name).read_text())
    print(json.dumps(command(load('config-v3.json'),load('fresh-authorization.json'),load('provider-v3.json'),sys.executable,time.time())))

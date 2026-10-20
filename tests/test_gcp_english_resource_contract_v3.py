# Creator: Navneet Prabhakar
import importlib.util
import copy
import pytest


def module():
    s=importlib.util.spec_from_file_location('resource_contract','scripts/gcp-english-session-v3.py')
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m


def fixture():
    p=dict(vm='owned',run_id='nonce',delete_at_utc='2026-10-22T01:00:00+00:00')
    d=dict(name='owned',labels={'run-id':'nonce'},machineType='zones/a/machineTypes/g2-standard-4',
           guestAccelerators=[dict(acceleratorCount=1,acceleratorType='types/nvidia-l4')],
           networkInterfaces=[dict(networkIP='10.0.0.2')],
           disks=[dict(autoDelete=True,boot=True)],
           scheduling=dict(automaticRestart=False,onHostMaintenance='TERMINATE',provisioningModel='STANDARD',
                           instanceTerminationAction='DELETE',terminationTime='2026-10-22T01:00:00Z'))
    disk=dict(sourceImageId='8190671948398954841',sizeGb='100',type='types/pd-standard')
    return p,d,disk


def test_actual_owned_finite_private_gpu_contract():
    p,d,disk=fixture();module().validate_instance(d,p,disk)


@pytest.mark.parametrize('bad',['other_owner','public_ip','service_account','two_gpus','wrong_machine','no_deletion','extended_clock','restart','disk_leak','wrong_image'])
def test_unsafe_or_unowned_resource_cannot_start_paid_training(bad):
    p,d,disk=fixture()
    if bad=='other_owner':d['labels']['run-id']='another'
    elif bad=='public_ip':d['networkInterfaces'][0]['accessConfigs']=[{'natIP':'example'}]
    elif bad=='service_account':d['serviceAccounts']=[{'email':'example'}]
    elif bad=='two_gpus':d['guestAccelerators'][0]['acceleratorCount']=2
    elif bad=='wrong_machine':d['machineType']='types/g2-standard-8'
    elif bad=='no_deletion':d['scheduling']['instanceTerminationAction']='STOP'
    elif bad=='extended_clock':d['scheduling']['terminationTime']='2026-10-23T01:00:00Z'
    elif bad=='restart':d['scheduling']['automaticRestart']=True
    elif bad=='disk_leak':d['disks'][0]['autoDelete']=False
    elif bad=='wrong_image':disk['sourceImageId']='different'
    with pytest.raises(ValueError):module().validate_instance(d,p,disk)

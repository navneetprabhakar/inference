# Creator: Navneet Prabhakar
import importlib.util
import pytest


def module():
    s=importlib.util.spec_from_file_location('capacity_wrapper','scripts/gcp-english-capacity-v4.py')
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m


def test_no_authorization_no_create_or_new_output(tmp_path,monkeypatch):
    m=module();monkeypatch.setattr(m,'AUTH',tmp_path/'absent.json')
    with pytest.raises(PermissionError,match='pending'):m.authorize(m.load_base())
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('text,allowed',[
    ('ZONE_RESOURCE_POOL_EXHAUSTED_WITH_DETAILS',True),
    ('PERMISSION_DENIED',False),('QUOTA_EXCEEDED',False),('connection timed out',False),('',False)])
def test_only_explicit_capacity_failure_can_try_another_approved_zone(text,allowed):
    assert module().capacity_error(text) is allowed

# Creator: Navneet Prabhakar
import sqlite3
import pytest
from slm.english_learning import Meter as OldMeter
from slm.english_budget_v2 import Meter
from slm.data.stream_hash import sha


def test_discarded_and_uncertain_work_carries_and_aggregate_cap_is_not_reset(tmp_path):
    path=tmp_path/'old.sqlite';old=OldMeter(path,'old',maximum=2000000,phase_maximum=2000000)
    old.reserve('common',0,786432);old.close()  # Unconfirmed reservations remain charged.
    prior=dict(path=str(path),sha256=sha(path),positions=786432,preliminary_positions=786432)
    meter=Meter(tmp_path/'new.sqlite','new',prior=prior)
    assert meter.total()==786432
    meter.reserve('common',0,262144);meter.complete('common',0)
    meter.reserve('mlx',0,458752);meter.reserve('cuda',0,458752)
    assert meter.total()==1966080
    with pytest.raises(ValueError,match='budget'):meter.reserve('cuda',1,33921)
    meter.close()
    db=sqlite3.connect(path);db.execute("UPDATE charges SET positions=1");db.commit();db.close()
    with pytest.raises(ValueError,match='changed'):Meter(tmp_path/'third.sqlite','third',prior=prior)


def test_global_and_phase_limits_include_prior_and_no_duplicate_refund(tmp_path):
    path=tmp_path/'old.sqlite';m=OldMeter(path,'old');m.reserve('common',0,8);m.close()
    prior=dict(path=str(path),sha256=sha(path),positions=8,preliminary_positions=8)
    m=Meter(tmp_path/'new.sqlite','new',maximum=20,phase_maximum=10,prior=prior)
    m.reserve('language',0,10)
    with pytest.raises(ValueError):m.reserve('language',1,1)
    with pytest.raises(sqlite3.IntegrityError):m.reserve('other',0,1);m.reserve('other',0,1)
    assert m.total()==19
    with pytest.raises(ValueError):m.reserve('another',0,2)
    m.close()

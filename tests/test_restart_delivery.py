import json,sqlite3
from pathlib import Path
import pytest
from slm.restart import delivery
from slm.restart.ledger import Ledger


@pytest.fixture
def candidate(tmp_path):
    ledger=Ledger(tmp_path/'exposures.sqlite','fixture',target_cap=100,update_cap=10,presentation_cap=3,deadline=9999999999)
    ledger.reserve('work-000001',[('doc',0,10)],now=1);ledger.complete('work-000001');ledger.close()
    db=sqlite3.connect(tmp_path/'measurements.sqlite')
    db.executescript('CREATE TABLE contract(id INTEGER,value TEXT);CREATE TABLE completions(seq INTEGER,reservation TEXT,step INTEGER,targets INTEGER,active REAL,ledger_pin TEXT);')
    db.execute('INSERT INTO contract VALUES (1,?)',(json.dumps(dict(identity='fixture',schedule='schedule')),))
    db.execute("INSERT INTO completions VALUES (1,'work-000001',1,10,10,'ledger-pin')");db.commit();db.close()
    (tmp_path/'work-000001-metrics.json').write_text(json.dumps(dict(loss=3.,gradient_norm=.2,update_ratio=.001,microbatches=1,supervised_targets=10)))
    return tmp_path


def test_delivery_preserves_charges_and_explicit_missing_metrics(candidate):
    data=delivery.histories(candidate,identity='fixture',schedule_sha256='schedule')
    assert data['charged_work']['targets_reserved']==10 and data['updates'][0]['metrics']['loss']==3
    (candidate/'work-000001-metrics.json').unlink()
    data=delivery.histories(candidate,identity='fixture',schedule_sha256='schedule')
    assert data['missing_metric_records']==1 and data['updates'][0]['metrics'] is None


@pytest.mark.parametrize('fault',['identity','targets','nan','extra'])
def test_history_rejects_unbound_evidence(candidate,fault):
    path=candidate/'work-000001-metrics.json';v=json.loads(path.read_bytes())
    if fault=='targets':v['supervised_targets']=11
    if fault=='nan':v['loss']=float('nan')
    path.write_text(json.dumps(v))
    if fault=='extra':(candidate/'work-000002-metrics.json').write_text('{}')
    with pytest.raises(ValueError):delivery.histories(candidate,identity='wrong' if fault=='identity' else 'fixture',schedule_sha256='schedule')


def test_static_plots_and_manifest_are_bound(candidate):
    output=candidate/'report';output.mkdir()
    result=delivery.build(candidate,output,identity='fixture',schedule_sha256='schedule',heartbeat=lambda:None)
    assert delivery.verify(output,result,identity='fixture')['charged_work']['targets_reserved']==10
    for name in ('updates.png','resources.png'):
        assert (output/'delivery'/name).read_bytes().startswith(b'\x89PNG')
    (output/'delivery/updates.png').write_bytes(b'changed')
    with pytest.raises(ValueError,match='Changed delivery artifact'):delivery.verify(output,result,identity='fixture')

from uuid import uuid4
from unittest.mock import Mock
from test_run_api import client


def test_sdm_delivery_binds_run_and_checksum(monkeypatch):
    run=uuid4();store=Mock(return_value={'release_ready':False})
    monkeypatch.setattr('app.sdm_delivery.prepare_sdm_delivery',store)
    api=client();url=f'/api/tasks/test/runs/{run}/sdm-delivery'
    assert api.post(url,json={'qa_binding_checksum':'a'*64}).json()=={'release_ready':False}
    assert store.call_args.args[1:]==('test',run,'a'*64)
    store.reset_mock()
    assert api.post(url,json={'qa_binding_checksum':'a'*64,'root':'/tmp'}).status_code==422
    store.assert_not_called()


def test_sdm_delivery_conflict(monkeypatch):
    monkeypatch.setattr('app.sdm_delivery.prepare_sdm_delivery',Mock(side_effect=ValueError('SDM_QA_VERSION_CONFLICT')))
    assert client().post(f'/api/tasks/test/runs/{uuid4()}/sdm-delivery',json={'qa_binding_checksum':'a'*64}).status_code==409

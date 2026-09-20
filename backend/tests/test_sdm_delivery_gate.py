from contextlib import nullcontext
from unittest.mock import Mock
import pytest
from app.sdm_store import save_delivery_candidate


def test_delivery_requires_actual_qa_before_render(monkeypatch,tmp_path):
    queue=Mock();queue.conn.return_value=nullcontext(Mock())
    monkeypatch.setattr('app.delivery_context.load_delivery_context',Mock(side_effect=ValueError('DELIVERY_CURRENT_QA_APPROVAL_REQUIRED')))
    render=Mock();monkeypatch.setattr('app.sdm_store.render_sdm_xlsx',render)
    with pytest.raises(ValueError,match='DELIVERY_CURRENT_QA_APPROVAL_REQUIRED'):
        save_delivery_candidate(queue,'t','r','s','h','q',root=tmp_path)
    render.assert_not_called()


def test_changed_qa_checksum_prevents_render(monkeypatch,tmp_path):
    queue=Mock();queue.conn.return_value=nullcontext(Mock())
    monkeypatch.setattr('app.delivery_context.load_delivery_context',lambda *a,**k:{'qa_binding_checksum':'current'})
    render=Mock();monkeypatch.setattr('app.sdm_store.render_sdm_xlsx',render)
    with pytest.raises(ValueError,match='SDM_QA_VERSION_CONFLICT'):
        save_delivery_candidate(queue,'t','r','s','h','old',root=tmp_path)
    render.assert_not_called()
